from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from openbim_runner.nodes.base import (
    AutoBind,
    ExecutionContext,
    NodeModel,
    node,
)
from openbim_runner.nodes.bcf_output.bcf_writer import BcfWriter
from openbim_runner.nodes.bcf_output.harmonized import HarmonizedElement
from openbim_runner.nodes.bcf_output.normalize import (
    INCLUDE_FAILED,
    FailedCheck,
    normalize,
)
from openbim_runner.nodes.bcf_output.render import (
    FILE_ONLY_PLACEHOLDERS,
    Namespace,
    RenderContext,
    ResolvingFormatter,
    build_namespace,
    resolve_template,
)
from openbim_runner.util.references import parse_element_ref

DEFAULT_TOPIC_TYPE = "Model Check"
DEFAULT_TOPIC_STATUS = "Open"


class BcfOutputSettings(NodeModel):
    mode: Literal["auto", "manual"] = Field(
        default="auto",
        title="Output mode",
        description=(
            "'auto' applies the condition-aware standard templates in the editor; "
            "'manual' resolves your own template exactly as written. The backend "
            "resolves the same placeholders in both modes; 'mode' is a UI-only toggle."
        ),
    )
    title_template: str = Field(
        default="",
        title="Title template",
        description=(
            "BCF topic title, resolved per failing check with Python string "
            "formatting. Placeholders: {id}, {guid}, {name}, {class_name} and check "
            "values keyed by the check's key, e.g. {key.expected}, {key.actual}."
        ),
    )
    description_template: str = Field(
        default="",
        title="Description template",
        description=(
            "BCF topic description (sentence) resolved per failing check, same "
            "placeholders as the title template."
        ),
    )
    project_name: str = Field(
        default="Default Project",
        title="Project name",
        description="Name written into the BCF project information. Empty means no project name.",
    )
    author: str = Field(
        default="Default Author",
        title="Creation author",
        description="Author recorded on every BCF topic's creation data.",
    )
    topic_type: str = Field(
        default=DEFAULT_TOPIC_TYPE,
        title="Topic type",
        description="BCF TopicType applied to every topic.",
    )
    topic_status: str = Field(
        default=DEFAULT_TOPIC_STATUS,
        title="Topic status",
        description="BCF TopicStatus applied to every topic.",
    )
    output_filename: str = Field(
        default="check-results.bcf",
        title="Output filename",
        description=(
            "Filename (relative to the output directory) to write the BCF into. "
            "A '{timestamp}' placeholder is replaced with a per-run timestamp."
        ),
    )
    included_elements: Literal["failed", "passed", "all"] = Field(
        default=INCLUDE_FAILED,
        title="Included elements",
        description=(
            "'failed' includes only elements with at least one failing check (their "
            "failing checks become topics); 'passed' includes only fully-passed "
            "elements (one info topic each); 'all' includes every element (failing "
            "checks become topics, fully-passed elements get one info topic each)."
        ),
    )


class BcfOutputInputs(NodeModel):
    elements: Annotated[list[HarmonizedElement], AutoBind()] = Field(
        default=[],
        title="Elements",
        description=(
            "Harmonized check elements from an upstream checking node "
            "(LOI-Check.elements or Tilt-of-Components.elements)."
        ),
    )


class BcfTopic(NodeModel):
    guids: list[str] = Field(
        title="GUIDs",
        description="IFC GlobalIds of the failing elements this topic references (resolved from the model by express ID).",
    )
    key: str = Field(
        title="Key",
        description="Key of the (first) failed check this topic reports.",
    )
    element_count: int = Field(
        title="Element count",
        description="Number of distinct failing elements this topic references.",
    )
    title: str = Field(
        title="Title",
        description="Resolved topic title from the title template.",
    )
    description: str = Field(
        title="Description",
        description="Resolved topic description from the description template.",
    )


class BcfOutputResult(NodeModel):
    output_path: str = Field(
        title="Output path",
        description="Filesystem path the BCF 3.0 file was written to.",
    )
    topic_count: int = Field(
        title="Topic count",
        description="Number of BCF topics written.",
    )
    viewpoint_count: int = Field(
        title="Viewpoint count",
        description="Number of viewpoints written (one per resolvable failing element).",
    )
    processed_result_count: int = Field(
        title="Processed result count",
        description="Total number of checks processed across all input elements.",
    )
    element_count: int = Field(
        title="Element count",
        description="Number of input elements consumed from the upstream node.",
    )
    failure_count: int = Field(
        title="Failure count",
        description="Total number of failed checks found.",
    )
    skipped: int = Field(
        default=0,
        title="Skipped",
        description="Number of elements (with reported checks) skipped because they could not be resolved.",
    )
    warnings: list[str] = Field(
        default=[],
        title="Warnings",
        description="Non-fatal notices collected while running.",
    )
    topics: list[BcfTopic] = Field(
        default=[],
        title="Topics",
        description="Resolved topics (element GUID, check key, title, description).",
    )


def _resolve_topic_identity(
    context: ExecutionContext,
    failed_check: FailedCheck,
) -> tuple[object, str, str] | None:
    """Resolve (entity, guid, name) for a failed check, or None if unresolvable."""
    element = parse_element_ref(failed_check.reference, node="bcf_output")
    try:
        entity = context.resolve_model(element.slug).by_id(element.express_id)
    except RuntimeError:
        return None
    guid = getattr(entity, "GlobalId", None)
    if not guid:
        return None
    name = getattr(entity, "Name", None)
    return entity, str(guid), (str(name) if name is not None else "")


def _emit_topic(
    *,
    writer: BcfWriter,
    context: ExecutionContext,
    group: list[FailedCheck],
    title_template: str,
    description_template: str,
    topics: list[BcfTopic],
    warnings: list[str],
    skipped_refs: set[str],
) -> None:
    """Resolve one BCF topic from a group of FailedChecks.

    The topic carries one viewpoint per distinct resolvable element in the
    group. Title / description are rendered from the first resolvable check.
    """
    resolved: list[tuple[FailedCheck, object, str, str]] = []
    seen_refs: set[str] = set()
    for failed_check in group:
        reference = failed_check.reference
        if reference in skipped_refs or reference in seen_refs:
            continue
        identity = _resolve_topic_identity(context, failed_check)
        if identity is None:
            skipped_refs.add(reference)
            warnings.append(
                f"Skipped check '{failed_check.check.key}' for element "
                f"{reference}: could not resolve its IFC GlobalId / entity."
            )
            continue
        seen_refs.add(reference)
        resolved.append((failed_check, *identity))

    if not resolved:
        return

    # Extract member names from all resolved entries for intersection context
    member_names = [name for (_, _, _, name) in resolved if name]
    name_a = member_names[0] if len(member_names) >= 1 else ""
    name_b = member_names[1] if len(member_names) >= 2 else ""

    # Build readable intersection phrase if this is an intersection element
    first, _, guid, name = resolved[0]
    intersection_phrase = ""
    if first.intersection and name_a and name_b:
        intersection_phrase = f"intersection of {name_a} and {name_b}"

    ctx = RenderContext(
        element_id=first.express_id,
        element_guid=guid,
        element_name=name,
        class_name=first.class_name,
        check=first.check,
        intersection=intersection_phrase,
        name_a=name_a,
        name_b=name_b,
    )
    namespace: Namespace = build_namespace(ctx)
    formatter = ResolvingFormatter()
    title = resolve_template(
        title_template,
        namespace,
        formatter,
        element_id=first.express_id,
        check_key=first.check.key,
    )
    description = resolve_template(
        description_template,
        namespace,
        formatter,
        element_id=first.express_id,
        check_key=first.check.key,
    )
    if not title:
        title = guid

    writer.add_topic(
        title=title,
        description=description,
        entities=[item[1] for item in resolved],
    )
    topics.append(
        BcfTopic(
            guids=[g for _, _, g, _ in resolved],
            key=first.check.key,
            element_count=len(resolved),
            title=title,
            description=description,
        )
    )


@node()
async def bcf_output(
    settings: BcfOutputSettings,
    inputs: BcfOutputInputs,
    context: ExecutionContext,
) -> BcfOutputResult:
    if not inputs.elements:
        raise ValueError(
            "bcf_output requires harmonized check elements as its input. "
            "Connect an upstream checking node's elements output (e.g. "
            "LOI-Check.elements or Tilt-of-Components.elements)."
        )

    if context.output_dir is None:
        raise ValueError(
            "bcf_output requires an output directory on the execution context."
        )

    warnings: list[str] = []

    file_only_used = [
        placeholder
        for placeholder in FILE_ONLY_PLACEHOLDERS
        if placeholder in settings.title_template
        or placeholder in settings.description_template
    ]
    if file_only_used:
        warnings.append(
            "Placeholder(s) not available at runtime and rendered as empty: "
            + ", ".join(f"{{{p}}}" for p in file_only_used)
            + ". Upstream node label/type/id are not transmitted on result models."
        )

    output = normalize(inputs.elements, included=settings.included_elements)

    writer = BcfWriter(
        project_name=settings.project_name,
        author=settings.author,
        topic_type=settings.topic_type or DEFAULT_TOPIC_TYPE,
        topic_status=settings.topic_status or DEFAULT_TOPIC_STATUS,
    )
    topics: list[BcfTopic] = []
    skipped_refs: set[str] = set()

    groups = [*output.failure_topics, *output.info_topics]
    for group in groups:
        _emit_topic(
            writer=writer,
            context=context,
            group=group,
            title_template=settings.title_template,
            description_template=settings.description_template,
            topics=topics,
            warnings=warnings,
            skipped_refs=skipped_refs,
        )

    output_dir = Path(context.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = settings.output_filename.replace(
        "{timestamp}", datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    )
    output_path = output_dir / filename

    writer.save(output_path)
    return BcfOutputResult(
        output_path=str(output_path),
        topic_count=writer.topic_count,
        viewpoint_count=writer.viewpoint_count,
        processed_result_count=output.processed_result_count,
        element_count=output.element_count,
        failure_count=output.failure_count,
        skipped=len(skipped_refs),
        warnings=warnings,
        topics=topics,
    )
