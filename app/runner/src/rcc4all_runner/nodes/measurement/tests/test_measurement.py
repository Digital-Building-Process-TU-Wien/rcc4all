from __future__ import annotations

import asyncio
import importlib
from typing import Any, cast

import numpy as np
import pytest
import trimesh
from pydantic import ValidationError

from conftest import main_ref as _ref
from rcc4all_runner.nodes.base import ExecutionContext
from rcc4all_runner.nodes.geometry_projection.geometry_projection import (
    GeometryProjectionInputs,
    GeometryProjectionSettings,
    geometry_projection,
)
from rcc4all_runner.nodes.measurement.measurement import (
    MeasurementInputs,
    MeasurementResult,
    MeasurementSettings,
    measurement,
)
from rcc4all_runner.util.geometry import cache_mesh

measurement_module = importlib.import_module(
    "rcc4all_runner.nodes.measurement.measurement"
)


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, object()), node_outputs={})


def _box(
    context: ExecutionContext,
    express_id: int,
    translation: list[float],
    extents: list[float] | None = None,
) -> None:
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
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "volume"
    assert result.unit == "volume_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(24.0)
    assert result.measurements[0].error is None


def test_measurement_surface_area_single_element() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "surface_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(52.0)
    assert result.measurements[0].error is None


def test_measurement_volume_multiple_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [10, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "volume"
    assert result.unit == "volume_unit"
    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[1].reference == "main:expr:2"
    assert result.measurements[1].value == pytest.approx(8.0)


def test_measurement_missing_geometry_returns_null() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=[_ref(1), _ref(999)]),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "main:expr:999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_empty_list_yields_no_measurements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [10, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=[]),
        context,
    )

    assert len(result.measurements) == 0


def test_measurement_with_object_id() -> None:
    context = _context()
    mesh = trimesh.creation.box(extents=[3, 3, 3])
    cache_mesh(context, mesh, object_id="mycube")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=["gen:mycube"]),
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
        MeasurementInputs(list_a=["inter:custom_key"]),
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
        MeasurementInputs(list_a=["gen:broken"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:broken"
    assert result.measurements[0].value is None
    # Exactly the error ensure_watertight reports — no duplicated prefix.
    assert result.measurements[0].error == "non-watertight"


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
        MeasurementInputs(list_a=["gen:broken"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:broken"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


def test_measurement_mixed_refs_with_missing() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    cache_mesh(context, mesh, object_id="cube")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=[_ref(1), "gen:cube", "main:expr:999"]),
        context,
    )

    assert len(result.measurements) == 3
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[1].reference == "gen:cube"
    assert result.measurements[1].value == pytest.approx(8.0)
    assert result.measurements[2].reference == "main:expr:999"
    assert result.measurements[2].value is None
    assert result.measurements[2].error == "no cached geometry"


def test_measurement_with_intersection_meshes_dict() -> None:
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    cache_mesh(context, mesh1, key="inter:intersection_main:expr:1_main:expr:2")
    cache_mesh(context, mesh2, key="inter:intersection_main:expr:3_main:expr:4")

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
        "main:expr:5__main:expr:6": None,
    }

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 2
    assert (
        result.measurements[0].reference == "inter:intersection_main:expr:1_main:expr:2"
    )
    assert result.measurements[0].value == pytest.approx(0.125)
    assert result.measurements[0].error is None
    assert (
        result.measurements[1].reference == "inter:intersection_main:expr:3_main:expr:4"
    )
    assert result.measurements[1].value == pytest.approx(1.0)
    assert result.measurements[1].error is None


def test_measurement_dict_reports_missing_and_invalid_cache_keys() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), key="bare_key")

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(
            list_a={
                "missing_pair": "inter:missing",
                "invalid_pair": "bare_key",
                "no_intersection": None,
            }
        ),
        context,
    )

    assert [
        (item.reference, item.value, item.error) for item in result.measurements
    ] == [
        ("inter:missing", None, "no cached geometry"),
        ("bare_key", None, "no cached geometry"),
    ]


def test_measurement_with_intersection_meshes_dict_surface_area() -> None:
    context = _context()
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    cache_mesh(context, mesh, key="inter:intersection_main:expr:1_main:expr:2")

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": None,
    }

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 1
    assert (
        result.measurements[0].reference == "inter:intersection_main:expr:1_main:expr:2"
    )
    assert result.measurements[0].value == pytest.approx(24.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_default_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 0.0, 1.0]
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(4.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_direction_x() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[1.0, 0.0, 0.0]
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(2.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_direction_y() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 1.0, 0.0]
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(3.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_diagonal_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[1.0, 1.0, 0.0]
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(5.0 / np.sqrt(2), abs=0.01)
    assert result.measurements[0].error is None


def test_measurement_component_height_non_watertight() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="open")

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 0.0, 1.0]
        ),
        MeasurementInputs(list_a=["gen:open"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:open"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


def test_measurement_component_height_missing_geometry() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 0.0, 1.0]
        ),
        MeasurementInputs(list_a=[_ref(1), _ref(999)]),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "main:expr:999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_component_height_dict_input() -> None:
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    cache_mesh(context, mesh1, key="inter:intersection_main:expr:1_main:expr:2")
    cache_mesh(context, mesh2, key="inter:intersection_main:expr:3_main:expr:4")

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
        "main:expr:5__main:expr:6": None,
    }

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 0.0, 1.0]
        ),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 2
    assert (
        result.measurements[0].reference == "inter:intersection_main:expr:1_main:expr:2"
    )
    assert result.measurements[0].value == pytest.approx(0.5, abs=0.01)
    assert result.measurements[0].error is None
    assert (
        result.measurements[1].reference == "inter:intersection_main:expr:3_main:expr:4"
    )
    assert result.measurements[1].value == pytest.approx(1.0, abs=0.01)
    assert result.measurements[1].error is None


def test_measurement_component_height_zero_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height", direction=[0.0, 0.0, 0.0]
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "undefined direction"


def test_measurement_distance_between_two_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    # Output order: grouped by first element (key_a), iterating all other keys
    assert result.measurements[0].reference == "main:expr:1_main:expr:2"
    assert result.measurements[1].reference == "main:expr:2_main:expr:1"
    for m in result.measurements:
        assert m.value == pytest.approx(4.0)
        assert m.error is None


def test_measurement_distance_between_three_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])
    _box(context, 3, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2), _ref(3)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 6
    # Output order: grouped by first element (key_a), iterating all other keys in order
    # key_a=1: 1_2, 1_3; key_a=2: 2_1, 2_3; key_a=3: 3_1, 3_2
    expected_order = [
        "main:expr:1_main:expr:2",
        "main:expr:1_main:expr:3",
        "main:expr:2_main:expr:1",
        "main:expr:2_main:expr:3",
        "main:expr:3_main:expr:1",
        "main:expr:3_main:expr:2",
    ]
    actual_order = [m.reference for m in result.measurements]
    assert actual_order == expected_order


def test_measurement_distance_between_empty_list_yields_no_measurements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 0


def test_measurement_distance_between_missing_geometry() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2), _ref(999)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 6
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "main:expr:1_main:expr:2",
        "main:expr:2_main:expr:1",
        "main:expr:999_main:expr:1",
        "main:expr:1_main:expr:999",
        "main:expr:999_main:expr:2",
        "main:expr:2_main:expr:999",
    }
    missing_entries = [m for m in result.measurements if "999" in m.reference]
    assert len(missing_entries) == 4
    for entry in missing_entries:
        assert entry.value is None
        assert entry.error == "no cached geometry"


def test_measurement_distance_between_intersecting_boxes() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [1, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:2_main:expr:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(0.0, abs=1e-6)
        assert m.error is None


def test_measurement_distance_between_crossing_plates() -> None:
    """Test intersecting meshes with no vertex penetration (face-interior intersection).

    Two thin plates crossing at right angles: the intersection happens in the
    interior of faces, not at any vertex. This tests that FCL-based intersection
    detection correctly returns 0.0 even when vertex sampling would fail.
    """
    context = _context()

    plate1 = trimesh.creation.box(extents=[4, 4, 0.1])
    plate2 = trimesh.creation.box(extents=[0.1, 4, 4])

    cache_mesh(context, plate1, key="main:expr:1")
    cache_mesh(context, plate2, key="main:expr:2")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:2_main:expr:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(0.0, abs=1e-6)
        assert m.error is None


def test_measurement_distance_between_dict_input() -> None:
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    cache_mesh(context, mesh1, key="inter:intersection_main:expr:1_main:expr:2")
    cache_mesh(context, mesh2, key="inter:intersection_main:expr:3_main:expr:4")

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
        "main:expr:5__main:expr:6": None,
    }

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "inter:intersection_main:expr:1_main:expr:2_inter:intersection_main:expr:3_main:expr:4",
        "inter:intersection_main:expr:3_main:expr:4_inter:intersection_main:expr:1_main:expr:2",
    }
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_between_mixed_refs() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    mesh = trimesh.creation.box(extents=[2, 2, 2])
    cache_mesh(context, mesh, object_id="cube")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), "gen:cube"]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"gen:cube_main:expr:1", "main:expr:1_gen:cube"}
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_between_non_watertight() -> None:
    context = _context()
    open_mesh1 = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    open_mesh2 = trimesh.Trimesh(
        vertices=[[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 1, 5]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh1, object_id="open1")
    cache_mesh(context, open_mesh2, object_id="open2")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["gen:open1", "gen:open2"]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"gen:open1_gen:open2", "gen:open2_gen:open1"}
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_between_alignment_with_signal() -> None:
    """Alignment (no Body geometry) + signal (has geometry) -> error entries.

    Simulates the Simple_Railway-Civil_3D.ifc scenario:
    - Alignment id=49 has no Body tessellation -> not in cache
    - Signal id=757 has Body geometry -> in cache
    Result: two error entries (both directions).
    """
    context = _context()
    _box(context, 757, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["main:expr:49", _ref(757)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:49_main:expr:757", "main:expr:757_main:expr:49"}
    for m in result.measurements:
        assert m.value is None
        assert m.error == "no cached geometry"


def test_measurement_distance_between_two_alignments() -> None:
    """Two alignments (both no Body geometry) -> error entries.

    Simulates the Simple_Railway-Civil_3D.ifc scenario:
    - Alignment id=49 and id=570 both have no Body tessellation
    Result: two error entries (both directions).
    """
    context = _context()

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["main:expr:49", "main:expr:570"]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:49_main:expr:570", "main:expr:570_main:expr:49"}
    for m in result.measurements:
        assert m.value is None
        assert m.error == "no cached geometry"


def test_measurement_distance_between_list_a_cross_list_b() -> None:
    """List_A x List_B cartesian product with one direction per pair."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])
    _box(context, 3, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1)], list_b=[_ref(2), _ref(3)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:1_main:expr:3"}


def test_measurement_distance_between_self_pair_skipped() -> None:
    """Self-pairs (key_a == key_b) are skipped."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)], list_b=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:2_main:expr:1"}


def test_measurement_distance_between_list_a_cross_list_b_dict() -> None:
    """List_A x List_B cartesian product where both are dicts (intersection_meshes)."""
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    mesh3 = trimesh.creation.box(extents=[1.5, 1.5, 1.5])
    cache_mesh(context, mesh1, key="inter:intersection_main:expr:1_main:expr:2")
    cache_mesh(context, mesh2, key="inter:intersection_main:expr:3_main:expr:4")
    cache_mesh(context, mesh3, key="inter:intersection_main:expr:5_main:expr:6")

    intersection_meshes_a: dict[str, str | None] = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
    }
    intersection_meshes_b: dict[str, str | None] = {
        "main:expr:5__main:expr:6": "inter:intersection_main:expr:5_main:expr:6",
    }

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=intersection_meshes_a, list_b=intersection_meshes_b),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    # Cross product: 2 elements in A x 1 element in B = 2 measurements
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "inter:intersection_main:expr:1_main:expr:2_inter:intersection_main:expr:5_main:expr:6",
        "inter:intersection_main:expr:3_main:expr:4_inter:intersection_main:expr:5_main:expr:6",
    }
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_to_reference_point() -> None:
    """Point distance: box centered at origin [-1,-1,-1] to [1,1,1], reference point at [5,0,0] -> distance 4.0."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[5.0, 0.0, 0.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(4.0)
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_point_on_surface() -> None:
    """Point on surface -> distance 0.0."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[1.0, 0.0, 0.0],  # on surface at x=1
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(0.0, abs=1e-6)
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_plane() -> None:
    """Plane z=0, normal [0,0,1], box centered at [0,0,2] spans z=1..3 -> min distance 1.0."""
    context = _context()
    _box(context, 1, [0, 0, 2], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(1.0)
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_plane_tilted() -> None:
    """Plane with tilted normal: box centered at origin spans x=-1..1, YZ plane (x=0) crosses box -> distance 0.0."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[1.0, 0.0, 0.0],  # YZ plane
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value == pytest.approx(
        0.0, abs=1e-6
    )  # box crosses plane at x=0


def test_measurement_distance_to_reference_plane_zero_normal() -> None:
    """Plane with zero normal -> error entry 'undefined normal'."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[0.0, 0.0, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "undefined normal"


def test_measurement_distance_to_reference_missing_geometry() -> None:
    """Missing geometry -> error entry 'no cached geometry'."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[5.0, 0.0, 0.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=[_ref(1), _ref(999)]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "main:expr:1"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "main:expr:999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_distance_to_reference_dict_input() -> None:
    """Dict input (intersection_meshes) support."""
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    cache_mesh(context, mesh1, key="inter:intersection_main:expr:1_main:expr:2")
    cache_mesh(context, mesh2, key="inter:intersection_main:expr:3_main:expr:4")

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
        "main:expr:5__main:expr:6": None,
    }

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[0.0, 0.0, 5.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "inter:intersection_main:expr:1_main:expr:2",
        "inter:intersection_main:expr:3_main:expr:4",
    }
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_to_reference_empty_list_yields_no_measurements() -> None:
    """Empty list_a yields zero measurements."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[0.0, 0.0, 5.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=[]),
        context,
    )

    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 0


def test_measurement_distance_to_reference_non_watertight() -> None:
    """Non-watertight mesh still computes (works on any mesh)."""
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="open")

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[0.5, 0.5, 2.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=["gen:open"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:open"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


def test_measurement_surface_area_equivalence_to_geometry_projection() -> None:
    """geometry_projection + surface_area reproduces the former projected_area result.

    Regression guard for the removal of the `projected_area` measurement mode:
    projecting a mesh with the `geometry_projection` node and measuring the
    generated footprint with `surface_area` yields the same footprint area the
    old `projected_area` node reported for that normal.
    """
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    proj_result = asyncio.run(
        geometry_projection(
            GeometryProjectionSettings(projection_normal=[0.0, 0.0, 1.0]),
            GeometryProjectionInputs(liste_a=[_ref(1)]),
            context,
        )
    )
    assert proj_result.errors == []
    generated_key = proj_result.projected_geometries[_ref(1)]

    result = _run(
        MeasurementSettings(measurement_type="surface_area"),
        MeasurementInputs(list_a=[generated_key]),
        context,
    )

    assert result.type == "surface_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == generated_key
    # Footprint of a [2,3,4] box projected onto the XY plane = 2 * 3 = 6.
    assert result.measurements[0].value == pytest.approx(6.0, abs=1e-9)
    assert result.measurements[0].error is None


# ---------------------------------------------------------------------------
# Exact surface-distance regressions (FCL triangle BVHs)
# ---------------------------------------------------------------------------


def test_measurement_distance_between_nested_boxes_positive_distance() -> None:
    """A closed mesh wholly inside another measures its surface gap, not 0.0.

    The inner box faces are 4.0 away from the outer box faces on every side;
    solid-collision semantics would wrongly report 0.0 here.
    """
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[10, 10, 10])
    _box(context, 2, [0, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:2_main:expr:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(4.0)
        assert m.error is None


def test_measurement_distance_between_nested_translated_box() -> None:
    """Inner box translated [2,0,0] inside a [10,10,10] box -> gap 2.0."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[10, 10, 10])
    _box(context, 2, [2, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == pytest.approx(2.0)
        assert m.error is None


def test_measurement_distance_between_perpendicular_open_plates() -> None:
    """Closest points in edge/face interiors, away from any vertex.

    Two perpendicular open plates whose true separation is 1.0. The former
    vertex-sampled implementation reported ~2.147 here.
    """
    context = _context()
    plate_a = trimesh.Trimesh(
        vertices=[[-2, -0.1, 0], [2, -0.1, 0], [2, 0.1, 0], [-2, 0.1, 0]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    plate_b = trimesh.Trimesh(
        vertices=[[-0.1, -2, 1], [0.1, -2, 1], [0.1, 2, 1], [-0.1, 2, 1]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    cache_mesh(context, plate_a, object_id="plate_a")
    cache_mesh(context, plate_b, object_id="plate_b")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["gen:plate_a", "gen:plate_b"]),
        context,
    )

    assert result.type == "distance_between"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"gen:plate_a_gen:plate_b", "gen:plate_b_gen:plate_a"}
    for m in result.measurements:
        assert m.value == pytest.approx(1.0)
        assert m.error is None


def test_measurement_distance_between_open_triangle_inside_box() -> None:
    """An open mesh wholly inside a closed box -> positive surface gap 0.5."""
    context = _context()
    _box(context, 1, [0.5, 0.5, 0.5], extents=[2, 2, 2])
    inner_triangle = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, inner_triangle, object_id="inner")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), "gen:inner"]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == pytest.approx(0.5)
        assert m.error is None


def test_measurement_distance_between_coplanar_overlapping_triangles() -> None:
    """Coplanar overlapping open surfaces -> exactly 0.0 (no solver noise)."""
    context = _context()
    triangle = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, triangle, object_id="tri_a")
    cache_mesh(context, triangle.copy(), object_id="tri_b")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["gen:tri_a", "gen:tri_b"]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == 0.0
        assert m.error is None


def test_measurement_distance_between_face_touching_boxes() -> None:
    """Boxes sharing exactly one face -> 0.0, not an approximate vertex value."""
    context = _context()
    _box(context, 1, [-1, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [1, 0, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == 0.0
        assert m.error is None


def test_measurement_distance_between_nested_nonconvex_tori_positive_distance() -> None:
    """A non-convex mesh wholly inside another non-convex mesh measures its gap.

    The former vertex-sampled / solid-collision semantics reported 0.0 for any
    contained mesh; the exact triangle-BVH surface distance must stay positive.
    """
    context = _context()
    outer = trimesh.creation.torus(5.0, 2.0, major_sections=64, minor_sections=64)
    inner = trimesh.creation.torus(5.0, 1.0, major_sections=64, minor_sections=64)
    assert outer.is_watertight and inner.is_watertight
    assert not outer.is_convex and not inner.is_convex
    cache_mesh(context, outer, object_id="torus_outer")
    cache_mesh(context, inner, object_id="torus_inner")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["gen:torus_outer", "gen:torus_inner"]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == pytest.approx(1.0, abs=0.01)
        assert m.error is None


def test_measurement_distance_between_edge_touching_boxes_exact_zero() -> None:
    """Boxes sharing exactly one edge measure 0.0, not a small approximation."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [2, 2, 0], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == 0.0
        assert m.error is None


def test_measurement_distance_between_vertex_touching_boxes_exact_zero() -> None:
    """Boxes sharing exactly one vertex measure 0.0, not a small approximation."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [2, 2, 2], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value == 0.0
        assert m.error is None


def test_measurement_distance_between_unreferenced_vertices_ignored() -> None:
    """Vertices not referenced by any face are not part of the surface."""
    context = _context()
    stray_vertex_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0.2, 0.2, 4]],
        faces=[[0, 1, 2]],
        process=False,
    )
    triangle_high = trimesh.Trimesh(
        vertices=[[0, 0, 5], [1, 0, 5], [1, 1, 5]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, stray_vertex_mesh, object_id="stray")
    cache_mesh(context, triangle_high, object_id="high")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=["gen:stray", "gen:high"]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        # The stray vertex at z=4 must not shorten the z=0 -> z=5 gap.
        assert m.value == pytest.approx(5.0)
        assert m.error is None


def test_measurement_distance_between_null_only_list_b_pairs_within_list_a() -> None:
    """A dict List B whose values are all null behaves like an empty List B."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)], list_b={"pair": None}),
        context,
    )

    assert result.type == "distance_between"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"main:expr:1_main:expr:2", "main:expr:2_main:expr:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(4.0)
        assert m.error is None


def test_measurement_distance_between_symmetric_pair_computed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both directions are emitted but each unordered pair is computed once."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])
    _box(context, 3, [10, 0, 0], extents=[1, 1, 1])

    calls = 0
    original = measurement_module.fcl_surface_distance

    def counted_distance(
        mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh
    ) -> float | None:
        nonlocal calls
        calls += 1
        return original(mesh_a, mesh_b)

    monkeypatch.setattr(measurement_module, "fcl_surface_distance", counted_distance)

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2), _ref(3)]),
        context,
    )

    assert len(result.measurements) == 6
    assert calls == 3
    for m in result.measurements:
        assert m.error is None


def _failing_distance_stub(
    mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh
) -> float | None:
    """Stand-in for ``fcl_surface_distance`` that reports a backend failure."""
    return None


def test_measurement_distance_between_backend_failure_reports_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An FCL backend failure yields a per-pair error, not an approximation."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    monkeypatch.setattr(
        measurement_module, "fcl_surface_distance", _failing_distance_stub
    )

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.reference in {
            "main:expr:1_main:expr:2",
            "main:expr:2_main:expr:1",
        }
        assert m.value is None
        assert m.error == "distance computation failed"
    captured = capsys.readouterr()
    assert "exact surface distance failed" in captured.err


# ---------------------------------------------------------------------------
# Per-item exception isolation (unexpected backend failures)
# ---------------------------------------------------------------------------


def test_measurement_distance_to_reference_backend_exception_isolated_per_item(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unexpected per-item failure is isolated and the batch continues."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [5, 0, 0], extents=[2, 2, 2])

    original = measurement_module.ProximityQuery
    calls = [0]

    class FlakyProximityQuery:
        def __init__(self, mesh: trimesh.Trimesh) -> None:
            if calls[0] == 0:
                calls[0] += 1
                raise RuntimeError("proximity backend exploded")
            calls[0] += 1
            self._inner = original(mesh)

        def on_surface(self, points: Any) -> Any:
            return self._inner.on_surface(points)

    monkeypatch.setattr(measurement_module, "ProximityQuery", FlakyProximityQuery)

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[0.0, 0.0, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    first, second = result.measurements
    assert first.reference == _ref(1)
    assert first.value is None
    assert first.error == "measurement failed"
    assert second.reference == _ref(2)
    assert second.value == pytest.approx(4.0)
    assert second.error is None

    captured = capsys.readouterr()
    assert "distance to reference failed" in captured.err
    assert "RuntimeError" in captured.err
    assert _ref(1) in captured.err


def test_measurement_volume_backend_exception_isolated_per_item(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The main measurement loop isolates an unexpected volume failure per item."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])
    _box(context, 2, [0, 0, 0], extents=[1, 1, 1])

    original = measurement_module.ensure_watertight
    calls = [0]

    def flaky_ensure_watertight(mesh: trimesh.Trimesh) -> Any:
        if calls[0] == 0:
            calls[0] += 1
            raise RuntimeError("repair backend exploded")
        calls[0] += 1
        return original(mesh)

    monkeypatch.setattr(
        measurement_module, "ensure_watertight", flaky_ensure_watertight
    )

    result = _run(
        MeasurementSettings(measurement_type="volume"),
        MeasurementInputs(list_a=[_ref(1), _ref(2)]),
        context,
    )

    assert len(result.measurements) == 2
    first, second = result.measurements
    assert first.reference == _ref(1)
    assert first.value is None
    assert first.error == "measurement failed"
    assert second.reference == _ref(2)
    assert second.value == pytest.approx(1.0)
    assert second.error is None

    captured = capsys.readouterr()
    assert "volume failed" in captured.err
    assert "RuntimeError" in captured.err
    assert _ref(1) in captured.err


# ---------------------------------------------------------------------------
# Empty geometry and unreferenced-vertex regressions
# ---------------------------------------------------------------------------


def _empty_mesh() -> trimesh.Trimesh:
    return trimesh.Trimesh(
        vertices=np.zeros((0, 3)),
        faces=np.zeros((0, 3), dtype=np.int64),
        process=False,
    )


def test_measurement_distance_between_empty_mesh_reports_error() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    cache_mesh(context, _empty_mesh(), object_id="empty")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[_ref(1), "gen:empty"]),
        context,
    )

    assert len(result.measurements) == 2
    for m in result.measurements:
        assert m.value is None
        assert m.error == "empty geometry"


def test_measurement_component_height_empty_mesh_reports_error() -> None:
    context = _context()
    cache_mesh(context, _empty_mesh(), object_id="empty")

    result = _run(
        MeasurementSettings(measurement_type="component_height"),
        MeasurementInputs(list_a=["gen:empty"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:empty"
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "empty geometry"


def test_measurement_distance_to_reference_point_empty_mesh_reports_error() -> None:
    context = _context()
    cache_mesh(context, _empty_mesh(), object_id="empty")

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="point",
            reference_point=[0.0, 0.0, 5.0],
        ),
        MeasurementInputs(list_a=["gen:empty"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "empty geometry"


def test_measurement_distance_to_reference_plane_empty_mesh_reports_error() -> None:
    context = _context()
    cache_mesh(context, _empty_mesh(), object_id="empty")

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=["gen:empty"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "empty geometry"


def test_measurement_component_height_ignores_unreferenced_vertices() -> None:
    """A stray vertex at z=4 must not inflate the z=0 triangle's height."""
    context = _context()
    stray_vertex_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0.2, 0.2, 4]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, stray_vertex_mesh, object_id="stray")

    result = _run(
        MeasurementSettings(measurement_type="component_height"),
        MeasurementInputs(list_a=["gen:stray"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:stray"
    assert result.measurements[0].value == pytest.approx(0.0, abs=1e-9)
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_plane_ignores_unreferenced_vertices() -> (
    None
):
    """Plane z=5 vs a z=0 triangle with a stray z=4 vertex -> 5.0, not 1.0."""
    context = _context()
    stray_vertex_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0.2, 0.2, 4]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, stray_vertex_mesh, object_id="stray")

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 5.0],
            reference_normal=[0.0, 0.0, 1.0],
        ),
        MeasurementInputs(list_a=["gen:stray"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:stray"
    assert result.measurements[0].value == pytest.approx(5.0)
    assert result.measurements[0].error is None


# ---------------------------------------------------------------------------
# Vector validation and numerically safe normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["direction", "reference_point", "reference_normal"],
)
@pytest.mark.parametrize(
    "bad",
    [
        [1.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [float("nan"), 0.0, 1.0],
        [float("inf"), 0.0, 1.0],
    ],
)
def test_measurement_vector_settings_reject_invalid_values(
    field: str, bad: list[float]
) -> None:
    kwargs: dict[str, Any] = {field: bad}
    with pytest.raises(ValidationError):
        MeasurementSettings(**kwargs)


def test_measurement_component_height_extreme_direction_normalized_safely() -> None:
    """[1e308,1e308,0] must not overflow to a zero vector (former bug: 0.0)."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height",
            direction=[1e308, 1e308, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].value == pytest.approx(5.0 / np.sqrt(2))
    assert result.measurements[0].error is None


def test_measurement_component_height_tiny_direction_normalized_safely() -> None:
    """[1e-300,1e-300,0] must not underflow to 'undefined direction'."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(
            measurement_type="component_height",
            direction=[1e-300, 1e-300, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].value == pytest.approx(5.0 / np.sqrt(2))
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_plane_extreme_normal() -> None:
    """[1e308,1e308,0] normal must not overflow to a zero measurement."""
    context = _context()
    _box(context, 1, [5, 7, 10], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[1e308, 1e308, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert len(result.measurements) == 1
    # Nearest referenced vertices: x=4, y=6 -> (4 + 6) / sqrt(2).
    assert result.measurements[0].value == pytest.approx(10.0 / np.sqrt(2))
    assert result.measurements[0].error is None


def test_measurement_distance_to_reference_plane_tiny_normal() -> None:
    """[1e-300,1e-300,0] must not underflow to 'undefined normal'."""
    context = _context()
    _box(context, 1, [5, 7, 10], extents=[2, 2, 2])

    result = _run(
        MeasurementSettings(
            measurement_type="distance_to_reference",
            reference_type="plane",
            reference_point=[0.0, 0.0, 0.0],
            reference_normal=[1e-300, 1e-300, 0.0],
        ),
        MeasurementInputs(list_a=[_ref(1)]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].value == pytest.approx(10.0 / np.sqrt(2))
    assert result.measurements[0].error is None
