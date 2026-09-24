from __future__ import annotations

from typing import Any, Literal

from ifcopenshell.util.element import get_psets
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import expr_key
from openbim_runner.util.references import guid_key, parse_element_refs

FilterMode = Literal["include", "exclude", "disabled"]
FilterOperator = Literal[
    "==", "!=", "<", ">", "<=", ">=", "contains", "starts_with", "ends_with"
]


class FilterRow(NodeModel):
    mode: FilterMode = Field(
        default="include",
        title="Mode",
        description="Row mode: include adds matches, exclude removes matches, disabled ignores the row.",
    )
    entity_type: str = Field(
        default="IFCWALL",
        title="Entity type",
        description="IFC entity type name, for example IFCWALL, IFCDOOR, or IFCSPACE.",
    )
    predefined_type: str = Field(
        default="",
        title="Predefined type",
        description="Optional PredefinedType value. Empty means any predefined type.",
    )
    property_set: str = Field(
        default="",
        title="Property set",
        description="Optional IFC PropertySet name. Empty means direct attribute lookup or search all PropertySets.",
    )
    property_name: str = Field(
        default="",
        title="Property name",
        description="Optional IFC attribute or PropertySet property name to compare.",
    )
    operator: FilterOperator = Field(
        default="==",
        title="Operator",
        description="Comparison operator used for property or attribute values.",
    )
    value: str = Field(
        default="",
        title="Value",
        description="Value to compare against when property_name is set.",
    )


class IfcElementFilterSettings(NodeModel):
    filter_rows: list[FilterRow] = Field(
        default=[],
        title="Filter rows",
        description="List of component filter rows. Include rows are unioned, exclude rows are subtracted.",
    )


class IfcElementFilterInputs(NodeModel):
    express_ids: list[str] | None = Field(
        default=None,
        title="Express IDs",
        description=(
            "Optional list of qualified element references (`<slug>:expr:<id>`) to filter "
            "within. When the input is not connected, the whole model is scanned. When "
            "connected, an empty list yields an empty result. Per-reference model slugs "
            "win over the model input."
        ),
    )
    model_slug: str = Field(
        default="main",
        title="Model",
        description="Model slug to scan when no references are bound. Defaults to the main model.",
    )


class IfcElementFilterResult(NodeModel):
    express_ids: list[str] = Field(
        default=[],
        title="Express IDs",
        description="Qualified references (`<slug>:expr:<id>`) of all matching IFC entities.",
    )
    guids: list[str] = Field(
        default=[],
        title="GUIDs",
        description=(
            "Qualified GUID references (`<slug>:guid:<GlobalId>`) for all matching IFC "
            "entities in the same order as express_ids."
        ),
    )


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _to_number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _compare(actual: Any, operator: str, expected: str) -> bool:
    actual_string = _string_value(actual)
    expected_string = _string_value(expected)

    if operator in {"<", ">", "<=", ">="}:
        actual_number = _to_number(actual)
        expected_number = _to_number(expected)
        if actual_number is None or expected_number is None:
            return False
        if operator == "<":
            return actual_number < expected_number
        if operator == ">":
            return actual_number > expected_number
        if operator == "<=":
            return actual_number <= expected_number
        return actual_number >= expected_number

    actual_lower = actual_string.lower()
    expected_lower = expected_string.lower()

    if operator == "==":
        return actual_lower == expected_lower
    if operator == "!=":
        return actual_lower != expected_lower
    if operator == "contains":
        return expected_lower in actual_lower
    if operator == "starts_with":
        return actual_lower.startswith(expected_lower)
    if operator == "ends_with":
        return actual_lower.endswith(expected_lower)

    raise ValueError(f"Unsupported filter operator '{operator}'.")


def _get_entity_attribute(entity: Any, name: str) -> Any:
    if hasattr(entity, name):
        return getattr(entity, name)

    lower_name = name.lower()
    for attribute_name in (
        "GlobalId",
        "Name",
        "Description",
        "ObjectType",
        "Tag",
        "PredefinedType",
    ):
        if attribute_name.lower() == lower_name and hasattr(entity, attribute_name):
            return getattr(entity, attribute_name)

    return None


def _get_property_value(entity: Any, property_set: str, property_name: str) -> Any:
    attribute_value = _get_entity_attribute(entity, property_name)
    if attribute_value is not None:
        return attribute_value

    psets = get_psets(entity)
    if property_set:
        pset = psets.get(property_set)
        if not pset:
            return None
        return pset.get(property_name)

    property_name_lower = property_name.lower()
    for pset in psets.values():
        for candidate_name, candidate_value in pset.items():
            if candidate_name.lower() == property_name_lower:
                return candidate_value

    return None


def _entity_matches_type(entity: Any, entity_type: str) -> bool:
    entity_type = _clean(entity_type).upper()
    if not entity_type:
        return True
    try:
        return bool(entity.is_a(entity_type))
    except (AttributeError, TypeError, RuntimeError):
        return False


def _matches_row(entity: Any, row: FilterRow) -> bool:
    # TODO: Support USERDEFINED predefined type - match PredefinedType == USERDEFINED and ObjectType == <entered value>
    if not _entity_matches_type(entity, row.entity_type):
        return False

    predefined_type = _clean(row.predefined_type)
    if predefined_type:
        entity_predefined_type = _string_value(
            _get_entity_attribute(entity, "PredefinedType")
        )
        if entity_predefined_type.lower() != predefined_type.lower():
            return False

    property_name = _clean(row.property_name)
    if not property_name:
        return True

    actual_value = _get_property_value(entity, _clean(row.property_set), property_name)
    return _compare(actual_value, row.operator, row.value)


def _candidate_entities(
    context: ExecutionContext,
    model_slug: str,
    inputs: IfcElementFilterInputs,
    rows: list[FilterRow],
) -> list[tuple[Any, str]]:
    """Return ``(entity, slug)`` pairs; the slug records where each entity came from."""
    seen: set[tuple[str, int]] = set()
    candidates: list[tuple[Any, str]] = []

    if inputs.express_ids is not None:
        seen_slugs: set[tuple[str, int]] = set()
        for element in parse_element_refs(
            inputs.express_ids, node="ifc_element_filter"
        ):
            dedupe_key = (element.slug, element.express_id)
            if dedupe_key in seen_slugs:
                continue
            seen_slugs.add(dedupe_key)
            try:
                candidates.append(
                    (
                        context.resolve_model(element.slug).by_id(element.express_id),
                        element.slug,
                    )
                )
            except RuntimeError:
                continue
        return candidates

    # No input: scan the model. Without any row to steer the scan, everything
    # is a candidate (all IfcElement); otherwise gather candidates from every
    # non-disabled row's entity type so entity types that are not IfcElement
    # subclasses (e.g. IFCSPACE) still match.
    model = context.resolve_model(model_slug)
    active_rows = [row for row in rows if row.mode != "disabled"]
    if not active_rows:
        try:
            return [(entity, model_slug) for entity in model.by_type("IfcElement")]
        except RuntimeError:
            return []

    for row in active_rows:
        entity_type = _clean(row.entity_type) or "IfcElement"
        try:
            entities = model.by_type(entity_type)
        except RuntimeError:
            entities = []
        for entity in entities:
            express_id = entity.id()
            dedupe_key = (model_slug, express_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            candidates.append((entity, model_slug))

    return candidates


@node()
async def ifc_element_filter(
    settings: IfcElementFilterSettings,
    inputs: IfcElementFilterInputs,
    context: ExecutionContext,
) -> IfcElementFilterResult:
    matched: list[tuple[Any, str]] = []

    candidates = _candidate_entities(
        context, inputs.model_slug, inputs, settings.filter_rows
    )
    active_rows = [row for row in settings.filter_rows if row.mode != "disabled"]

    for entity, slug in candidates:
        # Without any active row everything is a match (whole-model universe).
        if not active_rows:
            matched.append((entity, slug))
            continue

        matches_include = False
        matches_exclude = False

        for row in settings.filter_rows:
            if row.mode == "disabled":
                continue
            if not _matches_row(entity, row):
                continue
            if row.mode == "exclude":
                matches_exclude = True
                break
            matches_include = True

        if matches_include and not matches_exclude:
            matched.append((entity, slug))

    express_ids = [expr_key(slug, entity.id()) for entity, slug in matched]
    guids = [
        guid_key(slug, _string_value(_get_entity_attribute(entity, "GlobalId")))
        for entity, slug in matched
    ]

    return IfcElementFilterResult(express_ids=express_ids, guids=guids)
