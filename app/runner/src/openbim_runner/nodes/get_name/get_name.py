from __future__ import annotations

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node


class GetNameSettings(NodeModel):
    allow_missing: bool = Field(
        default=True,
        title="Allow missing names",
        description="When enabled, unresolved express IDs or nameless IFC entities produce None instead of raising an error.",
    )
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description="Ordered list of IFC express IDs whose object names should be resolved.",
    )


class GetNameResult(NodeModel):
    object_names: list[str | None] = Field(
        default=[],
        title="Object names",
        description="Ordered list of IFC object names aligned with the input express IDs.",
    )


@node()
async def get_name(settings: GetNameSettings, context: ExecutionContext) -> GetNameResult:
    object_names: list[str | None] = []

    for express_id in settings.express_ids:
        try:
            entity = context.ifc_model.by_id(express_id)
            object_name = getattr(entity, "Name", None)
            if object_name is not None:
                object_name = str(object_name)
        except RuntimeError:
            object_name = None

        if object_name is None and not settings.allow_missing:
            raise ValueError(f"Could not resolve a name for express ID {express_id}.")

        object_names.append(object_name)

    return GetNameResult(object_names=object_names)
