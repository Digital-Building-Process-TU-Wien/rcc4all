from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.generate_3d_cube.generate_3d_cube import (
    Generate3DCubeInputs,
    Generate3DCubeResult,
    Generate3DCubeSettings,
    generate_3d_cube,
)


class FakeIfcModel:
    pass


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, FakeIfcModel()), node_outputs={})


def _run(
    settings: Generate3DCubeSettings,
    context: ExecutionContext,
    inputs: Generate3DCubeInputs | None = None,
) -> Generate3DCubeResult:
    if inputs is None:
        inputs = Generate3DCubeInputs()
    return asyncio.run(generate_3d_cube(settings, inputs, context))


def _mesh_from_result(result: Generate3DCubeResult, context: ExecutionContext):
    assert context.geometry_cache is not None
    return context.geometry_cache[result.object_ids[0]]


def test_generate_3d_cube_default_unit_cube_at_origin() -> None:
    context = _context()

    result = _run(Generate3DCubeSettings(object_id="cube1"), context)

    assert isinstance(result, Generate3DCubeResult)
    assert result.object_ids == ["gen:cube1"]
    assert context.geometry_cache is not None
    assert "gen:cube1" in context.geometry_cache
    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_custom_position() -> None:
    context = _context()

    result = _run(
        Generate3DCubeSettings(position=[5.0, 10.0, 15.0], object_id="cube_pos"),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.centroid[0] == pytest.approx(5.0)
    assert mesh.centroid[1] == pytest.approx(10.0)
    assert mesh.centroid[2] == pytest.approx(15.0)


def test_generate_3d_cube_with_custom_rotation() -> None:
    context = _context()

    result = _run(
        Generate3DCubeSettings(rotation=[0.0, 0.0, 90.0], object_id="cube_rot"),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_custom_size() -> None:
    context = _context()

    result = _run(
        Generate3DCubeSettings(size=[2.0, 3.0, 4.0], object_id="cube_size"),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)
    extents = mesh.bounding_box.extents
    assert extents[0] == pytest.approx(2.0)
    assert extents[1] == pytest.approx(3.0)
    assert extents[2] == pytest.approx(4.0)


def test_generate_3d_cube_with_combined_transformations() -> None:
    context = _context()

    result = _run(
        Generate3DCubeSettings(
            position=[10.0, 20.0, 30.0],
            rotation=[45.0, 90.0, 180.0],
            size=[2.0, 2.0, 2.0],
            object_id="cube_comb",
        ),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_input_binding_position() -> None:
    context = _context()

    inputs = Generate3DCubeInputs(
        elements=[
            {
                "position": [5.0, 3.0, 0.0],
                "rotation": {"rotation_x": 0.0, "rotation_y": 0.0, "rotation_z": 45.0},
            }
        ]
    )

    # Offset von [0.5, 0, 0] sollte zu [5.5, 3.0, 0.0] führen
    result = _run(
        Generate3DCubeSettings(
            position=[0.5, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            size=[1.0, 1.0, 1.0],
            object_id="cube_offset",
        ),
        context,
        inputs,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.centroid[0] == pytest.approx(5.5)
    assert mesh.centroid[1] == pytest.approx(3.0)
    assert mesh.centroid[2] == pytest.approx(0.0)


def test_generate_3d_cube_with_input_binding_rotation() -> None:
    context = _context()

    inputs = Generate3DCubeInputs(
        elements=[
            {
                "position": [0.0, 0.0, 0.0],
                "rotation": {"rotation_x": 0.0, "rotation_y": 0.0, "rotation_z": 45.0},
            }
        ]
    )

    # Rotation-Offset von [0, 0, 15] sollte zu [0, 0, 60] führen
    result = _run(
        Generate3DCubeSettings(
            position=[0.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 15.0],
            size=[1.0, 1.0, 1.0],
            object_id="cube_rot_offset",
        ),
        context,
        inputs,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_input_binding_combined() -> None:
    context = _context()

    inputs = Generate3DCubeInputs(
        elements=[
            {
                "position": [10.0, 5.0, 2.0],
                "rotation": {"rotation_x": 10.0, "rotation_y": 20.0, "rotation_z": 30.0},
            }
        ]
    )

    # Position: [10, 5, 2] + [1, 1, 1] = [11, 6, 3]
    # Rotation: [10, 20, 30] + [5, 5, 5] = [15, 25, 35]
    result = _run(
        Generate3DCubeSettings(
            position=[1.0, 1.0, 1.0],
            rotation=[5.0, 5.0, 5.0],
            size=[1.0, 1.0, 1.0],
            object_id="cube_combined",
        ),
        context,
        inputs,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.centroid[0] == pytest.approx(11.0)
    assert mesh.centroid[1] == pytest.approx(6.0)
    assert mesh.centroid[2] == pytest.approx(3.0)


def test_generate_3d_cube_without_input_uses_origin() -> None:
    context = _context()

    # Kein Input-Binding, nur Offset [5, 0, 0]
    result = _run(
        Generate3DCubeSettings(
            position=[5.0, 0.0, 0.0],
            rotation=[0.0, 0.0, 0.0],
            size=[1.0, 1.0, 1.0],
            object_id="cube_no_input",
        ),
        context,
        Generate3DCubeInputs(),  # Leere Inputs
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.centroid[0] == pytest.approx(5.0)
    assert mesh.centroid[1] == pytest.approx(0.0)
    assert mesh.centroid[2] == pytest.approx(0.0)


def test_generate_3d_cube_with_zero_size_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        _run(Generate3DCubeSettings(size=[0.0, 0.0, 0.0], object_id="cube"), context)


def test_generate_3d_cube_with_negative_size_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        _run(Generate3DCubeSettings(size=[-1.0, 1.0, 1.0], object_id="cube"), context)


def test_generate_3d_cube_empty_object_id_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="object_id must be a non-empty string"):
        _run(Generate3DCubeSettings(object_id=""), context)


def test_generate_3d_cube_expr_marker_object_id_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="must not contain ':expr:'"):
        _run(
            Generate3DCubeSettings(object_id="main:expr:5"),
            context,
        )


def test_generate_3d_cube_duplicate_object_id_raises_error() -> None:
    context = _context()
    _run(Generate3DCubeSettings(object_id="cube"), context)

    with pytest.raises(ValueError, match="'gen:cube' already exists"):
        _run(Generate3DCubeSettings(object_id="cube"), context)


def test_generate_3d_cube_output_is_object_id() -> None:
    context = _context()

    result = _run(Generate3DCubeSettings(object_id="cube_out"), context)

    assert result.object_ids == ["gen:cube_out"]
    assert context.geometry_cache is not None
    assert "gen:cube_out" in context.geometry_cache
