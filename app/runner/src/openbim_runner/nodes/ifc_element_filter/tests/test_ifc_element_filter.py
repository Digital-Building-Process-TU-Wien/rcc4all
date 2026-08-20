from __future__ import annotations

import asyncio
from importlib import import_module
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.ifc_element_filter.ifc_element_filter import (
    FilterRow,
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
        self.psets: dict[str, dict[str, object]] = attributes.pop("psets", {})
        for key, value in attributes.items():
            setattr(self, key, value)

    def id(self) -> int:
        return self._express_id


class FakeIfcModel:
    def __init__(self, entities_by_type: dict[str, list[FakeEntity]]) -> None:
        self.entities_by_type = {
            key.upper(): value for key, value in entities_by_type.items()
        }

    def by_type(self, entity_type: str) -> list[FakeEntity]:
        entity_type = entity_type.upper()
        if entity_type == "IFCUNKNOWN":
            raise RuntimeError("Unknown entity type")
        return self.entities_by_type.get(entity_type, [])


def _fake_get_psets(entity: FakeEntity) -> dict[str, dict[str, object]]:
    return entity.psets


def run_filter(
    settings: IfcElementFilterSettings, ifc_model: FakeIfcModel
) -> IfcElementFilterResult:
    context = ExecutionContext(ifc_model=cast(Any, ifc_model), node_outputs={})
    return asyncio.run(ifc_element_filter(settings, context))


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
