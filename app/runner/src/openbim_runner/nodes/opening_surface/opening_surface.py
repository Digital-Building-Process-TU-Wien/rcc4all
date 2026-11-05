from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import cache_mesh, resolve_mesh
from openbim_runner.util.references import expr_key, iter_resolved_elements

# Faces join a planar surface when their normal deviates by less than ~1° from
# the group's seed face and their first vertex lies on its plane (mirroring the
# reference implementation).
_ALIGNED_COS = math.cos(math.pi / 180.0)
_PLANE_TOLERANCE = 0.01
# Two surface groups count as opposing cap faces while their normals enclose at
# least 170°.
_OPPOSING_COS = -math.cos(math.radians(10.0))
# Planes count as near-horizontal when their normal encloses less than ~2.5°
# with the world Z axis.
_HORIZONTAL_COS = 0.999


class OpeningSurfaceInputs(NodeModel):
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "Qualified element references (`<slug>:expr:<id>`) of host building "
            "elements (e.g. walls, slabs, roofs) whose openings are retrieved. "
            "Bind ifc_element_filter output here."
        ),
    )


class OpeningSurface(NodeModel):
    express_id: str = Field(
        title="Express ID",
        description="The qualified opening reference (`<slug>:expr:<id>`).",
    )
    guid: str = Field(
        default="",
        title="GUID",
        description="GlobalId of the opening element, empty when missing.",
    )
    host_express_id: str = Field(
        title="Host express ID",
        description="Qualified reference of the host element the opening voids.",
    )
    geometry_key: str | None = Field(
        default=None,
        title="Geometry key",
        description=(
            "Geometry-cache key (`gen:`) of the retrieved opening surfaces, or "
            "None when they could not be retrieved."
        ),
    )
    area: float | None = Field(
        default=None,
        title="Area",
        description=(
            "Opening area in the plane of the host surface (the larger cap "
            "face), or None when it could not be retrieved."
        ),
    )
    width: float | None = Field(
        default=None,
        title="Width",
        description=(
            "Horizontal extent of the opening surfaces in the host plane, or "
            "None when it could not be retrieved."
        ),
    )
    height: float | None = Field(
        default=None,
        title="Height",
        description=(
            "Vertical extent of the opening surfaces in the host plane, or "
            "None when it could not be retrieved."
        ),
    )
    depth: float | None = Field(
        default=None,
        title="Depth",
        description=(
            "Distance between the two cap faces along the host surface normal. "
            "None when only one cap face exists (e.g. a recess) or when it "
            "could not be retrieved."
        ),
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason when the opening surfaces could not be retrieved.",
    )


class OpeningSurfaceResult(NodeModel):
    opening_count: int = Field(
        title="Opening count",
        description="Number of openings found on the input elements.",
    )
    surface_count: int = Field(
        title="Surface count",
        description="Number of openings whose surfaces were retrieved into the geometry cache.",
    )
    geometry_keys: list[str] = Field(
        default=[],
        title="Geometry keys",
        description=(
            "Geometry-cache keys (`gen:`) of the retrieved opening surfaces, in "
            "opening order. Bind to geometry consumers such as measurement or "
            "collision."
        ),
    )
    openings: list[OpeningSurface] = Field(
        default=[],
        title="Openings",
        description="Flat list of openings with their retrieved surface data.",
    )


@node()
async def opening_surface(
    inputs: OpeningSurfaceInputs,
    context: ExecutionContext,
) -> OpeningSurfaceResult:
    openings: list[OpeningSurface] = []
    seen: set[str] = set()

    for element, model in iter_resolved_elements(
        inputs.express_ids, context, node="opening_surface"
    ):
        host = _resolve_entity(model, element.express_id)
        if host is None:
            continue

        for opening_entity in _iter_openings(host):
            opening_ref = expr_key(element.slug, opening_entity.id())
            if opening_ref in seen:
                continue
            seen.add(opening_ref)
            openings.append(
                _opening_surface(
                    context,
                    slug=element.slug,
                    host_ref=element.reference,
                    opening_ref=opening_ref,
                    opening_entity=opening_entity,
                )
            )

    geometry_keys = [
        opening.geometry_key for opening in openings if opening.geometry_key
    ]
    return OpeningSurfaceResult(
        opening_count=len(openings),
        surface_count=len(geometry_keys),
        geometry_keys=geometry_keys,
        openings=openings,
    )


def _resolve_entity(model: Any, express_id: int) -> Any | None:
    """The entity for ``express_id``, or None when the model has none."""
    try:
        return model.by_id(express_id)
    except RuntimeError:
        return None


def _iter_openings(host: Any) -> list[Any]:
    """The openings that void ``host``, via its ``IfcRelVoidsElement`` links."""
    openings: list[Any] = []
    for relationship in getattr(host, "HasOpenings", None) or []:
        opening = getattr(relationship, "RelatedOpeningElement", None)
        if opening is not None:
            openings.append(opening)
    return openings


def _opening_surface(
    context: ExecutionContext,
    *,
    slug: str,
    host_ref: str,
    opening_ref: str,
    opening_entity: Any,
) -> OpeningSurface:
    guid = str(getattr(opening_entity, "GlobalId", "") or "")
    try:
        mesh = resolve_mesh(context, opening_ref)
    except ValueError:
        return _failed(opening_ref, guid, host_ref, "no cached geometry")
    if len(mesh.faces) == 0:
        return _failed(opening_ref, guid, host_ref, "empty opening mesh")

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = _face_normals(vertices, faces)
    caps = _cap_groups(vertices, faces, normals)
    if not caps:
        return _failed(opening_ref, guid, host_ref, "no planar surfaces")

    cap_normal = normals[caps[0][0]]
    cap_indices = [index for group in caps for index in group]
    cap_points = vertices[np.unique(faces[cap_indices])]
    axis_u, axis_v = _in_plane_axes(cap_normal)

    geometry_key = cache_mesh(
        context,
        trimesh.Trimesh(vertices=vertices, faces=faces[cap_indices], process=False),
        object_id=f"opening_surface_{slug}_{opening_entity.id()}",
    )
    return OpeningSurface(
        express_id=opening_ref,
        guid=guid,
        host_express_id=host_ref,
        geometry_key=geometry_key,
        area=max(_group_area(vertices, faces, group) for group in caps),
        width=float(np.ptp(cap_points @ axis_u)),
        height=float(np.ptp(cap_points @ axis_v)),
        depth=_cap_depth(vertices, faces, cap_normal, caps),
    )


def _failed(opening_ref: str, guid: str, host_ref: str, reason: str) -> OpeningSurface:
    return OpeningSurface(
        express_id=opening_ref,
        guid=guid,
        host_express_id=host_ref,
        error=reason,
    )


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _group_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(0.5 * np.linalg.norm(cross, axis=1).sum())


def _planar_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """Group face indices into planar surfaces.

    A face joins the group of its seed face when its normal deviates by less
    than ~1° and its first vertex lies on the seed's plane. Every face joins
    exactly one group; degenerate faces end up in singleton groups.
    """
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


def _cap_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """The cap-face groups of an opening mesh.

    The caps are the void faces in the plane of the host surface: the two
    largest planar groups whose normals oppose each other. The remaining groups
    (the reveal band cut into the host) are dropped. A void exposing only one
    dominant flat face yields a single group.
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


def _in_plane_axes(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right-handed in-plane axes ``(u, v)`` of a cap plane.

    ``v`` stays as close to the world Z axis as the plane allows, so ``height``
    is the vertical extent for wall openings; near-horizontal planes
    (skylights) use the world Y axis instead. The chosen reference is never
    parallel to ``normal``, so the projection is always non-degenerate.
    """
    world_z = np.array([0.0, 0.0, 1.0])
    if abs(float(normal[2])) < _HORIZONTAL_COS:
        reference = world_z
    else:
        reference = np.array([0.0, 1.0, 0.0])
    vertical = reference - float(reference @ normal) * normal
    axis_v = vertical / float(np.linalg.norm(vertical))
    axis_u = np.cross(axis_v, normal)
    return axis_u, axis_v


def _cap_depth(
    vertices: np.ndarray,
    faces: np.ndarray,
    normal: np.ndarray,
    caps: list[list[int]],
) -> float | None:
    """Distance between the two cap planes along ``normal``; None for one cap."""
    if len(caps) < 2:
        return None
    offsets = [
        float(np.mean(vertices[np.unique(faces[group])] @ normal))
        for group in (caps[0], caps[1])
    ]
    return abs(offsets[1] - offsets[0])
