"""Numeric helpers for the opening_surface node."""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = [
    "_face_normals",
    "_group_area",
    "_in_plane_axes",
    "_iter_openings",
    "_resolve_entity",
]


def _resolve_entity(model: Any, express_id: int) -> Any | None:
    """The entity for ``express_id``, or None when the model has none."""
    try:
        return model.by_id(express_id)
    except RuntimeError:
        return None


def _iter_openings(host: Any) -> list[Any]:
    """The openings that void ``host``, via its ``IfcRelVoidsElement`` links."""
    openings: list[Any] = []
    for relationship in getattr(host, "HasOpenings", None) or []:
        opening = getattr(relationship, "RelatedOpeningElement", None)
        if opening is not None:
            openings.append(opening)
    return openings


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """The unit normals of ``faces``; degenerate faces get a zero normal."""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _group_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    """The total area of the ``group`` faces of ``faces``."""
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(0.5 * np.linalg.norm(cross, axis=1).sum())


# A plane this close to horizontal (skylights) cannot use the world Z axis as
# its in-plane vertical reference and falls back to the world Y axis.
_HORIZONTAL_COS = 0.999


def _in_plane_axes(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right-handed in-plane axes ``(u, v)`` of the plane with ``normal``.

    ``v`` stays as close to the world Z axis as the plane allows, so ``height``
    is the vertical extent for wall openings; near-horizontal planes
    (skylights) use the world Y axis instead. The chosen reference is never
    parallel to ``normal``, so the projection is always non-degenerate.
    """
    world_z = np.array([0.0, 0.0, 1.0])
    if abs(float(normal[2])) < _HORIZONTAL_COS:
        reference = world_z
    else:
        reference = np.array([0.0, 1.0, 0.0])
    vertical = reference - float(reference @ normal) * normal
    axis_v = vertical / float(np.linalg.norm(vertical))
    axis_u = np.cross(axis_v, normal)
    return axis_u, axis_v
