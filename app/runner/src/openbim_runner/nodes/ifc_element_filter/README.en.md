---
title: Ifc Element Filter
description: Filter IFC entities using table-based include and exclude rules.
categories: IFC, Filter, Advanced
---

The `ifc_element_filter` node filters IFC model elements with a component filter table. Each row defines one condition with entity type, optional `PredefinedType`, and optional attribute or PropertySet comparison. Include rows are combined with OR logic, then exclude rows are subtracted from the included result.

Use this node when you need to:

- Filter entities by IFC class such as `IFCWALL`, `IFCDOOR`, or `IFCSPACE`
- Include or exclude matching elements per row
- Filter by `GlobalId`, `Name`, `PredefinedType`, direct IFC attributes, or PropertySet values
- Build combined selections from multiple rules

## Settings

| Name | Type | Description |
|------|------|-------------|
| `filter_rows` | `list[FilterRow]` | List of filter rows. Each row defines a complete filter condition. |

## FilterRow structure

| Name | Type | Description |
|------|------|-------------|
| `mode` | `include`, `exclude`, `disabled` | Include adds matching elements, exclude removes matching elements, disabled ignores the row. |
| `entity_type` | `str` | IFC entity type name, for example `IFCWALL` or `IFCSLAB`. |
| `predefined_type` | `str` | Optional `PredefinedType` enum value. Empty means any predefined type. If the value is not selected from the predefined list but entered manually, the program should treat it as a user-defined type: `PredefinedType == USERDEFINED` and `ObjectType == <entered value>`. |
| `property_set` | `str` | Optional IFC PropertySet name, for example `Pset_WallCommon`. If `Attributes` is selected, it refers to the direct IFC attributes available for the selected entity. Empty allows direct attribute lookup or search across all PropertySets. |
| `property_name` | `str` | Optional IFC attribute or PropertySet property name. Empty means no value comparison. |
| `operator` | `str` | Comparison operator. |
| `value` | `str` | Value to compare against. |

## Operators

- `==` equals
- `!=` not equals
- `<` less than
- `>` greater than
- `<=` less than or equals
- `>=` greater than or equals
- `contains` contains substring
- `starts_with` starts with prefix
- `ends_with` ends with suffix

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[int]` | Optional list of IFC express IDs to restrict the filter to. Output keeps the input order and duplicate IDs are removed. When empty or unbound, the whole model is scanned. |

When `express_ids` is bound, only the listed entities are considered, and each one still has to match the filter rows (entity type, `PredefinedType`, and property comparisons all apply).

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[int]` | Express IDs of all matching entities. |
| `guids` | `list[str]` | `GlobalId` values of all matching entities in the same order as `express_ids`. |

## Example

Filter all walls, but exclude external walls:

```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCWALL",
      "predefined_type": "",
      "property_set": "",
      "property_name": "",
      "operator": "==",
      "value": ""
    },
    {
      "mode": "exclude",
      "entity_type": "IFCWALL",
      "predefined_type": "",
      "property_set": "Pset_WallCommon",
      "property_name": "IsExternal",
      "operator": "==",
      "value": "True"
    }
  ]
}
```

## Notes

- Empty `filter_rows` returns an empty result.
- Unknown IFC entity types return no matches.
- String comparisons are case-insensitive.
- Numeric comparison operators require numeric values.
- PropertySet suggestions can later be backed by JSON files in `app/web/public/list` without changing the runner contract.
