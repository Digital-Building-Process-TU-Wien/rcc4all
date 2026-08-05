from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.generate_3d_cube.generate_3d_cube import (
    Generate3DCubeInputs,
    Generate3DCubeResult,
    generate_3d_cube,
)


class FakeIfcModel:
    pass


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, FakeIfcModel()), node_outputs={})


def _run(inputs: Generate3DCubeInputs, context: ExecutionContext) -> Generate3DCubeResult:
    return asyncio.run(generate_3d_cube(inputs, context))


def _mesh_from_result(result: Generate3DCubeResult, context: ExecutionContext):
    assert context.geometry_cache is not None
    object_id = result.object_ids[0]
    return context.geometry_cache[f"gen:{object_id}"]


def test_generate_3d_cube_default_unit_cube_at_origin() -> None:
    context = _context()

    result = _run(Generate3DCubeInputs(object_id="cube1"), context)

    assert isinstance(result, Generate3DCubeResult)
    assert result.object_ids == ["cube1"]
    assert context.geometry_cache is not None
    assert "gen:cube1" in context.geometry_cache
    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_custom_position() -> None:
    context = _context()

    result = _run(
        Generate3DCubeInputs(position=[5.0, 10.0, 15.0], object_id="cube_pos"),
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
        Generate3DCubeInputs(rotation=[0.0, 0.0, 90.0], object_id="cube_rot"),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_custom_size() -> None:
    context = _context()

    result = _run(
        Generate3DCubeInputs(size=[2.0, 3.0, 4.0], object_id="cube_size"),
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
        Generate3DCubeInputs(position=[10.0, 20.0, 30.0], rotation=[45.0, 90.0, 180.0], size=[2.0, 2.0, 2.0], object_id="cube_comb"),
        context,
    )

    mesh = _mesh_from_result(result, context)
    assert mesh.vertices.shape == (8, 3)
    assert mesh.faces.shape == (12, 3)


def test_generate_3d_cube_with_zero_size_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        _run(Generate3DCubeInputs(size=[0.0, 0.0, 0.0], object_id="cube"), context)


def test_generate_3d_cube_with_negative_size_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        _run(Generate3DCubeInputs(size=[-1.0, 1.0, 1.0], object_id="cube"), context)


def test_generate_3d_cube_empty_object_id_raises_error() -> None:
    context = _context()

    with pytest.raises(ValueError, match="object_id must be a non-empty string"):
        _run(Generate3DCubeInputs(object_id=""), context)


def test_generate_3d_cube_duplicate_object_id_raises_error() -> None:
    context = _context()
    _run(Generate3DCubeInputs(object_id="cube"), context)

    with pytest.raises(ValueError, match="'gen:cube' already exists"):
        _run(Generate3DCubeInputs(object_id="cube"), context)


def test_generate_3d_cube_output_is_object_id() -> None:
    context = _context()

    result = _run(Generate3DCubeInputs(object_id="cube_out"), context)

    assert result.object_ids == ["cube_out"]
    assert context.geometry_cache is not None
    assert "gen:cube_out" in context.geometry_cache
