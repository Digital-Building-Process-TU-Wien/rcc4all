---
title: Get Property
description: Read property values from IFC entities for downstream processing.
categories: IFC
---

The `get_property` node reads property values from IFC entities. Each selection specifies an optional entity type, an optional property set, and a required property name. The node outputs property values in one of three modes: per explicit element, per element class, or without element class distinction.

## Use case example

- Read `FireRating` from `Pset_WallCommon` for all walls filtered by an `ifc_element_filter`
- Extract `LoadBearing` status from multiple element classes for analysis
- Gather distinct property values with occurrence counts for model-wide statistics

## Settings

### Output mode

Determines the granularity of the output.

| Value | Label | When to use |
|-------|-------|-------------|
| `elements` | **Per explicit element** | Each element in the input gets its own entry with resolved property values. Use when you need to process each element individually downstream. Requires an input binding. |
| `by_class` | **Per element class** | Elements are grouped by their actual runtime class (e.g., `IFCWALL`, `IFCDOOR`). Each class shows distinct property values with occurrence counts. Use when you want statistics per element type. |
| `model` | **Without element class distinction** | Distinct property values with occurrence counts across all entities and property sets. Property keys use a wildcard `Pset_*.PropertyName` to merge counts from different psets. Use when you want overall model-wide statistics. |

### Selections table

| Column | Description |
|--------|-------------|
| **Entity** (optional) | IFC entity type (e.g., `IFCWALL`, `IFCDOOR`). Placeholder: "Any Element". When set, only entities matching this type contribute to the property output (acts as a filter). Empty means any entity type. |
| **Pset** (optional) | IFC PropertySet name (e.g., `Pset_WallCommon`) or a custom property set name. Placeholder: "Any PSET". When set, restricts lookup to that property set. When empty, searches across all property sets for the property name. |
| **Property** (required) | The name of the property to read from the model. Placeholder: "Required". |

## Inputs

- **Express IDs** (optional): List of IFC express IDs to read property values from. Typically connected to the output of an `ifc_element_filter`. When unconnected, the output will be empty (no elements to read from).

## Outputs

Output structure depends on **Output mode**:

### Per explicit element

List of elements with their express IDs and property values. Each element contains:
- `express_id`: The IFC entity's express ID
- `properties`: Dictionary of property values keyed by `PropertySet.PropertyName`. Values are strings, or `null` for missing model values.

### Per element class

Aggregated by IFC class. Output contains:
- `classes`: Array of class groups, each with:
  - `id`: IFC class name (e.g., `IFCWALL`, `IFCDOOR`, or `unknown` for missing entities)
  - `properties`: Dictionary of distinct values with counts per property, sorted by count (descending) then value (ascending). Missing/null values are excluded.

### Without element class distinction

Distinct values with counts per property, aggregated across all property sets and classes. Output contains:
- `properties`: Dictionary keyed by `Pset_*.PropertyName` (wildcard pset to aggregate across psets), each containing:
  - Array of `{ value, count }` objects sorted by count (descending) then value (ascending)
  - Missing/null values are excluded from the count

## Example Configuration

### Example 1: Read property values from elements

**Selections:**
1. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `FireRating`
2. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `IsExternal`

**Output** for a wall with express_id 101 (model has FireRating="F90", IsExternal=false):

```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.IsExternal": "false"
      }
    }
  ]
}
```

### Example 2: Missing property returns null

If the model doesn't have a property, the value is `null`.

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `AcousticRating` (not present in model)

**Output:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.AcousticRating": null
      }
    }
  ]
}
```

### Example 3: Output mode — Per element class

**Scenario:** Three entities (two IFCWALL with FireRating F90, one IFCDOOR with IsExternal true).

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `FireRating`
2. Entity: `IFCDOOR`, Pset: `Pset_DoorCommon`, Property: `IsExternal`

**Output:**
```json
{
  "mode": "by_class",
  "classes": [
    {
      "id": "IFCDOOR",
      "properties": {
        "Pset_DoorCommon.IsExternal": [{"value": "true", "count": 1}]
      }
    },
    {
      "id": "IFCWALL",
      "properties": {
        "Pset_WallCommon.FireRating": [{"value": "F90", "count": 2}]
      }
    }
  ]
}
```

### Example 4: Output mode — Without element class distinction (with cross-pset aggregation)

**Scenario:** Multiple walls and slabs with `Compartmentation` property. Walls store it in `Pset_WallCommon`, slabs in `Pset_SlabCommon`. You want overall model-wide counts.

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `Compartmentation`
2. Entity: `IFCSLAB`, Pset: `Pset_SlabCommon`, Property: `Compartmentation`

**Output:**
```json
{
  "mode": "model",
  "properties": {
    "Pset_*.Compartmentation": [
      { "value": "true", "count": 20 },
      { "value": "false", "count": 5 }
    ]
  }
}
```

Note how counts from both property sets are merged into `Pset_*.Compartmentation`. This is the key difference from **Per element class** mode.

## CSV Import/Export

Property selections can be imported and exported as CSV files. The CSV format includes the following columns:

```csv
entity_type,property_set,property_name
IFCWALL,Pset_WallCommon,FireRating
IFCWALL,Pset_WallCommon,IsExternal
```

- **entity_type**: Optional. Used primarily for UI preselection and entity filtering.
- **property_set**: Optional. Leave empty to search across all property sets.
- **property_name**: Required.
