from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.measurement.measurement import (
    MeasurementInputs,
    MeasurementResult,
    MeasurementSettings,
    measurement,
)
from openbim_runner.util.geometry import cache_mesh


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, object()), node_outputs={})


def _box(context: ExecutionContext, express_id: int, translation: list[float], extents: list[float] | None = None) -> None:
    mesh = trimesh.creation.box(extents=extents or [2, 2, 2])
    mesh.apply_translation(translation)
    cache_mesh(context, mesh, express_id=express_id)


def _run(
    settings: MeasurementSettings,
    inputs: MeasurementInputs,
    context: ExecutionContext,
) -> MeasurementResult:
    return asyncio.run(measurement(settings, inputs, context))


def test_measurement_volume_single_element() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=[1]),
        context,
    )

    assert result.type == "volume"
    assert result.unit == "volume_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(24.0)
    assert result.measurements[0].error is None


def test_measurement_surface_area_single_element() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(elements=[1]),
        context,
    )

    assert result.type == "surface_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(52.0)
    assert result.measurements[0].error is None


def test_measurement_volume_multiple_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [10, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=[1, 2]),
        context,
    )

    assert result.type == "volume"
    assert result.unit == "volume_unit"
    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[1].reference == "ifc:2"
    assert result.measurements[1].value == pytest.approx(8.0)


def test_measurement_missing_geometry_returns_null() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=[1, 999]),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_empty_elements_uses_whole_model() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [10, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=[]),
        context,
    )

    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1", "ifc:2"}


def test_measurement_with_object_id() -> None:
    context = _context()
    mesh = trimesh.creation.box(extents=[3, 3, 3])
    cache_mesh(context, mesh, object_id="mycube")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=["mycube"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:mycube"
    assert result.measurements[0].value == pytest.approx(27.0)


def test_measurement_with_full_cache_key() -> None:
    context = _context()
    mesh = trimesh.creation.box(extents=[5, 5, 5])
    cache_mesh(context, mesh, key="inter:custom_key")

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(elements=["inter:custom_key"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "inter:custom_key"
    assert result.measurements[0].value == pytest.approx(150.0)


def test_measurement_non_watertight_volume_returns_error() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="broken")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=["broken"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:broken"
    assert result.measurements[0].value is None
    assert result.measurements[0].error is not None
    assert "non-watertight" in result.measurements[0].error


def test_measurement_non_watertight_surface_area_still_works() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="broken")

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(elements=["broken"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:broken"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


def test_measurement_unimplemented_mode_raises() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    for mode in ["projected_area", "component_height", "distance_between", "distance_to_reference"]:
        with pytest.raises(ValueError, match=f"Measurement type '{mode}' is not implemented yet"):
            _run(
                MeasurementSettings(measurement_type=mode),  # type: ignore[arg-type]
                MeasurementInputs(elements=[1]),
                context,
            )


def test_measurement_mixed_refs_with_missing() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    cache_mesh(context, mesh, object_id="cube")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=[1, "cube", 999]),
        context,
    )

    assert len(result.measurements) == 3
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[1].reference == "gen:cube"
    assert result.measurements[1].value == pytest.approx(8.0)
    assert result.measurements[2].reference == "999"
    assert result.measurements[2].value is None
    assert result.measurements[2].error == "no cached geometry"


def test_measurement_with_intersection_meshes_dict() -> None:
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    cache_mesh(context, mesh1, key="inter:intersection_ifc:1_ifc:2")
    cache_mesh(context, mesh2, key="inter:intersection_ifc:3_ifc:4")

    intersection_meshes = {
        "ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2",
        "ifc:3__ifc:4": "inter:intersection_ifc:3_ifc:4",
        "ifc:5__ifc:6": None,
    }

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(elements=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "inter:intersection_ifc:1_ifc:2"
    assert result.measurements[0].value == pytest.approx(0.125)
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "inter:intersection_ifc:3_ifc:4"
    assert result.measurements[1].value == pytest.approx(1.0)
    assert result.measurements[1].error is None


def test_measurement_with_intersection_meshes_dict_surface_area() -> None:
    context = _context()
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    cache_mesh(context, mesh, key="inter:intersection_ifc:1_ifc:2")

    intersection_meshes = {
        "ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2",
        "ifc:3__ifc:4": None,
    }

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(elements=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "inter:intersection_ifc:1_ifc:2"
    assert result.measurements[0].value == pytest.approx(24.0)
    assert result.measurements[0].error is None
