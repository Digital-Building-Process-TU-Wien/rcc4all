---
title: IFC Entity Filter
description: Filter IFC entities using a table-based component filter with include/exclude logic.
categories: IFC, Filter, Advanced
---

The `ifc_entity_filter` node provides advanced filtering capabilities for IFC models using a Solibri-style component filter table. Each row defines a complete filter condition with entity type, PredefinedType, and optional property filters. Rows are combined with OR logic, and each row can include or exclude matching elements.

Use this node when you need to:
- Filter entities by type with include/exclude control per row
- Apply PredefinedType filters contextually
- Create complex filter combinations with property conditions
- Build sophisticated selection criteria with multiple rules

## Features

### Component Filter Table
Table-based interface with the following columns:
- **Mode**: Include (✓), Exclude (✗), or Disabled (⊘)
- **Entity Type**: IFC entity type (e.g., IFCWALL, IFCSLAB)
- **PredefinedType**: Optional subtype filter (shows "Any" when empty)
- **Property Set**: Optional IFC PropertySet name
- **Property Name**: Property name within the PropertySet
- **Operator**: Comparison operator
- **Value**: Value to compare against

### Row Modes
- **Include (✓)**: Adds matching entities to the result set
- **Exclude (✗)**: Removes matching entities from the result set
- **Disabled (⊘)**: Ignores this row (not evaluated)

### OR Logic
All enabled rows are combined using OR logic (union of include rows, then subtract exclude rows).

### Property Filter Operators
- `==` - Equals
- `!=` - Not equals
- `<` - Less than
- `>` - Greater than
- `<=` - Less than or equals
- `>=` - Greater than or equals
- `contains` - Contains substring (case-insensitive)
- `starts_with` - Starts with prefix (case-insensitive)
- `ends_with` - Ends with suffix (case-insensitive)

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `filter_rows` | `list[FilterRow]` | List of filter rows. Each row defines a complete filter condition. |

### FilterRow Structure

| Name | Type | Description |
|------|------|-------------|
| `mode` | `"include" \| "exclude" \| "disabled"` | Row mode: include adds to result, exclude removes from result, disabled ignores the row |
| `entity_type` | `str` | IFC entity type name (e.g., "IFCWALL", "IFCSLAB") |
| `predefined_type` | `str` | Optional PredefinedType enum value. Empty means "Any" |
| `property_set` | `str` | Optional IFC PropertySet name (e.g., "Pset_WallCommon"). Empty means no property set filter |
| `property_name` | `str` | Property name within the PropertySet |
| `operator` | `str` | Comparison operator (see list above) |
| `value` | `str` | Value to compare against |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[int]` | Express IDs of all matching entities |
| `guids` | `list[str]` | Global Unique Identifiers (GUIDs) of all matching entities |

## Examples

### Example 1: Filter all walls (single include row)
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
    }
  ]
}
```

### Example 2: Filter walls OR slabs (multiple include rows)
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
      "mode": "include",
      "entity_type": "IFCSLAB",
      "predefined_type": "",
      "property_set": "",
      "property_name": "",
      "operator": "==",
      "value": ""
    }
  ]
}
```

### Example 3: Filter walls but exclude external walls
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

### Example 4: Filter load-bearing walls only
```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCWALL",
      "predefined_type": "STANDARD",
      "property_set": "Pset_WallCommon",
      "property_name": "LoadBearing",
      "operator": "==",
      "value": "True"
    }
  ]
}
```

### Example 5: Filter standard walls with fire rating
```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCWALL",
      "predefined_type": "STANDARD",
      "property_set": "Pset_WallCommon",
      "property_name": "FireRating",
      "operator": "contains",
      "value": "F90"
    }
  ]
}
```

### Example 6: Filter floor slabs with thermal transmittance > 0.5
```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCSLAB",
      "predefined_type": "FLOOR",
      "property_set": "Pset_SlabCommon",
      "property_name": "ThermalTransmittance",
      "operator": ">",
      "value": "0.5"
    }
  ]
}
```

### Example 7: Complex filter - walls OR beams with property conditions
```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCWALL",
      "predefined_type": "",
      "property_set": "Pset_WallCommon",
      "property_name": "LoadBearing",
      "operator": "==",
      "value": "True"
    },
    {
      "mode": "include",
      "entity_type": "IFCBEAM",
      "predefined_type": "",
      "property_set": "",
      "property_name": "Name",
      "operator": "starts_with",
      "value": "Main"
    }
  ]
}
```

### Example 8: Empty filter returns no elements
```json
{
  "filter_rows": []
}
```

## Notes

- **Empty filter_rows**: Returns an empty result (no entities selected)
- **Disabled rows**: Are completely ignored during evaluation
- **Entity types**: Case-insensitive but should be provided in standard IFC format (e.g., IFCWALL)
- **PredefinedType**: Empty string means "Any" (all predefined types)
- **Property filters**: Case-insensitive for string comparisons
- **Include/Exclude logic**: All include rows are evaluated first (OR), then exclude rows are subtracted
- **GUIDs**: Returned in the same order as express_ids
- **Unknown entity types**: Return empty results (no error thrown)

## Filter Logic

The filter evaluation follows this algorithm:

```python
# 1. Collect all include IDs (OR logic)
include_ids = union([filter(row) for row in rows if row.mode == "include"])

# 2. Collect all exclude IDs (OR logic)
exclude_ids = union([filter(row) for row in rows if row.mode == "exclude"])

# 3. Subtract excludes from includes
final_ids = include_ids - exclude_ids
```

## Data Sources

This node uses shared IFC data files for entity types, predefined types, property sets, and properties:
- `shared/ifc-data/entities.json` - Common IFC entity types
- `shared/ifc-data/predefined_types.json` - PredefinedType enum values per entity
- `shared/ifc-data/property_sets.json` - Standard IFC PropertySets
- `shared/ifc-data/properties.json` - Common IFC property names

These files provide suggestions in the UI, but manual entry is always supported.

## Migration from Previous Version

If you're migrating from the previous version that used `entity_types`, `entity_logic`, `predefined_type_filter`, and `property_filters` fields, you'll need to convert to the new `filter_rows` structure:

**Old format:**
```json
{
  "entity_types": ["IFCWALL", "IFCSLAB"],
  "entity_logic": "OR",
  "predefined_type_filter": "",
  "property_filters": []
}
```

**New format:**
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
      "mode": "include",
      "entity_type": "IFCSLAB",
      "predefined_type": "",
      "property_set": "",
      "property_name": "",
      "operator": "==",
      "value": ""
    }
  ]
}
```
