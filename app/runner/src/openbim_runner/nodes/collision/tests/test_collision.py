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
        CollisionInputs(list_a=[1], list_b=[2]),
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
        CollisionInputs(list_a=[1], list_b=[2]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2"]}
    assert result.errors == []


def test_collision_face_touching_pair_is_not_emitted() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [2, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[1], list_b=[2]),
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
        CollisionInputs(list_a=["broken"], list_b=[2]),
        context,
    )

    assert result.collisions == {"gen:broken": ["ifc:2"]}
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
        CollisionInputs(list_a=["broken"], list_b=[2]),
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
        CollisionInputs(list_a=["floating"], list_b=[1]),
        context,
    )

    assert result.collisions == {"gen:floating": ["ifc:1"]}
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
        CollisionInputs(list_a=[1, 2], list_b=[3, 4]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:3"]}
    assert result.errors == []


def test_collision_lists_mix_express_and_object_ids() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    mesh = trimesh.creation.box()
    mesh.apply_translation([1, 0, 0])
    cache_mesh(context, mesh, object_id="cube")

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[1], list_b=["cube"]),
        context,
    )

    assert result.collisions == {"ifc:1": ["gen:cube"]}
    assert result.errors == []


def test_collision_groups_multiple_collisions_per_key() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])
    _express_box(context, 3, [0.5, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[1], list_b=[2, 3]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2", "ifc:3"]}


def test_collision_empty_b_falls_back_to_whole_model() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])
    _express_box(context, 3, [0.5, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[1], list_b=[]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2", "ifc:3"]}


def test_collision_empty_a_falls_back_to_whole_model() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])
    _express_box(context, 3, [0.5, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[], list_b=[1]),
        context,
    )

    assert result.collisions == {"ifc:2": ["ifc:1"], "ifc:3": ["ifc:1"]}


def test_collision_self_pair_is_skipped_when_both_fall_back() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(),
        CollisionInputs(list_a=[], list_b=[]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2"], "ifc:2": ["ifc:1"]}


def test_collision_mode_boolean_stores_no_intersection_mesh() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(mode="boolean"),
        CollisionInputs(list_a=[1], list_b=[2]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {}
    assert (
        context.geometry_cache is None
        or "inter:intersection_ifc:1_ifc:2" not in context.geometry_cache
    )


def test_collision_mode_intersection_mesh_stores_deterministic_key() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])
    _express_box(context, 2, [1, 0, 0])

    result = _run(
        CollisionSettings(mode="intersection_mesh"),
        CollisionInputs(list_a=[1], list_b=[2]),
        context,
    )

    assert result.collisions == {"ifc:1": ["ifc:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {
        "ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2"
    }
    assert context.geometry_cache is not None
    key = "inter:intersection_ifc:1_ifc:2"
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
        CollisionInputs(list_a=["broken"], list_b=[2]),
        context,
    )

    assert result.collisions == {"gen:broken": ["ifc:2"]}
    assert result.errors == []
    assert result.intersection_meshes == {"gen:broken__ifc:2": None}
    assert (
        context.geometry_cache is None
        or "inter:intersection_gen:broken_ifc:2" not in context.geometry_cache
    )


def test_collision_missing_express_id_raises() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])

    with pytest.raises(ValueError, match="Express ID 999 has no tessellated geometry"):
        _run(
            CollisionSettings(),
            CollisionInputs(list_a=[1], list_b=[999]),
            context,
        )


def test_collision_missing_object_id_raises() -> None:
    context = _context()
    _express_box(context, 1, [0, 0, 0])

    with pytest.raises(ValueError, match="Object ID 'ghost' has no geometry"):
        _run(
            CollisionSettings(),
            CollisionInputs(list_a=["ghost"], list_b=[1]),
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
        CollisionInputs(list_a=[10], list_b=[20]),
        {10: ([0, 0, 0], [2, 2, 2]), 20: ([1, 0, 0], [2, 2, 2])},
    )
    assert result.collisions == {}
    assert result.errors == []


def test_collision_keeps_cross_tree_decomposition_collisions() -> None:
    # tree1: 10 -> 20 ; tree2: 30 -> 40.
    # 20 (tree1) overlaps 40 (tree2): distinct elements, must still be reported.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20]), _FakeAggregateRel(30, [40])],
        CollisionInputs(list_a=[20], list_b=[40]),
        {
            10: ([0, 0, 0], [2, 2, 2]),
            20: ([0, 0, 0], [2, 2, 2]),
            30: ([10, 0, 0], [2, 2, 2]),
            40: ([0.5, 0, 0], [2, 2, 2]),
        },
    )
    assert result.collisions == {"ifc:20": ["ifc:40"]}
    assert result.errors == []


def test_collision_skips_parent_child_in_whole_model_fallback() -> None:
    # list_b empty -> whole model fallback. Parent 10 vs its own part 20 must be
    # skipped even though the whole model includes both. (Regression for the
    # reported Attika self-collision on decomposed walls.)
    result = _run_with_model(
        [_FakeAggregateRel(10, [20])],
        CollisionInputs(list_a=[10], list_b=[]),
        {10: ([0, 0, 0], [2, 2, 2]), 20: ([1, 0, 0], [2, 2, 2])},
    )
    assert result.collisions == {}
    assert result.errors == []


def test_collision_transitive_ancestor_descendant_is_skipped() -> None:
    # Grandparent 10 -> 20 -> 30. 10 vs 30 (grandchild) is a self-comparison too.
    result = _run_with_model(
        [_FakeAggregateRel(10, [20]), _FakeAggregateRel(20, [30])],
        CollisionInputs(list_a=[10], list_b=[30]),
        {
            10: ([0, 0, 0], [2, 2, 2]),
            20: ([0, 0, 0], [2, 2, 2]),
            30: ([1, 0, 0], [2, 2, 2]),
        },
    )
    assert result.collisions == {}
    assert result.errors == []
