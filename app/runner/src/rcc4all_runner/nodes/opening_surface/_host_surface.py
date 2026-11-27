"""Host-surface analysis for the opening_surface node."""

from __future__ import annotations

import math
import weakref

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import trimesh

from rcc4all_runner.nodes.base import ExecutionContext
from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
    _group_area,  # pyright: ignore[reportPrivateUsage]
    _in_plane_axes,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._planes import (
    _planar_groups,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import reshape_flat
from rcc4all_runner.util.references import expr_key, split_expr_key

# Two face groups oppose each other when their normals cross within ~10°.
_OPPOSING_COS = -math.cos(math.radians(10.0))
_MIN_SLAB_THICKNESS = 0.01

# A face joins the region of an edge-adjacent face when its normal deviates by
# less than ~3° — the facet step of a tessellated curve.
_SURFACE_REGION_COS = math.cos(math.radians(3.0))
# A smooth surface region counts as curved when its normals span more than ~2°.
_CURVED_REGION_COS = math.cos(math.radians(2.0))
_CAP_VERTICAL_COS = math.cos(math.radians(45.0))
_OPENING_PERPENDICULAR_COS = math.cos(math.radians(60.0))
# Only a genuinely curved host (its curved regions dominate its surface) gets
# the hole-cap rewrite; a flat wall with a tiny rounded corner keeps the
# clip-to-slab path.
_CURVED_HOST_MIN_SHARE = 0.25

# A curved (faceted) host wall can sit the hole cap plane noticeably proud of
# the outer facet centroids, so the outer->inner facet span under-reads the wall
# and the generated void is left too shallow. When the cap plane is this far
# beyond the facet span, re-measure the depth from the cap plane out to the
# innermost host surface instead; a near-flush cap leaves the facet-span depth
# unchanged.
_CAP_PROUD_TOL = 0.08

_REVEAL_GEOMETRY_LIBRARY: ifcopenshell.geom.GEOMETRY_LIBRARY = "cgal"
_REVEAL_HOST_MEMO: weakref.WeakKeyDictionary[
    ExecutionContext, dict[str, trimesh.Trimesh | None]
] = weakref.WeakKeyDictionary()


__all__ = [
    "_curved_host_caps",
    "_host_mesh",
    "_host_surface_planes",
    "_reveal_host_mesh",
]


def _host_mesh(context: ExecutionContext, host_ref: str) -> trimesh.Trimesh | None:
    """The cached host mesh for ``host_ref``, or None when it is unavailable."""
    parsed = split_expr_key(host_ref)
    if parsed is None:
        return None
    host_slug, host_id = parsed
    return context.geometry_cache.get(expr_key(host_slug, host_id))


def _reveal_host_mesh(
    context: ExecutionContext, host_ref: str
) -> trimesh.Trimesh | None:
    """The host mesh re-tessellated so the bore reveal stays planar.

    The default geometry cache library fans a curved wall's opening bore to a
    centroid vertex, collapsing the vertical reveal faces into slivers that are
    no longer coplanar with the cutter. Re-tessellating just the host with the
    ``cgal`` library keeps them as clean planar strips. Falls back to the cached
    host mesh when the host cannot be re-tessellated (e.g. a decomposed parent
    with no own body). Re-tessellated meshes are memoized per context so a host
    with several openings is tessellated once.
    """
    memo: dict[str, trimesh.Trimesh | None] = _REVEAL_HOST_MEMO.setdefault(context, {})
    if host_ref in memo:
        return memo[host_ref]
    parsed = split_expr_key(host_ref)
    if parsed is not None:
        slug, express_id = parsed
        mesh: trimesh.Trimesh | None = None
        try:
            settings = ifcopenshell.geom.settings()
            settings.set("use-world-coords", True)
            settings.set("weld-vertices", True)
            settings.set("context_types", ["Body"])  # pyright: ignore[reportArgumentType]
            entity = context.resolve_model(slug).by_id(express_id)
            shape = ifcopenshell.geom.create_shape(
                settings, entity, geometry_library=_REVEAL_GEOMETRY_LIBRARY
            )
            geometry = shape.geometry  # pyright: ignore[reportAttributeAccessIssue]
            mesh = reshape_flat(geometry.verts, geometry.faces)  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            mesh = None
        memo[host_ref] = mesh if mesh is not None else _host_mesh(context, host_ref)
        return memo[host_ref]
    memo[host_ref] = _host_mesh(context, host_ref)
    return memo[host_ref]


def _host_surface_planes(
    context: ExecutionContext, host_ref: str
) -> list[tuple[np.ndarray, float, float, float]]:
    """The host's significant opposing surface-plane pairs, dominant first.

    Every entry is ``(normal, t_min, t_max, area)``: ``normal`` is the shared
    pierce direction of two opposing planar host face groups and ``t_min``/``t_max``
    bound the host slab along it. The largest pair comes first; the remaining
    significant pairs (e.g. the secondary pitch of a multi-slope roof) follow, so
    an opening that sits outside the dominant slab can be clipped to its own
    surface. Returns an empty list when the host cannot be analysed.
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


def _surface_regions(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """Group faces into smooth surface regions.

    A face joins the region of an edge-adjacent face when its normal deviates by
    less than ~3° — the facet step of a tessellated curve. The result groups a
    curved/faceted surface (e.g. a round wall) into one contiguous region, while
    sharper junction edges split distinct surfaces apart.
    """
    face_count = len(faces)
    if face_count == 0:
        return []
    edges: dict[tuple[int, int], list[int]] = {}
    for face_index in range(face_count):
        for offset in (0, 1, 2):
            a = int(faces[face_index, offset])
            b = int(faces[face_index, (offset + 1) % 3])
            key = (a, b) if a < b else (b, a)
            edges.setdefault(key, []).append(face_index)

    assigned = np.zeros(face_count, dtype=bool)
    regions: list[list[int]] = []
    for seed in range(face_count):
        if assigned[seed]:
            continue
        region = [seed]
        assigned[seed] = True
        stack = [seed]
        while stack:
            current = stack.pop()
            for offset in (0, 1, 2):
                a = int(faces[current, offset])
                b = int(faces[current, (offset + 1) % 3])
                key = (a, b) if a < b else (b, a)
                for neighbor in edges.get(key, ()):
                    if assigned[neighbor]:
                        continue
                    if (
                        float(normals[neighbor] @ normals[current])
                        < _SURFACE_REGION_COS
                    ):
                        continue
                    assigned[neighbor] = True
                    region.append(neighbor)
                    stack.append(neighbor)
        regions.append(region)
    return regions


def _region_is_curved(normals: np.ndarray, region: list[int]) -> bool:
    """Whether a smooth surface region is curved (normals span more than ~2°)."""
    region_normals = normals[region]
    mean_normal = region_normals.mean(axis=0)
    length = float(np.linalg.norm(mean_normal))
    if length <= 1e-10:
        return False
    mean_normal = mean_normal / length
    return bool((np.abs(region_normals @ mean_normal) < _CURVED_REGION_COS).any())


def _bbox_overlap(
    a_min: np.ndarray, a_max: np.ndarray, b_min: np.ndarray, b_max: np.ndarray
) -> bool:
    """Whether two axis-aligned boxes overlap."""
    return bool(np.all(a_min <= b_max) and np.all(a_max >= b_min))


def _curved_host_caps(
    context: ExecutionContext,
    host_ref: str,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
) -> tuple[list[list[int]], float | None] | None:
    """The hole caps of an oversized cutter on a curved host surface.

    A curved host (round wall) is faceted into thin strips, so it has no single
    dominant opposing plane pair to clip an oversized cutter to. The cutter's
    largest vertical faces are then its reveal wings — large faces lying along
    the wall — while the true hole caps are the vertical faces perpendicular to
    those wings (the through-window / through-door cross-section). The hole caps
    are selected from the cutter itself, and the depth is the host wall band
    along the hole normal.

    Returns ``(caps, depth)`` for a cutter that sits on a curved host surface
    region, or ``None`` for a flat host (which keeps the clip heuristic).
    """
    if len(faces) == 0:
        return None
    host_mesh = _host_mesh(context, host_ref)
    if host_mesh is None:
        return None
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    if len(host_faces) == 0:
        return None
    host_normals = _face_normals(host_vertices, host_faces)

    cutter_min = vertices.min(axis=0)
    cutter_max = vertices.max(axis=0)
    curved: list[list[int]] = []
    curved_area = 0.0
    total_faces = list(range(len(host_faces)))
    total_area = _group_area(host_vertices, host_faces, total_faces)
    for region in _surface_regions(host_vertices, host_faces, host_normals):
        if not _region_is_curved(host_normals, region):
            continue
        curved_area += _group_area(host_vertices, host_faces, region)
        region_vertices = host_vertices[np.unique(host_faces[region])]
        if _bbox_overlap(
            cutter_min,
            cutter_max,
            region_vertices.min(axis=0),
            region_vertices.max(axis=0),
        ):
            curved.append(region)
    if not curved or total_area <= 0.0:
        return None
    if curved_area / total_area < _CURVED_HOST_MIN_SHARE:
        return None

    vertical = [
        (group, _group_area(vertices, faces, group), normals[group[0]])
        for group in _planar_groups(vertices, faces, normals)
    ]
    vertical = [
        (group, area, normal)
        for group, area, normal in vertical
        if area > 0.0 and abs(float(normal[2])) < _CAP_VERTICAL_COS
    ]
    if len(vertical) < 2:
        return None
    vertical.sort(key=lambda item: item[1], reverse=True)

    # The largest vertical face is a reveal wing; the hole caps are the vertical
    # faces perpendicular to it. Wing faces themselves and the horizontal
    # top/bottom faces are dropped.
    wing_normal = vertical[0][2]
    hole_faces = [
        group
        for group, _area, normal in vertical
        if abs(float(normal @ wing_normal)) < _OPENING_PERPENDICULAR_COS
    ]
    if not hole_faces:
        return None

    depth = _host_band_depth(
        host_vertices,
        host_faces,
        host_normals,
        hole_faces[0],
        normals[hole_faces[0][0]],
        vertices,
        faces,
    )
    return (hole_faces, depth)


def _host_band_depth(
    host_vertices: np.ndarray,
    host_faces: np.ndarray,
    host_normals: np.ndarray,
    cap_group: list[int],
    cap_normal: np.ndarray,
    cutter_vertices: np.ndarray,
    cutter_faces: np.ndarray,
) -> float | None:
    """The host wall thickness along ``cap_normal`` under the hole cap face.

    The in-plane footprint of the hole cap selects the host wall facets that lie
    behind the opening. Their offsets along the cap normal span the inner and the
    outer wall surface; the full outer-to-inner span is the wall thickness the
    opening must reach (a faceted curved wall spans several offset bands, so a
    single-gap split would under-measure it). Returns ``None`` when the host
    contributes too few facets.
    """
    hole_points = cutter_vertices[np.unique(cutter_faces[cap_group])]
    center = hole_points.mean(axis=0)
    axis_u, axis_v = _in_plane_axes(cap_normal)
    pu = (hole_points - center) @ axis_u
    pv = (hole_points - center) @ axis_v
    u_min, u_max = float(pu.min()), float(pu.max())
    v_min, v_max = float(pv.min()), float(pv.max())

    centroids = host_vertices[host_faces].mean(axis=1)
    cu = (centroids - center) @ axis_u
    cv = (centroids - center) @ axis_v
    lateral = np.abs(host_normals[:, 2]) < _CAP_VERTICAL_COS
    in_region = lateral & (cu >= u_min) & (cu <= u_max) & (cv >= v_min) & (cv <= v_max)
    offsets = np.sort(centroids[in_region] @ cap_normal)
    if len(offsets) < 2:
        return None

    span = abs(float(offsets[-1]) - float(offsets[0]))

    # A cap plane sitting proud of the outer facet centroids stops short of the
    # far wall surface; re-measure from the cap plane out to the innermost host
    # surface, and keep the plain facet span when the cap is near-flush.
    cap_off = float(center @ cap_normal)
    cap_to_far = max(
        abs(cap_off - float(offsets[0])),
        abs(cap_off - float(offsets[-1])),
    )
    if cap_to_far - span > _CAP_PROUD_TOL:
        return cap_to_far
    return span
