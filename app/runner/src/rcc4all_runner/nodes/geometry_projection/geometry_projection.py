from __future__ import annotations

import sys

import numpy as np
import trimesh
from pydantic import Field, field_validator
from trimesh.geometry import plane_transform

from rcc4all_runner.nodes.base import ExecutionContext, NodeModel, node
from rcc4all_runner.util.geometry import cache_mesh, resolve_keys, resolve_mesh


class GeometryProjectionSettings(NodeModel):
    projection_normal: list[float] = Field(
        default=[0.0, 0.0, 1.0],
        title="Projection Normal",
        min_length=3,
        max_length=3,
        description=(
            "Normal vector of the projection plane, e.g. [0,0,1] projects onto the XY plane "
            "(top-down footprint). Normalized internally. Zero vector produces an 'undefined "
            "normal' error for every input."
        ),
    )

    @field_validator("projection_normal")
    @classmethod
    def _validate_projection_normal(cls, value: list[float]) -> list[float]:
        if len(value) != 3:
            raise ValueError(
                "projection_normal must be a list of exactly 3 floats [x, y, z]."
            )
        return value


class GeometryProjectionInputs(NodeModel):
    liste_a: list[str] | dict[str, str | None] = Field(
        title="List",
        description=(
            "List of fully qualified geometry cache keys — `<slug>:expr:<id>` for IFC "
            "elements, `gen:<object_id>` for generated geometry, `inter:<id>` for helper/"
            "intersection geometry — in the order to project. An empty list yields an empty "
            "result. Also accepts a dict (e.g., collision node's `intersection_meshes` output); "
            "in this case the dict's non-null values (cache keys) are used."
        ),
    )


class ProjectionError(NodeModel):
    reference: str = Field(
        title="Reference",
        description="The geometry cache key that failed to project, or the raw input when no geometry was found.",
    )
    error: str = Field(
        title="Error",
        description=(
            "Error reason: 'no cached geometry' (missing/invalid key), 'no projected geometry' "
            "(degenerate, edge-on projection) or 'undefined normal' (zero-length normal)."
        ),
    )


class GeometryProjectionResult(NodeModel):
    projected_geometries: dict[str, str] = Field(
        default={},
        title="Projected Geometries",
        description=(
            "Maps each input geometry cache key to the generated `gen:proj_<...>` key under "
            "which its flat projected footprint was stored in the geometry cache."
        ),
    )
    errors: list[ProjectionError] = Field(
        default=[],
        title="Errors",
        description="Per-input projection failures.",
    )


def _project_to_plane(
    mesh: trimesh.Trimesh, normal: np.ndarray
) -> trimesh.Trimesh | None:
    """Project a mesh onto the plane through the world origin with the given normal.

    Returns the flat world-space footprint mesh, or ``None`` if the projection is
    empty/degenerate (the mesh is edge-on to the projection plane) or cannot be
    triangulated.
    """
    try:
        path = mesh.projected(normal=normal.tolist())
    except Exception as exc:
        print(f"geometry_projection: mesh.projected() failed: {exc}", file=sys.stderr)
        return None
    if len(path.vertices) == 0:
        return None

    try:
        v2, faces = path.triangulate()
        if faces is None or len(faces) == 0:
            return None

        # Lift the 2D triangulated vertices back to world space. `plane_transform`
        # maps plane-local coordinates into world; its inverse maps the projected
        # 2D coordinates (in the plane basis) to world-space 3D points.
        transform = plane_transform(origin=None, normal=normal.tolist())
        inv_transform = np.linalg.inv(transform)
        homog = np.hstack([v2, np.zeros((len(v2), 1)), np.ones((len(v2), 1))])
        world_vertices = (homog @ inv_transform.T)[:, :3]

        footprint = trimesh.Trimesh(
            vertices=world_vertices, faces=np.asarray(faces, dtype=int), process=False
        )
    except Exception as exc:
        print(f"geometry_projection: triangulate/lift failed: {exc}", file=sys.stderr)
        return None

    if len(footprint.faces) == 0:
        return None
    return footprint


def _assign_projection_keys(
    context: ExecutionContext, reference_keys: list[str]
) -> dict[str, str]:
    """Assign a deterministic ``gen:proj_<reference>`` key per input reference.

    Idempotent within a single call: a reference that appears more than once in
    the list maps to the *same* generated key (no duplicate footprint, no ``_n``
    counter). Two *different* references that sanitize to the same base (e.g.
    ``gen:a_b`` vs ``gen:a:b``) still get distinct keys (``base``, ``base_1``,
    …) so their footprints never collide.

    The reference's ``:`` and ``/`` are reduced to ``_`` so the resulting key
    can never parse back as an IFC reference (which would break downstream slug
    detection). Keys already present in the shared cache are taken, so a base
    produced by an earlier node is not reused — it gets a ``_n`` suffix.
    """
    cache = context.geometry_cache or {}
    used = set(cache)
    assigned: dict[str, str] = {}

    for reference in reference_keys:
        if reference in assigned:
            continue
        base = "gen:proj_" + reference.replace(":", "_").replace("/", "_")
        key = base
        counter = 1
        while key in used:
            key = f"{base}_{counter}"
            counter += 1
        assigned[reference] = key
        used.add(key)

    return assigned


@node()
async def geometry_projection(
    settings: GeometryProjectionSettings,
    inputs: GeometryProjectionInputs,
    context: ExecutionContext,
) -> GeometryProjectionResult:
    normal = np.asarray(settings.projection_normal, dtype=float)
    norm = np.linalg.norm(normal)
    if norm == 0:
        errors = [
            ProjectionError(reference=label, error="undefined normal")
            for label, _ in resolve_keys(context, inputs.liste_a)
        ]
        return GeometryProjectionResult(projected_geometries={}, errors=errors)
    normal_unit = normal / norm

    resolved = resolve_keys(context, inputs.liste_a)
    key_map = _assign_projection_keys(context, [label for label, _ in resolved])

    projected_geometries: dict[str, str] = {}
    errors: list[ProjectionError] = []

    for label, cache_key in resolved:
        if cache_key is None:
            errors.append(ProjectionError(reference=label, error="no cached geometry"))
            continue

        mesh = resolve_mesh(context, cache_key)
        footprint = _project_to_plane(mesh, normal_unit)
        if footprint is None:
            errors.append(
                ProjectionError(reference=label, error="no projected geometry")
            )
            continue

        generated_key = key_map[label]
        if generated_key not in context.geometry_cache:
            cache_mesh(context, footprint, key=generated_key)
        projected_geometries[label] = generated_key

    return GeometryProjectionResult(
        projected_geometries=projected_geometries, errors=errors
    )
