from __future__ import annotations

import string
import uuid
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from xml.etree import ElementTree as ET

from pydantic import Field

from openbim_runner.nodes.base import (
    AutoBind,
    ExecutionContext,
    NodeModel,
    node,
)
from openbim_runner.nodes.loi_check.loi_check import (
    ComparisonElement,
    PropertyCheckResult,
)

# Fixed identity / bookkeeping values used inside each generated markup.
_TOPIC_TYPE = "ERROR"
_TOPIC_STATUS = "Open"
_CREATION_AUTHOR = "RCC4All"

# Check fields exposed per property key as `<property_key>.<field>` placeholders.
_CHECK_FIELDS = (
    "actual",
    "expected",
    "condition",
    "property_name",
    "expected_min",
    "expected_max",
)

# Adaptive (auto-mode) fields, computed per failed check. These dispatch on the
# check's condition / missing value so a single template stays grammatically
# correct across every scenario that loi_check can produce.
_ADAPTIVE_FIELDS = ("expectation", "actual_display", "failure_reason")

# Comparison condition -> compact operator symbol (for the {condition_symbol}
# placeholder). Unknown conditions fall back to the condition token.
_CONDITION_SYMBOLS = {
    "equals": "=",
    "not_equals": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    # Word/phrase conditions carry their own surrounding whitespace so direct
    # concatenation like `{property_name}{condition_symbol}{expected}` reads
    # cleanly (e.g. "Material contains concrete", "LoadBearing is true").
    "contains": " contains ",
    "one_of": " ∈ ",
    "is_true": " is true",
    "is_false": " is false",
    "between": " between ",
    "outside": " outside ",
}


class BcfOutputSettings(NodeModel):
    mode: Literal["auto", "manual"] = Field(
        default="auto",
        title="Output mode",
        description=(
            "'auto' uses condition-aware placeholders ({expectation}, {failure_reason}) so one "
            "description template stays correct for every LOI-Check scenario. 'manual' uses the raw "
            "placeholders ({actual}, {expected}, {condition_symbol}) exactly as written."
        ),
    )
    title_template: str = Field(
        default="",
        title="Title template",
        description=(
            "BCF topic title, resolved per failing check with Python string formatting. "
            "Available placeholders: {id}, {guid}, {name}, {class_name} and check values keyed by "
            "property, e.g. {Pset_WallCommon.ThermalTransmittance.actual}, "
            "{Pset_WallCommon.ThermalTransmittance.expected}, "
            "{Pset_WallCommon.ThermalTransmittance.condition}."
        ),
    )
    description_template: str = Field(
        default="",
        title="Description template",
        description=(
            "BCF topic description (sentence) resolved per failing check, same placeholders as the "
            "title template. The comparison row's expected value supplies the limit."
        ),
    )


class BcfOutputInputs(NodeModel):
    elements: Annotated[list[ComparisonElement], AutoBind()] = Field(
        default=[],
        title="Elements",
        description="Elements and their property check results from LOI-Check (LOI-Check.elements).",
    )


class BcfTopic(NodeModel):
    guid: str = Field(
        title="GUID",
        description="IFC GlobalId of the failing element (resolved from the model by express ID).",
    )
    property_key: str = Field(
        title="Property key",
        description="Property key of the failed check (e.g. 'Pset_WallCommon.ThermalTransmittance' or 'ThermalTransmittance').",
    )
    title: str = Field(
        title="Title",
        description="Resolved topic title from the title template.",
    )
    description: str = Field(
        title="Description",
        description="Resolved topic description (sentence) from the description template.",
    )


class BcfOutputResult(NodeModel):
    output_path: str = Field(
        title="Output path",
        description="Filesystem path the BCF 3.0 file was written to.",
    )
    topic_count: int = Field(
        title="Topic count",
        description="Number of BCF topics written (one per failing check).",
    )
    element_count: int = Field(
        title="Element count",
        description="Number of input elements consumed from LOI-Check.",
    )
    failed_check_count: int = Field(
        title="Failed check count",
        description="Total number of failed property checks across all elements.",
    )
    topics: list[BcfTopic] = Field(
        default=[],
        title="Topics",
        description="Resolved topics (element GUID, property key, title, description).",
    )


class _Namespace:
    """Attribute-access namespace used to resolve template placeholders.

    Supports dotted placeholder paths such as ``Pset_WallCommon.ThermalTransmittance.actual``
    via normal Python attribute traversal, so ``string.Formatter`` resolves
    them without any custom index-formatting tricks.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self
        for part in parts[:-1]:
            child = node._values.get(part)
            if not isinstance(child, _Namespace):
                child = _Namespace()
                node._values[part] = child
            node = child  # type: ignore[assignment]
        node._values[parts[-1]] = value

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as error:
            raise AttributeError(name) from error


class _ResolvingFormatter(string.Formatter):
    def get_field(
        self,
        field_name: str,
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
    ) -> tuple[Any, str]:
        if not args:
            raise ValueError(field_name)
        namespace = args[0]
        parts = field_name.split(".")
        target: Any = namespace
        try:
            for part in parts:
                target = getattr(target, part)
        except AttributeError as error:
            raise ValueError(field_name) from error
        return target, parts[0]


def _resolve_template(
    template: str,
    namespace: _Namespace,
    formatter: _ResolvingFormatter,
    *,
    element_id: int,
    property_key: str,
) -> str:
    if not template:
        return ""
    try:
        return formatter.format(template, namespace)
    except (AttributeError, KeyError, ValueError, IndexError) as error:
        placeholder = str(error)
        raise ValueError(
            f"Unresolved template placeholder '{placeholder}' for element {element_id} "
            f"(check '{property_key}')."
        ) from error


def _build_namespace(
    *,
    element_id: int,
    element_guid: str,
    element_name: str,
    class_name: str,
    check: PropertyCheckResult,
) -> _Namespace:
    ns = _Namespace()
    ns.set("id", element_id)
    ns.set("guid", element_guid)
    ns.set("name", element_name)
    ns.set("class_name", class_name)

    field_values: dict[str, Any] = {
        "actual": check.actual if check.actual is not None else "",
        "expected": check.expected,
        "condition": check.condition,
        "property_name": check.property_name,
        "expected_min": check.expected_min if check.expected_min is not None else "",
        "expected_max": check.expected_max if check.expected_max is not None else "",
        "condition_symbol": _CONDITION_SYMBOLS.get(
            check.condition, str(check.condition)
        ),
    }
    # Adaptive (auto-mode) values computed per check so one template covers every
    # scenario loi_check can produce (per condition and for missing values).
    field_values.update(_adaptive_values(check))
    # Expose the check's values under its own property key(s) ...
    for field in (*_CHECK_FIELDS, *_ADAPTIVE_FIELDS):
        ns.set(f"{check.property_key}.{field}", field_values[field])
    # ... and as generic top-level fields so templates can avoid hard-coding a
    # specific property key.
    for field, value in field_values.items():
        ns.set(field, value)

    return ns


def _adaptive_values(check: PropertyCheckResult) -> dict[str, str]:
    """Compute the condition-aware placeholder values for a failed check."""
    expectation = _expectation_clause(check)
    actual_display = check.actual if check.actual is not None else "missing"
    if check.actual is None:
        failure_reason = (
            f"property {check.property_name} is missing (expected {expectation})"
        )
    else:
        failure_reason = (
            f"property {check.property_name} is {check.actual} (expected {expectation})"
        )
    return {
        "expectation": expectation,
        "actual_display": actual_display,
        "failure_reason": failure_reason,
    }


def _expectation_clause(check: PropertyCheckResult) -> str:
    """A grammatically correct 'expected ...' clause for the check's condition."""
    condition = check.condition
    if condition in ("between", "outside"):
        bounds = f"{check.expected_min} and {check.expected_max}"
        return (
            f"between {bounds}" if condition == "between" else f"not between {bounds}"
        )
    if condition == "contains":
        return f'contains "{check.expected}"'
    if condition == "one_of":
        return f"is one of: {check.expected}"
    if condition == "is_true":
        return "is true"
    if condition == "is_false":
        return "is false"
    symbol = _CONDITION_SYMBOLS.get(condition, str(condition))
    return f"{symbol} {check.expected}".strip()


def _resolve_identity(
    context: ExecutionContext, element_id: int, property_key: str
) -> tuple[str, str]:
    """Resolve (guid, name) for an element by express ID (identity lookup only)."""
    try:
        entity = context.ifc_model.by_id(element_id)
    except RuntimeError as error:
        raise ValueError(
            f"Could not resolve IFC entity for express ID {element_id} "
            f"(check '{property_key}')."
        ) from error

    guid = getattr(entity, "GlobalId", None)
    if not guid:
        raise ValueError(
            f"Element express ID {element_id} has no GlobalId (check '{property_key}'); "
            "the element GUID is required to reference it in BCF."
        )

    name = getattr(entity, "Name", None)
    if name is None:
        name = ""
    return str(guid), str(name)


def _now_isodate() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_markup_xml(
    topic_guid: str,
    title: str,
    description: str,
    element_guid: str,
) -> str:
    """Build a markup file (one BCF Topic) with no viewpoint content."""
    root = ET.Element("Markup")

    topic = ET.SubElement(root, "Topic")
    topic.set("Guid", topic_guid)
    topic.set("TopicType", _TOPIC_TYPE)
    topic.set("TopicStatus", _TOPIC_STATUS)

    ET.SubElement(topic, "Title").text = title if title else element_guid
    ET.SubElement(topic, "CreationDate").text = _now_isodate()
    ET.SubElement(topic, "CreationAuthor").text = _CREATION_AUTHOR
    if description:
        ET.SubElement(topic, "Description").text = description

    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n'


def _write_bcf(
    output_path: Path,
    topics: list[tuple[str, str, str]],
) -> None:
    """Write a BCF 3.0 zip archive with one Topic per failing check.

    ``topics`` items are (element_guid, title, description). Each topic gets an
    UUID key used as its archive folder, containing only a ``markup.bcf``.
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "bcf.version",
            '<?xml version="1.0" encoding="UTF-8"?>\n<Version VersionId="3.0"/>\n',
        )
        project_id = str(uuid.uuid4())
        archive.writestr(
            "project.bcfp",
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<ProjectInfo><Project ProjectId="{project_id}"/></ProjectInfo>\n',
        )

        for element_guid, title, description in topics:
            topic_guid = str(uuid.uuid4())
            markup = _build_markup_xml(topic_guid, title, description, element_guid)
            archive.writestr(f"{topic_guid}/markup.bcf", markup)


@node()
async def bcf_output(
    settings: BcfOutputSettings,
    inputs: BcfOutputInputs,
    context: ExecutionContext,
) -> BcfOutputResult:
    if not inputs.elements:
        raise ValueError(
            "bcf_output requires LOI-Check.elements as its input. "
            "Connect the LOI-Check node's elements output."
        )

    if context.output_dir is None:
        raise ValueError(
            "bcf_output requires an output directory on the execution context."
        )

    formatter = _ResolvingFormatter()
    topics: list[BcfTopic] = []
    archive_topics: list[tuple[str, str, str]] = []
    failed_check_count = 0

    for element in inputs.elements:
        for check in element.checks:
            if check.passed:
                continue

            failed_check_count += 1
            element_guid, element_name = _resolve_identity(
                context, element.express_id, check.property_key
            )

            namespace = _build_namespace(
                element_id=element.express_id,
                element_guid=element_guid,
                element_name=element_name,
                class_name=element.class_name,
                check=check,
            )

            title = _resolve_template(
                settings.title_template,
                namespace,
                formatter,
                element_id=element.express_id,
                property_key=check.property_key,
            )
            description = _resolve_template(
                settings.description_template,
                namespace,
                formatter,
                element_id=element.express_id,
                property_key=check.property_key,
            )

            topics.append(
                BcfTopic(
                    guid=element_guid,
                    property_key=check.property_key,
                    title=title,
                    description=description,
                )
            )
            archive_topics.append((element_guid, title, description))

    output_dir = Path(context.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"bcf_output-{timestamp}.bcf"

    _write_bcf(output_path, archive_topics)
    return BcfOutputResult(
        output_path=str(output_path),
        topic_count=len(topics),
        element_count=len(inputs.elements),
        failed_check_count=failed_check_count,
        topics=topics,
    )
