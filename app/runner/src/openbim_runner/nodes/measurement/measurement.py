from __future__ import annotations

from typing import Literal

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import ensure_watertight, resolve_mesh
from trimesh.proximity import ProximityQuery


MeasurementType = Literal[
    "volume",
    "surface_area",
    "projected_area",
    "component_height",
    "distance_between",
    "distance_to_reference",
]


class MeasurementSettings(NodeModel):
    measurement_type: MeasurementType = Field(
        default="volume",
        title="Measurement Type",
        description="The type of measurement to compute. In v3, 'volume', 'surface_area', 'projected_area', 'component_height', and 'distance_between' are implemented.",
    )
    projection_normal: list[float] = Field(
        default=[0.0, 0.0, 1.0],
        title="Projection Normal",
        description="Normal vector for the projection plane. Default [0,0,1] computes footprint (top-down view). Only used for 'projected_area' mode.",
    )
    direction: list[float] = Field(
        default=[0.0, 0.0, 1.0],
        title="Direction",
        description="Direction vector for extent computation. Default [0,0,1] computes vertical height. Only used for 'component_height' mode. Normalized internally.",
    )


class MeasurementInputs(NodeModel):
    list_a: list[int | str] | dict[str, str | None] = Field(
        default=[],
        title="List A",
        description=(
            "First list of references — mix of express IDs (int → `ifc:<id>`) and object IDs "
            "(str → `gen:<id>`), in the order to test. When empty, the whole model is used. "
            "Also accepts a dict (e.g., collision node's `intersection_meshes` output); "
            "in this case, the dict's non-null values (intersection mesh cache keys) are used."
        ),
    )
    list_b: list[int | str] | dict[str, str | None] = Field(
        default=[],
        title="List B",
        description=(
            "Second (optional) list of references — mix of express IDs (int → `ifc:<id>`) and "
            "object IDs (str → `gen:<id>`). When empty, pairs are formed within List A. "
            "When non-empty, computes cartesian product A×B. Also accepts a dict (e.g., collision "
            "node's `intersection_meshes` output); non-null values are used as cache keys."
        ),
    )


class MeasurementItem(NodeModel):
    reference: str = Field(
        title="Reference",
        description="The geometry cache key (e.g., `ifc:123`, `gen:abc`, `inter:...`) of the measured element.",
    )
    value: float | None = Field(
        default=None,
        title="Value",
        description="The measured value. Null if geometry is missing or measurement failed.",
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason if measurement failed (e.g., 'no cached geometry', 'non-watertight').",
    )


class MeasurementResult(NodeModel):
    type: MeasurementType = Field(
        title="Type",
        description="The measurement type used to generate this result.",
    )
    unit: str = Field(
        title="Unit",
        description="The unit of measurement (model units, e.g., 'volume_unit' for volume, 'area_unit' for area and 'length_unit' for distance).",
    )
    measurements: list[MeasurementItem] = Field(
        default=[],
        title="Measurements",
        description="List of per-element measurements.",
    )


def _compute_distance_between(
    context: ExecutionContext,
    list_a: list[int | str] | dict[str, str | None],
    list_b: list[int | str] | dict[str, str | None],
) -> MeasurementResult:
    """Compute minimal surface-to-surface distance between element pairs.
    
    Behavior:
        - list_b empty: all unordered pairs within list_a (n choose 2), emit both directions
        - list_b non-empty: cartesian product A×B (skip self-pairs), emit one direction per pair
        - Reference format: dist:distance_{key_a}_{key_b} (directional, NOT sorted)
        - Pairs with missing geometry emit error item (value=null, error='no cached geometry')
    
    Unit: length_unit
    """
    resolved_a = _resolve_keys(context, list_a)
    measurements: list[MeasurementItem] = []
    
    if not list_b:
        keys_a = [ref for ref, _ in resolved_a]
        for key_a in keys_a:
            for key_b in keys_a:
                if key_a == key_b:
                    continue
                
                mesh_a: trimesh.Trimesh | None = None
                mesh_b: trimesh.Trimesh | None = None
                
                key_a_cache = next((ck for ref, ck in resolved_a if ref == key_a and ck is not None), None)
                key_b_cache = next((ck for ref, ck in resolved_a if ref == key_b and ck is not None), None)
                
                if key_a_cache is not None:
                    try:
                        mesh_a = resolve_mesh(context, key_a_cache)
                    except ValueError:
                        pass
                
                if key_b_cache is not None:
                    try:
                        mesh_b = resolve_mesh(context, key_b_cache)
                    except ValueError:
                        pass
                
                pair_ref_ab = f"dist:distance_{key_a}_{key_b}"
                
                if mesh_a is None or mesh_b is None:
                    measurements.append(MeasurementItem(reference=pair_ref_ab, value=None, error="no cached geometry"))
                else:
                    dist = _pair_distance(mesh_a, mesh_b)
                    measurements.append(MeasurementItem(reference=pair_ref_ab, value=dist, error=None))
    else:
        resolved_b = _resolve_keys(context, list_b)
        keys_a = [ref for ref, _ in resolved_a]
        keys_b = [ref for ref, _ in resolved_b]
        
        for key_a in keys_a:
            for key_b in keys_b:
                if key_a == key_b:
                    continue
                
                mesh_a: trimesh.Trimesh | None = None
                mesh_b: trimesh.Trimesh | None = None
                
                key_a_cache = next((ck for ref, ck in resolved_a if ref == key_a and ck is not None), None)
                key_b_cache = next((ck for ref, ck in resolved_b if ref == key_b and ck is not None), None)
                
                if key_a_cache is not None:
                    try:
                        mesh_a = resolve_mesh(context, key_a_cache)
                    except ValueError:
                        pass
                
                if key_b_cache is not None:
                    try:
                        mesh_b = resolve_mesh(context, key_b_cache)
                    except ValueError:
                        pass
                
                pair_ref_ab = f"dist:distance_{key_a}_{key_b}"
                
                if mesh_a is None or mesh_b is None:
                    measurements.append(MeasurementItem(reference=pair_ref_ab, value=None, error="no cached geometry"))
                else:
                    dist = _pair_distance(mesh_a, mesh_b)
                    measurements.append(MeasurementItem(reference=pair_ref_ab, value=dist, error=None))
    
    return MeasurementResult(
        type="distance_between",
        unit="length_unit",
        measurements=measurements,
    )


def _resolve_keys(
    context: ExecutionContext,
    refs: list[int | str] | dict[str, str | None] | None = None,
) -> list[tuple[str, str | None]]:
    """Resolve a list of mixed references into (reference_label, cache_key_or_None) pairs.

    - int → `ifc:<id>`
    - str starting with `ifc:`, `gen:`, or `inter:` → use as-is
    - str (other) → `gen:<id>`
    - Empty refs → whole model (all cache keys)
    - Dict (e.g., collision `intersection_meshes`) → use non-null values as cache keys

    Returns (ref_label, key) for present geometry, (ref_label, None) for missing.
    """
    cache = context.geometry_cache or {}
    refs = refs or []

    if isinstance(refs, dict):
        results: list[tuple[str, str | None]] = []
        for pair_key, mesh_key in refs.items():
            if mesh_key is None:
                continue
            if mesh_key in cache:
                results.append((mesh_key, mesh_key))
            else:
                results.append((pair_key, None))
        return results

    if not refs:
        return [(key, key) for key in cache.keys()]

    results_list: list[tuple[str, str | None]] = []
    for ref in refs:
        if isinstance(ref, int):
            key = f"ifc:{ref}"
        elif ref.startswith("ifc:") or ref.startswith("gen:") or ref.startswith("inter:"):
            key = ref
        else:
            key = f"gen:{ref}"

        if key in cache:
            results_list.append((key, key))
        else:
            results_list.append((str(ref), None))

    return results_list


def _aabb_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh) -> bool:
    """Quick bounding-box overlap test."""
    a_min, a_max = a.bounds
    b_min, b_max = b.bounds
    return bool(np.all(a_min <= b_max) and np.all(b_min <= a_max))


def _fcl_collision(a: trimesh.Trimesh, b: trimesh.Trimesh) -> bool | None:
    """Triangle-based collision test via FCL.
    
    Returns True if meshes collide, False if not, or None if FCL unavailable.
    """
    try:
        from trimesh.collision import CollisionManager
    except Exception:
        return None
    try:
        manager = CollisionManager()
        manager.add_object("a", a)
        manager.add_object("b", b)
        return bool(manager.in_collision_internal())
    except Exception:
        return None


def _meshes_intersect(a: trimesh.Trimesh, b: trimesh.Trimesh) -> bool:
    """Check if two meshes intersect using AABB + FCL."""
    if not _aabb_overlap(a, b):
        return False
    fcl_result = _fcl_collision(a, b)
    return fcl_result is True


def _pair_distance(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
    """Compute minimal surface-to-surface distance between two meshes.
    
    First checks for intersection using AABB + FCL. If meshes intersect,
    returns 0.0 immediately. Otherwise uses trimesh ProximityQuery (BVH-based)
    for efficient nearest-point lookup, sampling vertices from both meshes
    and taking the global minimum.
    
    Works on any mesh (convex or non-convex).
    
    Returns:
        Minimum distance in model units (0.0 if meshes intersect/touch).
    """
    if _meshes_intersect(a, b):
        return 0.0
    
    prox_a = ProximityQuery(a)
    prox_b = ProximityQuery(b)
    
    result_a = prox_a.on_surface(b.vertices)
    result_b = prox_b.on_surface(a.vertices)
    
    dist_a = result_a[1]
    dist_b = result_b[1]
    
    return float(min(dist_a.min(), dist_b.min()))


_IMPLEMENTED_MODES = {"volume", "surface_area", "projected_area", "component_height", "distance_between"}


@node()
async def measurement(
    settings: MeasurementSettings,
    inputs: MeasurementInputs,
    context: ExecutionContext,
) -> MeasurementResult:
    if settings.measurement_type not in _IMPLEMENTED_MODES:
        raise ValueError(f"Measurement type '{settings.measurement_type}' is not implemented yet.")

    if settings.measurement_type == "distance_between":
        return _compute_distance_between(context, inputs.list_a, inputs.list_b)

    resolved = _resolve_keys(context, inputs.list_a)

    measurements: list[MeasurementItem] = []

    for ref_label, cache_key in resolved:
        if cache_key is None:
            measurements.append(MeasurementItem(reference=ref_label, value=None, error="no cached geometry"))
            continue

        try:
            mesh = resolve_mesh(context, cache_key)
        except ValueError as exc:
            measurements.append(MeasurementItem(reference=ref_label, value=None, error=str(exc)))
            continue

        if settings.measurement_type == "volume":
            repaired, error = ensure_watertight(mesh)
            if repaired is None:
                measurements.append(MeasurementItem(reference=cache_key, value=None, error=f"non-watertight: {error}"))
            else:
                measurements.append(MeasurementItem(reference=cache_key, value=repaired.volume, error=None))

        elif settings.measurement_type == "surface_area":
            measurements.append(MeasurementItem(reference=cache_key, value=mesh.area, error=None))

        elif settings.measurement_type == "projected_area":
            normal = settings.projection_normal
            projected_path = mesh.projected(normal=normal)
            measurements.append(MeasurementItem(reference=cache_key, value=projected_path.area, error=None))

        elif settings.measurement_type == "component_height":
            direction = settings.direction
            norm = np.linalg.norm(direction)
            if norm == 0:
                measurements.append(MeasurementItem(reference=cache_key, value=None, error="undefined direction"))
                continue
            d_hat = np.array(direction) / norm
            extent = np.ptp(mesh.vertices @ d_hat)
            measurements.append(MeasurementItem(reference=cache_key, value=float(extent), error=None))

    if settings.measurement_type == "volume":
        unit = "volume_unit"
    elif settings.measurement_type in {"surface_area", "projected_area"}:
        unit = "area_unit"
    else:  # component_height, distance_between
        unit = "length_unit"

    return MeasurementResult(
        type=settings.measurement_type,
        unit=unit,
        measurements=measurements,
    )
