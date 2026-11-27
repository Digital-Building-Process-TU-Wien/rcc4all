"""Per-plane cap decomposition and open-ring capping for the opening_surface node."""

from __future__ import annotations

import numpy as np
import trimesh

from rcc4all_runner.nodes.base import ExecutionContext
from rcc4all_runner.nodes.opening_surface._host_surface import (
    _host_surface_planes,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._mesh_topology import (
    _edge_key,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
    _in_plane_axes,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._planes import (
    _PLANE_COS,  # pyright: ignore[reportPrivateUsage]
)

# A cap polygon needs at least this many distinct corners.
_MIN_CAP_LOOP = 3

# Residual of a best-fit plane below which a loop counts as planar.
_CAP_PLANAR_TOLERANCE = 0.03
# Distance a ring vertex may sit from a host cap plane and still lie on it.
_CAP_PLANE_TOLERANCE = 0.03


__all__ = [
    "_close_open_ring",
    "_loop_cap_groups",
]


def _loop_is_planar(points: np.ndarray) -> bool:
    """Whether ``points`` lie within a small residual of their best-fit plane."""
    centered = points - points.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    if vt.shape[0] < 3:
        return True
    residue = float(np.abs(centered @ vt[-1]).max())
    return residue <= _CAP_PLANAR_TOLERANCE


def _polygon_area(u: np.ndarray, v: np.ndarray) -> float:
    """The unsigned area of the polygon with successive 2D points ``(u, v)``."""
    return float(
        0.5 * abs(float(np.dot(u, np.roll(v, -1)) - np.dot(v, np.roll(u, -1))))
    )


def _order_loop_group(
    vertices: np.ndarray, group: np.ndarray, normal: np.ndarray
) -> np.ndarray | None:
    """Order the cap corner vertices of ``group`` as a simple polygon.

    The group's corners (a run of a non-planar rim that lies in one plane) are
    sorted by angle around their centroid projected onto the plane, so the
    polygon does not self-intersect and the centroid fan stays inside it. Returns
    ``None`` for a degenerate group that collapses to a line.
    """
    group = np.asarray(group, int)
    points = vertices[group]
    center = points.mean(axis=0)
    axis_u, axis_v = _in_plane_axes(normal)
    pu = (points - center) @ axis_u
    pv = (points - center) @ axis_v
    order = np.argsort(np.arctan2(pv, pu))
    ordered = group[order]
    if _polygon_area(pu[order], pv[order]) <= 1e-12:
        return None
    return ordered


def _plane_is_reveal(
    faces: np.ndarray,
    face_normals: np.ndarray,
    face_first: np.ndarray,
    normal: np.ndarray,
    t: float,
) -> bool:
    """Whether the tube already closes the plane ``(normal, t)`` with a reveal.

    The tube's faces are the reveal band; a host surface plane that already has a
    coplanar tube face is a reveal (a jamb/header that happens to coincide with a
    host side face), not an open cap to fill. Returning True keeps that plane out
    of the caps so a cap never overlaps a reveal.
    """
    coplanar = (np.abs(face_normals @ normal) >= _PLANE_COS) & (
        np.abs(face_first @ normal - t) <= _CAP_PLANE_TOLERANCE
    )
    return bool(coplanar.any())


def _loop_cap_groups(
    vertices: np.ndarray,
    faces: np.ndarray,
    loop_ids: np.ndarray,
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> list[np.ndarray]:
    """The planar cap groups of one boundary loop, one per plane it spans.

    A planar rim (a through-bore cross-section) is a single group. A rim that
    spans several planes (a floor-reaching door, a non-planar skylight rim) is
    split into one group per host surface plane a run of its corner vertices lies
    on, so every cap is a flat face in a host surface plane. A host plane that
    the tube already closes (a reveal face, e.g. a jamb or header coplanar with
    the host's own side face) is not a cap and is skipped. Returns an empty list
    when the loop is non-planar but lies on no cap plane.
    """
    points = vertices[loop_ids]
    if _loop_is_planar(points):
        return [loop_ids]
    if context is None or host_ref is None:
        return []
    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return []
    face_normals = _face_normals(vertices, faces)
    face_first = vertices[faces[:, 0]]
    groups: list[np.ndarray] = []
    seen: set[frozenset[int]] = set()
    for normal, t_min, t_max, _area in planes:
        offsets = points @ normal
        for t in (t_min, t_max):
            onplane = np.abs(offsets - t) <= _CAP_PLANE_TOLERANCE
            group = loop_ids[onplane]
            if len(group) < _MIN_CAP_LOOP:
                continue
            key = frozenset(int(v) for v in group)
            if key in seen:
                continue
            seen.add(key)
            if _plane_is_reveal(faces, face_normals, face_first, normal, t):
                continue
            ordered = _order_loop_group(vertices, group, normal)
            if ordered is None:
                continue
            groups.append(ordered)
    return groups


def _close_open_ring(
    context: ExecutionContext,
    host_ref: str,
    welded: trimesh.Trimesh,
    loops: list[list[int]],
) -> trimesh.Trimesh | None:
    """Add the cap faces of an open ring, or return None when none is known.

    An open ring is the non-planar boundary loop of an opening that reaches a
    free face of the host (a floor-reaching door). Each non-planar loop's free
    edges are compared with the host's surface planes (the dominant opposing
    plane pair first), and every run of loop vertices that lies in one of those
    planes is the outline of the cap face in that plane; the closed outline is
    filled with one flat cap face. The ring is deliberately NOT made watertight:
    the rim the host's own surface model has no face for (e.g. the door sill)
    stays open. Returns ``None`` when no host surface plane carries a cap
    outline; the caller then keeps the open tube.
    """
    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return None
    vertices = np.asarray(welded.vertices, float)
    faces = np.asarray(welded.faces, int)
    face_normals = _face_normals(vertices, faces)
    face_first = vertices[faces[:, 0]]
    open_loops = [
        loop for loop in loops if not _loop_is_planar(vertices[np.asarray(loop, int)])
    ]
    if not open_loops:
        return None
    for normal, t_min, t_max, _area in planes:
        chains: list[np.ndarray] = []
        for loop in open_loops:
            chains.extend(
                _ring_cap_chains(
                    vertices,
                    faces,
                    face_normals,
                    face_first,
                    loop,
                    normal,
                    t_min,
                    t_max,
                )
            )
        if chains:
            return _add_ring_caps(vertices, faces, chains)
    return None


def _ring_cap_chains(
    vertices: np.ndarray,
    faces: np.ndarray,
    face_normals: np.ndarray,
    face_first: np.ndarray,
    loop: list[int],
    normal: np.ndarray,
    t_min: float,
    t_max: float,
) -> list[np.ndarray]:
    """The cap outlines of an open ring in one host surface plane pair.

    The ring's vertices that lie on one of the two host surface planes (within
    ``_CAP_PLANE_TOLERANCE``) form runs; each run of consecutive ring vertices,
    kept in ring order, is the outline of the cap face in that plane. A plane
    the tube already closes with its own faces (a reveal, e.g. a jamb coplanar
    with the host's side face) carries no cap and is skipped. Runs shorter than
    ``_MIN_CAP_LOOP`` are degenerate fragments and are dropped.
    """
    ring = np.asarray(loop, int)
    offsets = vertices[ring] @ normal
    chains: list[np.ndarray] = []
    for plane_offset in (t_min, t_max):
        if _plane_is_reveal(faces, face_normals, face_first, normal, plane_offset):
            continue
        on_plane = np.abs(offsets - plane_offset) <= _CAP_PLANE_TOLERANCE
        chains.extend(_plane_runs(ring, on_plane))
    return chains


def _plane_runs(ring: np.ndarray, on_plane: np.ndarray) -> list[np.ndarray]:
    """The maximal runs of consecutive ring vertices whose ``on_plane`` is True.

    The cyclic ring order is rotated to start on an off-plane vertex, so every
    run is a contiguous, non-wrapping run of vertex ids in ring order. A run is
    open (the ring leaves the plane at both of its ends), so the cap built from
    it creates the new edge between its two end vertices. Runs shorter than
    ``_MIN_CAP_LOOP`` are degenerate fragments and are dropped.
    """
    if not on_plane.any():
        return []
    n = len(ring)
    if on_plane.all():
        return [np.asarray(ring, int)]
    start = int(np.argmin(on_plane))  # the first off-plane vertex
    runs: list[np.ndarray] = []
    run: list[int] = []
    for step in range(n):
        index = (start + step) % n
        if on_plane[index]:
            run.append(int(ring[index]))
            continue
        if len(run) >= _MIN_CAP_LOOP:
            runs.append(np.asarray(run, int))
        run = []
    if len(run) >= _MIN_CAP_LOOP:  # defensive: start is off-plane
        runs.append(np.asarray(run, int))
    return runs


def _add_ring_caps(
    vertices: np.ndarray,
    faces: np.ndarray,
    chains: list[np.ndarray],
) -> trimesh.Trimesh:
    """Fill one flat cap per chain outline, leaving the remaining rim open.

    Each chain is capped from its own centroid (a flat face in its host surface
    plane): the fan is wound uniformly in the direction opposing the tube's
    traversal of the chain, and the closing edge between the chain's two end
    vertices is the new edge the open ring needs. The result is deliberately not
    made watertight: the rim between the caps (e.g. the door sill) stays open,
    because the host's own surface model has no face there.
    """
    cap_vertices: list[np.ndarray] = [vertices[i] for i in range(len(vertices))]
    cap_faces: list[list[int]] = [list(f) for f in faces]
    # Boundary edge -> the direction the adjacent tube face traverses it. A cap
    # triangle sharing that edge must traverse it in the opposite direction.
    edge_traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_traversal.setdefault(_edge_key((u, v)), (u, v))
    for chain in chains:
        apex_index = len(cap_vertices)
        cap_vertices.append(vertices[chain].mean(axis=0))
        _add_chain_fan(cap_faces, edge_traversal, chain, apex_index)
    return trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )


def _add_chain_fan(
    cap_faces: list[list[int]],
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    chain: np.ndarray,
    apex_index: int,
) -> None:
    """Append the centroid-fan triangles of one open chain cap.

    ``chain`` is an open run of ring vertices: each of its edges is a tube
    boundary edge shared with exactly one tube face, except the closing edge
    (chain[-1] -> chain[0]), which the cap itself creates. The fan is wound
    uniformly — in the direction opposing the tube's traversal of the chain's
    first edge — so every fan triangle opposes the tube on its shared edge AND
    the closing triangle's winding is consistent with its fan neighbours (there
    is no tube face on the closing edge to oppose; opposing a made-up direction
    would flip it against them).
    """
    chain_ids = np.asarray(chain, int)
    n = len(chain_ids)
    if n < 2:
        return
    a0, a1 = int(chain_ids[0]), int(chain_ids[1])
    u, v = edge_traversal.get(_edge_key((a0, a1)), (a0, a1))
    # The tube traverses u -> v; the fan runs the chain in the opposite
    # direction so every triangle opposes the tube across its shared edge.
    with_ring_order = (u, v) == (a1, a0)
    for i in range(n):
        first = int(chain_ids[i if with_ring_order else (i + 1) % n])
        second = int(chain_ids[(i + 1) % n if with_ring_order else i])
        cap_faces.append([first, second, apex_index])
