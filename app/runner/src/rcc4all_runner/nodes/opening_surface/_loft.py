"""Ring pairing, twist detection and lofting for the opening_surface node."""

from __future__ import annotations

import numpy as np
import trimesh

from rcc4all_runner.nodes.opening_surface._mesh_topology import (
    _boundary_loops,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._rings import (
    _align_rings,  # pyright: ignore[reportPrivateUsage]
    _clean_degenerate_ring,  # pyright: ignore[reportPrivateUsage]
    _orient_ring,  # pyright: ignore[reportPrivateUsage]
    _resample_closed,  # pyright: ignore[reportPrivateUsage]
    _ring_shift,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._wedge import (
    _cut_ring_by_tube,  # pyright: ignore[reportPrivateUsage]
    _extrude_ring,  # pyright: ignore[reportPrivateUsage]
    _is_degenerate_wedge,  # pyright: ignore[reportPrivateUsage]
    _tapered_prism,  # pyright: ignore[reportPrivateUsage]
    _wall_faces_along,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_fix_normals,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
)

# Two equal-length cap rims bridge directly (the detected cap faces preserved
# verbatim) only when they are congruent: every vertex then maps to its
# counterpart at a pure offset along the cap normal, leaving no displacement
# inside the cap plane. Degenerate mirror-image rims (bevel slivers on different
# corners) leave some pairs displaced in-plane after any cyclic shift; when that
# displacement exceeds this fraction of the rims' in-plane extent a direct bridge
# would twist, so the rims are cleaned and re-lofted instead. Genuine congruent
# rims on the real-world model measure ~0.02 of extent; the degenerate ones
# measure 0.4 and up.
_TWIST_INPLANE_RATIO = 0.15


__all__ = [
    "_loft_caps_watertight",
    "_loft_open_ring",
    "_loft_polygons",
]


def _loft_open_ring(
    vertices: np.ndarray,
    faces: np.ndarray,
    caps: list[list[int]],
    cap_normal: np.ndarray,
    depth: float | None,
    tube: trimesh.Trimesh | None,
    cutter: trimesh.Trimesh | None = None,
    host: trimesh.Trimesh | None = None,
) -> trimesh.Trimesh | None:
    """The watertight volume lofted between the opening's two cap faces.

    The cap faces are split into a front and a back cluster by their offset along
    the cap normal. When both sides of the opening have cap faces, the two caps
    are kept exactly as they were detected (only new side faces bridge their
    boundary rings, connected in 3D). When the cap faces occupy only one side of
    the opening, a second ring is synthesized by copying the found ring across
    the wall by ``depth`` and clipping the copy against the tube reveal faces,
    and both caps are rebuilt from the derived rings. Returns ``None`` when no
    watertight closed surface can be built.
    """
    cap_face_indices = [index for group in caps for index in group]
    if not cap_face_indices:
        return None
    cap_faces = faces[cap_face_indices]
    offsets = vertices[cap_faces[:, 0]] @ cap_normal
    front: list[int] = []
    back: list[int] = []
    if float(offsets.max() - offsets.min()) <= 1e-9:
        front = list(cap_face_indices)
    else:
        mid = 0.5 * (float(offsets.min()) + float(offsets.max()))
        for index, offset in zip(cap_face_indices, offsets, strict=True):
            (back if float(offset) > mid else front).append(index)

    if front and back:
        front_ring = _outer_ring(vertices, faces, front)
        back_ring = _outer_ring(vertices, faces, back)
        if front_ring is None or back_ring is None:
            return None
        return _loft_caps_watertight(
            vertices, faces, front, back, front_ring, back_ring
        )

    # Only one cap side: synthesize the opposing cap across the wall thickness.
    side = front or back
    ring = _outer_ring(vertices, faces, side)
    if ring is None or depth is None or depth <= 0.0:
        return None
    near_ring = vertices[np.asarray(ring, int)]

    # A degenerate wedge (a coarse single-cap opening whose source solid does not
    # represent the true void): rebuild the cap as a clean prism spanning the two
    # host wall faces, preserving the wedge's per-side taper.
    if cutter is not None and host is not None and _is_degenerate_wedge(cutter):
        faces_off = _wall_faces_along(cap_normal, near_ring.mean(axis=0), host)
        if faces_off is not None:
            near_off, far_off = faces_off
        elif depth > 0.0:
            # The ray from a proud cap can miss the host (an angled or thin
            # wall): fall back to the host thickness measured by ``_cap_info``,
            # crossing the wall by ``depth`` into the host.
            ncap = np.asarray(cap_normal, dtype=np.float64)
            ncap = ncap / np.linalg.norm(ncap)
            near_off = float(np.mean(near_ring @ ncap))
            far_off = near_off - depth
        else:
            near_off = far_off = None
        if near_off is not None and far_off is not None:
            prism = _tapered_prism(
                vertices, faces, ring, caps, cap_normal, near_off, far_off
            )
            if prism is not None and _is_watertight(prism):
                return prism
        # The ray (or side-plane construction) cannot recover the void: extrude
        # the host-parallel cap flat across the wall INTO the host so the wedge
        # still closes into a sound prism.
        return _extrude_ring(near_ring, -depth * cap_normal)

    # Genuine open ring (a floor-reaching door / non-planar rim): keep the tube
    # reveal-band clip, which bounds the synthesized far cap to the wall opening.
    far_ring = near_ring + depth * cap_normal
    if tube is not None:
        far_ring = _cut_ring_by_tube(near_ring, far_ring, tube, cap_normal)
    return _loft_polygons(near_ring, far_ring)


def _outer_ring(
    vertices: np.ndarray, faces: np.ndarray, face_indices: list[int]
) -> list[int] | None:
    """The longest boundary loop of a cap face cluster, as global vertex ids."""
    subset = trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(faces[face_indices], int),
        process=False,
    )
    loops = _boundary_loops(subset)
    if not loops:
        return None
    return list(max(loops, key=len))


def _loft_caps_watertight(
    vertices: np.ndarray,
    faces: np.ndarray,
    front: list[int],
    back: list[int],
    front_ring: list[int],
    back_ring: list[int],
) -> trimesh.Trimesh | None:
    """A watertight solid that keeps the two detected cap faces unchanged.

    The front/back cap triangles are emitted as-is, so the caps are exactly the
    faces found by the cap analysis; only new side faces are added between the
    two cap boundary rings, connected in 3D. The two rims are first brought into
    a consistent winding (a cyclic shift alone cannot fix opposite winding) so
    the side band does not self-intersect. Equal-length rims that no cyclic shift
    can pair are cleaned and re-lofted when cleanup recovers congruent rings
    (degenerate mirror-image slivers, whose direct bridge would twist); when the
    rims genuinely differ after cleanup the direct bridge keeps the detected cap
    faces verbatim. Returns ``None`` when no watertight closed surface can be
    built (the caller degrades to ``caps_only``).
    """
    front_arr = np.asarray(front_ring, int)
    back_arr = np.asarray(back_ring, int)
    n = len(front_arr)
    m = len(back_arr)
    if n < 3 or m < 3:
        return None

    # The cap-plane normal is the mean of the front cap cluster's face normals.
    # Orienting both rims to it makes them wind the same way; without this the
    # two boundary loops can wind oppositely and the side band self-intersects,
    # collapsing the signed volume.
    cap_normal = _face_normals(vertices, faces)[front]
    cap_normal = np.asarray(cap_normal, dtype=np.float64).mean(axis=0)
    norm = float(np.linalg.norm(cap_normal))
    if norm > 0.0:
        cap_normal = cap_normal / norm
        front_arr = _orient_ring(vertices, front_arr, cap_normal)
        back_arr = _orient_ring(vertices, back_arr, cap_normal)

    if n != m:
        # An unequal rim can hide a degenerate ring (a sliver bevel corner with
        # near-coincident, near-collinear vertices). Collapse such redundant
        # vertices first, then rebuild a watertight volume from the cleaned rings;
        # a genuine unequal rim with real corners is untouched and keeps the
        # resampling loft.
        cleaned_f = _clean_degenerate_ring(vertices, front_arr)
        cleaned_b = _clean_degenerate_ring(vertices, back_arr)
        if cleaned_f is not None and cleaned_b is not None:
            front_arr, back_arr = cleaned_f, cleaned_b
        return _loft_polygons(vertices[front_arr], vertices[back_arr])

    if _rings_twisted(vertices[front_arr], vertices[back_arr], cap_normal):
        # Equal counts do not imply congruent rims: collinear bevel slivers on
        # different corners (mirror images) defeat every cyclic shift. Re-loft
        # only when cleanup recovers congruent rings — the signature of the
        # mirror-image case. Rims that stay non-congruent after cleanup genuinely
        # differ: their mispaired vertices all lie on the edge line, so the direct
        # bridge (and its detected cap faces) is exact, while a resampling loft
        # would push corners off the true rectangle and distort the volume.
        cleaned_f = _clean_degenerate_ring(vertices, front_arr)
        cleaned_b = _clean_degenerate_ring(vertices, back_arr)
        if cleaned_f is not None and cleaned_b is not None:
            a = vertices[cleaned_f]
            b = vertices[cleaned_b]
            if len(a) == len(b) and not _rings_twisted(a, b, cap_normal):
                return _loft_polygons(a, b)
        # No congruent recovery: fall through and bridge the original rims.

    shift = _ring_shift(vertices[front_arr], vertices[back_arr])
    back_arr = np.roll(back_arr, shift)
    side: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        side.append([int(front_arr[i]), int(front_arr[j]), int(back_arr[j])])
        side.append([int(front_arr[i]), int(back_arr[j]), int(back_arr[i])])

    all_faces = (
        [list(tri) for tri in np.asarray(faces[front], int)]
        + [list(tri) for tri in np.asarray(faces[back], int)]
        + side
    )
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(all_faces, dtype=np.int64),
        process=False,
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _rings_twisted(a: np.ndarray, b: np.ndarray, cap_normal: np.ndarray) -> bool:
    """Whether two equal-length cap rims cannot be paired by a cyclic shift.

    Equal vertex counts do not imply congruent rims: a rectangle authored with
    collinear bevel slivers can carry them on *different corners* in the two rims
    (mirror images), so no cyclic shift pairs corresponding vertices and a direct
    bridge collapses into long diagonal side triangles — a watertight but twisted
    solid. Congruent rims pair every vertex with its counterpart at a pure offset
    along the cap normal, so the in-plane part of each pair offset is ~0; a
    mismatched pair sits displaced inside the cap plane. That displacement is
    compared to the rims' in-plane extent, so the test is scale-free. Used only
    when the two rims already agree on vertex count (see
    ``_loft_caps_watertight``).
    """
    n = len(a)
    if n < 3 or n != len(b):
        return False
    normal = np.asarray(cap_normal, dtype=np.float64)
    norm = float(np.linalg.norm(normal))
    if norm <= 0.0:
        return False
    normal = normal / norm
    shift = _ring_shift(a, b)
    offsets = np.asarray(a, dtype=np.float64) - np.roll(
        np.asarray(b, dtype=np.float64), shift, axis=0
    )
    along = offsets @ normal
    in_plane = np.linalg.norm(offsets - np.outer(along, normal), axis=1)
    points = np.vstack(
        [np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)]
    )
    flat = points - np.outer(points @ normal, normal)
    extent = float(np.linalg.norm(flat[:, None, :] - flat[None, :, :], axis=2).max())
    if extent <= 1e-9:
        return False
    return bool(float(in_plane.max()) > _TWIST_INPLANE_RATIO * extent)


def _loft_polygons(
    a_pts: np.ndarray, b_pts: np.ndarray, n: int | None = None
) -> trimesh.Trimesh | None:
    """Loft the closed polygons ``a_pts`` and ``b_pts`` into one watertight solid.

    When ``n`` is given, both polygons are resampled to ``n`` points (uniform arc
    length). When ``n`` is omitted and the two rings already agree on vertex
    count, the original ring vertices are kept so the caps are exact; otherwise
    both rings are resampled to the larger count. The b ring is rotated to best
    align with the a ring, and the volume is built from the two re-triangulated
    caps plus the side quads between corresponding samples.
    """
    a_pts = np.asarray(a_pts, dtype=np.float64)
    b_pts = np.asarray(b_pts, dtype=np.float64)
    if len(a_pts) < 3 or len(b_pts) < 3:
        return None
    count = n if n is not None else max(len(a_pts), len(b_pts))
    if n is None and len(a_pts) == len(b_pts):
        # The two caps already agree on vertex count. Resampling by uniform arc
        # length would move the corner vertices to edge midpoints whenever the cap
        # is a non-regular polygon (e.g. a non-square rectangle), distorting the
        # emitted cap. Keep the original ring vertices so the cap is exact.
        a, b = a_pts, b_pts
    else:
        a = _resample_closed(a_pts, count)
        b = _resample_closed(b_pts, count)
        if a is None or b is None:
            return None
    a, b = _align_rings(a, b)

    all_vertices: list[np.ndarray] = [a[i] for i in range(count)]
    all_vertices.extend([b[i] for i in range(count)])
    apex_a = 2 * count
    apex_b = 2 * count + 1
    all_vertices.append(a.mean(axis=0))
    all_vertices.append(b.mean(axis=0))
    faces: list[list[int]] = []
    for i in range(count):
        j = (i + 1) % count
        # cap A: traverse A[j]->A[i] (opposite the side-quad A[i]->A[j])
        faces.append([apex_a, j, i])
        # cap B: traverse B[i]->B[j] (opposite the side-quad B[j]->B[i])
        faces.append([apex_b, count + i, count + j])
        # side quad A[i], A[j], B[j], B[i] -> two triangles
        faces.append([i, j, count + j])
        faces.append([i, count + j, count + i])
    mesh = trimesh.Trimesh(
        vertices=np.asarray(all_vertices, dtype=np.float64),
        faces=np.asarray(faces, int),
        process=False,
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None
