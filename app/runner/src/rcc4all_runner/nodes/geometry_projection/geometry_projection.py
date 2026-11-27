from __future__ import annotations

import sys

import numpy as np
import trimesh
from pydantic import Field, FiniteFloat
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from trimesh.creation import triangulate_polygon
from trimesh.geometry import plane_transform
from trimesh.path.polygons import projected as trimesh_projected
from trimesh.util import append_faces

from rcc4all_runner.nodes.base import ExecutionContext, NodeModel, node
from rcc4all_runner.util.geometry import cache_mesh, resolve_keys, resolve_mesh


class GeometryProjectionSettings(NodeModel):
    projection_normal: list[FiniteFloat] = Field(
        default=[0.0, 0.0, 1.0],
        title="Projection Normal",
        min_length=3,
        max_length=3,
        description=(
            "Normal vector of the projection plane, e.g. [0,0,1] projects onto the XY plane "
            "(top-down footprint). All three values must be finite. Normalized internally. "
            "Zero vector produces an 'undefined normal' error for every input."
        ),
    )


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
            "(degenerate, edge-on projection or projection/triangulation failure) or "
            "'undefined normal' (zero-length normal)."
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


def _polygons_from_geometry(geometry: BaseGeometry | None) -> list[Polygon]:
    """Return non-empty, non-zero-area polygons from a Shapely geometry."""
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry] if geometry.area > 0 else []
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return [
            polygon
            for child in geometry.geoms
            for polygon in _polygons_from_geometry(child)
        ]
    return []


def _project_polygons(mesh: trimesh.Trimesh, normal: np.ndarray) -> list[Polygon]:
    """Project every face into Shapely polygons without scale-dependent rounding.

    Watertight, consistently wound meshes can use Trimesh's one-sided silhouette
    optimization. Other meshes are projected in front/back groups and unioned so
    open or inconsistently oriented faces are never discarded.
    """
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        return []

    if mesh.is_watertight and mesh.is_winding_consistent:
        projection = trimesh_projected(
            mesh=mesh,
            normal=normal.tolist(),
            origin=None,
            ignore_sign=True,
            tol_dot=0.0,
            rpad=0.0,
        )
        return _polygons_from_geometry(projection)

    dot_face = np.dot(normal, mesh.face_normals.T)
    side_projections: list[BaseGeometry] = []
    for mask, reverse in ((dot_face > 0, False), (dot_face < 0, True)):
        if not mask.any():
            continue
        faces = mesh.faces[mask]
        if reverse:
            # Reverse back faces instead of the projection normal so both sides
            # are expressed in the same 2D coordinate system.
            faces = faces[:, [0, 2, 1]]
        side_mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=faces, process=False)
        projection = trimesh_projected(
            mesh=side_mesh,
            normal=normal.tolist(),
            origin=None,
            ignore_sign=False,
            tol_dot=0.0,
            rpad=0.0,
        )
        if projection is not None and not projection.is_empty:
            side_projections.append(projection)

    if not side_projections:
        return []
    return _polygons_from_geometry(unary_union(side_projections))


def _project_to_plane(
    mesh: trimesh.Trimesh, normal: np.ndarray, reference: str
) -> trimesh.Trimesh | None:
    """Project a mesh onto the plane through the world origin with the given normal.

    All faces contribute to the footprint, independently of winding and
    watertightness. Holes and disconnected regions are preserved. Returns the
    flat world-space footprint mesh, or ``None`` if the projection is empty or
    cannot be triangulated.
    """
    try:
        polygons = _project_polygons(mesh, normal)
    except Exception as exc:
        print(
            f"geometry_projection: projection failed for {reference!r} "
            f"({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return None
    if not polygons:
        return None

    try:
        triangulated: list[tuple[np.ndarray, np.ndarray]] = []
        for polygon in polygons:
            vertices_2d, faces_2d = triangulate_polygon(polygon, engine="manifold")
            if len(faces_2d) > 0:
                triangulated.append((vertices_2d, faces_2d))
        if not triangulated:
            return None

        v2, faces = append_faces(
            [vertices for vertices, _ in triangulated],
            [polygon_faces for _, polygon_faces in triangulated],
        )
        if len(faces) == 0:
            return None

        # plane_transform maps world points on the plane to XY. Its inverse
        # lifts the triangulated plane-local coordinates back to world space.
        transform = plane_transform(origin=None, normal=normal.tolist())
        inv_transform = np.linalg.inv(transform)
        homog = np.hstack([v2, np.zeros((len(v2), 1)), np.ones((len(v2), 1))])
        world_vertices = (homog @ inv_transform.T)[:, :3]

        footprint = trimesh.Trimesh(
            vertices=world_vertices, faces=np.asarray(faces, dtype=int), process=False
        )
    except Exception as exc:
        print(
            f"geometry_projection: triangulate/lift failed for {reference!r} "
            f"({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
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


def _unit_normal(value: list[float]) -> np.ndarray | None:
    """Normalize a finite vector without overflow/underflow; zero returns None."""
    normal = np.asarray(value, dtype=float)
    scale = float(np.max(np.abs(normal)))
    if scale == 0:
        return None
    scaled = normal / scale
    return scaled / np.linalg.norm(scaled)


@node()
async def geometry_projection(
    settings: GeometryProjectionSettings,
    inputs: GeometryProjectionInputs,
    context: ExecutionContext,
) -> GeometryProjectionResult:
    normal_unit = _unit_normal(settings.projection_normal)
    if normal_unit is None:
        errors = [
            ProjectionError(reference=label, error="undefined normal")
            for label, _ in resolve_keys(context, inputs.liste_a)
        ]
        return GeometryProjectionResult(projected_geometries={}, errors=errors)

    resolved = resolve_keys(context, inputs.liste_a)
    key_map = _assign_projection_keys(context, [label for label, _ in resolved])

    projected_geometries: dict[str, str] = {}
    errors: list[ProjectionError] = []
    footprints_by_reference: dict[str, trimesh.Trimesh | None] = {}

    for label, cache_key in resolved:
        if cache_key is None:
            errors.append(ProjectionError(reference=label, error="no cached geometry"))
            continue

        if label in footprints_by_reference:
            footprint = footprints_by_reference[label]
        else:
            mesh = resolve_mesh(context, cache_key)
            footprint = _project_to_plane(mesh, normal_unit, label)
            footprints_by_reference[label] = footprint
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
