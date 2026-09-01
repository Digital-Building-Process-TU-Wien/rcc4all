from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, cast

import ifcopenshell
import pytest
from ifctester import ids as ifc_ids

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.ids_checker.ids_checker import (
    IdsCheckerInputs,
    IdsCheckerResult,
    IdsCheckerSettings,
    ids_checker,
)


class FakeIfcModel:
    pass


def test_ids_checker_with_empty_ids_file() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
        workflow_dir=None,
    )

    with pytest.raises(ValueError, match="No IDS file specified"):
        asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file=""),
                IdsCheckerInputs(),
                context,
            )
        )


def test_ids_checker_with_missing_workflow_dir() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel()),
        node_outputs={},
        workflow_dir=None,
    )

    with pytest.raises(RuntimeError, match="Workflow directory not available"):
        asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(),
                context,
            )
        )


def test_ids_checker_with_nonexistent_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        context = ExecutionContext(
            ifc_model=cast(Any, FakeIfcModel()),
            node_outputs={},
            workflow_dir=Path(tmpdir),
        )

        with pytest.raises(FileNotFoundError, match="IDS file not found"):
            asyncio.run(
                ids_checker(
                    IdsCheckerSettings(ids_file="nonexistent.ids"),
                    IdsCheckerInputs(),
                    context,
                )
            )


def test_ids_checker_with_invalid_ids_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        ids_file = Path(tmpdir) / "test.ids"
        ids_file.write_text("not valid xml", encoding="utf-8")

        context = ExecutionContext(
            ifc_model=cast(Any, FakeIfcModel()),
            node_outputs={},
            workflow_dir=Path(tmpdir),
        )

        with pytest.raises(ValueError, match="Failed to parse IDS file"):
            asyncio.run(
                ids_checker(
                    IdsCheckerSettings(ids_file="test.ids"),
                    IdsCheckerInputs(),
                    context,
                )
            )


def test_ids_checker_with_valid_ids_and_ifc() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity(
            "IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV"
        )
        ifc_file.create_entity(
            "IfcSite", Name="Test Site", GlobalId="1y$yN$DPH95gqWMb$mqAOV"
        )
        ifc_file.write(str(ifc_file_path))

        my_ids = ifc_ids.Ids(title="Test IDS")
        my_spec = ifc_ids.Specification(name="Test Specification")
        my_spec.applicability.append(ifc_ids.Entity(name="IFCSITE"))
        my_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Test Site"))
        my_ids.specifications.append(my_spec)

        ids_file = tmpdir_path / "test.ids"
        my_ids.to_xml(str(ids_file))

        ifc_model = ifcopenshell.open(str(ifc_file_path))
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs={},
            workflow_dir=tmpdir_path,
        )

        result = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(),
                context,
            )
        )

        assert isinstance(result, IdsCheckerResult)
        assert len(result.failed_express_ids) == 0
        assert len(result.passed_express_ids) == 1


def test_ids_checker_with_entity_filtering() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity(
            "IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV"
        )
        wall1 = ifc_file.create_entity(
            "IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV"
        )
        wall2 = ifc_file.create_entity(
            "IfcWall", Name="Wall 2", GlobalId="2y$yN$DPH95gqWMb$mqAOV"
        )
        ifc_file.create_entity("IfcWall", Name="", GlobalId="3y$yN$DPH95gqWMb$mqAOV")
        ifc_file.write(str(ifc_file_path))

        my_ids = ifc_ids.Ids(title="Wall Name Check")
        my_spec = ifc_ids.Specification(name="Walls Must Have Name")
        my_spec.applicability.append(ifc_ids.Entity(name="IFCWALL"))
        my_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Wall 1"))
        my_ids.specifications.append(my_spec)

        ids_file = tmpdir_path / "test.ids"
        my_ids.to_xml(str(ids_file))

        ifc_model = ifcopenshell.open(str(ifc_file_path))
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs={},
            workflow_dir=tmpdir_path,
        )

        result_no_filter = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(express_ids=[]),
                context,
            )
        )

        assert len(result_no_filter.failed_express_ids) == 2
        assert len(result_no_filter.passed_express_ids) == 1
        assert wall1.id() in result_no_filter.passed_express_ids

        result_filtered = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(express_ids=[wall1.id()]),
                context,
            )
        )

        assert len(result_filtered.failed_express_ids) == 0
        assert len(result_filtered.passed_express_ids) == 1
        assert wall1.id() in result_filtered.passed_express_ids

        result_filtered_wall2 = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(express_ids=[wall2.id()]),
                context,
            )
        )

        assert len(result_filtered_wall2.failed_express_ids) == 1
        assert len(result_filtered_wall2.passed_express_ids) == 0
        assert wall2.id() in result_filtered_wall2.failed_express_ids


def test_ids_checker_detailed_report() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity(
            "IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV"
        )
        wall = ifc_file.create_entity(
            "IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV"
        )
        door = ifc_file.create_entity(
            "IfcDoor", Name="Door 1", GlobalId="2y$yN$DPH95gqWMb$mqAOV"
        )
        ifc_file.write(str(ifc_file_path))

        my_ids = ifc_ids.Ids(title="Multi Spec IDS")

        wall_spec = ifc_ids.Specification(name="Wall Check")
        wall_spec.applicability.append(ifc_ids.Entity(name="IFCWALL"))
        wall_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Wall 1"))
        my_ids.specifications.append(wall_spec)

        door_spec = ifc_ids.Specification(name="Door Check")
        door_spec.applicability.append(ifc_ids.Entity(name="IFCDOOR"))
        door_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Door 1"))
        my_ids.specifications.append(door_spec)

        ids_file = tmpdir_path / "test.ids"
        my_ids.to_xml(str(ids_file))

        ifc_model = ifcopenshell.open(str(ifc_file_path))
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs={},
            workflow_dir=tmpdir_path,
        )

        result_without_report = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(),
                context,
            )
        )
        assert len(result_without_report.failed_express_ids) == 0
        assert len(result_without_report.passed_express_ids) == 2
        assert wall.id() in result_without_report.passed_express_ids
        assert door.id() in result_without_report.passed_express_ids
        assert result_without_report.specifications is None

        result_with_report = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", generate_detailed_report=True),
                IdsCheckerInputs(),
                context,
            )
        )
        assert len(result_with_report.failed_express_ids) == 0
        assert len(result_with_report.passed_express_ids) == 2
        assert wall.id() in result_with_report.passed_express_ids
        assert door.id() in result_with_report.passed_express_ids
        assert len(result_with_report.specifications) == 2
        wall_spec_result = next(s for s in result_with_report.specifications if s.name == "Wall Check")
        assert len(wall_spec_result.failed_express_ids) == 0
        assert len(wall_spec_result.passed_express_ids) == 1
        assert wall.id() in wall_spec_result.passed_express_ids
        door_spec_result = next(s for s in result_with_report.specifications if s.name == "Door Check")
        assert len(door_spec_result.failed_express_ids) == 0
        assert len(door_spec_result.passed_express_ids) == 1
        assert door.id() in door_spec_result.passed_express_ids


def test_ids_checker_report_generation() -> None:
    """Test report file generation in JSON and HTML formats."""
    import json
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # IFC file erstellen
        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        wall = ifc_file.create_entity("IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
        door = ifc_file.create_entity("IfcDoor", Name="Door 1", GlobalId="2y$yN$DPH95gqWMb$mqAOV")
        ifc_file.write(str(ifc_file_path))
        
        # IDS file erstellen
        my_ids = ifc_ids.Ids(title="Report Test IDS")
        
        wall_spec = ifc_ids.Specification(name="Wall Check")
        wall_spec.applicability.append(ifc_ids.Entity(name="IFCWALL"))
        wall_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Wall 1"))
        my_ids.specifications.append(wall_spec)
        
        door_spec = ifc_ids.Specification(name="Door Check")
        door_spec.applicability.append(ifc_ids.Entity(name="IFCDOOR"))
        door_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Door 1"))
        my_ids.specifications.append(door_spec)
        
        ids_file = tmpdir_path / "test.ids"
        my_ids.to_xml(str(ids_file))
        
        ifc_model = ifcopenshell.open(str(ifc_file_path))
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs={},
            workflow_dir=tmpdir_path,
            output_dir=tmpdir_path,
        )
        
        # JSON Report generieren
        result_json = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", generate_detailed_report=True, report_format="json"),
                IdsCheckerInputs(),
                context,
            )
        )
        
        # Überprüfen dass Resultat korrekt ist
        assert len(result_json.failed_express_ids) == 0
        assert len(result_json.passed_express_ids) == 2
        assert result_json.specifications is not None
        assert len(result_json.specifications) == 2
        assert result_json.report_path is not None
        
        # Überprüfen dass JSON-Datei erstellt wurde und Inhalt korrekt ist
        json_files = list(tmpdir_path.glob("ids_report-*.json"))
        assert len(json_files) == 1
        assert json_files[0].exists()
        
        json_content = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "specifications" in json_content
        assert len(json_content["specifications"]) == 2
        assert json_content["total_specifications"] == 2
        assert json_content["total_checks"] == 2
        assert json_content["status"] is True
        
        # HTML Report generieren
        result_html = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", generate_detailed_report=True, report_format="html"),
                IdsCheckerInputs(),
                context,
            )
        )
        
        # Überprüfen dass Resultat korrekt ist
        assert len(result_html.failed_express_ids) == 0
        assert len(result_html.passed_express_ids) == 2
        assert result_html.specifications is not None
        assert len(result_html.specifications) == 2
        assert result_html.report_path is not None
        
        # Überprüfen dass HTML-Datei erstellt wurde und Inhalt korrekt ist
        html_files = list(tmpdir_path.glob("ids_report-*.html"))
        assert len(html_files) == 1
        assert html_files[0].exists()
        
        html_content = html_files[0].read_text(encoding="utf-8")
        assert "Report Test IDS" in html_content
        assert "Wall Check" in html_content
        assert "Door Check" in html_content
        assert "IfcWall" in html_content


def test_ids_checker_mixed_pass_fail_single_entity() -> None:
    """Test: One entity passes Spec 1 but fails Spec 2 → should be in failed (not passed).
    
    This tests the logic at ids_checker.py:132:
    passed_express_ids = sorted(all_applicable_ids - all_failed_ids)
    
    An entity that fails ANY applicable spec should be in failed, not passed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        wall = ifc_file.create_entity("IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
        ifc_file.write(str(ifc_file_path))
        
        my_ids = ifc_ids.Ids(title="Mixed Pass Fail Single Entity")
        
        # Spec 1: Wall passes (Name matches)
        name_spec = ifc_ids.Specification(name="Name Check")
        name_spec.applicability.append(ifc_ids.Entity(name="IFCWALL"))
        name_spec.requirements.append(ifc_ids.Attribute(name="Name", value="Wall 1"))
        my_ids.specifications.append(name_spec)
        
        # Spec 2: Wall fails (no Height attribute)
        height_spec = ifc_ids.Specification(name="Height Check")
        height_spec.applicability.append(ifc_ids.Entity(name="IFCWALL"))
        height_spec.requirements.append(ifc_ids.Attribute(name="Height", value="5"))
        my_ids.specifications.append(height_spec)
        
        ids_file = tmpdir_path / "test.ids"
        my_ids.to_xml(str(ids_file))
        
        ifc_model = ifcopenshell.open(str(ifc_file_path))
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs={},
            workflow_dir=tmpdir_path,
        )
        
        result = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids"),
                IdsCheckerInputs(),
                context,
            )
        )
        
        # Wall fails Spec 2, so it should be in failed (not passed)
        assert len(result.failed_express_ids) == 1
        assert len(result.passed_express_ids) == 0
        assert wall.id() in result.failed_express_ids


def test_ids_checker_with_real_ids_file() -> None:
    """Test using a real IDS file and IFC model from testdata."""
    testdata_dir = Path(__file__).parent / "testdata"

    ifc_model = ifcopenshell.open(str(testdata_dir / "ifc2023_de_D0077.ifc"))
    context = ExecutionContext(
        ifc_model=ifc_model,
        node_outputs={},
        workflow_dir=testdata_dir,
    )

    result = asyncio.run(
        ids_checker(
            IdsCheckerSettings(ids_file="test.ids"),
            IdsCheckerInputs(),
            context,
        )
    )

    assert isinstance(result, IdsCheckerResult)
    assert isinstance(result.failed_express_ids, list)
    assert isinstance(result.passed_express_ids, list)
    assert result.specifications is None
