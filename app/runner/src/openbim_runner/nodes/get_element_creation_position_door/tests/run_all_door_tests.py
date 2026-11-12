#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

import ifcopenshell

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_element_creation_position_door.get_element_creation_position_door import (
    GetElementCreationPositionDoorInputs,
    GetElementCreationPositionDoorSettings,
    get_element_creation_position_door,
)
from openbim_runner.util.geometry import build_geometry_cache

ifc_model = ifcopenshell.open(
    Path(__file__).resolve().parents[5]
    / "tests"
    / "testdata"
    / "models"
    / "buildings"
    / "RealWorldTestModel-EscapeRouteAnalysis-ZDB-v5.ifc"
)
# Analog zum Workflow (workflow.execute_workflow_async): den shared
# Body-Geometry-Cache einmalig aufbauen und über context.geometry_cache reichen.
geometry_cache = build_geometry_cache(ifc_model, slug="main")
context = ExecutionContext(
    ifc_model=ifc_model, node_outputs={}, geometry_cache=geometry_cache
)

door = ifc_model.by_type("IfcDoor")[4]
result = asyncio.run(
    get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=7),
        GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{door.id()}"]),
        context,
    )
)
print(f"Position: {result.elements[0].position}")
