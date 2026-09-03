from __future__ import annotations

import asyncio
from typing import Any, cast

import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.tilt_of_components.tilt_of_components import (
    TiltOfComponentsInputs,
    TiltOfComponentsResult,
    TiltOfComponentsSettings,
    tilt_of_components,
)
from openbim_runner.util.geometry import cache_mesh, resolve_mesh


class _FakeRelAggregates:
    def __init__(self, related_objects: list[_FakeEntity]) -> None:
        self._is_a = "IfcRelAggregates"
        self.RelatedObjects = related_objects

    def is_a(self) -> str:
        return self._is_a


class _FakeEntity:
    def __init__(
        self,
        express_id: int,
        is_a: str,
        decomposed: list[_FakeRelAggregates] | None = None,
    ) -> None:
        self._id = express_id
        self._is_a = is_a
        self.IsDecomposedBy = decomposed or []

    def id(self) -> int:
        return self._id

    def is_a(self) -> str:
        return self._is_a


class _FakeModel:
    def __init__(self, entities: list[_FakeEntity]) -> None:
        self._entities = {entity.id(): entity for entity in entities}
        self.header = _FakeHeader(name="Testmodell_TiltOfComponentsRule.ifc")

    def by_id(self, express_id: int) -> _FakeEntity:
        entity = self._entities.get(express_id)
        if entity is None:
            raise RuntimeError(f"No entity for {express_id}")
        return entity

    def by_type(self, entity_type: str) -> list[_FakeEntity]:
        if entity_type == "IfcElement":
            return list(self._entities.values())
        if entity_type == "IfcProject":
            return []
        return [e for e in self._entities.values() if e.is_a() == entity_type]


class _FakeHeader:
    def __init__(self, name: str) -> None:
        self.file_name = _FakeFileName(name)


class _FakeFileName:
    def __init__(self, name: str) -> None:
        self.name = name


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, _FakeModel([])), node_outputs={})


def _add_element(
    context: ExecutionContext, express_id: int, mesh: trimesh.Trimesh
) -> None:
    cache_mesh(context, mesh, express_id=express_id)
    model = cast(Any, context.ifc_model)
    model._entities[express_id] = _FakeEntity(express_id, "IFCWALL")


def _box(extents: list[float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=extents)


def _run(
    settings: TiltOfComponentsSettings,
    inputs: TiltOfComponentsInputs,
    context: ExecutionContext,
) -> TiltOfComponentsResult:
    return asyncio.run(tilt_of_components(settings, inputs, context))


# --- 2D: walls & slabs -------------------------------------------------------


def test_2d_vertical_wall_tilt_is_90_and_flagged_by_lower_limit() -> None:
    context = _context()
    # thin in Y, wide in X/Z ⇒ front/back faces (normal ±Y) are the two largest
    _add_element(context, 1, _box([4.0, 0.2, 3.0]))

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="greater_than_lower",
            lower_limit=89.0,
        ),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    assert result.element_count == 1
    element = result.elements[0]
    assert element.class_name == "IFCWALL"
    assert element.failed is True
    assert len(element.checks) == 2
    for check in element.checks:
        assert check.tilt_angle == 90.0
        assert check.passed is False
        assert check.expected == "less than or equal to 89"
        assert check.geometry_key is not None
    assert result.failed_count == 1
    assert result.check_count == 1
    assert result.model_name == "Testmodell_TiltOfComponentsRule"


def test_model_name_uses_basename_stem() -> None:
    context = _context()
    _add_element(context, 1, _box([4.0, 0.2, 3.0]))
    cast(
        Any, context.ifc_model
    ).header.file_name.name = (
        "C:\\Models\\2021-Projects\\Testmodell_TiltOfComponentsRule.ifc"
    )

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    assert result.model_name == "Testmodell_TiltOfComponentsRule"


def test_2d_horizontal_slab_tilt_is_0_and_passes_lower_limit() -> None:
    context = _context()
    # thin in Z, wide in X/Y ⇒ top/bottom faces (normal ±Z) are the two largest
    _add_element(context, 2, _box([4.0, 3.0, 0.2]))

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="greater_than_lower",
            lower_limit=1.0,
        ),
        TiltOfComponentsInputs(express_ids=[2]),
        context,
    )

    element = result.elements[0]
    assert len(element.checks) == 2
    for check in element.checks:
        assert check.tilt_angle == 0.0
        assert check.passed is True
        assert check.expected == "less than or equal to 1"
    assert result.failed_count == 0


def test_2d_flagged_surface_caches_helper_geometry() -> None:
    context = _context()
    _add_element(context, 3, _box([4.0, 0.2, 3.0]))

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="greater_than_lower",
            lower_limit=89.0,
        ),
        TiltOfComponentsInputs(express_ids=[3]),
        context,
    )

    keys = {
        check.geometry_key for check in result.elements[0].checks if check.geometry_key
    }
    assert keys == {"inter:tilt_surface_3_0", "inter:tilt_surface_3_1"}
    for key in keys:
        assert context.geometry_cache is not None
        assert key in context.geometry_cache
        assert len(resolve_mesh(context, key).faces) == 2


# --- 1D: columns & beams -----------------------------------------------------


def test_1d_vertical_column_tilt_is_90_and_flagged_by_lower_limit() -> None:
    context = _context()
    # tall in Z, thin in X/Y ⇒ farthest surface centroids are top/bottom ⇒ vertical axis
    _add_element(context, 10, _box([0.3, 0.3, 4.0]))

    result = _run(
        TiltOfComponentsSettings(
            element_category="1d",
            comparison_method="greater_than_lower",
            lower_limit=89.0,
        ),
        TiltOfComponentsInputs(express_ids=[10]),
        context,
    )

    element = result.elements[0]
    assert len(element.checks) == 1
    check = element.checks[0]
    assert check.tilt_angle == 90.0
    assert check.passed is False
    assert check.expected == "less than or equal to 89"
    assert check.geometry_key == "inter:tilt_axis_10"
    assert context.geometry_cache is not None
    assert check.geometry_key in context.geometry_cache


def test_1d_horizontal_beam_tilt_is_0_and_passes_lower_limit() -> None:
    context = _context()
    # long in X ⇒ farthest surface centroids are left/right ⇒ horizontal axis
    _add_element(context, 11, _box([4.0, 0.3, 0.3]))

    result = _run(
        TiltOfComponentsSettings(
            element_category="1d",
            comparison_method="greater_than_lower",
            lower_limit=1.0,
        ),
        TiltOfComponentsInputs(express_ids=[11]),
        context,
    )

    element = result.elements[0]
    check = element.checks[0]
    assert check.tilt_angle == 0.0
    assert check.passed is True
    assert check.geometry_key is None


# --- comparison methods ------------------------------------------------------


def test_inside_interval_flags_tilt_within_interval() -> None:
    context = _context()
    _add_element(context, 20, _box([4.0, 0.2, 3.0]))  # tilt 90 (wall)

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="inside_interval",
            interval_lower=89.0,
            interval_upper=91.0,
        ),
        TiltOfComponentsInputs(express_ids=[20]),
        context,
    )

    assert result.elements[0].checks[0].passed is False
    assert result.elements[0].checks[0].expected == "outside 89 and 91"


def test_outside_interval_passes_tilt_within_interval() -> None:
    context = _context()
    _add_element(context, 21, _box([4.0, 0.2, 3.0]))  # tilt 90 (wall)

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="outside_interval",
            interval_lower=89.0,
            interval_upper=91.0,
        ),
        TiltOfComponentsInputs(express_ids=[21]),
        context,
    )

    assert result.elements[0].checks[0].passed is True
    assert result.elements[0].checks[0].expected == "inside 89 and 91"


def test_less_than_upper_flags_shallow_surface() -> None:
    context = _context()
    _add_element(context, 22, _box([4.0, 3.0, 0.2]))  # tilt 0 (slab)

    result = _run(
        TiltOfComponentsSettings(
            element_category="2d",
            comparison_method="less_than_upper",
            upper_limit=1.0,
        ),
        TiltOfComponentsInputs(express_ids=[22]),
        context,
    )

    assert result.elements[0].checks[0].passed is False


# --- edge cases --------------------------------------------------------------


def test_missing_express_id_produces_unknown_element_without_checks() -> None:
    context = _context()

    result = _run(
        TiltOfComponentsSettings(),
        TiltOfComponentsInputs(express_ids=[999]),
        context,
    )

    element = result.elements[0]
    assert element.class_name == "unknown"
    assert element.checks == []
    assert element.failed is False


def test_empty_input_gathers_all_ifc_elements() -> None:
    context = _context()
    _add_element(context, 30, _box([4.0, 0.2, 3.0]))
    _add_element(context, 31, _box([0.3, 0.3, 4.0]))

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[]),
        context,
    )

    assert result.element_count == 2
    assert result.check_count == 2


def _add_decomposed(
    context: ExecutionContext,
    parent_id: int,
    parent_is_a: str,
    children: list[_FakeEntity],
) -> None:
    model = cast(Any, context.ifc_model)
    parent = _FakeEntity(parent_id, parent_is_a, [_FakeRelAggregates(children)])
    model._entities[parent_id] = parent
    for child in children:
        model._entities[child.id()] = child


# --- decomposed / composite elements ------------------------------------------


def test_decomposed_parent_without_body_measured_from_part_meshes() -> None:
    context = _context()
    child_a = _FakeEntity(2, "IFCBUILDINGELEMENTPART")
    child_b = _FakeEntity(3, "IFCBUILDINGELEMENTPART")
    _add_decomposed(context, 1, "IFCWALL", [child_a, child_b])
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=2)
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=3)

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    element = result.elements[0]
    assert element.class_name == "IFCWALL"
    assert len(element.checks) == 2
    for check in element.checks:
        assert check.tilt_angle == 90.0
    assert result.check_count == 1


def test_recursive_nested_decomposition_collects_descendant_meshes() -> None:
    context = _context()
    grandchild = _FakeEntity(3, "IFCBUILDINGELEMENTPART")
    child = _FakeEntity(2, "IFCBUILDINGELEMENTPART", [_FakeRelAggregates([grandchild])])
    _add_decomposed(context, 1, "IFCWALL", [child])
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=3)

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    assert len(result.elements[0].checks) == 2
    for check in result.elements[0].checks:
        assert check.tilt_angle == 90.0


def test_decomposed_parent_and_parts_all_measured() -> None:
    context = _context()
    child_a = _FakeEntity(2, "IFCBUILDINGELEMENTPART")
    child_b = _FakeEntity(3, "IFCBUILDINGELEMENTPART")
    _add_decomposed(context, 1, "IFCWALL", [child_a, child_b])
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=2)
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=3)

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1, 2, 3]),
        context,
    )

    assert result.element_count == 3
    assert result.check_count == 3
    classes = {element.class_name for element in result.elements}
    assert classes == {"IFCWALL", "IFCBUILDINGELEMENTPART"}


def test_parent_with_own_body_ignores_decomposition() -> None:
    context = _context()
    child = _FakeEntity(2, "IFCBUILDINGELEMENTPART")
    _add_decomposed(context, 1, "IFCWALL", [child])
    # own body = horizontal slab (tilt 0); child = vertical (tilt 90)
    cache_mesh(context, _box([4.0, 3.0, 0.2]), express_id=1)
    cache_mesh(context, _box([4.0, 0.2, 3.0]), express_id=2)

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    for check in result.elements[0].checks:
        assert check.tilt_angle == 0.0


def test_decomposition_cycle_does_not_loop() -> None:
    context = _context()
    child = _FakeEntity(2, "IFCBUILDINGELEMENTPART", [])
    parent = _FakeEntity(1, "IFCWALL", [_FakeRelAggregates([child])])
    child.IsDecomposedBy = [_FakeRelAggregates([parent])]
    cast(Any, context.ifc_model)._entities[1] = parent
    cast(Any, context.ifc_model)._entities[2] = child

    result = _run(
        TiltOfComponentsSettings(element_category="2d"),
        TiltOfComponentsInputs(express_ids=[1]),
        context,
    )

    assert result.element_count == 1
    assert result.elements[0].checks == []
