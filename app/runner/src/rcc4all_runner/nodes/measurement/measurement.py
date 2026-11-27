from __future__ import annotations

import sys
from typing import Literal

import numpy as np
import trimesh
from pydantic import Field, FiniteFloat
from trimesh.proximity import ProximityQuery

from rcc4all_runner.nodes.base import ExecutionContext, NodeModel, node
from rcc4all_runner.util.geometry import (
    ensure_watertight,
    fcl_surface_distance,
    resolve_keys,
    resolve_mesh,
    unit_vector,
)

MeasurementType = Literal[
    "volume",
    "surface_area",
    "component_height",
    "distance_between",
    "distance_to_reference",
]


class MeasurementSettings(NodeModel):
    measurement_type: MeasurementType = Field(
        default="volume",
        title="Measurement Type",
        description="The type of measurement to compute: 'volume', 'surface_area', 'component_height', 'distance_between', 'distance_to_reference'.",
    )
    direction: list[FiniteFloat] = Field(
        default=[0.0, 0.0, 1.0],
        title="Direction",
        min_length=3,
        max_length=3,
        description=(
            "Direction vector [x, y, z] for extent computation. Default [0,0,1] computes "
            "vertical height. Only used for 'component_height' mode. All three values "
            "must be finite. Normalized internally."
        ),
    )
    reference_type: Literal["point", "plane"] = Field(
        default="point",
        title="Reference Type",
        description="Reference type for 'distance_to_reference' mode. 'point' computes distance to a reference point; 'plane' computes perpendicular distance to a reference plane.",
    )
    reference_point: list[FiniteFloat] = Field(
        default=[0.0, 0.0, 0.0],
        title="Reference Point",
        min_length=3,
        max_length=3,
        description=(
            "Reference point coordinates [x, y, z] in metres. Used for both 'point' "
            "and 'plane' reference types (plane origin for 'plane'). All three "
            "values must be finite."
        ),
    )
    reference_normal: list[FiniteFloat] = Field(
        default=[0.0, 0.0, 1.0],
        title="Reference Normal",
        min_length=3,
        max_length=3,
        description=(
            "Plane normal vector [x, y, z]. Only used for 'distance_to_reference' "
            "mode with reference_type='plane'. All three values must be finite. "
            "Normalized internally; zero normal results in an error entry."
        ),
    )


class MeasurementInputs(NodeModel):
    list_a: list[str] | dict[str, str | None] = Field(
        default=[],
        title="List A",
        description=(
            "First list of fully qualified geometry cache keys — `<slug>:expr:<id>` for IFC "
            "elements, `gen:<object_id>` for generated geometry, `inter:<id>` for helper/intersection "
            "geometry — in the order to test. An empty list yields zero measurements. Also accepts a "
            "dict (e.g., collision node's `intersection_meshes` output); in this case, the dict's "
            "non-null values (intersection mesh cache keys) are used."
        ),
    )
    list_b: list[str] | dict[str, str | None] = Field(
        default=[],
        title="List B",
        description=(
            "Second (optional) list of fully qualified geometry cache keys. When empty, pairs are "
            "formed within List A. When non-empty, computes cartesian product AxB. Also accepts a "
            "dict (e.g., collision node's `intersection_meshes` output); non-null values are used "
            "as cache keys. A dict whose values are all null is treated like an empty List B."
        ),
    )


class MeasurementItem(NodeModel):
    reference: str = Field(
        title="Reference",
        description="The geometry cache key (e.g., `main:expr:63`, `gen:mycube`, `inter:...`) of the measured element, or the raw input when no geometry was found.",
    )
    value: float | None = Field(
        default=None,
        title="Value",
        description="The measured value. Null if geometry is missing or measurement failed.",
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason if measurement failed (e.g., 'no cached geometry', 'non-watertight', 'empty geometry').",
    )


class MeasurementResult(NodeModel):
    type: MeasurementType = Field(
        title="Type",
        description="The measurement type used to generate this result.",
    )
    unit: str = Field(
        title="Unit",
        description=(
            "The unit of measurement ('volume_unit' for volume, 'area_unit' for area and "
            "'length_unit' for distance). Cached IFC geometry is tessellated in metres, so "
            "values are m³, m² or m."
        ),
    )
    measurements: list[MeasurementItem] = Field(
        default=[],
        title="Measurements",
        description="List of per-element measurements.",
    )


def _is_empty_mesh(mesh: trimesh.Trimesh) -> bool:
    """True for a mesh with no vertices or no faces (nothing measurable)."""
    return len(mesh.vertices) == 0 or len(mesh.faces) == 0


def _compute_distance_between(
    context: ExecutionContext,
    list_a: list[str] | dict[str, str | None],
    list_b: list[str] | dict[str, str | None],
) -> MeasurementResult:
    """Compute minimal surface-to-surface distance between element pairs.

    Behavior:
        - list_b empty after null-value filtering: all unordered pairs within
          list_a (n choose 2), emit both directions. A dict whose values are
          all null therefore behaves like an empty List B.
        - list_b non-empty: cartesian product AxB (skip self-pairs), emit one
          direction per pair.
        - Reference format: {key_a}_{key_b} (directional, NOT sorted).
        - Distances are exact (FCL triangle-BVH surface distance, positive for
          nested non-touching surfaces) and computed once per unordered pair.
        - Missing geometry, empty meshes, and backend failures yield per-pair
          error items ('no cached geometry', 'empty geometry',
          'distance computation failed') instead of approximate values.

    Unit: length_unit (metres)
    """
    resolved_a = resolve_keys(context, list_a)
    resolved_b = resolve_keys(context, list_b)
    if not resolved_b:
        resolved_b = resolved_a

    lookup_a = dict(resolved_a)
    lookup_b = dict(resolved_b)
    keys_a = [ref for ref, _ in resolved_a]
    keys_b = [ref for ref, _ in resolved_b]

    meshes: dict[str, trimesh.Trimesh | None] = {}
    pair_results: dict[tuple[str, str], tuple[float | None, str | None]] = {}

    def _mesh_for(key: str, lookup: dict[str, str | None]) -> trimesh.Trimesh | None:
        if key not in meshes:
            mesh, _error = _resolve_reference(context, lookup.get(key))
            meshes[key] = mesh
        return meshes[key]

    def _pair_result(key_a: str, key_b: str) -> tuple[float | None, str | None]:
        memo_key = (key_a, key_b) if key_a <= key_b else (key_b, key_a)
        if memo_key not in pair_results:
            mesh_a = _mesh_for(key_a, lookup_a)
            mesh_b = _mesh_for(key_b, lookup_b)
            if mesh_a is None or mesh_b is None:
                pair_results[memo_key] = (None, "no cached geometry")
            elif _is_empty_mesh(mesh_a) or _is_empty_mesh(mesh_b):
                pair_results[memo_key] = (None, "empty geometry")
            else:
                distance = fcl_surface_distance(mesh_a, mesh_b)
                if distance is None:
                    print(
                        f"measurement: exact surface distance failed for pair "
                        f"{key_a!r} / {key_b!r}",
                        file=sys.stderr,
                    )
                    pair_results[memo_key] = (None, "distance computation failed")
                else:
                    pair_results[memo_key] = (distance, None)
        return pair_results[memo_key]

    measurements: list[MeasurementItem] = []
    for key_a in keys_a:
        for key_b in keys_b:
            if key_a == key_b:
                continue
            value, error = _pair_result(key_a, key_b)
            measurements.append(
                MeasurementItem(reference=f"{key_a}_{key_b}", value=value, error=error)
            )

    return MeasurementResult(
        type="distance_between",
        unit="length_unit",
        measurements=measurements,
    )


def _resolve_reference(
    context: ExecutionContext,
    cache_key: str | None,
) -> tuple[trimesh.Trimesh | None, str | None]:
    """Resolve a cache key into a mesh or an error.

    Returns (mesh, None) on success, or (None, error_message) on failure.
    All failures return "no cached geometry" for consistency.
    """
    if cache_key is None:
        return None, "no cached geometry"
    try:
        return resolve_mesh(context, cache_key), None
    except ValueError:
        return None, "no cached geometry"


def _compute_distance_to_reference(
    context: ExecutionContext,
    list_a: list[str] | dict[str, str | None],
    reference_type: Literal["point", "plane"],
    reference_point: list[float],
    reference_normal: list[float],
) -> MeasurementResult:
    """Compute absolute distance from each element to a reference point or plane.

    Behavior:
        - reference_type="point": min surface distance from the reference point
          to each element via ProximityQuery (works on any mesh).
        - reference_type="plane": min over referenced vertices of
          |(v - origin)·n̂| — the perpendicular distance to the plane, 0.0
          when the plane crosses the mesh. Vertices not referenced by any
          face are ignored; they are not part of the surface.
        - Zero normal for plane mode → error entry "undefined normal".
        - Empty meshes → error entry "empty geometry".
        - Unexpected backend failures are isolated per item
          ("measurement failed") and logged to stderr.

    Unit: length_unit (metres)
    """
    resolved = resolve_keys(context, list_a)
    measurements: list[MeasurementItem] = []

    normal_unit = unit_vector(reference_normal) if reference_type == "plane" else None
    origin = np.asarray(reference_point, dtype=float)

    if reference_type == "plane" and normal_unit is None:
        for ref_label, _ in resolved:
            measurements.append(
                MeasurementItem(
                    reference=ref_label, value=None, error="undefined normal"
                )
            )
        return MeasurementResult(
            type="distance_to_reference",
            unit="length_unit",
            measurements=measurements,
        )

    for ref_label, cache_key in resolved:
        mesh, error = _resolve_reference(context, cache_key)
        if error:
            measurements.append(
                MeasurementItem(reference=ref_label, value=None, error=error)
            )
            continue

        # mesh is guaranteed non-None here
        assert mesh is not None

        if _is_empty_mesh(mesh):
            measurements.append(
                MeasurementItem(reference=ref_label, value=None, error="empty geometry")
            )
            continue

        try:
            if reference_type == "point":
                prox = ProximityQuery(mesh)
                result = prox.on_surface(origin.reshape(1, 3))
                dist = float(abs(result[1][0]))
                measurements.append(
                    MeasurementItem(reference=ref_label, value=dist, error=None)
                )
            else:  # plane
                assert normal_unit is not None
                vertices = mesh.vertices[mesh.referenced_vertices]
                if len(vertices) == 0:
                    measurements.append(
                        MeasurementItem(
                            reference=ref_label, value=None, error="empty geometry"
                        )
                    )
                    continue
                signed_dists = (vertices - origin) @ normal_unit
                if signed_dists.min() <= 0 <= signed_dists.max():
                    min_dist = 0.0
                else:
                    min_dist = float(np.abs(signed_dists).min())
                measurements.append(
                    MeasurementItem(reference=ref_label, value=min_dist, error=None)
                )
        except Exception as exc:
            print(
                f"measurement: distance to reference failed for {ref_label!r} "
                f"({type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
            measurements.append(
                MeasurementItem(
                    reference=ref_label, value=None, error="measurement failed"
                )
            )

    return MeasurementResult(
        type="distance_to_reference",
        unit="length_unit",
        measurements=measurements,
    )


@node()
async def measurement(
    settings: MeasurementSettings,
    inputs: MeasurementInputs,
    context: ExecutionContext,
) -> MeasurementResult:
    if settings.measurement_type == "distance_between":
        return _compute_distance_between(context, inputs.list_a, inputs.list_b)

    if settings.measurement_type == "distance_to_reference":
        return _compute_distance_to_reference(
            context,
            inputs.list_a,
            settings.reference_type,
            settings.reference_point,
            settings.reference_normal,
        )

    resolved = resolve_keys(context, inputs.list_a)

    measurements: list[MeasurementItem] = []
    direction_unit = (
        unit_vector(settings.direction)
        if settings.measurement_type == "component_height"
        else None
    )

    for ref_label, cache_key in resolved:
        mesh, error = _resolve_reference(context, cache_key)
        if error:
            measurements.append(
                MeasurementItem(reference=ref_label, value=None, error=error)
            )
            continue

        # mesh is guaranteed non-None here (error would be set otherwise)
        assert mesh is not None
        assert cache_key is not None

        try:
            if settings.measurement_type == "volume":
                repaired, repair_error = ensure_watertight(mesh)
                if repaired is None:
                    assert repair_error is not None
                    measurements.append(
                        MeasurementItem(
                            reference=cache_key, value=None, error=repair_error
                        )
                    )
                else:
                    measurements.append(
                        MeasurementItem(
                            reference=cache_key, value=repaired.volume, error=None
                        )
                    )

            elif settings.measurement_type == "surface_area":
                measurements.append(
                    MeasurementItem(reference=cache_key, value=mesh.area, error=None)
                )

            else:  # component_height
                if direction_unit is None:
                    measurements.append(
                        MeasurementItem(
                            reference=cache_key,
                            value=None,
                            error="undefined direction",
                        )
                    )
                    continue
                # Only vertices referenced by at least one face are part of
                # the actual surface; unreferenced vertices are ignored.
                vertices = mesh.vertices[mesh.referenced_vertices]
                if len(vertices) == 0:
                    measurements.append(
                        MeasurementItem(
                            reference=cache_key, value=None, error="empty geometry"
                        )
                    )
                    continue
                extent = float(np.ptp(vertices @ direction_unit))
                measurements.append(
                    MeasurementItem(reference=cache_key, value=extent, error=None)
                )

        except Exception as exc:
            print(
                f"measurement: {settings.measurement_type} failed for "
                f"{cache_key!r} ({type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
            measurements.append(
                MeasurementItem(
                    reference=cache_key, value=None, error="measurement failed"
                )
            )

    if settings.measurement_type == "volume":
        unit = "volume_unit"
    elif settings.measurement_type == "surface_area":
        unit = "area_unit"
    else:  # component_height
        unit = "length_unit"

    return MeasurementResult(
        type=settings.measurement_type,
        unit=unit,
        measurements=measurements,
    )
