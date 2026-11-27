"""Opening cap-face analysis for the opening_surface node."""

from __future__ import annotations

import math

import numpy as np
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.opening_surface._host_surface import (
    _OPPOSING_COS,  # pyright: ignore[reportPrivateUsage]
    _curved_host_caps,  # pyright: ignore[reportPrivateUsage]
    _host_surface_planes,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
    _group_area,  # pyright: ignore[reportPrivateUsage]
    _in_plane_axes,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.nodes.opening_surface._planes import (
    _clip_to_slab,  # pyright: ignore[reportPrivateUsage]
    _planar_groups,  # pyright: ignore[reportPrivateUsage]
)

# Cap-face candidates run parallel to the host surface within ~10°.
_PARALLEL_COS = math.cos(math.radians(10.0))


__all__ = [
    "_cap_extents",
    "_cap_info",
]


def _cap_info(
    context: ExecutionContext, host_ref: str, cutter: trimesh.Trimesh
) -> tuple[np.ndarray, np.ndarray, list[list[int]], np.ndarray, float | None] | None:
    """The opening's cap faces ``(vertices, faces, caps, cap_normal, depth)``.

    The cutter is clipped to the host surface slab (or analysed via the
    curved-host path) and its host-parallel cap faces are returned, together
    with the shared cap normal and the host thickness.
    Returns ``None`` when the cutter exposes no planar cap surface.
    """
    vertices = np.asarray(cutter.vertices, dtype=np.float64)
    faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(faces) == 0:
        return None
    normals = _face_normals(vertices, faces)

    caps = _cap_groups(vertices, faces, normals)
    depth: float | None = None
    if caps:
        curved = _curved_host_caps(context, host_ref, vertices, faces, normals)
        if curved is not None:
            caps, depth = curved
        else:
            clipped = _clip_parallel_caps(
                context, host_ref, cutter, vertices, faces, normals, caps
            )
            if clipped is not None:
                vertices, faces, normals, caps = clipped

    if not caps:
        return None
    cap_normal = normals[caps[0][0]]
    if depth is None:
        depth = _cap_depth(vertices, faces, cap_normal, caps)
    return vertices, faces, caps, cap_normal, depth


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


def _cap_extents(
    vertices: np.ndarray,
    faces: np.ndarray,
    caps: list[list[int]],
    cap_normal: np.ndarray,
) -> tuple[float | None, float | None, float | None]:
    """``(area, width, height)`` of the cap faces in the host plane."""
    cap_indices = [index for group in caps for index in group]
    cap_points = vertices[np.unique(faces[cap_indices])]
    axis_u, axis_v = _in_plane_axes(cap_normal)
    area = max(_group_area(vertices, faces, group) for group in caps)
    width = float(np.ptp(cap_points @ axis_u))
    height = float(np.ptp(cap_points @ axis_v))
    return area, width, height


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
    host-parallel cap faces (the hole in the host). When that slab does not cut
    a proper through-void (e.g. an opening in a secondary pitch of a multi-slope
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
