from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import ifcopenshell
import ifcopenshell.guid
import numpy as np
from pydantic import Field

from openbim_runner.nodes.base import AutoBind, ExecutionContext, NodeModel, node
from openbim_runner.nodes.opening_surface.opening_surface import OpeningSurface
from openbim_runner.nodes.opening_surface_ifc_generator._ifc_helpers import (
    _add_area_quantity,  # pyright: ignore[reportPrivateUsage]
    _body_context,  # pyright: ignore[reportPrivateUsage]
    _build_polygonal_face_set,  # pyright: ignore[reportPrivateUsage]
    _create_model_shell,  # pyright: ignore[reportPrivateUsage]
    _face_normals,  # pyright: ignore[reportPrivateUsage]
    _local_placement,  # pyright: ignore[reportPrivateUsage]
    _planar_groups,  # pyright: ignore[reportPrivateUsage]
    _process_triangles,  # pyright: ignore[reportPrivateUsage]
    _replicate_spatial_structure,  # pyright: ignore[reportPrivateUsage]
    _result_storey,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.util.geometry import resolve_mesh


class OpeningSurfaceIfcGeneratorSettings(NodeModel):
    output_filename: str = Field(
        default="opening_surface_model.ifc",
        title="Output filename",
        description=(
            "Name of the generated IFC file. Written into the workflow output "
            "directory (the folder containing the workflow file)."
        ),
    )


class OpeningSurfaceIfcGeneratorInputs(NodeModel):
    openings: Annotated[list[OpeningSurface], AutoBind()] = Field(
        default=[],
        title="Openings",
        description=(
            "Opening closed-surface results of the opening_surface node. Bind its "
            "'openings' output here."
        ),
    )


class OpeningSurfaceIfcElementResult(NodeModel):
    opening_ref: str = Field(
        title="Opening reference",
        description="Qualified reference of the source opening (`<slug>:expr:<id>`).",
    )
    element_guid: str = Field(
        title="Element GUID",
        description="GlobalId of the generated IfcBuildingElementProxy.",
    )
    face_count: int = Field(
        default=0,
        title="Face count",
        description="Number of polygonal faces written for this opening closed "
        "surface.",
    )
    method: str | None = Field(
        default=None,
        title="Method",
        description=(
            "How the source closed surface was derived: 'closed_cut_surface', "
            "'lofted_caps' or 'caps_only'."
        ),
    )
    volume: float | None = Field(
        default=None,
        title="Volume",
        description=(
            "Volume of the opening solid written as an IfcQuantityVolume, in cubic "
            "metres, or None when it could not be retrieved."
        ),
    )
    host_ref: str | None = Field(
        default=None,
        title="Host reference",
        description="Qualified reference of the host element the opening voids.",
    )
    storey_ref: str | None = Field(
        default=None,
        title="Storey reference",
        description=(
            "Qualified reference of the source building storey the proxy was "
            "contained in, or None when the host is not inside a storey."
        ),
    )
    area: float | None = Field(
        default=None,
        title="Area",
        description="Opening area written as an IfcQuantityArea on the proxy.",
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason when the proxy could not be generated.",
    )


class OpeningSurfaceIfcGeneratorResult(NodeModel):
    output_path: str = Field(
        title="Output path",
        description="Absolute path of the generated IFC file.",
    )
    element_count: int = Field(
        title="Element count",
        description="Number of generated opening closed-surface proxies.",
    )
    storey_count: int = Field(
        title="Storey count",
        description="Number of building storeys replicated from the source model.",
    )
    elements: list[OpeningSurfaceIfcElementResult] = Field(
        default=[],
        title="Elements",
        description="Ordered list of generated proxies with their spatial relation.",
    )


@node()
async def opening_surface_ifc_generator(
    settings: OpeningSurfaceIfcGeneratorSettings,
    inputs: OpeningSurfaceIfcGeneratorInputs,
    context: ExecutionContext,
) -> OpeningSurfaceIfcGeneratorResult:
    if not inputs.openings:
        raise ValueError(
            "opening_surface_ifc_generator requires openings as its input. "
            "Connect the opening_surface node's openings output."
        )
    if context.output_dir is None:
        raise ValueError(
            "opening_surface_ifc_generator requires an output directory on the "
            "execution context."
        )

    new_model = _create_model_shell()
    storey_maps = _replicate_spatial_structure(context, new_model)
    body_context = _body_context(new_model)

    elements: list[OpeningSurfaceIfcElementResult] = []
    for index, opening in enumerate(inputs.openings):
        elements.append(
            _generate_surface(
                context,
                new_model,
                storey_maps,
                body_context,
                opening,
                index,
            )
        )

    output_dir = Path(context.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / settings.output_filename
    new_model.write(str(output_path))

    storey_count = len(
        {element.storey_ref for element in elements if element.storey_ref is not None}
    )
    return OpeningSurfaceIfcGeneratorResult(
        output_path=str(output_path),
        element_count=sum(1 for element in elements if element.error is None),
        storey_count=storey_count,
        elements=elements,
    )


def _generate_surface(
    context: ExecutionContext,
    new_model: Any,
    storey_maps: dict[str, dict[int, Any]],
    body_context: Any,
    opening: OpeningSurface,
    index: int,
) -> OpeningSurfaceIfcElementResult:
    """Generate one closing-opening closed-surface proxy for ``opening``.

    The cached mesh is the watertight opening closed surface (a closed
    cut-surface tube or a lofted-cap solid). Its planar face groups are flattened
    into polygonal
    faces of one ``IfcPolygonalFaceSet`` written as the Body of a single
    ``IfcBuildingElementProxy``, so the whole opening is one element.
    """
    if opening.geometry_key is None or opening.error is not None:
        return OpeningSurfaceIfcElementResult(
            opening_ref=opening.express_id,
            element_guid="",
            host_ref=opening.host_express_id,
            error=opening.error or "missing geometry",
        )

    try:
        mesh = resolve_mesh(context, opening.geometry_key)
    except ValueError:
        return OpeningSurfaceIfcElementResult(
            opening_ref=opening.express_id,
            element_guid="",
            host_ref=opening.host_express_id,
            error=f"unresolvable geometry '{opening.geometry_key}'",
        )

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) == 0:
        return OpeningSurfaceIfcElementResult(
            opening_ref=opening.express_id,
            element_guid="",
            host_ref=opening.host_express_id,
            error="empty opening closed-surface mesh",
        )

    normals = _face_normals(vertices, faces)
    groups = _planar_groups(vertices, faces, normals)
    solid_hole_pairs: dict[int, dict[str, Any]] = {}
    counter = 0
    for group in groups:
        triangles = vertices[faces[group]]
        # Drop degenerate (zero-area) triangles: slivers in a lofted side or a
        # triangulated cap would collapse under the 2D projection.
        first = triangles[:, 0, :]
        edge_a = triangles[:, 1, :] - first
        edge_b = triangles[:, 2, :] - first
        areas = np.linalg.norm(np.cross(edge_a, edge_b), axis=1)
        triangles = triangles[areas > 1e-12]
        if len(triangles) == 0:
            continue
        produced = _process_triangles(triangles)
        if not produced:
            continue
        for pair in produced.values():
            solid_hole_pairs[counter] = pair
            counter += 1

    if not solid_hole_pairs:
        return OpeningSurfaceIfcElementResult(
            opening_ref=opening.express_id,
            element_guid="",
            host_ref=opening.host_express_id,
            error="no polygon outline derived from opening closed-surface faces",
        )

    shape = _build_polygonal_face_set(new_model, body_context, solid_hole_pairs)
    proxy = _create_surface_proxy(new_model, shape, index)
    _add_area_quantity(new_model, proxy, opening.area)
    _add_volume_quantity(new_model, proxy, float(mesh.volume))

    storey_ref = None
    new_storey = None
    if opening.host_express_id:
        storey_ref, new_storey = _result_storey(
            context, storey_maps, opening.host_express_id
        )
    if new_storey is not None:
        new_model.createIfcRelContainedInSpatialStructure(
            ifcopenshell.guid.new(),
            None,
            None,
            None,
            [proxy],
            new_storey,
        )

    return OpeningSurfaceIfcElementResult(
        opening_ref=opening.express_id,
        element_guid=str(proxy.GlobalId),
        face_count=len(solid_hole_pairs),
        method=opening.method,
        volume=float(mesh.volume),
        host_ref=opening.host_express_id,
        storey_ref=storey_ref,
        area=opening.area,
    )


def _add_volume_quantity(new_model: Any, proxy: Any, volume: float | None) -> None:
    if volume is None or volume <= 0.0:
        return
    quantity_volume = new_model.createIfcQuantityVolume(
        "OpeningSurface", None, None, volume, None
    )
    quantity_set = new_model.createIfcElementQuantity(
        ifcopenshell.guid.new(),
        None,
        "OpeningSurfaceQuantities",
        None,
        None,
        [quantity_volume],
    )
    new_model.createIfcRelDefinesByProperties(
        ifcopenshell.guid.new(), None, None, None, [proxy], quantity_set
    )


def _create_surface_proxy(new_model: Any, shape: Any, index: int) -> Any:
    placement = _local_placement(new_model, (0.0, 0.0, 0.0))
    return new_model.createIfcBuildingElementProxy(
        ifcopenshell.guid.new(),
        None,
        f"OpeningSurface_{index}",
        None,
        None,
        placement,
        shape,
        None,
        None,
    )
