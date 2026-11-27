"""Cut-surface tube selection and jogged-ring closure for the opening_surface node."""

from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from rcc4all_runner.nodes.base import ExecutionContext
from rcc4all_runner.nodes.opening_surface._bore_closure import (
    _add_cap_fan,  # pyright: ignore[reportPrivateUsage]
    _close_bore,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._mesh_topology import (
    _boundary_loops,  # pyright: ignore[reportPrivateUsage]
    _edge_key,  # pyright: ignore[reportPrivateUsage]
    _prune_flaps,  # pyright: ignore[reportPrivateUsage]
    _weld_rim,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._planes import (
    _PLANE_COS,  # pyright: ignore[reportPrivateUsage]
    _PLANE_TOLERANCE,  # pyright: ignore[reportPrivateUsage]
    _footprint_contained,  # pyright: ignore[reportPrivateUsage]
    _planar_groups,  # pyright: ignore[reportPrivateUsage]
    _planar_surface,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._ring_caps import (
    _loop_cap_groups,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_fix_normals,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
)

# A ring edge is a mid-wall jog (a step through a layer interface) when it is
# essentially parallel to the cap normal. Such edges never lie flat in a single
# plane, so they are capping with the dedicated jogged-ring closure; a folded-
# roof skylight's rim edges are not parallel to the caps and fall through to the
# plane decomposition.
_AXIAL_EDGE_COS = 0.99


__all__ = [
    "_close_tube_rings",
    "_cut_surface_tube",
    "_select_cut_faces",
]


def _select_cut_faces(
    host_mesh: trimesh.Trimesh, cutter: trimesh.Trimesh
) -> trimesh.Trimesh | None:
    """The open cut-surface tube: the host faces that bound the bore.

    This is the selection half of the cut-surface tube closure, kept locally so
    the volume path can cap the bore's own rings instead of the centroid fans
    the generic closure adds. A host face is a cut face when a cutter
    face is coplanar with it (normal and plane position within tolerance) and the
    host face's footprint lies inside a cutter surface's footprint on that plane.
    Returns the raw open tube (unclosed), or ``None`` when no face is selected.
    """
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    cutter_vertices = np.asarray(cutter.vertices, dtype=np.float64)
    cutter_faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(host_faces) == 0 or len(cutter_faces) == 0:
        return None

    host_normals = _face_normals(host_vertices, host_faces)
    cutter_normals = _face_normals(cutter_vertices, cutter_faces)

    cutter_surfaces: list[
        tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any]
    ] = []
    for group in _planar_groups(cutter_vertices, cutter_faces, cutter_normals):
        surface = _planar_surface(cutter_vertices, cutter_faces, cutter_normals, group)
        if surface is not None:
            cutter_surfaces.append(surface)

    host_first_points = host_vertices[host_faces[:, 0]]
    selected = np.zeros(len(host_faces), dtype=bool)
    for cutter_normal, cutter_offset, cutter_axes, cutter_footprint in cutter_surfaces:
        coplanar = (np.abs(host_normals @ cutter_normal) >= _PLANE_COS) & (
            np.abs(host_first_points @ cutter_normal - cutter_offset)
            <= _PLANE_TOLERANCE
        )
        if not coplanar.any():
            continue
        for index in np.flatnonzero(coplanar):
            if _footprint_contained(
                host_vertices, host_faces[index], cutter_axes, cutter_footprint
            ):
                selected[index] = True
    if not selected.any():
        return None
    return trimesh.Trimesh(
        vertices=host_vertices, faces=host_faces[selected], process=False
    )


def _cut_surface_tube(
    context: ExecutionContext,
    host_ref: str,
    host_mesh: trimesh.Trimesh,
    cutter: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    """The cut-surface tube of an opening: the host faces that bound the bore.

    A host face is a cut face when a cutter face is coplanar with it (normal and
    plane position within tolerance) AND the host face's footprint lies inside a
    cutter surface's footprint that lies on that plane. The cutter faces are
    merged into planar surfaces first (``_planar_groups``) so the containment
    test is run against each whole surface rather than against a single
    triangle. Faces that share the cutter's plane but sit elsewhere (e.g. the
    wall's own large front face, coplanar with a cutter end cap) are excluded
    because their footprint is not contained in the cutter's. Keeping the
    coplanarity check at the individual-face level ensures the fine facets of a
    curved reveal band are matched to their cutter face, while the containment
    test prunes coplanar faces that lie outside the opening. The selected faces
    form the tube; the tube is closed when the faces can be made watertight,
    otherwise it is returned open.
    """
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    cutter_vertices = np.asarray(cutter.vertices, dtype=np.float64)
    cutter_faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(host_faces) == 0 or len(cutter_faces) == 0:
        return None

    host_normals = _face_normals(host_vertices, host_faces)
    cutter_normals = _face_normals(cutter_vertices, cutter_faces)

    # Cutter planar surfaces pre-computed once: their shared plane (mean normal,
    # offset along it, in-plane axes) and the 2D footprint polygon in that plane.
    cutter_surfaces: list[
        tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any]
    ] = []
    for group in _planar_groups(cutter_vertices, cutter_faces, cutter_normals):
        surface = _planar_surface(cutter_vertices, cutter_faces, cutter_normals, group)
        if surface is not None:
            cutter_surfaces.append(surface)

    host_first_points = host_vertices[host_faces[:, 0]]
    selected = np.zeros(len(host_faces), dtype=bool)
    for cutter_normal, cutter_offset, cutter_axes, cutter_footprint in cutter_surfaces:
        coplanar = (np.abs(host_normals @ cutter_normal) >= _PLANE_COS) & (
            np.abs(host_first_points @ cutter_normal - cutter_offset)
            <= _PLANE_TOLERANCE
        )
        if not coplanar.any():
            continue
        coplanar_indices = np.flatnonzero(coplanar)
        for index in coplanar_indices:
            if _footprint_contained(
                host_vertices, host_faces[index], cutter_axes, cutter_footprint
            ):
                selected[index] = True
    if not selected.any():
        return None

    tube = trimesh.Trimesh(
        vertices=host_vertices, faces=host_faces[selected], process=False
    )
    closed = _close_bore(context, host_ref, tube)
    if closed is not None:
        return closed
    return tube


def _close_tube_rings(
    context: ExecutionContext,
    host_ref: str,
    host_mesh: trimesh.Trimesh,
    cutter: trimesh.Trimesh,
    cap_info: tuple[Any, ...] | None,
) -> trimesh.Trimesh | None:
    """Re-close the bore's rim rings from their own planes, or return None.

    A decomposed multi-layer host (e.g. Zementputz / Stahlbeton / EPS) exposes a
    layer-interface plate between the caps, so the bore's rim is jogged: its
    edges span several planes (the caps, the layer interface, and the
    perpendicular reveal step). The generic centroid-fan closure caps such a rim
    wrongly. This rebuilds the open tube from the host faces
    (``_select_cut_faces``) and caps each rim ring from the planes its own
    edges lie in: every run of consecutive in-plane edges becomes a flat cap in
    its plane closed by a new chord, and the perpendicular step bands become
    faces in the plane of the axial edges, with new edges created at the vertices
    where edges of different planes coincide. A ring with no axial step is a
    plain rim (a planar cross-section, or a folded-roof skylight rim spanning two
    host planes); it is capped by the ``_loop_cap_groups`` plane decomposition.

    Returns ``None`` when re-capping is not watertight, so the caller keeps the
    original (fan-)closed tube.
    """
    if cap_info is None:
        return None
    open_tube = _select_cut_faces(host_mesh, cutter)
    if open_tube is None or len(open_tube.faces) == 0:
        return None
    welded = _weld_rim(open_tube)
    if welded is None:
        return None
    welded = _prune_flaps(welded)
    if welded is None:
        return None
    loops = _boundary_loops(welded)
    if not loops:
        return None
    cap_normal = np.asarray(cap_info[3], dtype=np.float64)
    length = float(np.linalg.norm(cap_normal))
    if length <= 0.0:
        return None
    ncap = cap_normal / length

    vertices = np.asarray(welded.vertices, dtype=np.float64)
    faces = np.asarray(welded.faces, dtype=np.int64)
    return _build_ring_closed(
        vertices, faces, loops, ncap, context=context, host_ref=host_ref
    )


def _build_ring_closed(
    vertices: np.ndarray,
    faces: np.ndarray,
    loops: list[list[int]],
    ncap: np.ndarray,
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> trimesh.Trimesh | None:
    """Build the closed mesh by capping every loop from its plane groups; None when not watertight."""
    edge_traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_traversal.setdefault(_edge_key((u, v)), (u, v))
    cap_vertices = [vertices[i] for i in range(len(vertices))]
    cap_faces = [list(f) for f in faces]
    for ring in loops:
        groups = _ring_cap_groups(vertices, faces, ring, ncap, context, host_ref)
        if not groups:
            return None
        for group in groups:
            group_ids = np.asarray(group, dtype=int)
            if len(group_ids) < 3:
                return None
            apex_index = len(cap_vertices)
            cap_vertices.append(vertices[group_ids].mean(axis=0))
            _add_cap_fan(cap_faces, edge_traversal, group_ids, apex_index)
    closed = trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )
    if not _safe_fix_normals(closed):
        return None
    if closed.is_winding_consistent and _safe_volume(closed) < 0:
        closed.faces = closed.faces[:, ::-1]
    return closed if _is_watertight(closed) else None


def _ring_cap_groups(
    vertices: np.ndarray,
    faces: np.ndarray,
    ring: list[int],
    ncap: np.ndarray,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> list[np.ndarray]:
    """The planar cap polygons of one rim ring.

    A ring with an axial-step edge (a mid-wall jog) is decomposed into one flat
    cap plane group per run of consecutive in-plane edges plus one band group for
    the axial steps. A ring with no axial step is a plain rim and is decomposed
    by ``_loop_cap_groups`` (a planar ring yields a single group, a folded-roof
    skylight rim one group per host surface plane).
    """
    if not _ring_has_axial_edge(vertices, ring, ncap):
        groups = _loop_cap_groups(
            vertices, faces, np.asarray(ring, int), context=context, host_ref=host_ref
        )
        return groups if groups else []
    return _jogged_ring_groups(vertices, ring, ncap)


def _ring_has_axial_edge(
    vertices: np.ndarray, ring: list[int], ncap: np.ndarray
) -> bool:
    """Whether any edge of the ring runs parallel to the cap normal."""
    n = len(ring)
    for k in range(n):
        d = vertices[ring[(k + 1) % n]] - vertices[ring[k]]
        length = float(np.linalg.norm(d))
        if length > 0.0 and abs(float(d @ ncap)) / length > _AXIAL_EDGE_COS:
            return True
    return False


def _jogged_ring_groups(
    vertices: np.ndarray, ring: list[int], ncap: np.ndarray
) -> list[np.ndarray]:
    """The planar cap polygons of a jogged ring.

    The ring is rotated onto an axial edge, then split into maximal runs of
    consecutive non-axial (in-plane) edges and maximal axial chains. Every in-
    plane run of two or more edges becomes one flat cap polygon (its run closed by
    a new chord in that plane); the axial chains collapse into the band polygon:
    walking the ring keeps the chain vertices and replaces each in-plane run by a
    jump to its far endpoint, so the band is one planar polygon closed by the new
    chords at the vertices where the planes of adjacent edges coincide.
    """
    n = len(ring)
    axial = [
        (
            float(np.linalg.norm(vertices[ring[(k + 1) % n]] - vertices[ring[k]])) > 0.0
            and abs(float((vertices[ring[(k + 1) % n]] - vertices[ring[k]]) @ ncap))
            / float(np.linalg.norm(vertices[ring[(k + 1) % n]] - vertices[ring[k]]))
            > _AXIAL_EDGE_COS
        )
        for k in range(n)
    ]
    start = axial.index(True)
    ring = ring[start:] + ring[:start]
    axial = axial[start:] + axial[:start]

    groups: list[tuple[str, int, int]] = []
    k = 0
    while k < n:
        j = k
        while j < n and axial[j]:
            j += 1
        if j > k:
            groups.append(("chain", k, j - k))
            k = j
        while j < n and not axial[j]:
            j += 1
        if j > k:
            groups.append(("run", k, j - k))
            k = j

    polys: list[np.ndarray] = []
    for kind, st, ln in groups:
        if kind == "run" and ln >= 2:
            polys.append(np.asarray([ring[(st + i) % n] for i in range(ln + 1)], int))

    band: list[int] = []
    for kind, st, ln in groups:
        if kind == "chain":
            band.extend(ring[(st + i) % n] for i in range(ln + 1))
        else:
            band.append(ring[(st + ln) % n])
    deduplicated: list[int] = [band[0]]
    for v in band[1:]:
        if v != deduplicated[-1]:
            deduplicated.append(v)
    if len(deduplicated) > 2 and deduplicated[-1] == deduplicated[0]:
        deduplicated.pop()
    if len(deduplicated) >= 3:
        polys.append(np.asarray(deduplicated, int))
    return polys
