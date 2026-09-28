from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import trimesh

from conftest import main_ref as _ref
from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.collision.collision import (
    CollisionInputs,
    CollisionResult,
    CollisionSettings,
    collision,
)
from openbim_runner.util.geometry import cache_mesh, resolve_mesh


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, object()), node_outputs={})


def _express_box(
    context: ExecutionContext,
    express_id: int,
    translation: list[float],
    extents: list[float] | None = None,
) -> None:
    mesh = trimesh.creation.box(extents=extents or [2, 2, 2])
    mesh.apply_translation(translation)
    cache_mesh(context, mesh, express_id=express_id)


def _run(
    settings: CollisionSettings, inputs: CollisionInputs, context: ExecutionContext
) -> CollisionResult:
    return asyncio.run(collision(settings, inputs, context))


def test_collision_disjoint_pair_is_not_emitted() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _express_box(context, 2, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {}
    assert result.errors == []


def test_collision_overlapping_pair_is_emitted_grouped() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["main:expr:2"]}
    assert result.errors == []


def test_collision_face_touching_pair_is_not_emitted() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [2, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {}
    assert result.errors == []


def test_collision_non_watertight_overlapping_reports_collision() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="broken")
    _express_box(context, 2, [0, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=["gen:broken"], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {"gen:broken": ["main:expr:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {}


def test_collision_non_watertight_disjoint_no_collision() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="broken")
    _express_box(context, 2, [10, 0, 0], extents=[1, 1, 1])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=["gen:broken"], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {}
    assert result.errors == []


def test_collision_non_watertight_inside_convex_reports_collision() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0], extents=[2, 2, 2])
    floating_triangle = trimesh.Trimesh(
        vertices=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.5, 0.0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, floating_triangle, object_id="floating")

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=["gen:floating"], list_b=[_ref(1)]),
        context,
    )

    assert result.collisions == {"gen:floating": ["main:expr:1"]}
    assert result.errors == []
    assert result.intersection_meshes == {}


def test_collision_cartesian_product_groups_colliding_keys() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0], extents=[1, 1, 1])
    _express_box(context, 2, [10, 0, 0], extents=[1, 1, 1])
    _express_box(context, 3, [0, 0, 0], extents=[2, 2, 2])
    _express_box(context, 4, [100, 0, 0], extents=[1, 1, 1])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1), _ref(2)], list_b=[_ref(3), _ref(4)]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["main:expr:3"]}
    assert result.errors == []


def test_collision_lists_mix_express_and_object_ids() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    mesh = trimesh.creation.box()
    mesh.apply_translation([1, 0, 0])
    cache_mesh(context, mesh, object_id="cube")

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=["gen:cube"]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["gen:cube"]}
    assert result.errors == []


def test_collision_groups_multiple_collisions_per_key() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])
    _express_box(context, 3, [0.5, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2), _ref(3)]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["main:expr:2", "main:expr:3"]}


def test_collision_bound_but_empty_lists_yield_no_pairs() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result_a = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[_ref(1)], list_b=[]),
        context,
    )
    assert result_a.collisions == {}
    assert result_a.errors == []

    result_ab = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[], list_b=[]),
        context,
    )
    assert result_ab.collisions == {}
    assert result_ab.errors == []


def test_collision_mode_boolean_stores_no_intersection_mesh() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(mode="boolean"),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["main:expr:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {}
    assert (
        context.geometry_cache is None
        or "inter:intersection_main:expr:1_main:expr:2" not in context.geometry_cache
    )


def test_collision_mode_intersection_mesh_stores_deterministic_key() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(mode="intersection_mesh"),
        CollisionInputs(list_a=[_ref(1)], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {"main:expr:1": ["main:expr:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {
        "main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2"
    }
    assert context.geometry_cache is not None
    key = "inter:intersection_main:expr:1_main:expr:2"
    assert key in context.geometry_cache
    assert resolve_mesh(context, key).volume > 0


def test_collision_mode_intersection_mesh_fcl_pair_gets_null() -> None:
    context = _context()
    open_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    cache_mesh(context, open_mesh, object_id="broken")
    _express_box(context, 2, [0, 0, 0])

    result = _run(
        CollisionSettings(mode="intersection_mesh"),
        CollisionInputs(list_a=["gen:broken"], list_b=[_ref(2)]),
        context,
    )

    assert result.collisions == {"gen:broken": ["main:expr:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {"gen:broken__main:expr:2": None}
    assert (
        context.geometry_cache is None
        or "inter:intersection_gen:broken_main:expr:2" not in context.geometry_cache
    )


def test_collision_mixed_model_refs_resolve_against_own_model() -> None:
    """Regression for the original bug: a filter on `main` feeding a collision with
    refs from both models must resolve each ref against its own model."""
    context = ExecutionContext(
        models={"main": cast(Any, object()), "second_model": cast(Any, object())},
        node_outputs={},
    )
    # Same express ID in both models, different geometry.
    mesh_main = trimesh.creation.box(extents=[1, 1, 1])
    mesh_main.apply_translation([0, 0, 0])
    cache_mesh(context, mesh_main, express_id=63, slug="main")
    mesh_second = trimesh.creation.box(extents=[1, 1, 1])
    mesh_second.apply_translation([0.9, 0, 0])
    cache_mesh(context, mesh_second, express_id=63, slug="second_model")

    result = _run(
        CollisionSettings(),
        CollisionInputs(
            list_a=["main:expr:63"],
            list_b=["second_model:expr:63"],
        ),
        context,
    )

    assert result.collisions == {"main:expr:63": ["second_model:expr:63"]}
    assert result.errors == []


def test_collision_missing_express_id_raises() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])

    with pytest.raises(
        ValueError, match="'main:expr:999' is not present in the workflow cache"
    ):
        _run(
            CollisionSettings(),
            CollisionInputs(list_a=[_ref(1)], list_b=[_ref(999)]),
            context,
        )


def test_collision_malformed_reference_raises() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])

    with pytest.raises(ValueError, match="not a valid geometry cache reference"):
        _run(
            CollisionSettings(),
            CollisionInputs(list_a=["ghost"], list_b=[_ref(1)]),
            context,
        )


class _FakePart:
    def __init__(self, pid: int) -> None:
        self._pid = pid

    def id(self) -> int:
        return self._pid


class _FakeAggregateRel:
    RelatingObject: Any = None
    RelatedObjects: list[Any] = None  # type: ignore[assignment]

    def __init__(self, parent: int, children: list[int]) -> None:
        self.RelatingObject = _FakePart(parent)
        self.RelatedObjects = [_FakePart(c) for c in children]


class _FakeAggregateModel:
    def __init__(self, rels: list[_FakeAggregateRel]) -> None:
        self._rels = rels

    def by_type(self, name: str) -> list[_FakeAggregateRel]:
        if name in ("IfcRelAggregates", "IfcRelNests"):
            return self._rels
        return []


def _run_with_model(
    rels: list[_FakeAggregateRel],
    inputs: CollisionInputs,
    boxes: dict[int, tuple[list[float], list[float]]],
) -> CollisionResult:
    context = ExecutionContext(
        ifc_model=cast(Any, _FakeAggregateModel(rels)), node_outputs={}
    )
    for express_id, (translation, extents) in boxes.items():
        _express_box(context, express_id, translation, extents)
    return _run(CollisionSettings(), inputs, context)


def test_collision_skips_parent_child_decomposition() -> None:
    # Wall parent 10 overlaps its own aggregated part 20 -> self-comparison, skipped.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20])],
        CollisionInputs(list_a=[_ref(10)], list_b=[_ref(20)]),
        {10: ([0, 0, 0], [2, 2, 2]), 20: ([1, 0, 0], [2, 2, 2])},
    )
    assert result.collisions == {}
    assert result.errors == []


def test_collision_keeps_cross_tree_decomposition_collisions() -> None:
    # tree1: 10 -> 20 ; tree2: 30 -> 40.
    # 20 (tree1) overlaps 40 (tree2): distinct elements, must still be reported.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20]), _FakeAggregateRel(30, [40])],
        CollisionInputs(list_a=[_ref(20)], list_b=[_ref(40)]),
        {
            10: ([0, 0, 0], [2, 2, 2]),
            20: ([0, 0, 0], [2, 2, 2]),
            30: ([10, 0, 0], [2, 2, 2]),
            40: ([0.5, 0, 0], [2, 2, 2]),
        },
    )
    assert result.collisions == {"main:expr:20": ["main:expr:40"]}
    assert result.errors == []


def test_collision_skips_parent_child_decomposition_pairs() -> None:
    # Wall parent 10 overlaps its own aggregated part 20 -> self-comparison, skipped.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20])],
        CollisionInputs(list_a=[_ref(10)], list_b=[_ref(20), _ref(30)]),
        {
            10: ([0, 0, 0], [2, 2, 2]),
            20: ([1, 0, 0], [2, 2, 2]),
            30: ([10, 0, 0], [2, 2, 2]),
        },
    )
    assert result.collisions == {}
    assert result.errors == []


def test_collision_transitive_ancestor_descendant_is_skipped() -> None:
    # Grandparent 10 -> 20 -> 30. 10 vs 30 (grandchild) is a self-comparison too.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20]), _FakeAggregateRel(20, [30])],
        CollisionInputs(list_a=[_ref(10)], list_b=[_ref(30)]),
        {
            10: ([0, 0, 0], [2, 2, 2]),
            20: ([0, 0, 0], [2, 2, 2]),
            30: ([1, 0, 0], [2, 2, 2]),
        },
    )
    assert result.collisions == {}
    assert result.errors == []
