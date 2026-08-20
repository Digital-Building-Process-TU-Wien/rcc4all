from __future__ import annotations

from typing import Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.ifc_properties import (
    build_property_key,
    entity_matches_type,
    get_property_value,
    stringify_value,
)


OutputMode = Literal["elements", "by_class", "model"]


class PropertySelection(NodeModel):
    entity_type: str = Field(
        default="",
        title="Entity type",
        description="Optional IFC entity type (e.g., IFCWALL, IFCDOOR). Empty means any entity type. Used for UI preselection only.",
    )
    property_set: str = Field(
        default="",
        title="Property set",
        description="IFC PropertySet name (e.g., Pset_WallCommon) or custom property set name.",
    )
    property_name: str = Field(
        default="",
        title="Property name",
        description="Name of the property to read within the PropertySet.",
    )


class GetPropertySettings(NodeModel):
    output_mode: OutputMode = Field(
        default="elements",
        title="Output mode",
        description="Output granularity: 'elements' (per entity), 'by_class' (grouped by element class), or 'model' (distinct values across all entities).",
    )
    selections: list[PropertySelection] = Field(
        default=[],
        title="Selections",
        description="List of properties to read from each entity.",
    )


class GetPropertyInputs(NodeModel):
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description="List of IFC express IDs to read property values from.",
    )


class ElementProperties(NodeModel):
    express_id: int = Field(
        title="Express ID",
        description="The express ID of the IFC entity.",
    )
    properties: dict[str, str | None] = Field(
        default={},
        title="Properties",
        description="Dictionary of property values keyed by 'Pset.Property' format.",
    )


class ClassGroup(NodeModel):
    id: str = Field(
        title="Class",
        description="IFC entity class (e.g., IFCWALL) or 'unknown' for missing entities.",
    )
    properties: dict[str, list[ValueWithCount]] = Field(
        default={},
        title="Properties",
        description="Distinct values with counts per property for this class.",
    )


class ValueWithCount(NodeModel):
    value: str = Field(
        title="Value",
        description="A distinct property value.",
    )
    count: int = Field(
        title="Count",
        description="Number of occurrences of this value.",
    )


class GetPropertyResult(NodeModel):
    mode: OutputMode = Field(
        title="Mode",
        description="The output mode used to generate this result.",
    )
    elements: list[ElementProperties] | None = Field(
        default=None,
        title="Elements",
        description="List of elements with their property values (output_mode = elements).",
    )
    classes: list[ClassGroup] | None = Field(
        default=None,
        title="Classes",
        description="Elements grouped by IFC class (output_mode = by_class).",
    )
    properties: dict[str, list[ValueWithCount]] | None = Field(
        default=None,
        title="Properties",
        description="Distinct values with counts per property (output_mode = model).",
    )


@node()
async def get_property(
    settings: GetPropertySettings,
    inputs: GetPropertyInputs,
    context: ExecutionContext,
) -> GetPropertyResult:
    from ifcopenshell.util.element import get_psets

    # Validate that at least one selection is provided
    if not settings.selections:
        raise ValueError("At least one property selection must be specified.")

    # Validate each selection has a property name
    for i, sel in enumerate(settings.selections):
        if not sel.property_name:
            raise ValueError(f"Selection {i + 1} must have a property name.")

    # Resolve per-entity properties (common for all output modes)
    resolved: list[
        tuple[int, str, dict[str, str | None]]
    ] = []  # (express_id, class, properties)

    for express_id in inputs.express_ids:
        try:
            entity = context.ifc_model.by_id(express_id)
            entity_class = entity.is_a()
        except RuntimeError:
            # Entity not found - use "unknown" class with empty properties
            resolved.append((express_id, "unknown", {}))
            continue

        psets = get_psets(entity)
        elem_props: dict[str, str | None] = {}

        for sel in settings.selections:
            # Skip this selection if entity type doesn't match (entity_type acts as a filter)
            if sel.entity_type and not entity_matches_type(entity, sel.entity_type):
                continue

            # Build the property key
            key = build_property_key(
                sel.property_set, sel.property_name, settings.output_mode
            )

            # Read the property value from the model
            value = get_property_value(
                entity, psets, sel.property_set, sel.property_name
            )
            elem_props[key] = stringify_value(value)

        resolved.append((express_id, entity_class, elem_props))

    # Build output based on mode
    if settings.output_mode == "elements":
        elements = [
            ElementProperties(express_id=eid, properties=props)
            for eid, _, props in resolved
        ]
        return GetPropertyResult(mode="elements", elements=elements)

    elif settings.output_mode == "by_class":
        # Aggregate per class, per property, per value with counts
        class_props: dict[str, dict[str, dict[str, int]]] = {}
        for _, cls, props in resolved:
            cp = class_props.setdefault(cls, {})
            for key, value in props.items():
                if value is None:
                    continue
                vc = cp.setdefault(key, {})
                vc[value] = vc.get(value, 0) + 1

        classes: list[ClassGroup] = []
        for cls in sorted(class_props.keys()):
            property_lists: dict[str, list[ValueWithCount]] = {}
            for key, vc in class_props[cls].items():
                sorted_values = sorted(vc.items(), key=lambda x: (-x[1], x[0]))
                property_lists[key] = [
                    ValueWithCount(value=v, count=c) for v, c in sorted_values
                ]
            classes.append(ClassGroup(id=cls, properties=property_lists))
        return GetPropertyResult(mode="by_class", classes=classes)

    else:  # model
        # Aggregate distinct values with counts per property key
        prop_value_counts: dict[str, dict[str, int]] = {}  # key -> {value: count}
        for _, _, props in resolved:
            for key, value in props.items():
                if value is None:  # skip missing values
                    continue
                if key not in prop_value_counts:
                    prop_value_counts[key] = {}
                if value not in prop_value_counts[key]:
                    prop_value_counts[key][value] = 0
                prop_value_counts[key][value] += 1

        # Convert to ValueWithCount lists, sorted by count desc then value asc
        properties: dict[str, list[ValueWithCount]] = {}
        for key, value_counts in prop_value_counts.items():
            sorted_values = sorted(value_counts.items(), key=lambda x: (-x[1], x[0]))
            properties[key] = [
                ValueWithCount(value=v, count=c) for v, c in sorted_values
            ]

        return GetPropertyResult(mode="model", properties=properties)
