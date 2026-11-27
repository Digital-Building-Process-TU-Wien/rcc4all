"""Bore closing for the opening_surface node."""

from __future__ import annotations

import numpy as np
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.opening_surface._mesh_topology import (
    _boundary_loops,  # pyright: ignore[reportPrivateUsage]
    _edge_key,  # pyright: ignore[reportPrivateUsage]
    _prune_flaps,  # pyright: ignore[reportPrivateUsage]
    _weld_rim,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.nodes.opening_surface._ring_caps import (
    _MIN_CAP_LOOP,  # pyright: ignore[reportPrivateUsage]
    _close_open_ring,  # pyright: ignore[reportPrivateUsage]
    _loop_cap_groups,  # pyright: ignore[reportPrivateUsage]
    _loop_is_planar,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_fix_normals,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
)

__all__ = [
    "_close_bore",
]


def _close_bore(
    context: ExecutionContext,
    host_ref: str,
    tube: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    """Close the cut-surface tube, or return None to keep the open tube.

    The tube's boundary consists of open rims. A through-bore (window) has two
    planar rims; an opening reaching a free face of the host (a floor-reaching
    door) has a non-planar rim, an open ring. The tube is first welded
    (coincident tessellation corners collapse to a single point), then each
    remaining boundary loop is capped. An open ring is deliberately NOT made
    watertight (``_close_open_ring``): only its cap faces are added — every run of
    ring vertices in one of the host's surface planes is closed with the new edge
    the open ring needs and filled with one flat cap face — while the rim the
    host's own surface model has no face for (e.g. the door sill) stays open. Any
    other rim (a window cross-section) is capped by the generic loop capping: one
    planar fan per plane it spans, with a single centroid fan as the watertight
    fallback.

    Returns ``None`` when the tube cannot be processed: a degenerate loop, or a
    through-bore rim that cannot be capped watertight. The caller then keeps the
    open tube.
    """
    if len(tube.faces) == 0:
        return None
    try:
        welded = _weld_rim(tube)
        if welded is None:
            return None
        welded = _prune_flaps(welded)
        if welded is None:
            return None
        loops = _boundary_loops(welded)
        if len(loops) == 0:
            return welded if _is_watertight(welded) else None
        if any(len(loop) < _MIN_CAP_LOOP for loop in loops):
            return None
        # A single non-planar boundary loop is an open ring: an opening that
        # reaches a free face of the host (e.g. a floor-reaching door), whose rim
        # (e.g. the door sill) the host's surface model leaves open. A bent
        # through-bore (e.g. a skylight whose rim spans two host planes) keeps
        # more than one boundary loop, so it falls through to the generic
        # per-plane capping below.
        if len(loops) == 1 and not _loop_is_planar(
            welded.vertices[np.asarray(loops[0], int)]
        ):
            return _close_open_ring(context, host_ref, welded, loops)
        if len(loops) not in (1, 2):
            return None
        return _cap_loops(welded, loops, context=context, host_ref=host_ref)
    except Exception:
        return None


def _cap_loops(
    mesh: trimesh.Trimesh,
    loops: list[list[int]],
    *,
    context: ExecutionContext | None = None,
    host_ref: str | None = None,
) -> trimesh.Trimesh | None:
    """Append a cap for each boundary ``loop``; return the closed mesh.

    Each loop is split into one planar cap group per plane it spans, then each
    group is capped from its own centroid so every cap face lies flat in that
    plane. A planar loop yields a single group and is capped with one fan (the
    classic through-bore closure). When a non-planar rim cannot be decomposed
    into a cleanly watertight set of flat caps (e.g. a heavily faceted curved-wall
    bore), the loop is re-capped with a single centroid fan so the result stays
    watertight. Each cap triangle is wound opposite to the tube face that uses its
    boundary edge so the combined surface keeps one consistent winding. The mesh
    is then re-oriented to a positive volume. Returns ``None`` when the result is
    not watertight.
    """
    vertices = np.asarray(mesh.vertices, float)
    faces = np.asarray(mesh.faces, int)
    edge_traversal = _edge_traversal(faces)
    closed = _build_closed(
        vertices,
        faces,
        edge_traversal,
        loops,
        context=context,
        host_ref=host_ref,
        decompose=True,
    )
    if closed is not None:
        return closed
    return _build_closed(
        vertices,
        faces,
        edge_traversal,
        loops,
        context=context,
        host_ref=host_ref,
        decompose=False,
    )


def _edge_traversal(faces: np.ndarray) -> dict[tuple[int, int], tuple[int, int]]:
    """Boundary edge -> the direction the adjacent tube face traverses it.

    A cap triangle sharing that edge must traverse it in the opposite direction.
    """
    traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            traversal.setdefault(_edge_key((u, v)), (u, v))
    return traversal


def _build_closed(
    vertices: np.ndarray,
    faces: np.ndarray,
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    loops: list[list[int]],
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
    decompose: bool,
) -> trimesh.Trimesh | None:
    """Build the closed mesh with one cap strategy; None when not watertight.

    With ``decompose`` a non-planar loop is capped per host-surface plane (flat
    caps); without it every loop is capped with one centroid fan (the classic
    closure, watertight even across a non-planar rim).
    """
    cap_vertices = list(vertices)
    cap_faces = [list(f) for f in faces]
    for loop in loops:
        loop_ids = np.asarray(loop, int)
        if len(loop_ids) < _MIN_CAP_LOOP:
            return None
        if decompose:
            cap_groups = _loop_cap_groups(
                vertices,
                faces,
                loop_ids,
                context=context,
                host_ref=host_ref,
            )
            if not cap_groups:
                return None
        else:
            cap_groups = [loop_ids]
        for group in cap_groups:
            apex = vertices[group].mean(axis=0)
            apex_index = len(cap_vertices)
            cap_vertices.append(apex)
            _add_cap_fan(cap_faces, edge_traversal, group, apex_index)
    closed_mesh = trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )
    # The tube is winding-consistent; the caps follow it. Re-orient to positive
    # volume (the interior-facing orientation is equally "watertight"). Only a
    # genuinely closed, consistently-wound mesh is re-oriented: reading volume on
    # a degenerate/self-intersecting one would reverse faces of a mesh that is
    # going to be rejected anyway.
    if (
        closed_mesh.is_watertight
        and closed_mesh.is_winding_consistent
        and _safe_volume(closed_mesh) < 0
    ):
        closed_mesh.faces = closed_mesh.faces[:, ::-1]
    if not _safe_fix_normals(closed_mesh):
        return None
    return closed_mesh if _is_watertight(closed_mesh) else None


def _add_cap_fan(
    cap_faces: list[list[int]],
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    group: np.ndarray,
    apex_index: int,
) -> None:
    """Append the centroid-fan triangles of one planar cap ``group``.

    Each triangle uses ``apex_index`` as its third vertex. The winding of the edge
    shared with a tube face opposes the tube's traversal; a virtual edge created
    by the cap itself (joining two planes, e.g. the door sill's front edge) has no
    tube traversal to oppose and defaults to the group's winding, which the final
    ``fix_normals`` re-orients consistently.
    """
    group_ids = np.asarray(group, int)
    for i in range(len(group_ids)):
        a = int(group_ids[i])
        b = int(group_ids[(i + 1) % len(group_ids)])
        u, v = edge_traversal.get(_edge_key((a, b)), (a, b))
        # tube traverses u->v; the cap must traverse v->u.
        first, second = (b, a) if (a, b) == (u, v) else (a, b)
        cap_faces.append([first, second, apex_index])
