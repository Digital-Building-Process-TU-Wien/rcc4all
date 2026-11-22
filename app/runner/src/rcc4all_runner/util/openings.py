from __future__ import annotations

from typing import Any


def build_opening_to_wall_map(ifc_model: Any) -> dict[int, Any]:
    """Build O(1) lookup map: opening_id -> wall entity via IfcRelVoidsElement.

    Args:
        ifc_model: IFC model instance

    Returns:
        Dictionary mapping opening express IDs to their associated wall entities
    """
    mapping: dict[int, Any] = {}
    for rel in ifc_model.by_type("IfcRelVoidsElement"):
        opening = rel.RelatedOpeningElement
        wall = rel.RelatingBuildingElement
        if opening and wall:
            mapping[opening.id()] = wall
    return mapping


def build_door_to_opening_map(ifc_model: Any) -> dict[int, Any]:
    """Build O(1) lookup map: door_id -> opening entity via IfcRelFillsElement.

    Args:
        ifc_model: IFC model instance

    Returns:
        Dictionary mapping door express IDs to their associated opening entities
    """
    mapping: dict[int, Any] = {}
    for rel in ifc_model.by_type("IfcRelFillsElement"):
        door = rel.RelatedBuildingElement
        opening = rel.RelatingOpeningElement
        if door and door.is_a("IfcDoor") and opening:
            mapping[door.id()] = opening
    return mapping
