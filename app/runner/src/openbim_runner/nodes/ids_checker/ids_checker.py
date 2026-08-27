from __future__ import annotations

from typing import Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node

OutputMode = Literal["combined", "per_specification", "both"]


class IdsCheckerSettings(NodeModel):
    ids_file: str = Field(
        default="",
        title="IDS File",
        description="Path to the IDS specification file to validate against.",
    )
    output_mode: OutputMode = Field(
        default="combined",
        title="Output Mode",
        description="Controls how results are structured: 'combined' produces flat lists across all specifications, 'per_specification' produces a per-specification breakdown, 'both' produces both.",
    )


class IdsCheckerInputs(NodeModel):
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description="Optional list of IFC entity express IDs to validate. If provided, only these entities will be checked against the IDS requirements. If not provided, the whole IFC file is tested.",
    )


class IdsCheckerSpecificationResult(NodeModel):
    name: str = Field(
        default="",
        title="Specification Name",
        description="Name of the IDS specification.",
    )
    failed_express_ids: list[int] = Field(
        default=[],
        title="Failed Express IDs",
        description="List of express IDs of entities that failed this specification's requirements.",
    )
    passed_express_ids: list[int] = Field(
        default=[],
        title="Passed Express IDs",
        description="List of express IDs of entities that passed this specification's requirements.",
    )


class IdsCheckerResult(NodeModel):
    failed_express_ids: list[int] = Field(
        default=[],
        title="Failed Express IDs",
        description="List of express IDs of entities that failed at least one IDS requirement (combined across all specifications).",
    )
    passed_express_ids: list[int] = Field(
        default=[],
        title="Passed Express IDs",
        description="List of express IDs of entities that passed all applicable IDS requirements (combined across all specifications).",
    )
    specifications: list[IdsCheckerSpecificationResult] = Field(
        default=[],
        title="Specification Results",
        description="Per-specification breakdown of passed and failed express IDs.",
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

    input_id_set = set(inputs.express_ids) if inputs.express_ids else None

    try:
        ids_file = ids.open(str(ids_path))
    except Exception as e:
        raise ValueError(f"Failed to parse IDS file: {e}") from e

    try:
        ids_file.validate(context.ifc_model)
    except Exception as e:
        raise RuntimeError(f"Validation error: {e}") from e

    all_applicable_ids: set[int] = set()
    all_failed_ids: set[int] = set()
    specification_results: list[IdsCheckerSpecificationResult] = []

    for specification in ids_file.specifications:
        applicable_entities = specification.applicable_entities
        failed_entities = specification.failed_entities

        if input_id_set is not None:
            applicable_entities = [
                e for e in applicable_entities if e.id() in input_id_set
            ]
            failed_entities = {e for e in failed_entities if e.id() in input_id_set}

        spec_applicable_ids = {e.id() for e in applicable_entities}
        spec_failed_ids = {e.id() for e in failed_entities}
        spec_passed_ids = spec_applicable_ids - spec_failed_ids

        for e in applicable_entities:
            all_applicable_ids.add(e.id())
        for e in failed_entities:
            all_failed_ids.add(e.id())

        specification_results.append(
            IdsCheckerSpecificationResult(
                name=specification.name,
                failed_express_ids=sorted(spec_failed_ids),
                passed_express_ids=sorted(spec_passed_ids),
            )
        )

    failed_express_ids = sorted(all_failed_ids)
    passed_express_ids = sorted(all_applicable_ids - all_failed_ids)

    if settings.output_mode == "per_specification":
        return IdsCheckerResult(
            failed_express_ids=[],
            passed_express_ids=[],
            specifications=specification_results,
        )
    if settings.output_mode == "combined":
        return IdsCheckerResult(
            failed_express_ids=failed_express_ids,
            passed_express_ids=passed_express_ids,
            specifications=[],
        )
    return IdsCheckerResult(
        failed_express_ids=failed_express_ids,
        passed_express_ids=passed_express_ids,
        specifications=specification_results,
    )
