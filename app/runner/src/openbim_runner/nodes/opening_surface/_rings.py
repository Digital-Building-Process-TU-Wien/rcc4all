"""Cap ring utilities: orientation, sliver cleanup, shift/align and resampling."""

from __future__ import annotations

import math

import numpy as np

from openbim_runner.nodes.opening_surface._mesh_topology import (
    _COINCIDENT_VERTS_EPS,  # pyright: ignore[reportPrivateUsage]
)

# A cap-ring vertex is a redundant sliver when the two edges meeting at it run
# in nearly the same direction (the path is almost straight through it) and one
# of those edges is only a short stub; collapsing it recovers the true polygon
# without changing the shape.
_COLLINEAR_COS = math.cos(math.radians(8.0))
_SLIVER_EDGE_LEN = 0.05


__all__ = [
    "_align_rings",
    "_clean_degenerate_ring",
    "_orient_ring",
    "_resample_closed",
    "_ring_shift",
]


def _polygon_normal(points: np.ndarray) -> np.ndarray:
    """The polygon (Newell) normal of a closed 3D polyline."""
    points = np.asarray(points, dtype=np.float64)
    normal = np.zeros(3, dtype=np.float64)
    count = len(points)
    for i in range(count):
        normal += np.cross(points[i], points[(i + 1) % count])
    return normal


def _orient_ring(
    vertices: np.ndarray, ring: np.ndarray, cap_normal: np.ndarray
) -> np.ndarray:
    """Reverse ``ring`` (global vertex ids) so its polygon normal points along ``cap_normal``.

    Boundary loops are walked without a shared orientation, so the front and back
    rims of a through-void can wind in opposite directions. Flipping the ring
    whose polygon normal opposes the cap normal brings the two rims into a
    consistent winding, which is what the side band needs to avoid
    self-intersecting when index i is matched to index i.
    """
    ring = np.asarray(ring, int)
    if float(_polygon_normal(vertices[ring]) @ cap_normal) < 0.0:
        return ring[::-1]
    return ring


def _clean_degenerate_ring(vertices: np.ndarray, ring: np.ndarray) -> np.ndarray | None:
    """Collapse redundant near-collinear sliver vertices from a cap ring.

    A cap rim authored as a degenerate polygon (a door/window frame with a tiny
    bevel corner) carries an extra near-coincident vertex: the two edges meeting
    at it run in almost the same direction, so the path is nearly straight through
    it and the point lies on a short stub. Dropping such a vertex merges the two
    edges and recovers the true polygon without changing its shape.

    A vertex is removed only when BOTH hold: its two incident edges are
    near-collinear (same direction, ``cos >= _COLLINEAR_COS``) AND one of them is
    a short stub (``<= _SLIVER_EDGE_LEN``), so a genuine corner with an angle is
    never simplified. This keeps at least three vertices; returns ``None`` when a
    valid ring cannot be produced (the caller then keeps the resampling loft).
    """
    ring = np.asarray(ring, int)
    pts = np.asarray(vertices[ring], dtype=np.float64)
    n = len(pts)
    if n < 4:
        return ring
    kept = list(range(n))
    changed = True
    while changed and len(kept) >= 3:
        changed = False
        next_kept: list[int] = []
        count = len(kept)
        for k in range(count):
            index = kept[k]
            previous = kept[(k - 1) % count]
            following = kept[(k + 1) % count]
            forward = pts[index] - pts[previous]
            backward = pts[following] - pts[index]
            forward_len = float(np.linalg.norm(forward))
            backward_len = float(np.linalg.norm(backward))
            if (
                forward_len <= _COINCIDENT_VERTS_EPS
                or backward_len <= _COINCIDENT_VERTS_EPS
            ):
                changed = True
                continue
            collinear = float((forward / forward_len) @ (backward / backward_len))
            if (
                collinear >= _COLLINEAR_COS
                and min(forward_len, backward_len) <= _SLIVER_EDGE_LEN
            ):
                changed = True
                continue
            next_kept.append(index)
        kept = next_kept
    if len(kept) < 3:
        return None
    return ring[kept]


def _ring_shift(a: np.ndarray, b: np.ndarray) -> int:
    """Cyclic row shift of ``b`` that best aligns it to ``a``."""
    n = len(a)
    best_shift = 0
    best_distance = float("inf")
    for shift in range(n):
        distance = float(np.sum(np.linalg.norm(a - np.roll(b, shift, axis=0), axis=1)))
        if distance < best_distance:
            best_distance = distance
            best_shift = shift
    return best_shift


def _align_rings(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rotate ``b`` (cyclic) so its samples best line up with ``a``."""
    n = len(a)
    if n == 0:
        return a, b
    best_shift = 0
    best_distance = float("inf")
    for shift in range(n):
        distance = float(np.sum(np.linalg.norm(a - np.roll(b, shift, axis=0), axis=1)))
        if distance < best_distance:
            best_distance = distance
            best_shift = shift
    return a, np.roll(b, best_shift, axis=0)


def _resample_closed(pts: np.ndarray, n: int) -> np.ndarray | None:
    """Resample the closed polygon ``pts`` to ``n`` points by uniform arc length."""
    pts = np.asarray(pts, dtype=np.float64)
    m = len(pts)
    if m == 0 or n <= 0:
        return None
    if m == 1:
        return np.repeat(pts[:1], n, axis=0)
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total <= 1e-12:
        return np.repeat(pts[:1], n, axis=0)
    targets = np.linspace(0.0, total, n, endpoint=False)
    out = np.empty((n, 3), dtype=np.float64)
    for k, target in enumerate(targets):
        index = int(np.searchsorted(s, target, side="right"))
        index = min(max(index, 1), m)
        t0, t1 = float(s[index - 1]), float(s[index])
        fraction = 0.0 if t1 <= t0 else (target - t0) / (t1 - t0)
        out[k] = pts[(index - 1) % m] * (1.0 - fraction) + pts[index % m] * fraction
    return out
