from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, cast

import ifcopenshell
from ifctester import ids as ifc_ids
import pytest

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
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        ifc_file.create_entity("IfcSite", Name="Test Site", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
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
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        wall1 = ifc_file.create_entity("IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
        wall2 = ifc_file.create_entity("IfcWall", Name="Wall 2", GlobalId="2y$yN$DPH95gqWMb$mqAOV")
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


def test_ids_checker_with_multiple_specifications() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        wall = ifc_file.create_entity("IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
        door = ifc_file.create_entity("IfcDoor", Name="Door 1", GlobalId="2y$yN$DPH95gqWMb$mqAOV")
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

        result = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", output_mode="both"),
                IdsCheckerInputs(),
                context,
            )
        )

        assert len(result.failed_express_ids) == 0
        assert len(result.passed_express_ids) == 2
        assert wall.id() in result.passed_express_ids
        assert door.id() in result.passed_express_ids

        assert len(result.specifications) == 2
        wall_spec_result = next(s for s in result.specifications if s.name == "Wall Check")
        door_spec_result = next(s for s in result.specifications if s.name == "Door Check")
        assert len(wall_spec_result.failed_express_ids) == 0
        assert len(wall_spec_result.passed_express_ids) == 1
        assert wall.id() in wall_spec_result.passed_express_ids
        assert len(door_spec_result.failed_express_ids) == 0
        assert len(door_spec_result.passed_express_ids) == 1
        assert door.id() in door_spec_result.passed_express_ids


def test_ids_checker_output_modes() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        ifc_file_path = tmpdir_path / "test.ifc"
        ifc_file = ifcopenshell.file()
        ifc_file.create_entity("IfcProject", Name="Test Project", GlobalId="0y$yN$DPH95gqWMb$mqAOV")
        wall = ifc_file.create_entity("IfcWall", Name="Wall 1", GlobalId="1y$yN$DPH95gqWMb$mqAOV")
        door = ifc_file.create_entity("IfcDoor", Name="Door 1", GlobalId="2y$yN$DPH95gqWMb$mqAOV")
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

        result_combined = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", output_mode="combined"),
                IdsCheckerInputs(),
                context,
            )
        )
        assert len(result_combined.failed_express_ids) == 0
        assert len(result_combined.passed_express_ids) == 2
        assert len(result_combined.specifications) == 0

        result_per_spec = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", output_mode="per_specification"),
                IdsCheckerInputs(),
                context,
            )
        )
        assert len(result_per_spec.failed_express_ids) == 0
        assert len(result_per_spec.passed_express_ids) == 0
        assert len(result_per_spec.specifications) == 2
        wall_spec_result = next(s for s in result_per_spec.specifications if s.name == "Wall Check")
        assert len(wall_spec_result.passed_express_ids) == 1
        assert wall.id() in wall_spec_result.passed_express_ids

        result_both = asyncio.run(
            ids_checker(
                IdsCheckerSettings(ids_file="test.ids", output_mode="both"),
                IdsCheckerInputs(),
                context,
            )
        )
        assert len(result_both.failed_express_ids) == 0
        assert len(result_both.passed_express_ids) == 2
        assert len(result_both.specifications) == 2
