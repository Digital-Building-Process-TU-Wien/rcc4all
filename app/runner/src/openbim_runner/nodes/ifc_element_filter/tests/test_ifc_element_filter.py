from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.ifc_element_filter.ifc_element_filter import (
    FilterRow,
    IfcElementFilterInputs,
    IfcElementFilterResult,
    IfcElementFilterSettings,
    ifc_element_filter,
)

filter_module = import_module(
    "openbim_runner.nodes.ifc_element_filter.ifc_element_filter"
)


class FakeEntity:
    def __init__(self, express_id: int, **attributes: Any) -> None:
        self._express_id = express_id
        self.type_name = attributes.pop("type_name", "IFCWALL")
        self.psets: dict[str, dict[str, object]] = attributes.pop("psets", {})
        for key, value in attributes.items():
            setattr(self, key, value)

    def id(self) -> int:
        return self._express_id

    def is_a(self, name: str | None = None) -> bool | str:
        if name is None:
            return self.type_name
        return self.type_name == name.upper()


class FakeIfcModel:
    def __init__(self, entities_by_type: dict[str, list[FakeEntity]]) -> None:
        self.entities_by_type: dict[str, list[FakeEntity]] = {}
        self.entities_by_id: dict[int, FakeEntity] = {}
        for key, entities in entities_by_type.items():
            type_name = key.upper()
            for entity in entities:
                entity.type_name = type_name
                self.entities_by_id[entity.id()] = entity
            self.entities_by_type[type_name] = entities

    def by_type(self, entity_type: str) -> list[FakeEntity]:
        entity_type = entity_type.upper()
        if entity_type == "IFCUNKNOWN":
            raise RuntimeError("Unknown entity type")
        return self.entities_by_type.get(entity_type, [])

    def by_id(self, express_id: int) -> FakeEntity:
        try:
            return self.entities_by_id[express_id]
        except KeyError:
            raise RuntimeError(f"Entity {express_id} not found") from None


def _fake_get_psets(entity: FakeEntity) -> dict[str, dict[str, object]]:
    return entity.psets


def run_filter(
    settings: IfcElementFilterSettings,
    ifc_model: FakeIfcModel,
    inputs: IfcElementFilterInputs | None = None,
) -> IfcElementFilterResult:
    context = ExecutionContext(ifc_model=cast(Any, ifc_model), node_outputs={})
    return asyncio.run(
        ifc_element_filter(settings, inputs or IfcElementFilterInputs(), context)
    )


def test_ifc_element_filter_include_and_exclude_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall_inside = FakeEntity(
        1,
        GlobalId="wall-inside",
        Name="Inside wall",
        PredefinedType="STANDARD",
        psets={"Pset_WallCommon": {"IsExternal": False}},
    )
    wall_outside = FakeEntity(
        2,
        GlobalId="wall-outside",
        Name="Outside wall",
        PredefinedType="STANDARD",
        psets={"Pset_WallCommon": {"IsExternal": True}},
    )

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(
            filter_rows=[
                FilterRow(mode="include", entity_type="IFCWALL"),
                FilterRow(
                    mode="exclude",
                    entity_type="IFCWALL",
                    property_set="Pset_WallCommon",
                    property_name="IsExternal",
                    value="True",
                ),
            ]
        ),
        FakeIfcModel({"IFCWALL": [wall_inside, wall_outside]}),
    )

    assert result.express_ids == [1]
    assert result.guids == ["wall-inside"]


def test_ifc_element_filter_matches_attribute_and_predefined_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door = FakeEntity(
        10, GlobalId="door-1", Name="Main Entrance", PredefinedType="DOOR"
    )
    gate = FakeEntity(11, GlobalId="gate-1", Name="Main Gate", PredefinedType="GATE")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(
            filter_rows=[
                FilterRow(
                    mode="include",
                    entity_type="IFCDOOR",
                    predefined_type="DOOR",
                    property_name="Name",
                    operator="contains",
                    value="entrance",
                )
            ]
        ),
        FakeIfcModel({"IFCDOOR": [door, gate]}),
    )

    assert result.express_ids == [10]
    assert result.guids == ["door-1"]


def test_ifc_element_filter_unknown_entity_type_returns_empty() -> None:
    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCUNKNOWN")]),
        FakeIfcModel({}),
    )

    assert result.express_ids == []
    assert result.guids == []


def test_ifc_element_filter_empty_entity_type_searches_all_ifc_elements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    internal = FakeEntity(
        20,
        GlobalId="internal-element",
        psets={"Pset_WallCommon": {"IsExternal": False}},
    )
    external = FakeEntity(
        21,
        GlobalId="external-element",
        psets={"Pset_WallCommon": {"IsExternal": True}},
    )

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(
            filter_rows=[
                FilterRow(
                    entity_type="",
                    property_set="Pset_WallCommon",
                    property_name="IsExternal",
                    value="True",
                )
            ]
        ),
        FakeIfcModel({"IFCELEMENT": [internal, external]}),
    )

    assert result.express_ids == [21]
    assert result.guids == ["external-element"]


def test_ifc_element_filter_restricts_to_input_express_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(1, GlobalId="wall-1")
    door = FakeEntity(2, GlobalId="door-1")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall], "IFCDOOR": [door]}),
        inputs=IfcElementFilterInputs(express_ids=[1, 2]),
    )

    assert result.express_ids == [1]
    assert result.guids == ["wall-1"]


def test_ifc_element_filter_output_follows_input_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall_a = FakeEntity(1, GlobalId="wall-a")
    wall_b = FakeEntity(2, GlobalId="wall-b")
    wall_c = FakeEntity(3, GlobalId="wall-c")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall_a, wall_b, wall_c]}),
        inputs=IfcElementFilterInputs(express_ids=[3, 1, 2]),
    )

    assert result.express_ids == [3, 1, 2]
    assert result.guids == ["wall-c", "wall-a", "wall-b"]


def test_ifc_element_filter_input_deduplicates_express_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(1, GlobalId="wall-1")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall]}),
        inputs=IfcElementFilterInputs(express_ids=[1, 1, 1]),
    )

    assert result.express_ids == [1]


def test_ifc_element_filter_unknown_input_express_id_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(1, GlobalId="wall-1")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall]}),
        inputs=IfcElementFilterInputs(express_ids=[1, 999]),
    )

    assert result.express_ids == [1]
    assert result.guids == ["wall-1"]


def test_ifc_element_filter_input_applies_exclude_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall_inside = FakeEntity(
        1,
        GlobalId="wall-inside",
        psets={"Pset_WallCommon": {"IsExternal": False}},
    )
    wall_outside = FakeEntity(
        2,
        GlobalId="wall-outside",
        psets={"Pset_WallCommon": {"IsExternal": True}},
    )

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    result = run_filter(
        IfcElementFilterSettings(
            filter_rows=[
                FilterRow(mode="include", entity_type="IFCWALL"),
                FilterRow(
                    mode="exclude",
                    entity_type="IFCWALL",
                    property_set="Pset_WallCommon",
                    property_name="IsExternal",
                    value="True",
                ),
            ]
        ),
        FakeIfcModel({"IFCWALL": [wall_inside, wall_outside]}),
        inputs=IfcElementFilterInputs(express_ids=[2, 1]),
    )

    assert result.express_ids == [1]
    assert result.guids == ["wall-inside"]


def test_ifc_element_filter_connected_empty_input_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(1, GlobalId="wall-1")
    door = FakeEntity(2, GlobalId="door-1")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    # A connected input that resolved to no matches must NOT fall back to
    # scanning the whole model.
    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall], "IFCDOOR": [door]}),
        inputs=IfcElementFilterInputs(express_ids=[]),
    )

    assert result.express_ids == []
    assert result.guids == []


def test_ifc_element_filter_unbound_input_scans_whole_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wall = FakeEntity(1, GlobalId="wall-1")
    door = FakeEntity(2, GlobalId="door-1")

    monkeypatch.setattr(filter_module, "get_psets", _fake_get_psets)

    # No input connected (express_ids defaults to None) keeps the legacy
    # whole-model behavior.
    result = run_filter(
        IfcElementFilterSettings(filter_rows=[FilterRow(entity_type="IFCWALL")]),
        FakeIfcModel({"IFCWALL": [wall], "IFCDOOR": [door]}),
    )

    assert result.express_ids == [1]
    assert result.guids == ["wall-1"]
