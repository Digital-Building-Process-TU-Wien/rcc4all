"""Mesh topology helpers for the opening_surface node."""

from __future__ import annotations

import numpy as np
import trimesh

# Vertices closer than this are one corner: a curved-wall bore can have several
# tessellation vertices at one 3D corner, and snapping them makes the rim its
# geometric outline so a cap can close it without zero-length edges.
_COINCIDENT_VERTS_EPS = 1e-3


__all__ = [
    "_boundary_loops",
    "_edge_key",
    "_edge_use_counts",
    "_prune_flaps",
    "_weld_positions",
    "_weld_rim",
]


def _edge_key(edge: tuple[int, int]) -> tuple[int, int]:
    """The unordered ``(min, max)`` key of an edge so it matches regardless of order."""
    u, v = edge
    return (u, v) if u < v else (v, u)


def _edge_use_counts(edges: list[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """How often each (undirected) edge in ``edges`` appears."""
    use: dict[tuple[int, int], int] = {}
    for edge in edges:
        use[edge] = use.get(edge, 0) + 1
    return use


def _boundary_loops(mesh: trimesh.Trimesh) -> list[list[int]]:
    """Cyclic, corner-distinct vertex loops of the mesh's boundary.

    Boundary edges (used exactly once) are walked into ordered cycles. The walk
    follows real boundary edges (never a diagonal jump between two corners), so
    the cap fan for each loop always coincides with the tube's boundary.
    """
    edge_use: dict[tuple[int, int], int] = {}
    faces = np.asarray(mesh.faces, int)
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_use[key] = edge_use.get(key, 0) + 1
    adjacency: dict[int, list[int]] = {}
    for (u, v), use in edge_use.items():
        if use == 1:
            adjacency.setdefault(u, []).append(v)
            adjacency.setdefault(v, []).append(u)
    visited: set[int] = set()
    loops: list[list[int]] = []
    for start in sorted(adjacency):
        if start in visited:
            continue
        loop = [start]
        visited.add(start)
        cur = start
        prev = -1
        while True:
            candidates = [
                n for n in adjacency.get(cur, ()) if n != prev and n not in visited
            ]
            if not candidates:
                break
            nxt = candidates[0]
            loop.append(nxt)
            visited.add(nxt)
            prev, cur = cur, nxt
            if nxt == start:
                break
        loops.append(loop)
    return loops


def _weld_rim(tube: trimesh.Trimesh | None) -> trimesh.Trimesh | None:
    """Weld the tube's coincident corner vertices into distinct corners.

    Several tessellation vertices can share one 3D corner (e.g. where a reveal
    meets a curved facade); those within a small tolerance are collapsed so the
    rim becomes its geometric outline.
    """
    if tube is None or len(tube.faces) == 0:
        return None
    vertices = np.asarray(tube.vertices, float)
    faces = np.asarray(tube.faces, int)
    referenced = np.unique(faces)
    representative, remap, welded_vertices = _weld_positions(vertices, referenced)
    welded_faces: list[list[int]] = []
    for face in faces:
        mapped = [remap[representative[int(v)]] for v in face]
        if len(set(mapped)) < 3:
            continue
        welded_faces.append(mapped)
    return trimesh.Trimesh(
        vertices=welded_vertices,
        faces=np.asarray(welded_faces, int),
        process=False,
    )


def _weld_positions(
    vertices: np.ndarray, referenced: np.ndarray
) -> tuple[dict[int, int], dict[int, int], np.ndarray]:
    """Collapse near-coincident referenced vertices; return (rep map, remap, verts).

    Vertices within ``_COINCIDENT_VERTS_EPS`` are grouped by a spatial grid (with
    a 27-cell neighbourhood scan so tolerance-cell boundaries never split a
    corner).
    """
    tol = _COINCIDENT_VERTS_EPS
    cell = tol
    grid: dict[tuple[int, int, int], int] = {}
    representative: dict[int, int] = {}
    for v in referenced:
        iv = int(v)
        x, y, z = vertices[iv]
        key = (
            int(np.floor(x / cell)),
            int(np.floor(y / cell)),
            int(np.floor(z / cell)),
        )
        rep = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    found = grid.get((key[0] + dx, key[1] + dy, key[2] + dz))
                    if (
                        found is not None
                        and np.linalg.norm(vertices[found] - vertices[iv]) < tol
                    ):
                        rep = found
                        break
                if rep is not None:
                    break
            if rep is not None:
                break
        if rep is None:
            rep = iv
            grid[key] = rep
        representative[iv] = rep
    order = np.sort(np.unique([representative[v] for v in referenced]))
    remap = {rep: new for new, rep in enumerate(order)}
    welded = vertices[order]
    return representative, remap, welded


def _prune_flaps(welded: trimesh.Trimesh) -> trimesh.Trimesh | None:
    """Drop non-manifold tessellation flaps from a welded tube, or return None.

    A sliver triangle can share an edge with two larger faces, so that edge is
    used three times and the tube is non-manifold -- no capping can ever close
    it (a boundary walk sees a fake loop through the flap). The smallest face
    on each over-used edge is dropped until every edge is used at most twice,
    which removes the flap and exposes the true rim. A manifold tube is
    returned unchanged. Returns ``None`` when no face remains.
    """
    faces = np.asarray(welded.faces, int)
    face_edges = [
        (
            _edge_key((int(face[0]), int(face[1]))),
            _edge_key((int(face[1]), int(face[2]))),
            _edge_key((int(face[2]), int(face[0]))),
        )
        for face in faces
    ]
    use = _edge_use_counts([edge for edges in face_edges for edge in edges])
    if all(count <= 2 for count in use.values()):
        return welded
    vertices = np.asarray(welded.vertices, float)
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    keep = [True] * len(faces)
    while True:
        use = _edge_use_counts(
            [edge for i, edges in enumerate(face_edges) if keep[i] for edge in edges]
        )
        over = {key for key, count in use.items() if count > 2}
        if not over:
            break
        drop = min(
            (
                i
                for i in range(len(faces))
                if keep[i] and any(edge in over for edge in face_edges[i])
            ),
            key=lambda i: float(areas[i]),
        )
        keep[drop] = False
    if not any(keep):
        return None
    return trimesh.Trimesh(
        vertices=vertices,
        faces=faces[np.asarray(keep, bool)],
        process=False,
    )
