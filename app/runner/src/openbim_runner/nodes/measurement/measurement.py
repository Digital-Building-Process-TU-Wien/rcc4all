from __future__ import annotations

from typing import Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import ensure_watertight, resolve_mesh


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
        description="The type of measurement to compute. In v1, only 'volume' and 'surface_area' are implemented.",
    )


class MeasurementInputs(NodeModel):
    elements: list[int | str] | dict[str, str | None] = Field(
        default=[],
        title="Elements",
        description=(
            "List of element references to measure — mix of express IDs (int → `ifc:<id>`), "
            "object IDs (str → `gen:<id>`), and full geometry-cache keys (`ifc:`, `gen:`, `inter:`). "
            "When empty, the whole model is used. "
            "Also accepts a dict (e.g., collision node's `intersection_meshes` output); "
            "in this case, the dict's non-null values (intersection mesh cache keys) are measured."
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
    refs = refs or {}

    if not refs:
        return [(key, key) for key in cache.keys()]

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


_IMPLEMENTED_MODES = {"volume", "surface_area"}


@node()
async def measurement(
    settings: MeasurementSettings,
    inputs: MeasurementInputs,
    context: ExecutionContext,
) -> MeasurementResult:
    if settings.measurement_type not in _IMPLEMENTED_MODES:
        raise ValueError(f"Measurement type '{settings.measurement_type}' is not implemented yet.")

    resolved = _resolve_keys(context, inputs.elements)

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

    unit = "volume_unit" if settings.measurement_type == "volume" else "area_unit"

    return MeasurementResult(
        type=settings.measurement_type,
        unit=unit,
        measurements=measurements,
    )
