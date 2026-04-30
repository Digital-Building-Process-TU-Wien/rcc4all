from __future__ import annotations

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node


class ElementFilterSettings(NodeModel):
    entity_type: str = Field(
        default="IFCWALL",
        title="Entity type",
        description="IFC entity name to filter by, for example IFCWALL.",
    )


class ElementFilterResult(NodeModel):
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description="Express IDs for all IFC entities matching the requested entity type.",
    )


@node()
async def element_filter(settings: ElementFilterSettings, context: ExecutionContext) -> ElementFilterResult:
    entity_type = settings.entity_type.strip()
    if not entity_type:
        raise ValueError("Element Filter requires a non-empty IFC entity type.")

    try:
        express_ids = [entity.id() for entity in context.ifc_model.by_type(entity_type)]
    except RuntimeError as error:
        raise ValueError(f"Unknown IFC entity type '{entity_type}'.") from error

    return ElementFilterResult(express_ids=express_ids)