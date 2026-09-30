from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from conftest import main_ref as _ref
from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.bcf_output.bcf_output import (
    BcfOutputInputs,
    BcfOutputSettings,
    bcf_output,
)
from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
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


class FakeWriter:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.topic_count = 0
        self.viewpoint_count = 0
        self.added: list[dict[str, Any]] = []
        self.saved_to: Path | None = None

    def add_topic(self, *, title: str, description: str, entities: Any = None) -> None:
        self.topic_count += 1
        for entity in entities or []:
            if entity is not None:
                self.viewpoint_count += 1
        self.added.append(
            {"title": title, "description": description, "entities": entities}
        )

    def save(self, path: Path) -> None:
        self.saved_to = path


_REF_101 = _ref(101)
_REF_102 = _ref(102)


def _failing_check(
    key: str = "Pset_WallCommon.ThermalTransmittance",
    check_parameter: str = "ThermalTransmittance",
    actual_value: str = "15",
    condition: str = "lt",
    expected_value: str = "10",
) -> HarmonizedCheckResult:
    return HarmonizedCheckResult(
        key=key,
        check_parameter=check_parameter,
        expected_value=expected_value,
        actual_value=actual_value,
        unit="",
        missing=False,
        passed=False,
        expected_value_condition=condition,
    )


def _passing_check() -> HarmonizedCheckResult:
    return HarmonizedCheckResult(
        key="Pset_WallCommon.LoadBearing",
        check_parameter="LoadBearing",
        expected_value="true",
        actual_value="true",
        passed=True,
        expected_value_condition="equals",
    )


def _model() -> FakeIfcModel:
    return FakeIfcModel(
        {
            101: FakeEntity(101, "guid-111", name="Wall A"),
            102: FakeEntity(102, "guid-222", name="Wall B"),
        }
    )


def _bcf_module():
    import importlib

    return importlib.import_module("openbim_runner.nodes.bcf_output.bcf_output")


def _run(
    model: FakeIfcModel,
    settings: BcfOutputSettings,
    elements: list[HarmonizedElement],
    tmp_path: Path,
    writer: FakeWriter,
) -> Any:
    mod = _bcf_module()

    original = mod.BcfWriter

    def factory(**kw: Any) -> FakeWriter:
        writer.kwargs = kw
        return writer

    mod.BcfWriter = factory  # type: ignore[assignment]
    context = ExecutionContext(
        ifc_model=cast(Any, model), node_outputs={}, output_dir=tmp_path
    )
    try:
        return asyncio.run(
            bcf_output(settings, BcfOutputInputs(elements=elements), context)
        )
    finally:
        mod.BcfWriter = original  # type: ignore[assignment]


def test_one_topic_per_element_merges_checks(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check(), _failing_check(key="Pset.FireRating")],
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(
            title_template="{name} failed",
            description_template="desc",
        ),
        elements,
        tmp_path,
        writer,
    )

    # Always one topic per element, regardless of how many checks fail.
    assert result.topic_count == 1
    assert result.failure_count == 2
    assert result.topics[0].guids == ["guid-111"]
    assert writer.added[0]["entities"][0].GlobalId == "guid-111"


def test_unknown_placeholder_raises(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    with pytest.raises(ValueError, match=r"Pset_Other\.Nope\.actual"):
        _run(
            _model(),
            BcfOutputSettings(title_template="{Pset_Other.Nope.actual}"),
            elements,
            tmp_path,
            writer,
        )


def test_file_only_placeholder_renders_empty_with_warning(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(
            title_template="{node_label} {name}",
            description_template="d",
        ),
        elements,
        tmp_path,
        writer,
    )
    assert result.topics[0].title == " Wall A"
    assert any("node_label" in warning for warning in result.warnings)


def test_empty_input_raises(tmp_path: Path) -> None:
    writer = FakeWriter()
    with pytest.raises(ValueError, match=r"check elements"):
        _run(_model(), BcfOutputSettings(title_template="{guid}"), [], tmp_path, writer)


def test_skips_unresolvable_element(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_ref(999)],
            class_name="unknown",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(title_template="{guid}", description_template="d"),
        elements,
        tmp_path,
        writer,
    )
    assert result.topic_count == 0
    assert result.skipped == 1
    assert result.warnings


def test_settings_forwarded_to_writer(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    _run(
        _model(),
        BcfOutputSettings(
            project_name="Demo",
            author="Alice",
            topic_type="Issue",
            topic_status="In review",
            title_template="{guid}",
            description_template="d",
        ),
        elements,
        tmp_path,
        writer,
    )
    assert writer.kwargs == {
        "project_name": "Demo",
        "author": "Alice",
        "topic_type": "Issue",
        "topic_status": "In review",
    }


def test_output_filename_used(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(
            output_filename="custom.bcf",
            title_template="{guid}",
            description_template="d",
        ),
        elements,
        tmp_path,
        writer,
    )
    assert writer.saved_to == tmp_path / "custom.bcf"
    assert result.output_path == str(tmp_path / "custom.bcf")


def test_timestamp_placeholder_replaced(tmp_path: Path) -> None:
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    _run(
        _model(),
        BcfOutputSettings(
            output_filename="out-{timestamp}.bcf",
            title_template="{guid}",
            description_template="d",
        ),
        elements,
        tmp_path,
        writer,
    )
    assert writer.saved_to is not None
    assert writer.saved_to.name.startswith("out-")
    assert writer.saved_to.name.endswith(".bcf")
    assert "{timestamp}" not in writer.saved_to.name


def test_resolves_identity_from_refs_own_model(tmp_path: Path) -> None:
    writer = FakeWriter()
    other = FakeIfcModel({77: FakeEntity(77, "guid-777", name="Wall C")})
    elements = [
        HarmonizedElement(
            express_ids=["second_model:expr:77"],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]

    mod = _bcf_module()

    original = mod.BcfWriter

    def factory(**kw: Any) -> FakeWriter:
        writer.kwargs = kw
        return writer

    mod.BcfWriter = factory  # type: ignore[assignment]
    context = ExecutionContext(
        models={
            "main": cast(Any, FakeIfcModel({})),
            "second_model": cast(Any, other),
        },
        node_outputs={},
        output_dir=tmp_path,
    )
    try:
        result = asyncio.run(
            bcf_output(
                BcfOutputSettings(title_template="{guid} n={name}"),
                BcfOutputInputs(elements=elements),
                context,
            )
        )
    finally:
        mod.BcfWriter = original  # type: ignore[assignment]

    assert result.topics[0].guids == ["guid-777"]
    assert result.topics[0].title == "guid-777 n=Wall C"


def _mixed_elements() -> list[HarmonizedElement]:
    return [
        HarmonizedElement(
            express_ids=[_REF_101],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        ),
        HarmonizedElement(
            express_ids=[_REF_102],
            class_name="IFCWALL",
            failed=False,
            checks=[_passing_check()],
        ),
    ]


def test_included_failed_excludes_passed_elements(tmp_path: Path) -> None:
    writer = FakeWriter()
    result = _run(
        _model(),
        BcfOutputSettings(
            included_elements="failed",
            title_template="{name}: {key} :: {passed}",
            description_template="d",
        ),
        _mixed_elements(),
        tmp_path,
        writer,
    )
    assert result.topic_count == 1
    assert result.topics[0].guids == ["guid-111"]
    assert result.element_count == 2
    assert result.failure_count == 1


def test_included_passed_emits_only_info_topics(tmp_path: Path) -> None:
    writer = FakeWriter()
    result = _run(
        _model(),
        BcfOutputSettings(
            included_elements="passed",
            title_template="{name}: {key} :: {passed}",
            description_template="d",
        ),
        _mixed_elements(),
        tmp_path,
        writer,
    )
    assert result.topic_count == 1
    assert result.topics[0].guids == ["guid-222"]
    assert result.failure_count == 0
    # {passed} renders True for the info topic (first check passed).
    assert "True" in result.topics[0].title


def test_included_all_mixes_failure_and_info_topics(tmp_path: Path) -> None:
    writer = FakeWriter()
    result = _run(
        _model(),
        BcfOutputSettings(
            included_elements="all",
            title_template="{name}: {key} :: {passed}",
            description_template="d",
        ),
        _mixed_elements(),
        tmp_path,
        writer,
    )
    assert result.topic_count == 2
    assert result.failure_count == 1
    guids = set().union(*(topic.guids for topic in result.topics))
    assert guids == {"guid-111", "guid-222"}


def test_included_all_viewpoints_for_both_types(tmp_path: Path) -> None:
    writer = FakeWriter()
    result = _run(
        _model(),
        BcfOutputSettings(
            included_elements="all",
            title_template="{name}",
            description_template="d",
        ),
        _mixed_elements(),
        tmp_path,
        writer,
    )
    assert result.viewpoint_count == 2
    assert writer.viewpoint_count == 2


def test_multi_id_element_one_topic_both_viewpoints(tmp_path: Path) -> None:
    """Element with multiple express_ids → one topic with viewpoints for all."""
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101, _REF_102],
            class_name="IFCWALL",
            failed=True,
            checks=[_failing_check()],
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(
            title_template="{name} failed",
            description_template="desc",
        ),
        elements,
        tmp_path,
        writer,
    )

    # One topic for the pair, with both viewpoints
    assert result.topic_count == 1
    assert result.viewpoint_count == 2
    assert writer.viewpoint_count == 2
    assert set(result.topics[0].guids) == {"guid-111", "guid-222"}
    # Both entities should have viewpoints
    assert len(writer.added[0]["entities"]) == 2


def test_intersection_placeholders(tmp_path: Path) -> None:
    """Intersection element renders {intersection}, {name_a}, {name_b} placeholders."""
    writer = FakeWriter()
    elements = [
        HarmonizedElement(
            express_ids=[_REF_101, _REF_102],
            class_name="IFCWALL",
            failed=True,
            checks=[
                HarmonizedCheckResult(
                    key="volume",
                    check_parameter="volume",
                    expected_value="0.0",
                    actual_value="0.32",
                    unit="volume_unit",
                    missing=False,
                    passed=False,
                    expected_value_condition="equals",
                )
            ],
            intersection="inter:intersection_main:expr:101_main:expr:102",
        )
    ]
    result = _run(
        _model(),
        BcfOutputSettings(
            title_template="{name_a} ↔ {name_b}",
            description_template="The {check_parameter} of {name_a} and {name_b} is {actual_value} {unit} — {intersection}",
        ),
        elements,
        tmp_path,
        writer,
    )

    assert result.topic_count == 1
    # Title should have both member names
    assert result.topics[0].title == "Wall A ↔ Wall B"
    # Description should have intersection phrase
    assert "intersection of Wall A and Wall B" in result.topics[0].description
    assert (
        "volume of Wall A and Wall B is 0.32 volume_unit"
        in result.topics[0].description
    )
