from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import (
    cache_mesh,
    ensure_watertight,
    resolve_mesh,
)
from openbim_runner.util.references import (
    expr_key,
    iter_resolved_elements,
    split_expr_key,
)

# Faces join a planar surface when their normal deviates by less than ~1° from
# the group's seed face and their first vertex lies on its plane (mirroring the
# reference implementation).
_ALIGNED_COS = math.cos(math.pi / 180.0)
_PLANE_TOLERANCE = 0.01
# Two surface groups count as opposing cap faces while their normals enclose at
# least 170°.
_OPPOSING_COS = -math.cos(math.radians(10.0))
# A cap face counts as parallel to the host surface while its normal crosses the
# host surface normal by less than ~10°.
_PARALLEL_COS = math.cos(math.radians(10.0))
# Host opposing face pairs closer than this are coincident duplicates (e.g.
# inner faces of aggregated geometry) rather than the two faces of a real
# surface slab, and are not treated as a pierce direction.
_MIN_SLAB_THICKNESS = 0.01
# In-plane overhang applied to the clip slab before intersecting the opening
# solid, so numeric tolerance cannot cut the hole profile short.
_CLIP_EPSILON = 0.02
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

    # Openings are cutting solids that often extend far beyond the element they
    # void, so the true opening surface (the hole in the host) must lie in the
    # plane of the host surface. The opening is always clipped to the host's
    # surface slab and its host-parallel caps are used: when the cutter's largest
    # opposing faces are perpendicular to the host (an oversized cutter extending
    # along the wall) the dominant surface pair yields the true hole, and when the
    # opening sits in a secondary pitch of a multi-slope roof the neighbouring
    # surface pair of that pitch is used instead. The largest-opposing heuristic
    # is kept only as a fallback for recesses/single-cap voids, where clipping
    # cuts no through-opening.
    caps = _cap_groups(vertices, faces, normals)
    if caps:
        clipped = _clip_parallel_caps(
            context, host_ref, mesh, vertices, faces, normals, caps
        )
        if clipped is not None:
            vertices, faces, normals, caps = clipped

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


def _host_surface_planes(
    context: ExecutionContext, host_ref: str
) -> list[tuple[np.ndarray, float, float, float]]:
    """The host's significant opposing surface-plane pairs, dominant first.

    Every entry is ``(normal, t_min, t_max, area)``: ``normal`` is the shared
    pierce direction of two opposing planar host face groups and ``t_min``/``t_max``
    bound the host slab along it. The largest pair comes first; the remaining
    significant pairs (e.g. the secondary pitch of a multi-slope roof) follow, so
    an opening that sits outside the dominant slab can be clipped to its own
    surface. Returns an empty list when the host cannot be analysed (no cached
    mesh, no planar surfaces, no opposing pair).
    """
    parsed = split_expr_key(host_ref)
    if parsed is None:
        return []
    host_slug, host_id = parsed
    host_mesh = context.geometry_cache.get(expr_key(host_slug, host_id))
    if host_mesh is None:
        return []
    try:
        vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
        faces = np.asarray(host_mesh.faces, dtype=np.int64)
    except Exception:
        return []
    if len(faces) == 0:
        return []

    normals = _face_normals(vertices, faces)
    sized = [
        (group, _group_area(vertices, faces, group), normals[group[0]])
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [(group, area, normal) for group, area, normal in sized if area > 0.0]
    sized.sort(key=lambda item: item[1], reverse=True)
    if not sized:
        return []

    # Opposing-plane pairs, deduplicated by their (sign-aware) pierce normal so
    # mirrored pitches are kept as separate candidates.
    pairs: list[tuple[np.ndarray, float, float, float]] = []
    seen: set[tuple[float, ...]] = set()
    for group, area, normal in sized:
        key = tuple(np.round(normal, 2))
        if key in seen:
            continue
        for other, other_area, other_normal in sized:
            if float(other_normal @ normal) > _OPPOSING_COS:
                continue
            first_off = float(np.mean(vertices[np.unique(faces[group])] @ normal))
            second_off = float(np.mean(vertices[np.unique(faces[other])] @ normal))
            thickness = abs(second_off - first_off)
            if thickness < _MIN_SLAB_THICKNESS:
                continue
            pairs.append(
                (
                    normal,
                    min(first_off, second_off),
                    max(first_off, second_off),
                    area + other_area,
                )
            )
            seen.add(key)
            break

    pairs.sort(key=lambda item: item[3], reverse=True)
    return pairs


def _clip_to_slab(
    mesh: trimesh.Trimesh,
    host_normal: np.ndarray,
    t_min: float,
    t_max: float,
) -> trimesh.Trimesh | None:
    """The part of the opening solid that lies inside the host slab.

    Clips ``mesh`` between the two host surface planes by boolean intersection
    with a slab spanning the opening's in-plane footprint across ``[t_min, t_max]``
    along ``host_normal``. This cuts away the parts of the oversized opening that
    extend outside the element. Returns ``None`` when the intersection cannot be
    computed.
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    axis_u, axis_v = _in_plane_axes(host_normal)
    u = float(np.ptp(vertices @ axis_u))
    v = float(np.ptp(vertices @ axis_v))
    dt = t_max - t_min
    if dt <= 0.0:
        return None
    origin = (
        float(np.mean(vertices @ axis_u)) * axis_u
        + float(np.mean(vertices @ axis_v)) * axis_v
        + (t_min + t_max) * 0.5 * host_normal
    )
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([axis_u, axis_v, host_normal])
    transform[:3, 3] = origin
    slab = trimesh.creation.box(
        extents=[u + 2.0 * _CLIP_EPSILON, v + 2.0 * _CLIP_EPSILON, dt],
        transform=transform,
    )

    solid, _error = ensure_watertight(mesh)
    if solid is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clipped = trimesh.boolean.intersection(
                [solid, slab], engine="manifold", check_volume=False
            )
    except Exception:
        return None
    if clipped is None or len(clipped.faces) == 0:
        return None
    return clipped


def _parallel_caps(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    host_normal: np.ndarray,
) -> list[list[int]]:
    """The cap-face groups parallel to the host surface.

    Only planar groups whose normal crosses ``host_normal`` by less than ~10°
    are candidates (the hole faces in the plane of the host surface). Among those
    the largest group and its largest opposing group are chosen, so the opening
    surface is always parallel to the wall it voids.
    """
    sized = [
        (
            group,
            _group_area(vertices, faces, group),
            float(normals[group[0]] @ host_normal),
        )
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [
        (group, area)
        for group, area, parallel in sized
        if area > 0.0 and abs(parallel) >= _PARALLEL_COS
    ]
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


def _clip_parallel_caps(
    context: ExecutionContext,
    host_ref: str,
    mesh: trimesh.Trimesh,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    caps: list[list[int]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[list[int]]] | None:
    """The host-parallel caps of ``mesh`` after clipping it to the host slab.

    Clips the opening solid to the host's dominant surface pair and returns its
    host-parallel cap faces (the hole in the host). When that slab does not cut a
    proper through-void (e.g. an opening in a secondary pitch of a multi-slope
    roof, where the dominant pair belongs to a different pitch), the remaining
    significant host surface pairs are tried in order of alignment with the
    opening's dominant face; the first to cut a two-cap, host-parallel through-void
    wins. Returns the clipped ``(vertices, faces, normals)`` and the new caps, or
    ``None`` when nothing cuts a through-void (the caller keeps the largest
    opposing heuristic, e.g. for recesses or single-cap voids).
    """
    cap_normal = normals[caps[0][0]]

    def clip_pair(
        normal: np.ndarray, t_min: float, t_max: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[list[int]]] | None:
        clipped = _clip_to_slab(mesh, normal, t_min, t_max)
        if clipped is None or len(clipped.faces) == 0:
            return None
        clipped_vertices = np.asarray(clipped.vertices, dtype=np.float64)
        clipped_faces = np.asarray(clipped.faces, dtype=np.int64)
        clipped_normals = _face_normals(clipped_vertices, clipped_faces)
        parallel_caps = _parallel_caps(
            clipped_vertices, clipped_faces, clipped_normals, normal
        )
        if len(parallel_caps) < 2:
            return None
        return (
            clipped_vertices,
            clipped_faces,
            clipped_normals,
            parallel_caps,
        )

    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return None
    result = clip_pair(planes[0][0], planes[0][1], planes[0][2])
    if result is None:
        for normal, t_min, t_max, _area in sorted(
            planes[1:], key=lambda pair: -abs(float(pair[0] @ cap_normal))
        ):
            result = clip_pair(normal, t_min, t_max)
            if result is not None:
                break
    return result


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
