from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.collision.collision import (
    CollisionInputs,
    CollisionResult,
    CollisionSettings,
    collision,
)
from openbim_runner.nodes.geometry import Geometry, cache_mesh


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, object()), node_outputs={})


def _box(context: ExecutionContext, extents: list[float], translation: list[float], express_id: int | None = None) -> Geometry:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(translation)
    return cache_mesh(context, mesh, express_id=express_id)


def _run(settings: CollisionSettings, inputs: CollisionInputs, context: ExecutionContext) -> CollisionResult:
    return asyncio.run(collision(settings, inputs, context))


def test_collision_disjoint_pair_is_false() -> None:
    context = _context()
    a = _box(context, [1, 1, 1], [0, 0, 0])
    b = _box(context, [1, 1, 1], [10, 0, 0])

    result = _run(CollisionSettings(), CollisionInputs(geometries_a=[a], geometries_b=[b]), context)

    assert len(result.pairs) == 1
    assert result.pairs[0].collides is False
    assert result.pairs[0].intersection_volume is None


def test_collision_overlapping_pair_is_true_with_volume() -> None:
    context = _context()
    a = _box(context, [2, 2, 2], [0, 0, 0])
    b = _box(context, [2, 2, 2], [1, 0, 0])

    result = _run(CollisionSettings(), CollisionInputs(geometries_a=[a], geometries_b=[b]), context)

    assert result.pairs[0].collides is True
    assert result.pairs[0].intersection_volume is not None
    assert result.pairs[0].intersection_volume > 0


def test_collision_face_touching_pair_is_false_via_tolerance() -> None:
    context = _context()
    a = _box(context, [2, 2, 2], [0, 0, 0])
    b = _box(context, [2, 2, 2], [2, 0, 0])

    result = _run(CollisionSettings(), CollisionInputs(geometries_a=[a], geometries_b=[b]), context)

    assert result.pairs[0].collides is False


def test_collision_zip_pairing() -> None:
    context = _context()
    a1 = _box(context, [1, 1, 1], [0, 0, 0])
    a2 = _box(context, [1, 1, 1], [10, 0, 0])
    b1 = _box(context, [2, 2, 2], [0, 0, 0])
    b2 = _box(context, [1, 1, 1], [100, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(geometries_a=[a1, a2], geometries_b=[b1, b2]),
        context,
    )

    assert len(result.pairs) == 2
    assert result.pairs[0].index == 0
    assert result.pairs[0].collides is True
    assert result.pairs[1].index == 1
    assert result.pairs[1].collides is False
    assert result.pairs[0].key_a == a1.key
    assert result.pairs[0].key_b == b1.key
    assert result.pairs[1].key_a == a2.key
    assert result.pairs[1].key_b == b2.key


def test_collision_length_one_a_raises() -> None:
    context = _context()
    single = _box(context, [2, 2, 2], [0, 0, 0])
    others = [
        _box(context, [1, 1, 1], [0, 0, 0], express_id=1),
        _box(context, [1, 1, 1], [10, 0, 0], express_id=2),
        _box(context, [1, 1, 1], [0, 0, 0], express_id=3),
    ]

    with pytest.raises(ValueError, match="length mismatch"):
        _run(
            CollisionSettings(),
            CollisionInputs(geometries_a=[single], geometries_b=others),
            context,
        )


def test_collision_length_one_b_raises() -> None:
    context = _context()
    others = [
        _box(context, [1, 1, 1], [0, 0, 0], express_id=1),
        _box(context, [1, 1, 1], [10, 0, 0], express_id=2),
    ]
    single = _box(context, [2, 2, 2], [0, 0, 0])

    with pytest.raises(ValueError, match="length mismatch"):
        _run(
            CollisionSettings(),
            CollisionInputs(geometries_a=others, geometries_b=[single]),
            context,
        )


def test_collision_mismatched_lengths_raise() -> None:
    context = _context()
    a_list = [_box(context, [1, 1, 1], [0, 0, 0]), _box(context, [1, 1, 1], [1, 0, 0])]
    b_list = [
        _box(context, [1, 1, 1], [0, 0, 0]),
        _box(context, [1, 1, 1], [1, 0, 0]),
        _box(context, [1, 1, 1], [2, 0, 0]),
    ]

    with pytest.raises(ValueError, match="length mismatch"):
        _run(
            CollisionSettings(),
            CollisionInputs(geometries_a=a_list, geometries_b=b_list),
            context,
        )


def test_collision_non_watertight_reports_error() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    a = cache_mesh(context, open_mesh)
    b = _box(context, [2, 2, 2], [0, 0, 0])

    result = _run(CollisionSettings(), CollisionInputs(geometries_a=[a], geometries_b=[b]), context)

    pair = result.pairs[0]
    assert pair.collides is None
    assert pair.error == "non-watertight"


def test_collision_include_intersection_mesh_stores_key_and_cache() -> None:
    context = _context()
    a = _box(context, [2, 2, 2], [0, 0, 0])
    b = _box(context, [2, 2, 2], [1, 0, 0])

    result = _run(
        CollisionSettings(include_intersection_mesh=True),
        CollisionInputs(geometries_a=[a], geometries_b=[b]),
        context,
    )

    pair = result.pairs[0]
    assert pair.collides is True
    assert pair.intersection_key is not None
    assert context.geometry_cache is not None
    assert pair.intersection_key in context.geometry_cache


def test_collision_exclude_intersection_mesh_omits_key() -> None:
    context = _context()
    a = _box(context, [2, 2, 2], [0, 0, 0])
    b = _box(context, [2, 2, 2], [1, 0, 0])

    result = _run(
        CollisionSettings(include_intersection_mesh=False),
        CollisionInputs(geometries_a=[a], geometries_b=[b]),
        context,
    )

    pair = result.pairs[0]
    assert pair.collides is True
    assert pair.intersection_key is None


def test_collision_pair_carries_express_ids() -> None:
    context = _context()
    a = _box(context, [2, 2, 2], [0, 0, 0], express_id=42)
    b = _box(context, [2, 2, 2], [1, 0, 0], express_id=99)

    result = _run(CollisionSettings(), CollisionInputs(geometries_a=[a], geometries_b=[b]), context)

    pair = result.pairs[0]
    assert pair.express_id_a == 42
    assert pair.express_id_b == 99
