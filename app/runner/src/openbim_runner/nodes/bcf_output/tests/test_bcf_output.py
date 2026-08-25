from __future__ import annotations

import asyncio
import uuid
import zipfile
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.bcf_output.bcf_output import (
    BcfOutputInputs,
    BcfOutputSettings,
    bcf_output,
)
from openbim_runner.nodes.loi_check.loi_check import (
    ComparisonCondition,
    ComparisonElement,
    PropertyCheckResult,
)


class FakeEntity:
    def __init__(
        self, express_id: int, global_id: str, name: str | None = None
    ) -> None:
        self._express_id = express_id
        self.GlobalId = global_id
        self.Name = name

    def id(self) -> int:
        return self._express_id


class FakeIfcModel:
    def __init__(self, entities_by_id: dict[int, FakeEntity]) -> None:
        self.entities_by_id = entities_by_id

    def by_id(self, express_id: int) -> FakeEntity:
        if express_id not in self.entities_by_id:
            raise RuntimeError("Unknown express ID")
        return self.entities_by_id[express_id]


def _failing_check(
    property_key: str = "Pset_WallCommon.ThermalTransmittance",
    property_name: str = "ThermalTransmittance",
    actual: str | None = "15",
    condition: ComparisonCondition = "lt",
    expected: str = "10",
) -> PropertyCheckResult:
    return PropertyCheckResult(
        id=property_key,
        property_key=property_key,
        property_name=property_name,
        condition=condition,
        expected=expected,
        actual=actual,
        passed=False,
    )


def _passing_check() -> PropertyCheckResult:
    return PropertyCheckResult(
        id="Pset_WallCommon.LoadBearing",
        property_key="Pset_WallCommon.LoadBearing",
        property_name="LoadBearing",
        condition="equals",
        expected="true",
        actual="true",
        passed=True,
    )


def _run(
    model: FakeIfcModel,
    settings: BcfOutputSettings,
    elements: list[ComparisonElement],
    tmp_path: Path,
) -> Any:
    context = ExecutionContext(
        ifc_model=cast(Any, model), node_outputs={}, output_dir=tmp_path
    )
    return asyncio.run(
        bcf_output(settings, BcfOutputInputs(elements=elements), context)
    )


def test_one_topic_per_failing_check(tmp_path: Path) -> None:
    model = FakeIfcModel(
        {
            101: FakeEntity(101, "guid-111", name="Wall A"),
            102: FakeEntity(102, "guid-222", name="Wall B"),
        }
    )
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(), _passing_check()],
        ),
        ComparisonElement(
            express_id=102,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(actual="20")],
        ),
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{class_name} {name} failed {Pset_WallCommon.ThermalTransmittance.property_name}",
            description_template=(
                "{name} has {Pset_WallCommon.ThermalTransmittance.actual} for {Pset_WallCommon.ThermalTransmittance.property_name}"
            ),
        ),
        elements,
        tmp_path,
    )

    assert result.topic_count == 2
    assert result.failed_check_count == 2
    assert result.element_count == 2
    assert [topic.guid for topic in result.topics] == ["guid-111", "guid-222"]
    assert [topic.title for topic in result.topics] == [
        "IFCWALL Wall A failed ThermalTransmittance",
        "IFCWALL Wall B failed ThermalTransmittance",
    ]
    assert [topic.description for topic in result.topics] == [
        "Wall A has 15 for ThermalTransmittance",
        "Wall B has 20 for ThermalTransmittance",
    ]


def test_written_file_is_valid_bcf(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{guid}",
            description_template="{class_name} name={name} actual={Pset_WallCommon.ThermalTransmittance.actual}",
        ),
        elements,
        tmp_path,
    )

    assert result.output_path.startswith(str(tmp_path))
    filename = sorted(tmp_path.glob("bcf_output-*.bcf"))[-1]
    assert filename.exists()

    with zipfile.ZipFile(filename) as archive:
        names = archive.namelist()
        assert "bcf.version" in names
        assert "project.bcfp" in names
        markup_names = [n for n in names if n.endswith("/markup.bcf")]
        assert len(markup_names) == 1
        markup = archive.read(markup_names[0]).decode("utf-8")
        assert '<Version VersionId="3.0"/>' in archive.read("bcf.version").decode(
            "utf-8"
        )
        assert "guid-111" in markup
        assert "Wall A" in markup
        assert "actual=15" in markup
        assert not any(n.endswith(".bcfv") for n in names)


def test_empty_input_raises(tmp_path: Path) -> None:
    model = FakeIfcModel({})
    with pytest.raises(ValueError, match=r"LOI-Check\.elements"):
        _run(model, BcfOutputSettings(title_template="{guid}"), [], tmp_path)


def test_unresolved_placeholder_raises(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    with pytest.raises(ValueError, match=r"Pset_Other\.Nope\.actual"):
        _run(
            model,
            BcfOutputSettings(
                title_template="{Pset_Other.Nope.actual}",
            ),
            elements,
            tmp_path,
        )


def test_missing_entity_raises(tmp_path: Path) -> None:
    model = FakeIfcModel({})
    elements = [
        ComparisonElement(
            express_id=999,
            class_name="unknown",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    with pytest.raises(ValueError, match="express ID 999"):
        _run(
            model,
            BcfOutputSettings(title_template="{guid}", description_template="{guid}"),
            elements,
            tmp_path,
        )


def test_missing_global_id_raises(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    with pytest.raises(ValueError, match="no GlobalId"):
        _run(
            model,
            BcfOutputSettings(title_template="{guid}", description_template="{guid}"),
            elements,
            tmp_path,
        )


def test_missing_name_renders_empty(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name=None)})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="[{name}]",
            description_template="n={name}",
        ),
        elements,
        tmp_path,
    )

    assert result.topics[0].title == "[]"
    assert result.topics[0].description == "n="


def test_no_topics_writes_empty_bcf(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=False,
            checks=[_passing_check()],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{guid}",
            description_template="all passed",
        ),
        elements,
        tmp_path,
    )

    assert result.topic_count == 0
    assert result.failed_check_count == 0
    filename = sorted(tmp_path.glob("bcf_output-*.bcf"))[-1]
    with zipfile.ZipFile(filename) as archive:
        assert "bcf.version" in archive.namelist()
        assert "project.bcfp" in archive.namelist()
        assert not [n for n in archive.namelist() if n.endswith("/markup.bcf")]
        assert not [n for n in archive.namelist() if n.endswith(".bcfv")]


def test_generic_placeholders_resolve(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="failed {property_name}",
            description_template=(
                "prop={property_name} actual={actual} expected={expected} "
                "cond={condition}"
            ),
        ),
        elements,
        tmp_path,
    )

    assert result.topics[0].title == "failed ThermalTransmittance"
    assert result.topics[0].description == ("prop=ThermalTransmittance actual=15 expected=10 cond=lt")


def test_condition_symbol_map(tmp_path: Path) -> None:
    model = FakeIfcModel(
        {
            101: FakeEntity(101, "guid-111", name="Wall A"),
            102: FakeEntity(102, "guid-222", name="Wall B"),
        }
    )
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(condition="lt")],
        ),
        ComparisonElement(
            express_id=102,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(condition="ge")],
        ),
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{property_name}{condition_symbol}{expected}",
            description_template="c={condition_symbol}",
        ),
        elements,
        tmp_path,
    )

    assert [topic.title for topic in result.topics] == ["ThermalTransmittance<10", "ThermalTransmittance>=10"]
    assert [topic.description for topic in result.topics] == ["c=<", "c=>="]


def test_word_condition_concatenation_is_spaced(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[
                _failing_check(
                    property_name="LoadBearing", condition="is_true", expected=""
                ),
                _failing_check(condition="one_of"),
            ],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{property_name}{condition_symbol}{expected}",
            description_template="{property_name}{condition_symbol}{expected}",
        ),
        elements,
        tmp_path,
    )

    assert result.topics[0].title == "LoadBearing is true"
    assert result.topics[0].description == "LoadBearing is true"
    assert result.topics[1].title == "ThermalTransmittance ∈ 10"


def _range_check(
    condition: ComparisonCondition,
    *,
    expected_min: str = "0.25",
    expected_max: str = "0.30",
    actual: str = "0.0",
) -> PropertyCheckResult:
    return PropertyCheckResult(
        id="Pset_WallCommon.ThermalTransmittance",
        property_key="Pset_WallCommon.ThermalTransmittance",
        property_name="ThermalTransmittance",
        condition=condition,
        expected="",
        expected_min=expected_min,
        expected_max=expected_max,
        actual=actual,
        passed=False,
    )


@pytest.mark.parametrize(
    ("condition", "expected_value", "expectation"),
    [
        ("equals", "10", "= 10"),
        ("not_equals", "10", "!= 10"),
        ("lt", "10", "< 10"),
        ("le", "10", "<= 10"),
        ("gt", "10", "> 10"),
        ("ge", "10", ">= 10"),
        ("contains", "concrete", 'contains "concrete"'),
        ("one_of", "F30, F60", "is one of: F30, F60"),
        ("is_true", "", "is true"),
        ("is_false", "", "is false"),
        ("between", "", "between 0.25 and 0.30"),
        ("outside", "", "not between 0.25 and 0.30"),
    ],
)
def test_expectation_placeholder_per_condition(
    tmp_path: Path,
    condition: ComparisonCondition,
    expected_value: str,
    expectation: str,
) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    if condition in ("between", "outside"):
        checks = [_range_check(condition)]
    else:
        checks = [_failing_check(condition=condition, expected=expected_value)]
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=checks,
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{expectation}",
            description_template="{expectation}",
        ),
        elements,
        tmp_path,
    )
    assert result.topics[0].title == expectation


def test_failure_reason_with_present_actual(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(condition="lt", expected="10")],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{failure_reason}",
            description_template="{failure_reason}",
        ),
        elements,
        tmp_path,
    )
    assert result.topics[0].title == ("property ThermalTransmittance is 15 (expected < 10)")


def test_failure_reason_with_missing_actual(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(actual=None, expected="10")],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{actual_display}",
            description_template="{failure_reason}",
        ),
        elements,
        tmp_path,
    )
    assert result.topics[0].title == "missing"
    assert result.topics[0].description == ("property ThermalTransmittance is missing (expected < 10)")


def test_report_issue_between_bounds_are_included(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_range_check("between")],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="Element #{id} failed",
            description_template="Element #{id} failed because {failure_reason}",
        ),
        elements,
        tmp_path,
    )
    assert result.topics[0].description == (
        "Element #101 failed because "
        "property ThermalTransmittance is 0.0 (expected between 0.25 and 0.30)"
    )


def test_adaptive_placeholders_under_property_key(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_range_check("outside")],
        )
    ]

    result = _run(
        model,
        BcfOutputSettings(
            title_template="{Pset_WallCommon.ThermalTransmittance.expectation}",
            description_template="{Pset_WallCommon.ThermalTransmittance.failure_reason}",
        ),
        elements,
        tmp_path,
    )
    assert result.topics[0].title == "not between 0.25 and 0.30"
    assert result.topics[0].description == (
        "property ThermalTransmittance is 0.0 (expected not between 0.25 and 0.30)"
    )


def test_markup_topic_fields(tmp_path: Path) -> None:
    model = FakeIfcModel({101: FakeEntity(101, "guid-111", name="Wall A")})
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    _run(
        model,
        BcfOutputSettings(
            title_template="{guid}", description_template="description present"
        ),
        elements,
        tmp_path,
    )

    filename = sorted(tmp_path.glob("bcf_output-*.bcf"))[-1]
    with zipfile.ZipFile(filename) as archive:
        markup_name = next(n for n in archive.namelist() if n.endswith("/markup.bcf"))
        markup = ET.fromstring(archive.read(markup_name))

    assert markup.tag == "Markup"
    topic = markup.find("Topic")
    assert topic is not None
    assert topic.get("Guid")
    assert topic.get("TopicType") == "ERROR"
    assert topic.get("TopicStatus") == "Open"
    assert topic.find("Title") is not None
    assert topic.find("CreationDate") is not None
    assert topic.find("CreationAuthor") is not None
    assert topic.find("Description") is not None
    assert topic.find("Viewpoints") is None


def test_zip_structure_is_bcf_30(tmp_path: Path) -> None:
    model = FakeIfcModel(
        {
            101: FakeEntity(101, "guid-111", name="Wall A"),
            102: FakeEntity(102, "guid-222", name="Wall B"),
        }
    )
    elements = [
        ComparisonElement(
            express_id=101,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        ),
        ComparisonElement(
            express_id=102,
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(property_key="Pset_WallCommon.FireRating")],
        ),
    ]

    _run(
        model,
        BcfOutputSettings(title_template="{guid}", description_template="n={name}"),
        elements,
        tmp_path,
    )

    filename = sorted(tmp_path.glob("bcf_output-*.bcf"))[-1]
    with zipfile.ZipFile(filename) as archive:
        names = archive.namelist()
        assert "bcf.version" in names
        assert "project.bcfp" in names

        topic_folders = {n.split("/", maxsplit=1)[0] for n in names if "/" in n}
        assert len(topic_folders) == 2
        for folder in topic_folders:
            assert uuid.UUID(folder).version == 4
            assert folder == folder.lower()

        for folder in topic_folders:
            markup_name = f"{folder}/markup.bcf"
            assert markup_name in names
        assert not any(n.endswith(".bcfv") for n in names)
