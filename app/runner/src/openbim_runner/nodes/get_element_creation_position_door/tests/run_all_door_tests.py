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

ifc_model = ifcopenshell.open(Path(__file__).parent / "CustomTestModel-EscapeRouteAnalysis-ZDB-v3.ifc")
context = ExecutionContext(ifc_model=ifc_model, node_outputs={})

door = ifc_model.by_type("IfcDoor")[4]
result = asyncio.run(get_element_creation_position_door(
    GetElementCreationPositionDoorSettings(point_index=4),
    GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{door.id()}"]),
    context,
))
print(f"Position: {result.elements[0].position}")
