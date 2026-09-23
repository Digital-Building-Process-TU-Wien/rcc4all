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
| `model_slug` | `str` | Slug of the IFC model to scan when `express_ids` is not connected. Defaults to the main model; typically bound to a `file_input`'s `model_slug` output. |
| `express_ids` | `list[str]` | Optional list of fully qualified element references (`<slug>:expr:<id>`) to restrict the filter to. Output keeps the input order and duplicate references are removed. When the input is not connected, the model named by the `model_slug` input is scanned; when connected, the references narrow the candidates — each reference's own slug wins over the `model_slug` input, missing ids are skipped silently, and an empty bound list yields an empty result. |

When `express_ids` is connected, only the referenced elements are considered, and each one still has to match the filter rows (entity type, `PredefinedType`, and property comparisons all apply). Each reference resolves against the model named inside it via `context.resolve_model(slug)`, so mixed-model reference lists are allowed. An empty bound list stays empty, so chained filters do not silently re-scan the model.

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[str]` | Fully qualified references (`<slug>:expr:<id>`) of all matching entities. |
| `guids` | `list[str]` | Fully qualified GUID references (`<slug>:guid:<GlobalId>`) of all matching entities in the same order as `express_ids`. |

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

- Scan mode (unbound `express_ids`) with no active filter rows returns **all** `IfcElement` entities of the model.
- Unknown IFC entity types return no matches.
- String comparisons are case-insensitive.
- Numeric comparison operators require numeric values.
- PropertySet suggestions can later be backed by JSON files in `app/web/public/list` without changing the runner contract.
