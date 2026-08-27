"""Shared helpers for reading, keying and comparing IFC property values.

These were historically copy-pasted across the `get_property`,
`property_comparison` (and related) nodes. Keeping them in one place means a
change to property lookup semantics is applied once instead of in every node.
"""

from __future__ import annotations

from typing import Any


def get_property_value(
    entity: Any,
    psets: dict[str, dict[str, Any]],
    property_set: str,
    property_name: str,
) -> Any | None:
    """Read a property value from an entity.

    If ``property_set`` is non-empty the value is looked up only in that set;
    otherwise every property set is searched (case-insensitive on the property
    name). Returns ``None`` when the property is missing.
    """
    if property_set:
        pset = psets.get(property_set)
        if pset:
            return pset.get(property_name)
        return None

    property_name_lower = property_name.lower()
    for pset in psets.values():
        for candidate_name, candidate_value in pset.items():
            if candidate_name.lower() == property_name_lower:
                return candidate_value

    return None


def build_property_key(
    property_set: str,
    property_name: str,
    output_mode: str | None = None,
) -> str:
    """Build a ``Pset.Property`` (or ``Property``) key.

    When ``output_mode == "model"`` the property set is collapsed to the
    ``Pset_*`` wildcard so values from different sets aggregate together.
    """
    if output_mode == "model" and property_set:
        return f"Pset_*.{property_name}"
    if property_set:
        return f"{property_set}.{property_name}"
    return property_name


def stringify_value(value: Any) -> str | None:
    """Convert a property value to a string, or ``None`` if missing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def is_any_entity_type(entity_type: str) -> bool:
    """Return True for the "Any Element" signal: empty or the literal 'any' token."""
    return entity_type.strip().upper() in ("", "ANY")


def entity_matches_type(entity: Any, entity_type: str) -> bool:
    """Check whether an entity matches a given IFC entity type.

    Uses IfcOpenShell's ``is_a()`` for hierarchy-aware matching (includes
    subtypes). Case-insensitive. Empty (or the literal ``any`` token) matches
    all entities.
    """
    if is_any_entity_type(entity_type):
        return True
    entity_type = entity_type.strip().upper()
    is_a = getattr(entity, "is_a", None)
    if is_a is None:
        return False
    try:
        return bool(is_a(entity_type))
    except TypeError:
        return is_a().upper() == entity_type
