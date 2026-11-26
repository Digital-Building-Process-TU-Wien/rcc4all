from __future__ import annotations

import asyncio
from typing import Any, cast

import numpy as np
import pytest
import trimesh

from conftest import main_ref as _ref
from rcc4all_runner.nodes.base import ExecutionContext
from rcc4all_runner.nodes.geometry_projection.geometry_projection import (
    GeometryProjectionInputs,
    GeometryProjectionResult,
    GeometryProjectionSettings,
    geometry_projection,
)
from rcc4all_runner.util.geometry import cache_mesh


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
    settings: GeometryProjectionSettings,
    inputs: GeometryProjectionInputs,
    context: ExecutionContext,
) -> GeometryProjectionResult:
    return asyncio.run(geometry_projection(settings, inputs, context))


def _gen_mesh(
    context: ExecutionContext, result: GeometryProjectionResult, reference: str
) -> trimesh.Trimesh:
    mesh = context.geometry_cache[result.projected_geometries[reference]]
    assert isinstance(mesh, trimesh.Trimesh)
    return mesh


def test_geometry_projection_default_normal() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    assert result.projected_geometries == {"main:expr:1": "gen:proj_main_expr_1"}
    assert result.errors == []

    mesh = _gen_mesh(context, result, "main:expr:1")
    assert mesh.bounds[0] == pytest.approx([-1.0, -1.5, 0.0], abs=1e-4)
    assert mesh.bounds[1] == pytest.approx([1.0, 1.5, 0.0], abs=1e-4)
    assert mesh.area == pytest.approx(6.0, abs=0.1)


def test_geometry_projection_normal_x() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        GeometryProjectionSettings(projection_normal=[1.0, 0.0, 0.0]),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    mesh = _gen_mesh(context, result, "main:expr:1")
    assert mesh.bounds[0] == pytest.approx([0.0, -1.5, -2.0], abs=1e-4)
    assert mesh.bounds[1] == pytest.approx([0.0, 1.5, 2.0], abs=1e-4)
    assert mesh.area == pytest.approx(12.0, abs=0.1)


def test_geometry_projection_normal_y() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        GeometryProjectionSettings(projection_normal=[0.0, 1.0, 0.0]),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    mesh = _gen_mesh(context, result, "main:expr:1")
    assert mesh.bounds[0] == pytest.approx([-1.0, 0.0, -2.0], abs=1e-4)
    assert mesh.bounds[1] == pytest.approx([1.0, 0.0, 2.0], abs=1e-4)
    assert mesh.area == pytest.approx(8.0, abs=0.1)


def test_geometry_projection_negative_normal() -> None:
    """Opposite normal yields the same footprint as the default."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 3, 4])

    result = _run(
        GeometryProjectionSettings(projection_normal=[0.0, 0.0, -1.0]),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    mesh = _gen_mesh(context, result, "main:expr:1")
    assert mesh.bounds[0] == pytest.approx([-1.0, -1.5, 0.0], abs=1e-4)
    assert mesh.bounds[1] == pytest.approx([1.0, 1.5, 0.0], abs=1e-4)
    assert mesh.area == pytest.approx(6.0, abs=0.1)


def test_geometry_projection_diagonal_normal() -> None:
    context = _context()
    _box(context, 1, [5, 7, 10], extents=[2, 2, 2])

    result = _run(
        GeometryProjectionSettings(projection_normal=[1.0, 1.0, 0.0]),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    mesh = _gen_mesh(context, result, "main:expr:1")
    # The plane through the origin with normal (1,1,0) is x + y = 0.
    assert np.allclose(mesh.vertices[:, 0] + mesh.vertices[:, 1], 0.0, atol=1e-4)
    assert mesh.area == pytest.approx(5.656854, abs=1e-3)
    assert mesh.bounds[0] == pytest.approx([-2.0, 0.0, 9.0], abs=1e-3)
    assert mesh.bounds[1] == pytest.approx([0.0, 2.0, 11.0], abs=1e-3)


def test_geometry_projection_non_normalized_normal() -> None:
    """A non-unit-length normal is normalized, so the footprint matches the diagonal case."""
    context = _context()
    _box(context, 1, [5, 7, 10], extents=[2, 2, 2])

    result = _run(
        GeometryProjectionSettings(projection_normal=[2.0, 2.0, 0.0]),
        GeometryProjectionInputs(liste_a=[_ref(1)]),
        context,
    )

    mesh = _gen_mesh(context, result, "main:expr:1")
    assert np.allclose(mesh.vertices[:, 0] + mesh.vertices[:, 1], 0.0, atol=1e-4)
    assert mesh.area == pytest.approx(5.656854, abs=1e-3)


def test_geometry_projection_multiple_elements() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    _box(context, 2, [10, 0, 0], extents=[2, 2, 2])

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.projected_geometries == {
        "main:expr:1": "gen:proj_main_expr_1",
        "main:expr:2": "gen:proj_main_expr_2",
    }
    assert result.errors == []
    assert _gen_mesh(context, result, "main:expr:1").area == pytest.approx(4.0, abs=0.1)
    assert _gen_mesh(context, result, "main:expr:2").area == pytest.approx(4.0, abs=0.1)


def test_geometry_projection_dict_input() -> None:
    context = _context()
    cache_mesh(
        context,
        trimesh.creation.box(extents=[0.5, 0.5, 0.5]),
        key="inter:intersection_main:expr:1_main:expr:2",
    )
    cache_mesh(
        context,
        trimesh.creation.box(extents=[1, 1, 1]),
        key="inter:intersection_main:expr:3_main:expr:4",
    )

    intersection_meshes = {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2",
        "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4",
        "main:expr:5__main:expr:6": None,
    }

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=intersection_meshes),
        context,
    )

    assert result.projected_geometries == {
        "inter:intersection_main:expr:1_main:expr:2": (
            "gen:proj_inter_intersection_main_expr_1_main_expr_2"
        ),
        "inter:intersection_main:expr:3_main:expr:4": (
            "gen:proj_inter_intersection_main_expr_3_main_expr_4"
        ),
    }
    assert result.errors == []
    assert _gen_mesh(
        context, result, "inter:intersection_main:expr:1_main:expr:2"
    ).area == pytest.approx(0.25, abs=0.01)
    assert _gen_mesh(
        context, result, "inter:intersection_main:expr:3_main:expr:4"
    ).area == pytest.approx(1.0, abs=0.01)


def test_geometry_projection_missing_geometry() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=[_ref(1), _ref(999)]),
        context,
    )

    assert result.projected_geometries == {"main:expr:1": "gen:proj_main_expr_1"}
    assert [(e.reference, e.error) for e in result.errors] == [
        ("main:expr:999", "no cached geometry")
    ]


def test_geometry_projection_invalid_ref_is_missing() -> None:
    context = _context()
    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=["not_a_geometry_key"]),
        context,
    )
    assert result.projected_geometries == {}
    assert [(e.reference, e.error) for e in result.errors] == [
        ("not_a_geometry_key", "no cached geometry")
    ]


def test_geometry_projection_zero_normal() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _box(context, 2, [5, 5, 5], extents=[1, 1, 1])

    result = _run(
        GeometryProjectionSettings(projection_normal=[0.0, 0.0, 0.0]),
        GeometryProjectionInputs(liste_a=[_ref(1), _ref(2)]),
        context,
    )

    assert result.projected_geometries == {}
    assert [(e.reference, e.error) for e in result.errors] == [
        ("main:expr:1", "undefined normal"),
        ("main:expr:2", "undefined normal"),
    ]


def test_geometry_projection_degenerate_edge_on() -> None:
    """A flat wall parallel to the projection direction has no area in the plane."""
    context = _context()
    wall = trimesh.Trimesh(
        vertices=[[0, 0, 0], [4, 0, 0], [4, 0, 4], [0, 0, 4]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    cache_mesh(context, wall, object_id="edgeon")

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=["gen:edgeon"]),
        context,
    )

    assert result.projected_geometries == {}
    assert [(e.reference, e.error) for e in result.errors] == [
        ("gen:edgeon", "no projected geometry")
    ]


def test_geometry_projection_empty_list() -> None:
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=[]),
        context,
    )

    assert result.projected_geometries == {}
    assert result.errors == []


def test_geometry_projection_non_watertight() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="open")

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=["gen:open"]),
        context,
    )

    assert result.errors == []
    assert _gen_mesh(context, result, "gen:open").area == pytest.approx(0.5, abs=1e-3)


def test_geometry_projection_key_sanitization_and_guard() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(extents=[1, 1, 1]), object_id="a_b")
    cache_mesh(context, trimesh.creation.box(extents=[1, 1, 1]), object_id="a:b")

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=["gen:a_b", "gen:a:b"]),
        context,
    )

    assert result.projected_geometries == {
        "gen:a_b": "gen:proj_gen_a_b",
        "gen:a:b": "gen:proj_gen_a_b_1",
    }
    assert result.errors == []


def test_geometry_projection_duplicate_refs_are_idempotent() -> None:
    """The same reference listed twice maps to one key and caches one footprint."""
    context = _context()
    _box(context, 1, [0, 0, 0], extents=[1, 1, 1])

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=[_ref(1), _ref(1)]),
        context,
    )

    assert result.projected_geometries == {"main:expr:1": "gen:proj_main_expr_1"}
    assert result.errors == []
    # Only the source mesh and the single shared footprint are cached — no `_1`.
    assert set(context.geometry_cache) == {"main:expr:1", "gen:proj_main_expr_1"}


def test_geometry_projection_generated_key_is_not_ifc_ref() -> None:
    """Generated keys must never parse back as an IFC reference."""
    from rcc4all_runner.util.references import split_reference

    context = _context()
    cache_mesh(context, trimesh.creation.box(extents=[1, 1, 1]), object_id="a:b")

    result = _run(
        GeometryProjectionSettings(),
        GeometryProjectionInputs(liste_a=["gen:a:b"]),
        context,
    )

    key = result.projected_geometries["gen:a:b"]
    assert key == "gen:proj_gen_a_b"
    assert ":expr:" not in key
    # split_reference raises for any non-expr/non-gen key; for a gen key it must
    # yield kind "gen", never "expr".
    _slug, kind, _value = split_reference(key)
    assert kind == "gen"


def test_geometry_projection_wrong_normal_length_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GeometryProjectionSettings(projection_normal=[1.0, 0.0])
