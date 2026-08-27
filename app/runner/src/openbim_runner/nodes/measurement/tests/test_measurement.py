from __future__ import annotations

import asyncio
from typing import Any, cast

import numpy as np
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
        MeasurementInputs(list_a=[1]),
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
        MeasurementInputs(list_a=[1]),
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
        MeasurementInputs(list_a=[1, 2]),
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
        MeasurementInputs(list_a=[1, 999]),
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
        MeasurementInputs(list_a=[]),
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
        MeasurementInputs(list_a=["mycube"]),
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
        MeasurementInputs(list_a=["broken"]),
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
        MeasurementInputs(list_a=["broken"]),
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
        MeasurementInputs(list_a=[1, "cube", 999]),
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
        MeasurementInputs(list_a=intersection_meshes),
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
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "inter:intersection_ifc:1_ifc:2"
    assert result.measurements[0].value == pytest.approx(24.0)
    assert result.measurements[0].error is None


def test_measurement_projected_area_default_normal() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="projected_area", projection_normal=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "projected_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(6.0, abs=0.1)
    assert result.measurements[0].error is None


def test_measurement_projected_area_custom_normal_x() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="projected_area", projection_normal=[1.0, 0.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "projected_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(12.0, abs=0.1)
    assert result.measurements[0].error is None


def test_measurement_projected_area_custom_normal_y() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="projected_area", projection_normal=[0.0, 1.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "projected_area"
    assert result.unit == "area_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(8.0, abs=0.1)
    assert result.measurements[0].error is None


def test_measurement_projected_area_non_watertight() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="open")

    result = _run(
        MeasurementSettings(measurement_type="projected_area", projection_normal=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=["open"]),
        context,
    )

    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:open"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


def test_measurement_projected_area_missing_geometry() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="projected_area", projection_normal=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=[1, 999]),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_projected_area_dict_input() -> None:
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
        MeasurementSettings(measurement_type="projected_area", projection_normal=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "inter:intersection_ifc:1_ifc:2"
    assert result.measurements[0].value == pytest.approx(0.25, abs=0.01)
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "inter:intersection_ifc:3_ifc:4"
    assert result.measurements[1].value == pytest.approx(1.0, abs=0.01)
    assert result.measurements[1].error is None


def test_measurement_component_height_default_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(4.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_direction_x() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="component_height", direction=[1.0, 0.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(2.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_direction_y() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 1.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(3.0)
    assert result.measurements[0].error is None


def test_measurement_component_height_diagonal_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="component_height", direction=[1.0, 1.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
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
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=["open"]),
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
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=[1, 999]),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_component_height_dict_input() -> None:
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
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 0.0, 1.0]),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "inter:intersection_ifc:1_ifc:2"
    assert result.measurements[0].value == pytest.approx(0.5, abs=0.01)
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "inter:intersection_ifc:3_ifc:4"
    assert result.measurements[1].value == pytest.approx(1.0, abs=0.01)
    assert result.measurements[1].error is None


def test_measurement_component_height_zero_direction() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        MeasurementSettings(measurement_type="component_height", direction=[0.0, 0.0, 0.0]),
        MeasurementInputs(list_a=[1]),
        context,
    )

    assert result.type == "component_height"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value is None
    assert result.measurements[0].error == "undefined direction"


def test_measurement_distance_between_two_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[1, 2]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    # Output order: grouped by first element (key_a), iterating all other keys
    assert result.measurements[0].reference == "ifc:1_ifc:2"
    assert result.measurements[1].reference == "ifc:2_ifc:1"
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
        MeasurementInputs(list_a=[1, 2, 3]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 6
    # Output order: grouped by first element (key_a), iterating all other keys in order
    # key_a=1: 1_2, 1_3; key_a=2: 2_1, 2_3; key_a=3: 3_1, 3_2
    expected_order = [
        "ifc:1_ifc:2", "ifc:1_ifc:3",
        "ifc:2_ifc:1", "ifc:2_ifc:3",
        "ifc:3_ifc:1", "ifc:3_ifc:2",
    ]
    actual_order = [m.reference for m in result.measurements]
    assert actual_order == expected_order


def test_measurement_distance_between_empty_elements_uses_whole_model() -> None:
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
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1_ifc:2", "ifc:2_ifc:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(4.0)


def test_measurement_distance_between_missing_geometry() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[1, 2, 999]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 6
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "ifc:1_ifc:2", "ifc:2_ifc:1",
        "999_ifc:1", "ifc:1_999",
        "999_ifc:2", "ifc:2_999",
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
        MeasurementInputs(list_a=[1, 2]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1_ifc:2", "ifc:2_ifc:1"}
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
    
    cache_mesh(context, plate1, key="ifc:1")
    cache_mesh(context, plate2, key="ifc:2")

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[1, 2]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1_ifc:2", "ifc:2_ifc:1"}
    for m in result.measurements:
        assert m.value == pytest.approx(0.0, abs=1e-6)
        assert m.error is None


def test_measurement_distance_between_dict_input() -> None:
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
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=intersection_meshes),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "inter:intersection_ifc:1_ifc:2_inter:intersection_ifc:3_ifc:4",
        "inter:intersection_ifc:3_ifc:4_inter:intersection_ifc:1_ifc:2",
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
        MeasurementInputs(list_a=[1, "cube"]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"gen:cube_ifc:1", "ifc:1_gen:cube"}
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
        MeasurementInputs(list_a=["open1", "open2"]),
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
        MeasurementInputs(list_a=[49, 757]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"49_ifc:757", "ifc:757_49"}
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
        MeasurementInputs(list_a=[49, 570]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"49_570", "570_49"}
    for m in result.measurements:
        assert m.value is None
        assert m.error == "no cached geometry"


def test_measurement_distance_between_list_a_cross_list_b() -> None:
    """List_A × List_B cartesian product with one direction per pair."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])
    _box(context, 3, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[1], list_b=[2, 3]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1_ifc:2", "ifc:1_ifc:3"}


def test_measurement_distance_between_self_pair_skipped() -> None:
    """Self-pairs (key_a == key_b) are skipped."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 0, 0], extents=[1, 1, 1])

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=[1, 2], list_b=[1, 2]),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1_ifc:2", "ifc:2_ifc:1"}


def test_measurement_distance_between_list_a_cross_list_b_dict() -> None:
    """List_A × List_B cartesian product where both are dicts (intersection_meshes)."""
    context = _context()
    mesh1 = trimesh.creation.box(extents=[0.5, 0.5, 0.5])
    mesh2 = trimesh.creation.box(extents=[1, 1, 1])
    mesh3 = trimesh.creation.box(extents=[1.5, 1.5, 1.5])
    cache_mesh(context, mesh1, key="inter:intersection_ifc:1_ifc:2")
    cache_mesh(context, mesh2, key="inter:intersection_ifc:3_ifc:4")
    cache_mesh(context, mesh3, key="inter:intersection_ifc:5_ifc:6")

    intersection_meshes_a: dict[str, str | None] = {
        "ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2",
        "ifc:3__ifc:4": "inter:intersection_ifc:3_ifc:4",
    }
    intersection_meshes_b: dict[str, str | None] = {
        "ifc:5__ifc:6": "inter:intersection_ifc:5_ifc:6",
    }

    result = _run(
        MeasurementSettings(measurement_type="distance_between"),
        MeasurementInputs(list_a=intersection_meshes_a, list_b=intersection_meshes_b),
        context,
    )

    assert result.type == "distance_between"
    assert result.unit == "length_unit"
    # Cross product: 2 elements in A × 1 element in B = 2 measurements
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {
        "inter:intersection_ifc:1_ifc:2_inter:intersection_ifc:5_ifc:6",
        "inter:intersection_ifc:3_ifc:4_inter:intersection_ifc:5_ifc:6",
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
        MeasurementInputs(list_a=[1]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
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
        MeasurementInputs(list_a=[1]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
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
        MeasurementInputs(list_a=[1]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
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
        MeasurementInputs(list_a=[1]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value == pytest.approx(0.0, abs=1e-6)  # box crosses plane at x=0


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
        MeasurementInputs(list_a=[1]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "ifc:1"
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
        MeasurementInputs(list_a=[1, 999]),
        context,
    )
    
    assert result.type == "distance_to_reference"
    assert result.unit == "length_unit"
    assert len(result.measurements) == 2
    assert result.measurements[0].reference == "ifc:1"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None
    assert result.measurements[1].reference == "999"
    assert result.measurements[1].value is None
    assert result.measurements[1].error == "no cached geometry"


def test_measurement_distance_to_reference_dict_input() -> None:
    """Dict input (intersection_meshes) support."""
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
    assert refs == {"inter:intersection_ifc:1_ifc:2", "inter:intersection_ifc:3_ifc:4"}
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


def test_measurement_distance_to_reference_empty_list_uses_whole_model() -> None:
    """Empty list_a -> whole model fallback."""
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
    assert len(result.measurements) == 2
    refs = {m.reference for m in result.measurements}
    assert refs == {"ifc:1", "ifc:2"}
    for m in result.measurements:
        assert m.value is not None
        assert m.error is None


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
        MeasurementInputs(list_a=["open"]),
        context,
    )
    
    assert len(result.measurements) == 1
    assert result.measurements[0].reference == "gen:open"
    assert result.measurements[0].value is not None
    assert result.measurements[0].error is None


