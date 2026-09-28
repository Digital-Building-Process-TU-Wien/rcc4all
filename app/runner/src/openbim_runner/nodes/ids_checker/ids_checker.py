from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import expr_key
from openbim_runner.util.references import parse_element_refs


class IdsCheckerSettings(NodeModel):
    ids_file: str = Field(
        default="",
        title="IDS File",
        description="Path to the IDS specification file to validate against.",
    )
    generate_detailed_report: bool = Field(
        default=False,
        title="Detaillierten Report generieren",
        description="Wenn aktiviert, werden die Ergebnisse zusätzlich nach Specification gruppiert ausgegeben (für Report-Generierung). Die kombinierten Listen (failed_express_ids, passed_express_ids) werden immer erstellt.",
    )
    report_format: Literal["json", "html"] | None = Field(
        default=None,
        title="Report Format",
        description="Format für den generierten Report. Nur wirksam wenn generate_detailed_report aktiviert ist.",
    )


class IdsCheckerInputs(NodeModel):
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "Qualified element references (`<slug>:expr:<id>`) to validate against the "
            "IDS requirements. Mixed-model lists are grouped by model and each model is "
            "validated once. Bind ifc_element_filter output here."
        ),
    )


class IdsCheckerSpecificationResult(NodeModel):
    name: str = Field(
        default="",
        title="Specification Name",
        description="Name of the IDS specification.",
    )
    failed_express_ids: list[str] = Field(
        default=[],
        title="Failed Express IDs",
        description="Qualified references of entities that failed this specification's requirements.",
    )
    passed_express_ids: list[str] = Field(
        default=[],
        title="Passed Express IDs",
        description="Qualified references of entities that passed this specification's requirements.",
    )


class IdsCheckerResult(NodeModel):
    failed_express_ids: list[str] = Field(
        default=[],
        title="Failed Express IDs",
        description="Qualified references of entities that failed at least one IDS requirement (combined across all specifications).",
    )
    passed_express_ids: list[str] = Field(
        default=[],
        title="Passed Express IDs",
        description="Qualified references of entities that passed all applicable IDS requirements (combined across all specifications).",
    )
    specifications: list[IdsCheckerSpecificationResult] | None = Field(
        default=None,
        title="Specification Results",
        description="Per-specification breakdown. Only included when generate_detailed_report is enabled.",
    )
    report_path: str | None = Field(
        default=None,
        title="Report File Path",
        description="Path to the generated report file. Only included when generate_detailed_report and report_format are enabled.",
    )


@node()
async def ids_checker(
    settings: IdsCheckerSettings,
    inputs: IdsCheckerInputs,
    context: ExecutionContext,
) -> IdsCheckerResult:
    from ifctester import ids

    if not settings.ids_file:
        raise ValueError("No IDS file specified!")

    if context.workflow_dir is None:
        raise RuntimeError("Workflow directory not available for IDS file resolution.")

    ids_path = context.workflow_dir / settings.ids_file

    if not ids_path.exists():
        raise FileNotFoundError(f"IDS file not found: {ids_path}")

    # Group the qualified references by their model slug; each model is
    # validated once and results are filtered down to the given references.
    refs_by_slug: dict[str, set[int]] = {}
    for element in parse_element_refs(inputs.express_ids, node="ids_checker"):
        refs_by_slug.setdefault(element.slug, set()).add(element.express_id)

    # The reporter wraps one ids file (and therefore one validated model);
    # refuse mixed-model runs up front instead of after full validation.
    if (
        settings.generate_detailed_report
        and settings.report_format
        and len(refs_by_slug) > 1
    ):
        raise ValueError(
            "Detailed IDS reports require references from a single model; "
            f"got {len(refs_by_slug)} models."
        )

    all_applicable_ids: set[str] = set()
    all_failed_ids: set[str] = set()
    merged_specs: dict[str, tuple[set[str], set[str]]] = {}
    spec_order: list[str] = []
    ids_file: Any | None = None

    for slug in sorted(refs_by_slug):
        wanted_ids = refs_by_slug[slug]

        try:
            ids_file = ids.open(str(ids_path))
        except Exception as e:
            raise ValueError(f"Failed to parse IDS file: {e}") from e

        model = context.resolve_model(slug)

        try:
            ids_file.validate(model)
        except Exception as e:
            raise RuntimeError(f"Validation error: {e}") from e

        for specification in ids_file.specifications:
            applicable_entities = [
                e for e in specification.applicable_entities if e.id() in wanted_ids
            ]
            failed_entities = {
                e for e in specification.failed_entities if e.id() in wanted_ids
            }

            spec_failed = {expr_key(slug, e.id()) for e in failed_entities}
            spec_passed = {
                expr_key(slug, e.id()) for e in applicable_entities
            } - spec_failed

            if specification.name in merged_specs:
                merged_failed, merged_passed = merged_specs[specification.name]
                merged_specs[specification.name] = (
                    merged_failed | spec_failed,
                    merged_passed | spec_passed,
                )
            else:
                merged_specs[specification.name] = (spec_failed, spec_passed)
                spec_order.append(specification.name)

            all_applicable_ids |= {expr_key(slug, e.id()) for e in applicable_entities}
            all_failed_ids |= spec_failed

    failed_express_ids = sorted(all_failed_ids)
    passed_express_ids = sorted(all_applicable_ids - all_failed_ids)

    specification_results = [
        IdsCheckerSpecificationResult(
            name=name,
            failed_express_ids=sorted(merged_specs[name][0]),
            passed_express_ids=sorted(merged_specs[name][1]),
        )
        for name in spec_order
    ]

    specifications = (
        specification_results if settings.generate_detailed_report else None
    )

    # Report-Datei generieren wenn beide Settings aktiv. The single-model
    # requirement was already validated above.
    report_path: str | None = None
    if (
        settings.generate_detailed_report
        and settings.report_format
        and ids_file is not None
    ):
        from ifctester import reporter

        # Output-Verzeichnis ermitteln
        if context.output_dir is None:
            # Fallback: Festes Verzeichnis verwenden
            current_dir = Path(__file__).parent
            web_dir = current_dir.parent.parent.parent.parent / "web" / ".dev-files"
            web_dir.mkdir(parents=True, exist_ok=True)
            output_dir = web_dir
        else:
            output_dir = context.output_dir

        reporter_class = getattr(reporter, settings.report_format.capitalize())
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"ids_report-{timestamp}.{settings.report_format}"
        output_path = output_dir / filename

        reporter_instance = reporter_class(ids_file)
        reporter_instance.report()
        reporter_instance.to_file(str(output_path))
        report_path = str(output_path)

    return IdsCheckerResult(
        failed_express_ids=failed_express_ids,
        passed_express_ids=passed_express_ids,
        specifications=specifications,
        report_path=report_path,
    )
