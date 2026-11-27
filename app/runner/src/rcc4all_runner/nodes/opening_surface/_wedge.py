"""Degenerate-wedge handling and tube ring clipping for the opening_surface node."""

from __future__ import annotations

import numpy as np
import trimesh

from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_fix_normals,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
)

# A tube face roughly perpendicular to the cap normal is a reveal face; it bounds
# the hole laterally. Faces closer to parallel are the caps themselves and must
# not clip the offset far ring.
_REVEAL_PARALLEL_COS = 0.8

# Wall thickness below which lofting two cap faces collapses into a flat sliver;
# those thin openings keep their closed cut-surface tube instead.
_MIN_LOFT_DEPTH = 0.05


__all__ = [
    "_cut_ring_by_tube",
    "_extrude_ring",
    "_is_degenerate_wedge",
    "_tapered_prism",
    "_wall_faces_along",
]


def _is_degenerate_wedge(cutter: trimesh.Trimesh) -> bool:
    """Whether ``cutter`` is a coarse single-cap wedge rather than a fit opening.

    A malformed opening can be authored as a low-poly degenerate solid (6-8
    vertices): a door/window cross-section that tapers to a point or collapses
    towards a thin sliver instead of the clean prism a proper through-opening
    would expose. It reaches the single-cap loft path because its cut-surface
    tube never closes to a watertight bore. A genuine opening solid orders many
    more vertices, so a low vertex count is the reliable signature of the
    malformed wedge.
    """
    vertices = np.asarray(cutter.vertices)
    return len(vertices) >= 3 and len(vertices) <= 8


def _wall_faces_along(
    cap_normal: np.ndarray, cap_centroid: np.ndarray, host: trimesh.Trimesh
) -> tuple[float, float] | None:
    """The two host wall-face offsets bounding the opening along ``cap_normal``.

    Casts a ray from ``cap_centroid`` into the wall (along ``-cap_normal``, the
    direction away from the outward-facing cap) and returns the cap-normal offsets
    of the nearest and farthest *distinct* host surface crossed -- the two sides of
    the host wall the void spans. Coincident faces (a doubly-tessellated host
    surface) are de-duplicated, so a curved wall's outermost and innermost surfaces
    are used rather than its doubled facets. Returns ``None`` when the host is not
    crossed twice (an already-voided or oblique host).
    """
    ncap = np.asarray(cap_normal, dtype=np.float64)
    ncap = ncap / np.linalg.norm(ncap)
    hv = np.asarray(host.vertices, dtype=np.float64)
    hf = np.asarray(host.faces, dtype=np.int64)
    if len(hf) == 0:
        return None
    hmesh = trimesh.Trimesh(vertices=hv, faces=hf, process=False, validate=False)
    try:
        loc, _ridx, _tri = hmesh.ray.intersects_location(
            np.array([cap_centroid], dtype=np.float64),
            np.array([-ncap]),
            multiple_hits=True,
        )
    except Exception:
        return None
    if len(loc) == 0:
        return None
    cap_off = float(np.asarray(cap_centroid) @ ncap)
    offs = np.asarray(loc, dtype=np.float64) @ ncap
    distinct: dict[float, float] = {}
    for key, val in zip(np.round(offs, 4), offs, strict=True):
        distinct.setdefault(float(key), float(val))
    into = sorted(val for val in distinct.values() if val < cap_off)
    if len(into) < 2:
        return None
    near_off, far_off = float(max(into)), float(min(into))
    if abs(near_off - far_off) < _MIN_LOFT_DEPTH:
        return None
    return near_off, far_off


def _tapered_prism(
    vertices: np.ndarray,
    faces: np.ndarray,
    ring: list[int],
    caps: list[list[int]],
    cap_normal: np.ndarray,
    near_off: float,
    far_off: float,
) -> trimesh.Trimesh | None:
    """A watertight prism for a degenerate wedge between two host-parallel planes.

    Each ring vertex is projected along its two adjacent wedge side faces to the
    near and far wall-face planes, so the two caps keep the wedge's per-side taper
    (the angle+distance construction) and the void spans the wall *into* the host
    instead of out the far side. A side face is the non-cap cutter face sharing the
    ring edge, and its plane carries the reveal taper; a ring vertex is moved
    along the intersection line of its two adjacent side planes to each wall-plane
    offset. Returns ``None`` when no watertight prism can be built.
    """
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    ncap = np.asarray(cap_normal, dtype=np.float64)
    ncap = ncap / np.linalg.norm(ncap)
    n = len(ring)
    if n < 3 or near_off <= far_off:
        return None
    face_normals = _face_normals(v, f)
    cap_faces = {int(index) for group in caps for index in group}
    side_normals: list[np.ndarray] = []
    for i in range(n):
        a, b = int(ring[i]), int(ring[(i + 1) % n])
        adj = [
            j for j in range(len(f)) if j not in cap_faces and a in f[j] and b in f[j]
        ]
        if not adj:
            return None
        nn = face_normals[np.asarray(adj)].mean(axis=0)
        norm = float(np.linalg.norm(nn))
        if norm <= 0.0:
            return None
        side_normals.append(nn / norm)
    side_normal_array = np.asarray(side_normals, dtype=np.float64)

    near_pts: list[np.ndarray] = []
    far_pts: list[np.ndarray] = []
    for i in range(n):
        direction = np.cross(side_normal_array[(i - 1) % n], side_normal_array[i])
        norm = float(np.linalg.norm(direction))
        if norm < 1e-9:
            return None
        direction = direction / norm
        p0 = v[int(ring[i])]
        for offset, acc in ((near_off, near_pts), (far_off, far_pts)):
            dn = float(direction @ ncap)
            if abs(dn) < 1e-12:
                return None
            t = (offset - float(p0 @ ncap)) / dn
            acc.append(p0 + t * direction)

    verts = np.vstack(
        [np.asarray(near_pts, dtype=np.float64), np.asarray(far_pts, dtype=np.float64)]
    )
    new_faces: list[list[int]] = []
    for i in range(1, n - 1):
        new_faces.append([0, i, i + 1])  # near cap, kept flat
        new_faces.append([n, n + i + 1, n + i])  # far cap, kept flat
    for i in range(n):
        j = (i + 1) % n
        new_faces.append([i, j, n + j])
        new_faces.append([i, n + j, n + i])
    mesh = trimesh.Trimesh(
        vertices=verts, faces=np.asarray(new_faces, int), process=False
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _extrude_ring(ring_pts: np.ndarray, vec: np.ndarray) -> trimesh.Trimesh | None:
    """A watertight prism extruding a planar ring by ``vec``.

    The single host-parallel cap of a degenerate wedge is extruded along the cap
    normal by the wall thickness. Both caps are triangulated as a fan from the
    first ring vertex so they stay flat and the solid is a true prism. The ring
    must be a simple, convex-ish polygon (the door / skylight cross-sections are
    quadrilaterals or triangles); a ring that cannot close watertight yields
    ``None`` and the caller degrades to ``caps_only``.
    """
    ring_pts = np.asarray(ring_pts, dtype=np.float64)
    vec = np.asarray(vec, dtype=np.float64)
    n = len(ring_pts)
    if n < 3:
        return None
    verts = np.vstack([ring_pts, ring_pts + vec])
    faces: list[list[int]] = []
    for i in range(1, n - 1):
        faces.append([0, i, i + 1])  # near cap, kept flat
        faces.append([n, n + i + 1, n + i])  # far cap, kept flat
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces, int), process=False)
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _cut_ring_by_tube(
    near_ring: np.ndarray,
    far_ring: np.ndarray,
    tube: trimesh.Trimesh,
    cap_normal: np.ndarray,
) -> np.ndarray:
    """Clip ``far_ring`` so it stays inside the tube reveal band, or return it.

    The tube reveal faces bound the bore laterally. Each is a half-space; the far
    ring is clipped against every half-space (keeping the side that holds the near
    ring's centre) so the copied far cap matches the actual opening. When no tube
    face is a reveal, ``far_ring`` is returned unchanged (a pure thickness offset).
    """
    center = np.mean(near_ring, axis=0)
    points = np.asarray(far_ring, dtype=np.float64)
    for face in np.asarray(tube.faces, int):
        triangle = np.asarray(tube.vertices, dtype=np.float64)[face]
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        length = float(np.linalg.norm(normal))
        if length <= 1e-12:
            continue
        normal = normal / length
        if abs(float(normal @ cap_normal)) > _REVEAL_PARALLEL_COS:
            continue
        origin = triangle[0]
        keep_sign = 1.0 if float((center - origin) @ normal) >= 0.0 else -1.0
        clipped = _clip_polygon_halfspace(points, origin, normal, keep_sign)
        if clipped is None or len(clipped) < 3:
            return np.asarray(far_ring, dtype=np.float64)
        points = clipped
    return points


def _clip_polygon_halfspace(
    points: np.ndarray, origin: np.ndarray, normal: np.ndarray, keep_sign: float
) -> np.ndarray | None:
    """Sutherland-Hodgman clip of ``points`` to the half-space of ``normal``."""
    points = np.asarray(points, dtype=np.float64)
    n = len(points)
    if n < 3:
        return None
    signed = (points - origin) @ normal * keep_sign
    output: list[np.ndarray] = []
    for i in range(n):
        cur = points[i]
        nxt = points[(i + 1) % n]
        cur_inside = signed[i] >= 0
        nxt_inside = signed[(i + 1) % n] >= 0
        if cur_inside:
            output.append(cur)
        if cur_inside != nxt_inside:
            denominator = signed[i] - signed[(i + 1) % n]
            if abs(denominator) <= 1e-12:
                continue
            t = signed[i] / denominator
            output.append(cur + t * (nxt - cur))
    if len(output) < 3:
        return None
    return np.asarray(output, dtype=np.float64)
