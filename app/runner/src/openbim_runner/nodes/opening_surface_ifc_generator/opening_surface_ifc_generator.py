from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Any

import ifcopenshell
import ifcopenshell.api.context
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.guid
import numpy as np
from pydantic import Field
from shapely.geometry import Polygon
from shapely.ops import unary_union

from openbim_runner.nodes.base import AutoBind, ExecutionContext, NodeModel, node
from openbim_runner.nodes.opening_surface.opening_surface import OpeningSurface
from openbim_runner.util.geometry import resolve_mesh
from openbim_runner.util.references import split_expr_key

_ALIGNED_COS = math.cos(math.pi / 180.0)
_PLANE_TOLERANCE = 0.01
# Two cap-face groups count as the two faces of a through-opening while their
# normals enclose at least 170°.
_OPPOSING_COS = -math.cos(math.radians(10.0))


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
            "Opening surface results of the opening_surface node. Bind its "
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
    cap: int = Field(
        default=0,
        title="Cap index",
        description=(
            "Index of the cap face this proxy represents (0 = larger cap, 1 = "
            "its opposing cap; a single-cap recess yields only cap 0)."
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
        description="Number of generated opening-surface proxies.",
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
    for opening in inputs.openings:
        elements.extend(
            _generate_opening(
                context,
                new_model,
                storey_maps,
                body_context,
                opening,
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


def _create_model_shell() -> Any:
    model = ifcopenshell.file(schema="IFC4X3")
    model.header.file_description.description = ("ViewDefinition[]",)
    ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcProject", name="Opening Surface Result"
    )
    length = ifcopenshell.api.unit.add_si_unit(model, unit_type="LENGTHUNIT")
    area = ifcopenshell.api.unit.add_si_unit(model, unit_type="AREAUNIT")
    volume = ifcopenshell.api.unit.add_si_unit(model, unit_type="VOLUMEUNIT")
    ifcopenshell.api.unit.assign_unit(model, units=[length, area, volume])
    model_context = ifcopenshell.api.context.add_context(model, context_type="Model")
    ifcopenshell.api.context.add_context(
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )
    return model


def _body_context(model: Any) -> Any:
    return model.by_type("IfcGeometricRepresentationSubContext")[0]


def _replicate_spatial_structure(
    context: ExecutionContext, new_model: Any
) -> dict[str, dict[int, Any]]:
    """Replicate the project/site/building/storey skeleton into ``new_model``.

    Returns a mapping ``{slug: {source_storey_id: new_storey_entity}}`` so each
    generated proxy can be contained in the new storey that mirrors the source
    storey holding its host.
    """
    storey_maps: dict[str, dict[int, Any]] = {}
    new_project = new_model.by_type("IfcProject")[0]

    for slug, model in context.models.items():
        source_project = _first_project(model)
        if source_project is None:
            continue
        storey_map: dict[int, Any] = {}
        _replicate_level(new_model, new_project, source_project, None, storey_map)
        if storey_map:
            storey_maps[slug] = storey_map

    return storey_maps


def _first_project(model: Any) -> Any | None:
    projects = model.by_type("IfcProject")
    return projects[0] if projects else None


def _replicate_level(
    new_model: Any,
    new_parent: Any,
    source_parent: Any,
    new_parent_placement: Any,
    storey_map: dict[int, Any],
) -> None:
    for relationship in getattr(source_parent, "IsDecomposedBy", None) or []:
        for source_child in relationship.RelatedObjects or []:
            if not source_child.is_a("IfcSpatialStructureElement"):
                continue
            if source_child.is_a("IfcSpace"):
                continue
            new_placement = _replicate_placement(
                new_model, source_child, new_parent_placement
            )
            new_child = _new_spatial_entity(new_model, source_child, new_placement)
            if new_child is None:
                continue
            new_model.createIfcRelAggregates(
                ifcopenshell.guid.new(),
                None,
                None,
                None,
                new_parent,
                [new_child],
            )
            if source_child.is_a("IfcBuildingStorey"):
                storey_map[source_child.id()] = new_child
            _replicate_level(
                new_model, new_child, source_child, new_placement, storey_map
            )


def _new_spatial_entity(
    new_model: Any, source_entity: Any, placement: Any
) -> Any | None:
    entity_class = source_entity.is_a()
    name = source_entity.Name
    if entity_class == "IfcSite":
        return new_model.createIfcSite(
            ifcopenshell.guid.new(),
            None,
            name,
            None,
            None,
            placement,
            None,
            None,
            "ELEMENT",
        )
    if entity_class == "IfcBuilding":
        return new_model.createIfcBuilding(
            ifcopenshell.guid.new(),
            None,
            name,
            None,
            None,
            placement,
            None,
            None,
            "ELEMENT",
        )
    if entity_class == "IfcBuildingStorey":
        return new_model.createIfcBuildingStorey(
            ifcopenshell.guid.new(),
            None,
            name,
            None,
            None,
            placement,
            None,
            None,
            "ELEMENT",
        )
    return None


def _replicate_placement(
    new_model: Any, source_entity: Any, new_parent_placement: Any
) -> Any:
    source_placement = getattr(source_entity, "ObjectPlacement", None)
    if source_placement is None or not source_placement.is_a("IfcLocalPlacement"):
        return _local_placement(new_model, (0.0, 0.0, 0.0), new_parent_placement)

    relative = source_placement.RelativePlacement
    point = _vec3(relative.Location.Coordinates or (0.0, 0.0, 0.0))
    axis = (
        _vec3(relative.Axis.DirectionRatios)
        if relative.Axis is not None
        else (0.0, 0.0, 1.0)
    )
    ref_direction = (
        _vec3(relative.RefDirection.DirectionRatios)
        if relative.RefDirection is not None
        else (1.0, 0.0, 0.0)
    )
    return _local_placement(new_model, point, axis, ref_direction, new_parent_placement)


def _vec3(value: Any) -> tuple[float, float, float]:
    coordinates = tuple(float(component) for component in value)
    if len(coordinates) < 3:
        return (0.0, 0.0, 0.0)
    return (coordinates[0], coordinates[1], coordinates[2])


def _local_placement(
    new_model: Any,
    point: tuple[float, float, float],
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
    ref_direction: tuple[float, float, float] = (1.0, 0.0, 0.0),
    relative_to: Any | None = None,
) -> Any:
    placement_point = new_model.createIfcCartesianPoint(point)
    axis_direction = new_model.createIfcDirection(axis)
    ref_direction3d = new_model.createIfcDirection(ref_direction)
    axis_placement = new_model.createIfcAxis2Placement3D(
        placement_point, axis_direction, ref_direction3d
    )
    return new_model.createIfcLocalPlacement(relative_to, axis_placement)


def _generate_opening(
    context: ExecutionContext,
    new_model: Any,
    storey_maps: dict[str, dict[int, Any]],
    body_context: Any,
    opening: OpeningSurface,
) -> list[OpeningSurfaceIfcElementResult]:
    """Generate one proxy per cap face of ``opening``.

    The cached opening mesh already holds both cap faces (front + back) of a
    through-void, so each cap group is emitted as its own independent
    ``IfcBuildingElementProxy``. A single-cap recess yields one proxy.
    """
    if opening.geometry_key is None or opening.error is not None:
        return [
            OpeningSurfaceIfcElementResult(
                opening_ref=opening.express_id,
                element_guid="",
                host_ref=opening.host_express_id,
                error=opening.error or "missing geometry",
            )
        ]

    try:
        mesh = resolve_mesh(context, opening.geometry_key)
    except ValueError:
        return [
            OpeningSurfaceIfcElementResult(
                opening_ref=opening.express_id,
                element_guid="",
                host_ref=opening.host_express_id,
                error=f"unresolvable geometry '{opening.geometry_key}'",
            )
        ]

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = _face_normals(vertices, faces)
    cap_groups = _cap_groups(vertices, faces, normals)
    if not cap_groups:
        return [
            OpeningSurfaceIfcElementResult(
                opening_ref=opening.express_id,
                element_guid="",
                host_ref=opening.host_express_id,
                error="no planar cap faces in opening mesh",
            )
        ]

    storey_ref = None
    new_storey = None
    if opening.host_express_id:
        storey_ref, new_storey = _result_storey(
            context, storey_maps, opening.host_express_id
        )

    results: list[OpeningSurfaceIfcElementResult] = []
    for cap_index, cap_group in enumerate(cap_groups):
        triangles = vertices[faces[cap_group]]
        solid_hole_pairs = _process_triangles(triangles)
        if not solid_hole_pairs:
            results.append(
                OpeningSurfaceIfcElementResult(
                    opening_ref=opening.express_id,
                    element_guid="",
                    cap=cap_index,
                    host_ref=opening.host_express_id,
                    error="no polygon outline derived from cap faces",
                )
            )
            continue

        shape = _build_polygonal_face_set(new_model, body_context, solid_hole_pairs)
        proxy = _create_proxy(new_model, shape, cap_index)
        _add_area_quantity(new_model, proxy, opening.area)
        if new_storey is not None:
            new_model.createIfcRelContainedInSpatialStructure(
                ifcopenshell.guid.new(),
                None,
                None,
                None,
                [proxy],
                new_storey,
            )

        results.append(
            OpeningSurfaceIfcElementResult(
                opening_ref=opening.express_id,
                element_guid=str(proxy.GlobalId),
                cap=cap_index,
                host_ref=opening.host_express_id,
                storey_ref=storey_ref,
                area=opening.area,
            )
        )
    return results


def _cap_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """The cap face groups of an opening mesh.

    The cached cap mesh contains the two opposing faces of a through-opening (or
    one face for a recess). The largest planar group is the larger cap; its
    largest opposing group (normals enclosing ≥170°) is the other cap. Returns
    an empty list when the mesh has no planar faces.
    """
    sized = [
        (group, _group_area(vertices, faces, group))
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [(group, area) for group, area in sized if area > 0.0]
    sized.sort(key=lambda item: item[1], reverse=True)
    if not sized:
        return []

    caps = [sized[0][0]]
    first_normal = normals[caps[0][0]]
    for group, _area in sized[1:]:
        if float(normals[group[0]] @ first_normal) <= _OPPOSING_COS:
            caps.append(group)
            break
    return caps


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _planar_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    first_points = vertices[faces[:, 0]]
    assigned = np.zeros(len(faces), dtype=bool)
    groups: list[list[int]] = []
    for seed in range(len(faces)):
        if assigned[seed]:
            continue
        normal = normals[seed]
        offsets = (first_points - first_points[seed]) @ normal
        same = (
            (normals @ normal >= _ALIGNED_COS)
            & (np.abs(offsets) <= _PLANE_TOLERANCE)
            & ~assigned
        )
        same[seed] = True
        assigned |= same
        groups.append(np.flatnonzero(same).tolist())
    return groups


def _group_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(0.5 * np.linalg.norm(cross, axis=1).sum())


def _build_polygonal_face_set(
    new_model: Any, body_context: Any, solid_hole_pairs: dict[int, dict[str, Any]]
) -> Any:
    face_set_list = []
    for pair in solid_hole_pairs.values():
        point_list = new_model.createIfcCartesianPointList3d(pair["vertices"])
        if pair["hole_indices"]:
            indexed_face = new_model.createIfcIndexedPolygonalFaceWithVoids(
                pair["outline_indices"], pair["hole_indices"]
            )
        else:
            indexed_face = new_model.createIfcIndexedPolygonalFace(
                pair["outline_indices"]
            )
        face_set = new_model.createIfcPolygonalFaceSet(
            point_list, None, [indexed_face], None
        )
        face_set_list.append(face_set)
    representation = new_model.createIfcShapeRepresentation(
        body_context, "Body", "Tessellation", face_set_list
    )
    return new_model.createIfcProductDefinitionShape(None, None, [representation])


def _create_proxy(new_model: Any, shape: Any, cap_index: int) -> Any:
    placement = _local_placement(new_model, (0.0, 0.0, 0.0))
    return new_model.createIfcBuildingElementProxy(
        ifcopenshell.guid.new(),
        None,
        f"OpeningSurface_{cap_index}",
        None,
        None,
        placement,
        shape,
        None,
        None,
    )


def _add_area_quantity(new_model: Any, proxy: Any, area: float | None) -> None:
    if area is None:
        return
    quantity_area = new_model.createIfcQuantityArea(
        "OpeningArea", None, None, area, None
    )
    quantity_set = new_model.createIfcElementQuantity(
        ifcopenshell.guid.new(),
        None,
        "OpeningSurfaceQuantities",
        None,
        None,
        [quantity_area],
    )
    new_model.createIfcRelDefinesByProperties(
        ifcopenshell.guid.new(), None, None, None, [proxy], quantity_set
    )


def _result_storey(
    context: ExecutionContext,
    storey_maps: dict[str, dict[int, Any]],
    host_express_id: str,
) -> tuple[str | None, Any | None]:
    parsed = split_expr_key(host_express_id)
    if parsed is None:
        return None, None
    slug, host_id = parsed
    try:
        model = context.resolve_model(slug)
    except ValueError:
        return None, None
    try:
        host = model.by_id(host_id)
    except RuntimeError:
        return None, None

    source_storey = _source_storey(host)
    if source_storey is None:
        return None, None
    new_storey = (storey_maps.get(slug) or {}).get(source_storey.id())
    return f"{slug}:expr:{source_storey.id()}", new_storey


def _source_storey(host: Any) -> Any | None:
    for relationship in getattr(host, "ContainedInStructure", None) or []:
        structure = getattr(relationship, "RelatingStructure", None)
        if structure is None:
            continue
        storey = _ascend_to_storey(structure)
        if storey is not None:
            return storey
    part = _containing_part(host)
    if part is not None:
        return _source_storey(part)
    return None


def _containing_part(entity: Any) -> Any | None:
    for relationship in getattr(entity, "Decomposes", None) or []:
        relating = getattr(relationship, "RelatingObject", None)
        if relating is not None:
            return relating
    for relationship in getattr(entity, "Nests", None) or []:
        relating = getattr(relationship, "RelatingObject", None)
        if relating is not None:
            return relating
    return None


def _ascend_to_storey(entity: Any) -> Any | None:
    current = entity
    seen: set[int] = set()
    while current is not None and current.id() not in seen:
        seen.add(current.id())
        if current.is_a("IfcBuildingStorey"):
            return current
        current = _containing_part(current)
    return None


def _compute_triangle_normal(triangle: np.ndarray) -> np.ndarray:
    v1 = triangle[1] - triangle[0]
    v2 = triangle[2] - triangle[0]
    normal = np.cross(v1, v2)
    norm = np.linalg.norm(normal)
    if norm > 1e-10:
        normal = normal / norm
    return normal


def _plane_basis_and_projection(
    triangles: np.ndarray, normal: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[np.ndarray]]:
    abs_normal = np.abs(normal)
    if abs_normal[0] >= abs_normal[1] and abs_normal[0] >= abs_normal[2]:
        u = np.array([0.0, 1.0, 0.0], dtype=float)
    elif abs_normal[1] >= abs_normal[0] and abs_normal[1] >= abs_normal[2]:
        u = np.array([1.0, 0.0, 0.0], dtype=float)
    else:
        u = np.array([1.0, 0.0, 0.0], dtype=float)

    u = u - float(np.dot(u, normal)) * normal
    u_norm = np.linalg.norm(u)
    if u_norm > 1e-10:
        u = u / u_norm
    else:
        u = np.array([0.0, 1.0, 0.0], dtype=float)
        u = u - float(np.dot(u, normal)) * normal
        u = u / np.linalg.norm(u)

    v = np.cross(normal, u)
    v = v / np.linalg.norm(v)

    origin = triangles[0][0]
    triangles_2d = []
    for tri in triangles:
        tri_2d = np.zeros((3, 2))
        for i in range(3):
            vec = tri[i] - origin
            tri_2d[i, 0] = float(np.dot(vec, u))
            tri_2d[i, 1] = float(np.dot(vec, v))
        triangles_2d.append(tri_2d)
    return u, v, origin, triangles_2d


def _transform_2d_to_3d(
    coords_2d: np.ndarray, u: np.ndarray, v: np.ndarray, origin: np.ndarray
) -> np.ndarray:
    coords_3d = np.zeros((coords_2d.shape[0], 3))
    for i in range(coords_2d.shape[0]):
        coords_3d[i] = origin + coords_2d[i, 0] * u + coords_2d[i, 1] * v
    return coords_3d


def _merge_close_polygons(multipoly: Any, distance_threshold: float = 1e-3) -> Any:
    if multipoly.geom_type == "Polygon":
        return multipoly
    buffered = multipoly.buffer(distance_threshold / 2)
    merged = buffered.buffer(-distance_threshold / 2)
    if not merged.is_valid:
        merged = merged.buffer(0)
    return merged.simplify(distance_threshold / 10)


def _process_triangles(
    triangles: np.ndarray,
) -> dict[int, dict[str, Any]]:
    normals = np.array([_compute_triangle_normal(tri) for tri in triangles])
    avg_normal = normals.mean(axis=0)
    if np.linalg.norm(avg_normal) > 1e-10:
        avg_normal = avg_normal / np.linalg.norm(avg_normal)
    u, v, origin, triangles_2d = _plane_basis_and_projection(triangles, avg_normal)

    shapely_polys = [Polygon(tri_2d) for tri_2d in triangles_2d]
    merged = unary_union(shapely_polys)
    merged = _merge_close_polygons(merged)

    solid_hole_pairs: dict[int, dict[str, Any]] = {}
    counter = 0

    def extract(shape: Any) -> None:
        nonlocal counter
        outline_2d = _closed_ring(shape.exterior)
        vertices = _transform_2d_to_3d(outline_2d, u, v, origin).tolist()
        outline_indices = [i + 1 for i in range(len(vertices))]
        hole_indices = []
        for interior in shape.interiors:
            hole_2d = _closed_ring(interior)
            hole_vertices = _transform_2d_to_3d(hole_2d, u, v, origin).tolist()
            start_index = len(vertices) + 1
            vertices.extend(hole_vertices)
            hole_indices.append([start_index + i for i in range(len(hole_vertices))])
        solid_hole_pairs[counter] = {
            "vertices": vertices,
            "outline_indices": outline_indices,
            "hole_indices": hole_indices,
        }
        counter += 1

    if merged.geom_type == "Polygon":
        extract(merged)
    elif merged.geom_type == "MultiPolygon":
        for polygon in merged.geoms:
            extract(polygon)
    return solid_hole_pairs


def _closed_ring(ring: Any) -> np.ndarray:
    coords = np.array(ring.xy).T
    if coords.shape[0] > 1 and np.allclose(coords[0], coords[-1]):
        coords = coords[:-1]
    return coords
