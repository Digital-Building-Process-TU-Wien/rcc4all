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


def test_generate_3d_cube_default_unit_cube_at_origin() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 0.0],
        size=[1.0, 1.0, 1.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert isinstance(result, Generate3DCubeResult)
    assert len(result.vertices) == 8
    assert len(result.faces) == 12
    assert result.vertices[0] == [-0.5, -0.5, -0.5]


def test_generate_3d_cube_with_custom_position() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[5.0, 10.0, 15.0],
        rotation=[0.0, 0.0, 0.0],
        size=[1.0, 1.0, 1.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert isinstance(result, Generate3DCubeResult)
    assert len(result.vertices) == 8
    assert result.vertices[0] == [4.5, 9.5, 14.5]


def test_generate_3d_cube_with_custom_rotation() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 90.0],
        size=[1.0, 1.0, 1.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert isinstance(result, Generate3DCubeResult)
    assert len(result.vertices) == 8
    assert len(result.faces) == 12


def test_generate_3d_cube_with_custom_size() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 0.0],
        size=[2.0, 3.0, 4.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert isinstance(result, Generate3DCubeResult)
    assert len(result.vertices) == 8
    assert len(result.faces) == 12


def test_generate_3d_cube_with_combined_transformations() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[10.0, 20.0, 30.0],
        rotation=[45.0, 90.0, 180.0],
        size=[2.0, 2.0, 2.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert isinstance(result, Generate3DCubeResult)
    assert len(result.vertices) == 8
    assert len(result.faces) == 12


def test_generate_3d_cube_with_zero_size_raises_error() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 0.0],
        size=[0.0, 0.0, 0.0],
    )

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))


def test_generate_3d_cube_with_negative_size_raises_error() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 0.0],
        size=[-1.0, 1.0, 1.0],
    )

    with pytest.raises(ValueError, match="Size dimensions must be positive"):
        asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))


def test_generate_3d_cube_output_format_is_trimesh_compatible() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
    )

    inputs = Generate3DCubeInputs(
        position=[0.0, 0.0, 0.0],
        rotation=[0.0, 0.0, 0.0],
        size=[1.0, 1.0, 1.0],
    )

    result = asyncio.run(generate_3d_cube(Generate3DCubeSettings(), inputs, context))

    assert hasattr(result, "vertices")
    assert hasattr(result, "faces")
    assert isinstance(result.vertices, list)
    assert isinstance(result.faces, list)
    assert all(len(vertex) == 3 for vertex in result.vertices)
    assert all(len(face) == 3 for face in result.faces)
