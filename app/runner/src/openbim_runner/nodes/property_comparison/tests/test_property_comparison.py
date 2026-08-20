from __future__ import annotations

import asyncio
import math
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.property_comparison.property_comparison import (
    ComparisonRow,
    PropertyComparisonInputs,
    PropertyComparisonSettings,
    property_comparison,
)


class FakeEntity:
    def __init__(
        self, express_id: int, entity_type: str = "IFCWALL", **attributes: Any
    ) -> None:
        self._express_id = express_id
        self._entity_type = entity_type.upper()
        self.psets: dict[str, dict[str, Any]] = attributes.pop("psets", {})
        for key, value in attributes.items():
            setattr(self, key, value)

    def id(self) -> int:
        return self._express_id

    def is_a(self, type_name: str | None = None) -> str | bool:
        if type_name is None:
            return self._entity_type
        return self._entity_type == type_name.upper()


class FakeIfcModel:
    def __init__(self, entities_by_id: dict[int, FakeEntity]) -> None:
        self.entities_by_id = entities_by_id

    def by_id(self, express_id: int) -> FakeEntity:
        if express_id not in self.entities_by_id:
            raise RuntimeError("Unknown express ID")
        return self.entities_by_id[express_id]

    def by_type(self, type_name: str) -> list[FakeEntity]:
        entities = list(self.entities_by_id.values())
        if type_name.upper() == "IFCELEMENT":
            # In the fake, any entity is treated as an IfcElement subtype.
            return entities
        return [entity for entity in entities if entity.is_a(type_name)]


def _fake_get_psets(entity: FakeEntity) -> dict[str, dict[str, Any]]:
    return entity.psets


def _run(
    monkeypatch: pytest.MonkeyPatch,
    model: FakeIfcModel,
    rows: list[ComparisonRow],
    express_ids: list[int],
) -> Any:
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)
    context = ExecutionContext(ifc_model=cast(Any, model), node_outputs={})
    return asyncio.run(
        property_comparison(
            PropertyComparisonSettings(rows=rows),
            PropertyComparisonInputs(express_ids=express_ids),
            context,
        )
    )


def test_comparison_emits_class(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(
        101,
        GlobalId="guid-123",
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="FireRating",
                condition="equals",
                expected_value="F90",
            )
        ],
        [101],
    )

    assert result.element_count == 1
    assert result.elements[0].express_id == 101
    assert result.elements[0].class_name == "IFCWALL"
    assert result.elements[0].failed is False


def test_equals_pass_and_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"IsExternal": True}},
    )
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="IsExternal",
                condition="equals",
                expected_value="true",
            )
        ],
        [101],
    )

    check = result.elements[0].checks[0]
    assert check.passed is True
    assert check.actual == "true"
    assert check.property_key == "Pset_WallCommon.IsExternal"
    assert check.id == "Pset_WallCommon.IsExternal"
    assert result.failed_count == 0


def test_not_equals_and_multi_row(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"LoadBearing": True, "Length": 12}},
    )
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="LoadBearing",
                condition="equals",
                expected_value="true",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="lt",
                expected_value="10",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="not_equals",
                expected_value="11",
            ),
        ],
        [101],
    )

    assert result.total_checks == 3
    assert [check.passed for check in result.elements[0].checks] == [True, False, True]
    assert result.failed_count == 1
    assert result.elements[0].failed is True


def test_numeric_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="lt",
                expected_value="6",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="le",
                expected_value="5",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="gt",
                expected_value="4",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="ge",
                expected_value="5",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="lt",
                expected_value="5",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="gt",
                expected_value="5",
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [
        True,
        True,
        True,
        True,
        False,
        False,
    ]


def test_numeric_non_numeric_value_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"FireRating": "F90"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="FireRating",
                condition="lt",
                expected_value="10",
            )
        ],
        [101],
    )

    check = result.elements[0].checks[0]
    assert check.actual == "F90"
    assert check.passed is False


def test_numeric_non_numeric_expected_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="lt",
                expected_value="abc",
            )
        ],
        [101],
    )

    assert result.elements[0].checks[0].passed is False


def test_contains_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"Name": "FireWall-A"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="Wall",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="wall",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="FIRE",
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [True, True, True]


def test_equals_and_not_equals_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "Concrete"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="equals",
                expected_value="concrete",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="equals",
                expected_value="CONCRETE",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="not_equals",
                expected_value="wood",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="not_equals",
                expected_value="Concrete",
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [
        True,
        True,
        True,
        False,
    ]


def test_equals_not_equals_whitespace_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "  Concrete "}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="equals",
                expected_value="concrete",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="equals",
                expected_value="  Concrete  ",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="not_equals",
                expected_value="wood",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="not_equals",
                expected_value=" Concrete",
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [
        True,
        True,
        True,
        False,
    ]


def test_contains_whitespace_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"Name": "  Fire Wall A "}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="wall",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="  fire  ",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Name",
                condition="contains",
                expected_value="slab",
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [True, True, False]


def test_string_leading_trailing_whitespace_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(
        101,
        psets={"Pset_A": {"Material": "  Reinforced Concrete  ", "Name": "Fire Wall"}},
    )
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="equals",
                expected_value="Reinforced Concrete",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="not_equals",
                expected_value="ReinforcedConcrete",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Name",
                condition="contains",
                expected_value="fire wall",
            ),
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["   Reinforced Concrete   "],
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [
        True,
        True,
        True,
        True,
    ]


def test_is_true_accepts_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(
        101,
        psets={"Pset_A": {"A": True, "B": 1, "C": "yes", "D": "NO", "E": 0}},
    )
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A", property_name="A", condition="is_true"
            ),
            ComparisonRow(
                property_set="Pset_A", property_name="B", condition="is_true"
            ),
            ComparisonRow(
                property_set="Pset_A", property_name="C", condition="is_true"
            ),
            ComparisonRow(
                property_set="Pset_A", property_name="D", condition="is_false"
            ),
            ComparisonRow(
                property_set="Pset_A", property_name="E", condition="is_false"
            ),
        ],
        [101],
    )

    assert [check.passed for check in result.elements[0].checks] == [
        True,
        True,
        True,
        True,
        True,
    ]


def test_is_true_unknown_is_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"A": "nothing"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [ComparisonRow(property_set="Pset_A", property_name="A", condition="is_true")],
        [101],
    )

    assert result.elements[0].checks[0].passed is False


def test_missing_property_fails_all(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_WallCommon": {"FireRating": "F90"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="AcousticRating",
                condition="equals",
                expected_value="x",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="AcousticRating",
                condition="is_true",
            ),
        ],
        [101],
    )

    for check in result.elements[0].checks:
        assert check.actual is None
        assert check.passed is False


def test_entity_type_filters_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [101, 202],
    )

    # Only the wall (matching IFCWALL) is emitted; the door is excluded entirely.
    assert [e.express_id for e in result.elements] == [101]
    wall_elem = result.elements[0]
    assert wall_elem.checks[0].passed is True
    assert result.element_count == 1
    assert result.total_checks == 1


def test_entity_type_multiple_components_union(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    slab = FakeEntity(202, entity_type="IFCSLAB", psets={"Pset_A": {"X": "2"}})
    door = FakeEntity(303, entity_type="IFCDOOR", psets={"Pset_A": {"X": "3"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: slab, 303: door}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            ),
            ComparisonRow(
                entity_type="IFCSLAB",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="2",
            ),
        ],
        [101, 202, 303],
    )

    # Wall and slab (specified components) are emitted; door is excluded.
    assert {e.express_id for e in result.elements} == {101, 202}
    assert result.element_count == 2


def test_entity_type_missing_express_id_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [101, 999],
    )

    # Missing express ID (unknown type) is excluded when a component is specified.
    assert [e.express_id for e in result.elements] == [101]


def test_entity_type_empty_keeps_all_input(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [101, 202],
    )

    # No Component specified -> all input elements are emitted.
    assert {e.express_id for e in result.elements} == {101, 202}
    assert result.element_count == 2
    assert result.total_checks == 2


def test_any_element_empty_row_disables_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            ),
            ComparisonRow(
                entity_type="",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="2",
            ),
        ],
        [101, 202],
    )

    # The empty (Any Element) row disables output filtering -> all input emitted.
    assert {e.express_id for e in result.elements} == {101, 202}
    wall_elem = next(e for e in result.elements if e.express_id == 101)
    door_elem = next(e for e in result.elements if e.express_id == 202)
    assert len(wall_elem.checks) == 2
    assert len(door_elem.checks) == 1
    assert result.element_count == 2


def test_literal_any_token_disables_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            ),
            ComparisonRow(
                entity_type="Any",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="2",
            ),
        ],
        [101, 202],
    )

    # The literal "any" token (case-insensitive) disables output filtering too.
    assert {e.express_id for e in result.elements} == {101, 202}
    wall_elem = next(e for e in result.elements if e.express_id == 101)
    door_elem = next(e for e in result.elements if e.express_id == 202)
    assert len(wall_elem.checks) == 2
    assert len(door_elem.checks) == 1
    assert result.element_count == 2


def test_missing_express_id_unknown_class(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run(
        monkeypatch,
        FakeIfcModel({}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [999],
    )

    elem = result.elements[0]
    assert elem.class_name == "unknown"
    assert elem.failed is False


def test_requires_at_least_one_row() -> None:
    context = ExecutionContext(ifc_model=cast(Any, FakeIfcModel({})), node_outputs={})
    with pytest.raises(
        ValueError, match="At least one comparison row must be specified"
    ):
        asyncio.run(
            property_comparison(
                PropertyComparisonSettings(rows=[]),
                PropertyComparisonInputs(express_ids=[]),
                context,
            )
        )


def test_requires_property_name() -> None:
    context = ExecutionContext(ifc_model=cast(Any, FakeIfcModel({})), node_outputs={})
    with pytest.raises(ValueError, match="Comparison row 1 must have a property name"):
        asyncio.run(
            property_comparison(
                PropertyComparisonSettings(
                    rows=[
                        ComparisonRow(
                            property_set="Pset_A",
                            property_name="",
                            condition="equals",
                            expected_value="1",
                        )
                    ]
                ),
                PropertyComparisonInputs(express_ids=[]),
                context,
            )
        )


def test_company_level_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    wall1 = FakeEntity(
        101, psets={"Pset_WallCommon": {"LoadBearing": False, "Length": 12}}
    )
    wall2 = FakeEntity(
        102, psets={"Pset_WallCommon": {"LoadBearing": True, "Length": 14}}
    )

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall1, 102: wall2}),
        [
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="LoadBearing",
                condition="equals",
                expected_value="true",
            ),
            ComparisonRow(
                property_set="Pset_WallCommon",
                property_name="Length",
                condition="lt",
                expected_value="10",
            ),
        ],
        [101, 102],
    )

    assert result.element_count == 2
    assert result.total_checks == 4
    assert result.failed_count == 3
    assert [e.failed for e in result.elements] == [True, True]


def test_float_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Ratio": math.nan}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Ratio",
                condition="le",
                expected_value="1",
            )
        ],
        [101],
    )
    # NaN cannot be meaningfully compared; float('nan') converts but comparisons are False
    assert result.elements[0].checks[0].passed is False


def test_range_between_inclusive_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="between",
                range_min="3",
                range_max="5",
                inclusive_min=True,
                inclusive_max=True,
            )
        ],
        [101],
    )
    check = result.elements[0].checks[0]
    assert check.passed is True
    assert check.condition == "between"
    assert check.expected_min == "3"
    assert check.expected_max == "5"


def test_range_between_exclusive_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="between",
                range_min="3",
                range_max="5",
                inclusive_min=False,
                inclusive_max=False,
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is False  # == max, exclusive -> out


def test_range_between_inclusive_mixed_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="between",
                range_min="5",
                range_max="6",
                inclusive_min=True,
                inclusive_max=False,
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is True  # min inclusive


def test_range_outside_inclusive_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 3}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="outside",
                range_min="4",
                range_max="10",
                inclusive_min=True,
                inclusive_max=True,
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is True  # 3 outside [4,10]


def test_range_outside_exclusive_boundary_equal_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 4}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="outside",
                range_min="4",
                range_max="10",
                inclusive_min=True,
                inclusive_max=True,
            )
        ],
        [101],
    )
    # 4 equals the (inclusive) min -> inside -> not outside
    assert result.elements[0].checks[0].passed is False


def test_range_non_numeric_actual_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": "F90"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="between",
                range_min="3",
                range_max="5",
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is False


def test_range_non_numeric_barrier_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="must both be numeric"):
        _run(
            monkeypatch,
            FakeIfcModel({}),
            [
                ComparisonRow(
                    property_set="Pset_A",
                    property_name="L",
                    condition="between",
                    range_min="abc",
                    range_max="5",
                )
            ],
            [],
        )


def test_range_partial_barrier_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="both range_min and range_max"):
        _run(
            monkeypatch,
            FakeIfcModel({}),
            [
                ComparisonRow(
                    property_set="Pset_A",
                    property_name="L",
                    condition="between",
                    range_min="3",
                )
            ],
            [],
        )


def test_range_inverted_barriers_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(
        ValueError, match="range_min must be less than or equal to range_max"
    ):
        _run(
            monkeypatch,
            FakeIfcModel({}),
            [
                ComparisonRow(
                    property_set="Pset_A",
                    property_name="L",
                    condition="between",
                    range_min="10",
                    range_max="2",
                )
            ],
            [],
        )


def test_single_mode_ignores_range_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Length": 5}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Length",
                condition="ge",
                expected_value="4",
            )
        ],
        [101],
    )
    check = result.elements[0].checks[0]
    assert check.passed is True
    assert check.condition == "ge"
    assert check.expected_min is None
    assert check.expected_max is None


def test_one_of_matches_any_allowed_value(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "concrete"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["wood", "concrete", "masonry"],
            )
        ],
        [101],
    )
    check = result.elements[0].checks[0]
    assert check.passed is True
    assert check.condition == "one_of"
    assert check.expected == "wood, concrete, masonry"


def test_one_of_no_match_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "steel"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["wood", "concrete", "masonry"],
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is False


def test_one_of_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "CONCRETE"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["concrete"],
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is True


def test_one_of_ignores_blank_allowed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Material": "wood"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["", "wood", "", "  "],
            )
        ],
        [101],
    )
    assert result.elements[0].checks[0].passed is True
    assert result.elements[0].checks[0].expected == "wood"


def test_one_of_missing_property_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, psets={"Pset_A": {"Other": "x"}})
    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="Material",
                condition="one_of",
                allowed_values=["wood"],
            )
        ],
        [101],
    )
    check = result.elements[0].checks[0]
    assert check.actual is None
    assert check.passed is False


def test_one_of_requires_allowed_value(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="requires at least one allowed value"):
        _run(
            monkeypatch,
            FakeIfcModel({}),
            [
                ComparisonRow(
                    property_set="Pset_A",
                    property_name="Material",
                    condition="one_of",
                    allowed_values=[],
                )
            ],
            [],
        )


def test_contains_requires_non_empty_target(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="requires a non-empty expected value"):
        _run(
            monkeypatch,
            FakeIfcModel({}),
            [
                ComparisonRow(
                    property_set="Pset_A",
                    property_name="Name",
                    condition="contains",
                    expected_value="   ",
                )
            ],
            [],
        )


def test_optional_input_without_component_uses_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [],  # no express_ids -> fall back to all elements from context
    )

    assert {e.express_id for e in result.elements} == {101, 202}
    assert result.element_count == 2
    assert result.total_checks == 2


def test_optional_input_with_component_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_A": {"X": "1"}})
    door = FakeEntity(202, entity_type="IFCDOOR", psets={"Pset_A": {"X": "2"}})

    result = _run(
        monkeypatch,
        FakeIfcModel({101: wall, 202: door}),
        [
            ComparisonRow(
                entity_type="IFCWALL",
                property_set="Pset_A",
                property_name="X",
                condition="equals",
                expected_value="1",
            )
        ],
        [],  # no express_ids -> use all elements, then Component filters to walls
    )

    assert [e.express_id for e in result.elements] == [101]
    assert result.element_count == 1
    assert result.total_checks == 1
