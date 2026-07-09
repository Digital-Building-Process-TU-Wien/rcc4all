from __future__ import annotations

from typing import Any

import ifcopenshell.geom
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.geometry import Geometry, cache_mesh, reshape_flat


class GetGeometrySettings(NodeModel):
    fail_on_missing: bool = Field(
        default=False,
        title="Fail on missing",
        description=(
            "When enabled, raises an error if an express ID does not exist in the model "
            "or an element has no body geometry representation."
        ),
    )


class GetGeometryInputs(NodeModel):
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description="Ordered list of IFC express IDs whose body geometry should be tessellated.",
    )


class GetGeometryResult(NodeModel):
    geometries: list[Geometry] = Field(
        default=[],
        title="Geometries",
        description="Geometry handles aligned with the input express IDs (missing elements are skipped).",
    )


def _build_settings() -> Any:
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    s.set("weld-vertices", True)
    s.set("context_types", ["Body"])  # pyright: ignore[reportArgumentType]
    return s


def _is_empty(geo: Any) -> bool:
    return len(geo.verts) == 0 or len(geo.faces) == 0


@node()
async def get_geometry(
    settings: GetGeometrySettings,
    inputs: GetGeometryInputs,
    context: ExecutionContext,
) -> GetGeometryResult:
    geom_settings = _build_settings()
    geometries: list[Geometry] = []

    for express_id in inputs.express_ids:
        try:
            element = context.ifc_model.by_id(express_id)
            shape: Any = ifcopenshell.geom.create_shape(geom_settings, element)
            geo: Any = shape.geometry
        except RuntimeError as error:
            if settings.fail_on_missing:
                raise ValueError(
                    f"Could not tessellate body geometry for express ID {express_id}: {error}"
                ) from error
            continue

        if _is_empty(geo):
            if settings.fail_on_missing:
                raise ValueError(
                    f"Express ID {express_id} has no body geometry representation."
                )
            continue

        mesh = reshape_flat(geo.verts, geo.faces)
        geometries.append(cache_mesh(context, mesh, express_id))

    return GetGeometryResult(geometries=geometries)
