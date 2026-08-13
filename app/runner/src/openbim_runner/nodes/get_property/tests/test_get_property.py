from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_property.get_property import (
    GetPropertyInputs,
    GetPropertySettings,
    PropertySelection,
    ValueWithCount,
    get_property,
)


class FakeEntity:
    def __init__(self, express_id: int, entity_type: str = "IFCWALL", **attributes: Any) -> None:
        self._express_id = express_id
        self._entity_type = entity_type.upper()
        self.psets: dict[str, dict[str, Any]] = attributes.pop("psets", {})
        for key, value in attributes.items():
            setattr(self, key, value)

    def id(self) -> int:
        return self._express_id

    def is_a(self, type_name: str | None = None) -> str | bool:
        """Return the entity type string, or check if it matches a given type."""
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


def _fake_get_psets(entity: FakeEntity) -> dict[str, dict[str, Any]]:
    return entity.psets


def test_get_property_reads_property_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_property reads property values from entities."""
    wall = FakeEntity(
        101,
        GlobalId="test-wall",
        Name="Test Wall",
        psets={"Pset_WallCommon": {"FireRating": "F90", "IsExternal": False}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                    ),
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="IsExternal",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert len(result.elements) == 1
    assert result.elements[0].express_id == 101
    assert result.elements[0].properties == {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.IsExternal": "false",
    }


def test_get_property_multiple_entities(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_property reads values for multiple entities."""
    wall1 = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )
    wall2 = FakeEntity(
        205,
        psets={"Pset_WallCommon": {"FireRating": "F30"}},
    )
    wall3 = FakeEntity(
        77,
        psets={"Pset_WallCommon": {"FireRating": "F60"}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2, 77: wall3})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205, 77]),
            context,
        )
    )

    assert len(result.elements) == 3
    assert result.elements[0].express_id == 101
    assert result.elements[0].properties == {"Pset_WallCommon.FireRating": "F90"}
    assert result.elements[1].express_id == 205
    assert result.elements[1].properties == {"Pset_WallCommon.FireRating": "F30"}
    assert result.elements[2].express_id == 77
    assert result.elements[2].properties == {"Pset_WallCommon.FireRating": "F60"}


def test_get_property_missing_property_returns_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing properties return null."""
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                    ),
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="AcousticRating",  # not present
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.AcousticRating": None,
    }


def test_get_property_missing_express_id_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing express_id returns element with empty properties."""
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 999]),  # 999 doesn't exist
            context,
        )
    )

    assert len(result.elements) == 2
    assert result.elements[0].express_id == 101
    assert result.elements[0].properties == {"Pset_WallCommon.FireRating": "F90"}
    assert result.elements[1].express_id == 999
    assert result.elements[1].properties == {}


def test_get_property_without_property_set_searches_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty property_set searches across all psets."""
    wall = FakeEntity(
        101,
        psets={
            "Pset_WallCommon": {"FireRating": "F90"},
            "Custom_Pset": {"MyProperty": "custom_value"},
        },
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="",  # search all
                        property_name="MyProperty",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {"MyProperty": "custom_value"}


def test_get_property_requires_at_least_one_selection() -> None:
    """Test that get_property raises error if no selections are specified."""
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="At least one property selection must be specified"):
        asyncio.run(
            get_property(
                GetPropertySettings(
                    selections=[],
                ),
                GetPropertyInputs(express_ids=[]),
                context,
            )
        )


def test_get_property_requires_property_name_in_each_selection() -> None:
    """Test that get_property raises error if a selection has no property name."""
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="Selection 1 must have a property name"):
        asyncio.run(
            get_property(
                GetPropertySettings(
                    selections=[
                        PropertySelection(
                            property_set="Pset_WallCommon",
                            property_name="",
                        ),
                    ],
                ),
                GetPropertyInputs(express_ids=[]),
                context,
            )
        )


def test_get_property_fallback_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that fallback uses manual value when property is missing."""
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                        source="from_model",
                    ),
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="AcousticRating",  # missing
                        source="fallback",
                        manual_value="Rw45",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.AcousticRating": "Rw45",  # fallback applied
    }


def test_get_property_fallback_on_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that fallback uses manual value when property value is empty string."""
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90", "Comments": ""}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="Comments",
                        source="fallback",
                        manual_value="No comments",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.Comments": "No comments"}


def test_get_property_override_ignores_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that override always uses manual value, ignoring the model."""
    wall = FakeEntity(
        101,
        psets={"Pset_WallCommon": {"FireRating": "F90"}},
    )

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                        source="override",
                        manual_value="F120",  # override value
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.FireRating": "F120"}


def test_get_property_manual_value_required_for_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that manual_value is required when source is fallback."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="Selection 1 requires a manual value when source is 'fallback'"):
        asyncio.run(
            get_property(
                GetPropertySettings(
                    selections=[
                        PropertySelection(
                            property_set="Pset_WallCommon",
                            property_name="FireRating",
                            source="fallback",
                            manual_value="",  # missing
                        ),
                    ],
                ),
                GetPropertyInputs(express_ids=[101]),
                context,
            )
        )


def test_get_property_manual_value_required_for_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that manual_value is required when source is override."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="Selection 1 requires a manual value when source is 'override'"):
        asyncio.run(
            get_property(
                GetPropertySettings(
                    selections=[
                        PropertySelection(
                            property_set="Pset_WallCommon",
                            property_name="FireRating",
                            source="override",
                            manual_value="",  # missing
                        ),
                    ],
                ),
                GetPropertyInputs(express_ids=[101]),
                context,
            )
        )


def test_get_property_output_mode_by_class(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that by_class mode aggregates values with counts per class."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    door = FakeEntity(307, entity_type="IFCDOOR", psets={"Pset_DoorCommon": {"IsExternal": "true"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2, 307: door})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(property_set="Pset_WallCommon", property_name="FireRating"),
                    PropertySelection(property_set="Pset_DoorCommon", property_name="IsExternal"),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205, 307]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 2
    # Alphabetical order: IFCDOOR, IFCWALL
    assert result.classes[0].id == "IFCDOOR"
    assert result.classes[1].id == "IFCWALL"
    # IFCDOOR has one value for IsExternal
    assert "Pset_DoorCommon.IsExternal" in result.classes[0].properties
    assert result.classes[0].properties["Pset_DoorCommon.IsExternal"] == [ValueWithCount(value="true", count=1)]
    # IFCWALL has two F90 values
    assert "Pset_WallCommon.FireRating" in result.classes[1].properties
    assert result.classes[1].properties["Pset_WallCommon.FireRating"] == [ValueWithCount(value="F90", count=2)]


def test_get_property_output_mode_by_class_multiple_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that by_class mode handles multiple properties with distinct values."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": "Yes", "Combustible": "REI30"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": "Yes", "Combustible": "REI30"}})
    wall3 = FakeEntity(307, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": "No", "Combustible": "EI60"}})
    column = FakeEntity(408, entity_type="IFCCOLUMN", psets={"Pset_ColumnCommon": {"LoadBearing": "Yes"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2, 307: wall3, 408: column})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(property_set="Pset_WallCommon", property_name="LoadBearing"),
                    PropertySelection(property_set="Pset_WallCommon", property_name="Combustible"),
                    PropertySelection(property_set="Pset_ColumnCommon", property_name="LoadBearing"),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205, 307, 408]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 2  # IFCCOLUMN, IFCWALL

    # IFCCOLUMN
    column_class = next(c for c in result.classes if c.id == "IFCCOLUMN")
    assert column_class.properties["Pset_ColumnCommon.LoadBearing"] == [ValueWithCount(value="Yes", count=1)]

    # IFCWALL
    wall_class = next(c for c in result.classes if c.id == "IFCWALL")
    # LoadBearing: Yes=2, No=1
    assert wall_class.properties["Pset_WallCommon.LoadBearing"] == [
        ValueWithCount(value="Yes", count=2),
        ValueWithCount(value="No", count=1),
    ]
    # Combustible: REI30=2, EI60=1
    assert wall_class.properties["Pset_WallCommon.Combustible"] == [
        ValueWithCount(value="REI30", count=2),
        ValueWithCount(value="EI60", count=1),
    ]


def test_get_property_output_mode_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that model mode aggregates distinct values with counts."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    wall3 = FakeEntity(307, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F30"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2, 307: wall3})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(property_set="Pset_WallCommon", property_name="FireRating"),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205, 307]),
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    assert "Pset_*.FireRating" in result.properties
    values = result.properties["Pset_*.FireRating"]
    # Sorted by count desc, then value asc: F90 (count 2), F30 (count 1)
    assert len(values) == 2
    assert values[0].value == "F90"
    assert values[0].count == 2
    assert values[1].value == "F30"
    assert values[1].count == 1


def test_get_property_output_mode_model_skips_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that model mode excludes null (missing) values."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {}})  # missing FireRating

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(property_set="Pset_WallCommon", property_name="FireRating"),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205]),
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    assert "Pset_*.FireRating" in result.properties
    # Only F90 counted (wall2's missing value is skipped)
    assert len(result.properties["Pset_*.FireRating"]) == 1
    assert result.properties["Pset_*.FireRating"][0].value == "F90"
    assert result.properties["Pset_*.FireRating"][0].count == 1


def test_get_property_output_mode_default_elements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that default output_mode is 'elements' for backward compatibility."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    # Don't specify output_mode - should default to "elements"
    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(property_set="Pset_WallCommon", property_name="FireRating"),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.mode == "elements"
    assert result.elements is not None
    assert len(result.elements) == 1
    assert result.elements[0].express_id == 101
    assert result.elements[0].properties == {"Pset_WallCommon.FireRating": "F90"}


def test_get_property_entity_type_filters_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that entity_type in a selection filters which entities contribute to the model output."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": True}})
    slab = FakeEntity(202, entity_type="IFCSLAB", psets={"Pset_SlabCommon": {"LoadBearing": False}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall, 202: slab})),
        node_outputs={},
    )

    # Specify entity_type=IFCWALL - should only count the wall
    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 202]),  # both wall and slab in input
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    # Only the wall should contribute, so count should be 1
    assert "Pset_*.LoadBearing" in result.properties
    assert result.properties["Pset_*.LoadBearing"][0].value == "true"
    assert result.properties["Pset_*.LoadBearing"][0].count == 1


def test_get_property_entity_type_filters_by_class_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that entity_type in a selection filters which entities contribute to the by_class output."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": True}})
    slab = FakeEntity(202, entity_type="IFCSLAB", psets={"Pset_SlabCommon": {"LoadBearing": False}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall, 202: slab})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 202]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    # Only IFCWALL class should have the property
    wall_class = next((c for c in result.classes if c.id == "IFCWALL"), None)
    assert wall_class is not None
    assert "Pset_WallCommon.LoadBearing" in wall_class.properties
    assert wall_class.properties["Pset_WallCommon.LoadBearing"][0].count == 1

    # IFCSLAB should not have Pset_WallCommon.LoadBearing
    slab_class = next((c for c in result.classes if c.id == "IFCSLAB"), None)
    assert slab_class is not None
    assert "Pset_WallCommon.LoadBearing" not in slab_class.properties


def test_get_property_empty_entity_type_no_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty entity_type does not filter (all entities contribute)."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": True}})
    slab = FakeEntity(202, entity_type="IFCSLAB", psets={"Pset_WallCommon": {"LoadBearing": True}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall, 202: slab})),
        node_outputs={},
    )

    # entity_type empty - should count both wall and slab
    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(
                        entity_type="",  # empty = no filter
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 202]),
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    # Both entities contribute, count should be 2
    assert result.properties["Pset_*.LoadBearing"][0].count == 2


def test_get_property_by_class_with_empty_inputs_and_manual_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that by_class mode synthesizes entries from manual values when no input elements are connected."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="true",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 1
    assert result.classes[0].id == "IFCWALL"
    assert result.classes[0].properties["Pset_WallCommon.LoadBearing"] == [ValueWithCount(value="true", count=1)]


def test_get_property_model_with_empty_inputs_and_manual_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that model mode synthesizes entries from manual values when no input elements are connected."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="true",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    assert "Pset_*.LoadBearing" in result.properties
    assert result.properties["Pset_*.LoadBearing"] == [ValueWithCount(value="true", count=1)]


def test_get_property_model_mode_merges_across_psets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that model mode merges counts from the same property name across different psets."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Compartmentation": True}})
    wall2 = FakeEntity(102, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Compartmentation": True}})
    slab = FakeEntity(201, entity_type="IFCSLAB", psets={"Pset_SlabCommon": {"Compartmentation": False}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall, 102: wall2, 201: slab})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="model",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="Compartmentation",
                    ),
                    PropertySelection(
                        entity_type="IFCSLAB",
                        property_set="Pset_SlabCommon",
                        property_name="Compartmentation",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 102, 201]),
            context,
        )
    )

    assert result.mode == "model"
    assert result.properties is not None
    # Both psets merge into Pset_*.Compartmentation
    assert "Pset_*.Compartmentation" in result.properties
    values = result.properties["Pset_*.Compartmentation"]
    # true×2 (walls), false×1 (slab)
    assert len(values) == 2
    assert values[0].value == "true"
    assert values[0].count == 2
    assert values[1].value == "false"
    assert values[1].count == 1


def test_get_property_by_class_multiple_manual_selections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that by_class mode handles multiple manual selections across different classes."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="true",
                    ),
                    PropertySelection(
                        entity_type="IFCCOLUMN",
                        property_set="Pset_ColumnCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="false",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 2  # IFCCOLUMN, IFCWALL (alphabetical)
    
    column_class = next(c for c in result.classes if c.id == "IFCCOLUMN")
    assert column_class.properties["Pset_ColumnCommon.LoadBearing"] == [ValueWithCount(value="false", count=1)]
    
    wall_class = next(c for c in result.classes if c.id == "IFCWALL")
    assert wall_class.properties["Pset_WallCommon.LoadBearing"] == [ValueWithCount(value="true", count=1)]


def test_get_property_from_model_with_empty_inputs_contributes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that from_model selections with no input elements produce no output."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="from_model",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 0  # No manual values, no inputs → empty output


def test_get_property_by_class_empty_entity_type_groups_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that manual selections with empty entity_type are grouped under 'unknown'."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="",  # empty → "unknown"
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="true",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 1
    assert result.classes[0].id == "unknown"
    assert result.classes[0].properties["Pset_WallCommon.LoadBearing"] == [ValueWithCount(value="true", count=1)]


def test_get_property_elements_mode_with_empty_inputs_produces_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that elements mode with no input elements produces empty output (no synthesis)."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="elements",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="override",
                        manual_value="true",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "elements"
    assert result.elements is not None
    assert len(result.elements) == 0  # elements mode doesn't synthesize


def test_get_property_by_class_fallback_with_empty_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that fallback source also synthesizes entries when no input elements are connected."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                output_mode="by_class",
                selections=[
                    PropertySelection(
                        entity_type="IFCWALL",
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="fallback",
                        manual_value="yes",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[]),
            context,
        )
    )

    assert result.mode == "by_class"
    assert result.classes is not None
    assert len(result.classes) == 1
    assert result.classes[0].id == "IFCWALL"
    assert result.classes[0].properties["Pset_WallCommon.LoadBearing"] == [ValueWithCount(value="yes", count=1)]


def test_get_property_condition_source_greater_than(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source overrides when model value > threshold."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Area": 45.0}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Area": 20.0}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="Area",
                        source="condition",
                        manual_value="large",
                        condition_operator=">",
                        condition_value="30",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.Area": "large"}  # 45 > 30
    assert result.elements[1].properties == {"Pset_WallCommon.Area": "20.0"}  # 20 <= 30


def test_get_property_condition_source_equal_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source with == operator works for string equality."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Status": "New"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Status": "Existing"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="Status",
                        source="condition",
                        manual_value="renovated",
                        condition_operator="==",
                        condition_value="New",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.Status": "renovated"}  # Status == "New"
    assert result.elements[1].properties == {"Pset_WallCommon.Status": "Existing"}  # Status != "New"


def test_get_property_condition_source_not_equal_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source with != operator works."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F90"}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"FireRating": "F30"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="FireRating",
                        source="condition",
                        manual_value="non-compliant",
                        condition_operator="!=",
                        condition_value="F90",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.FireRating": "F90"}  # F90 == F90, condition false
    assert result.elements[1].properties == {"Pset_WallCommon.FireRating": "non-compliant"}  # F30 != F90


def test_get_property_condition_source_boolean_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source works with boolean model values."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": True}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"LoadBearing": False}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="LoadBearing",
                        source="condition",
                        manual_value="yes",
                        condition_operator="==",
                        condition_value="true",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.LoadBearing": "yes"}  # True == "true"
    assert result.elements[1].properties == {"Pset_WallCommon.LoadBearing": "false"}  # False != "true"


def test_get_property_condition_source_missing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source keeps null when model value is missing."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="AcousticRating",  # missing
                        source="condition",
                        manual_value="fallback",
                        condition_operator=">",
                        condition_value="30",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.AcousticRating": None}


def test_get_property_condition_source_non_numeric_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source handles non-numeric model values gracefully."""
    wall = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Name": "Test Wall"}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall})),
        node_outputs={},
    )

    # Ordering operator on non-numeric: condition doesn't match, keep model value
    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="Name",
                        source="condition",
                        manual_value="overridden",
                        condition_operator=">",
                        condition_value="30",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.Name": "Test Wall"}


def test_get_property_condition_requires_condition_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source requires a condition_value."""
    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="Selection 1 requires a condition value when source is 'condition'"):
        asyncio.run(
            get_property(
                GetPropertySettings(
                    selections=[
                        PropertySelection(
                            property_set="Pset_WallCommon",
                            property_name="Area",
                            source="condition",
                            manual_value="large",
                            condition_value="",  # missing
                        ),
                    ],
                ),
                GetPropertyInputs(express_ids=[101]),
                context,
            )
        )


def test_get_property_condition_source_less_than_or_equal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that condition source with <= operator works correctly."""
    wall1 = FakeEntity(101, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Area": 25.0}})
    wall2 = FakeEntity(205, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Area": 30.0}})
    wall3 = FakeEntity(307, entity_type="IFCWALL", psets={"Pset_WallCommon": {"Area": 35.0}})

    monkeypatch.setattr("ifcopenshell.util.element.get_psets", _fake_get_psets)

    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({101: wall1, 205: wall2, 307: wall3})),
        node_outputs={},
    )

    result = asyncio.run(
        get_property(
            GetPropertySettings(
                selections=[
                    PropertySelection(
                        property_set="Pset_WallCommon",
                        property_name="Area",
                        source="condition",
                        manual_value="small",
                        condition_operator="<=",
                        condition_value="30",
                    ),
                ],
            ),
            GetPropertyInputs(express_ids=[101, 205, 307]),
            context,
        )
    )

    assert result.elements[0].properties == {"Pset_WallCommon.Area": "small"}  # 25 <= 30
    assert result.elements[1].properties == {"Pset_WallCommon.Area": "small"}  # 30 <= 30
    assert result.elements[2].properties == {"Pset_WallCommon.Area": "35.0"}  # 35 > 30
