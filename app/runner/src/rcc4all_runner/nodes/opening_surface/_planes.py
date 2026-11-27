"""Planar grouping, footprint containment and slab clipping for the opening_surface node."""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import trimesh
from shapely.geometry import MultiPoint

from rcc4all_runner.nodes.opening_surface._numeric import (
    _in_plane_axes,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import ensure_watertight

# Two faces are coplanar when their normals align within ~1° and their planes
# sit within this offset of each other.
_PLANE_COS = math.cos(math.radians(1.0))
_PLANE_TOLERANCE = 0.02

# A face joins a planar group when its normal deviates from the seed by less
# than ~1° and its first vertex lies within this offset of the seed's plane.
_ALIGNED_COS = math.cos(math.pi / 180.0)
_SURFACE_PLANE_TOLERANCE = 0.01

# A small buffer on the cutter footprint that absorbs tessellation jitter on
# shared edges during the containment test.
_CONTAINMENT_EPS = 0.02

# Grows the clip slab slightly beyond the opening's in-plane footprint.
_CLIP_EPSILON = 0.02


__all__ = [
    "_clip_to_slab",
    "_footprint_contained",
    "_planar_groups",
    "_planar_surface",
]


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
            & (np.abs(offsets) <= _SURFACE_PLANE_TOLERANCE)
            & ~assigned
        )
        same[seed] = True
        assigned |= same
        groups.append(np.flatnonzero(same).tolist())

    return groups


def _mean_normal(normals: np.ndarray, group: list[int]) -> np.ndarray:
    """The normalised mean of a planar face group's normals."""
    mean_normal = normals[group].mean(axis=0)
    length = float(np.linalg.norm(mean_normal))
    if length <= 1e-10:
        return mean_normal
    return mean_normal / length


def _planar_surface(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    group: list[int],
) -> tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any] | None:
    """The plane of a planar face group as ``(normal, offset, axes, footprint)``.

    ``normal`` is the group's mean normal and ``offset`` its plane position along
    it. ``axes`` are the in-plane ``(u, v)`` directions and ``footprint`` the 2D
    convex hull of the group projected onto the plane. Returns ``None`` for a
    degenerate group (no area, so no footprint).
    """
    points = vertices[np.unique(faces[group])]
    normal = _mean_normal(normals, group)
    if float(np.linalg.norm(normal)) <= 1e-10:
        return None
    axes = _in_plane_axes(normal)
    footprint = _project_footprint(points, axes)
    if footprint is None:
        return None
    offset = float(np.mean(points @ normal))
    return normal, offset, axes, footprint


def _project_footprint(
    points: np.ndarray, axes: tuple[np.ndarray, np.ndarray]
) -> Any | None:
    """The convex hull of ``points`` projected onto the in-plane axes, or None."""
    axis_u, axis_v = axes
    data = np.column_stack([points @ axis_u, points @ axis_v])
    footprint = MultiPoint(data).convex_hull
    if footprint.area <= 0.0:
        return None
    return footprint


def _footprint_contained(
    vertices: np.ndarray,
    face: np.ndarray,
    axes: tuple[np.ndarray, np.ndarray],
    cutter_footprint: Any,
) -> bool:
    """Whether a host face's footprint lies inside the cutter surface footprint.

    The host face is projected onto the cutter surface's in-plane axes so the
    test runs in a single shared 2D frame; a small buffer on the cutter absorbs
    tessellation jitter on shared edges. Returns False for a degenerate face.
    """
    face_points = vertices[face]
    data = np.column_stack([face_points @ axes[0], face_points @ axes[1]])
    footprint = MultiPoint(data).convex_hull
    if footprint.area <= 0.0:
        return False
    return bool(cutter_footprint.buffer(_CONTAINMENT_EPS).covers(footprint))


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
