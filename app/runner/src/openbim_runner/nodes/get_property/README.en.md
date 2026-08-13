---
title: Get Property
description: Define property values manually or read them from IFC entities for downstream processing.
categories: IFC
---

The `get_property` node bridges **manually defined values** and **values read from the model**, making it usable either as a pure value provider for downstream nodes or as an extraction step from the IFC model.

- **Define values manually** — No input required. Specify property values by hand to inject data that the model lacks or to provide custom values for downstream nodes.
- **Read values from the model** — Connect an input (Express IDs, typically from an `ifc_element_filter`). The node reads property values from those IFC entities.

Each selection specifies an optional entity type, an optional property set, a required property name, and a **Value Source** that determines how the value is resolved. The node outputs property values in one of three modes: per explicit element, per element class, or without element class distinction.

## Use case example

- Define a custom property (e.g., `CostCategory`) for walls without any model input, then use it in downstream analysis
- Read `FireRating` from `Pset_WallCommon` for all walls filtered by an `ifc_element_filter`
- Use `Fallback` to provide a default `AcousticRating` when the model value is missing
- Classify walls as "large" or "small" using `Override if condition` based on area

## Settings

### Output mode

Determines the granularity of the output. The mode can auto-switch depending on whether an input is bound or an entity is selected.

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
| **Property** (required) | The name of the property to read or define. Placeholder: "Required". |
| **Value Source** | Determines how the value is resolved. See the four options below. |
| **Manual Value** | The value to use when Value Source is `Fallback`, `Manual`, or `Override if condition`. Required for `Fallback` and `Manual`. Used by `Override if condition` when the condition is met. |

### Value Source options

| Value Source | Description | Example |
|--------------|-------------|---------|
| **From model** | Read the value from the IFC entity via `get_psets`. Returns `null` if the property is not found. Use when you always want the raw model value. | Model has `FireRating = "F90"` → output is `"F90"`. Property doesn't exist → output is `null`. |
| **Fallback** | Use the model value if present; use the manual value if the model value is missing (`null`) or empty (`""`). Use when you want to fill gaps in the model data. | Model has `AcousticRating = "Rw45"` → output is `"Rw45"`. Model has no `AcousticRating` or it's `""` → output is the manual fallback value (e.g., `"Rw0"`). |
| **Manual** | Always use the manual value, ignoring the model value completely. This is the source to use when you want to define properties without any input data. Use when you want to enforce a specific value regardless of what's in the model. | Model has `IsExternal = "true"`, but you set manual value `"false"` → output is `"false"`. |
| **Override if condition** | Use the manual value when the model value meets a condition; otherwise use the model value. Requires an **operator** and a **condition value**. Use for classification, compliance checks, or data quality rules. | Model has `Area = 45`. Condition: `>` `30`, manual value: `"large"` → output is `"large"`. Another element has `Area = 20` → condition not met, output is `"20.0"` (the model value). |

**Condition operators:** `>` (greater than), `≥` (greater than or equal), `<` (less than), `≤` (less than or equal), `=` (equals), `≠` (not equals).

## Inputs

- **Express IDs** (optional): List of IFC express IDs to read property values from. Typically connected to the output of an `ifc_element_filter`. Can be left unconnected when using manual values with **Per element class** or **Without element class distinction** output modes. When unconnected, only `Fallback` and `Manual` sources produce output (in **Per element class** and **Without element class distinction** modes). **Per explicit element** mode requires actual input elements and produces empty output when no elements are connected.

## Outputs

Output structure depends on **Output mode**:

### Per explicit element

List of elements with their express IDs and property values. Each element contains:
- `express_id`: The IFC entity's express ID
- `properties`: Dictionary of property values keyed by `PropertySet.PropertyName`. Values are strings, or `null` for missing model values (when source is `From model` and the property is absent).

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

### Example 1: Mixed Value Sources (From model, Fallback, Manual)

**Selections:**
1. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `FireRating`, Value Source: `From model`
2. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `AcousticRating`, Value Source: `Fallback`, Manual value: `Rw45`
3. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `IsExternal`, Value Source: `Manual`, Manual value: `false`

**Output** for a wall with express_id 101 (model has FireRating="F90", no AcousticRating, IsExternal="true"):

```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.AcousticRating": "Rw45",
        "Pset_WallCommon.IsExternal": "false"
      }
    }
  ]
}
```

### Example 2: Fallback on empty string

If the model has `Comments: ""` (empty string), a `Fallback` selection for `Comments` will use the manual value.

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `Comments`, Value Source: `Fallback`, Manual value: `No comments`

**Output:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.Comments": "No comments"
      }
    }
  ]
}
```

### Example 3: Override if condition

**Scenario:** Two walls with areas 45 m² and 20 m². Classify walls larger than 30 m² as "large".

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `Area`, Value Source: `Override if condition`, Operator: `>`, Condition value: `30`, Manual value: `large`

**Output:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.Area": "large"
      }
    },
    {
      "express_id": 205,
      "properties": {
        "Pset_WallCommon.Area": "20.0"
      }
    }
  ]
}
```

The first wall (45 > 30) is overridden to "large"; the second wall (20 ≤ 30) keeps its model value.

### Example 4: Output mode — Per element class

**Scenario:** Three entities (two IFCWALL with FireRating F90, one IFCDOOR with IsExternal true).

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `FireRating`, Value Source: `From model`
2. Entity: `IFCDOOR`, Pset: `Pset_DoorCommon`, Property: `IsExternal`, Value Source: `From model`

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

### Example 5: Output mode — Without element class distinction (with cross-pset aggregation)

**Scenario:** Multiple walls and slabs with `Compartmentation` property. Walls store it in `Pset_WallCommon`, slabs in `Pset_SlabCommon`. You want overall model-wide counts.

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `Compartmentation`, Value Source: `From model`
2. Entity: `IFCSLAB`, Pset: `Pset_SlabCommon`, Property: `Compartmentation`, Value Source: `From model`

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

### Example 6: Manual values without input elements

When no elements are connected to **Express IDs**, selections with `Fallback` or `Manual` source still produce output in **Per element class** and **Without element class distinction** modes. This allows defining property values manually without filtering elements from the model.

**Selection:** Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `LoadBearing`, Value Source: `Manual`, Manual value: `true`

**Output** with **Per element class** mode:
```json
{
  "mode": "by_class",
  "classes": [
    {
      "id": "IFCWALL",
      "properties": {
        "Pset_WallCommon.LoadBearing": [{ "value": "true", "count": 1 }]
      }
    }
  ]
}
```

**Output** with **Without element class distinction** mode:
```json
{
  "mode": "model",
  "properties": {
    "Pset_*.LoadBearing": [{ "value": "true", "count": 1 }]
  }
}
```

Note: **Per explicit element** mode requires actual input elements and produces empty output when no elements are connected.

## CSV Import/Export

Property selections can be imported and exported as CSV files. The CSV format includes the following columns:

```csv
entity_type,property_set,property_name,source,manual_value
IFCWALL,Pset_WallCommon,FireRating,from_model,
IFCWALL,Pset_WallCommon,AcousticRating,fallback,Rw45
IFCWALL,Pset_WallCommon,IsExternal,override,false
```

- **entity_type**: Optional. Used primarily for UI preselection and entity filtering.
- **property_set**: Optional. Leave empty to search across all property sets.
- **property_name**: Required.
- **source**: Defaults to `from_model` if omitted. One of: `from_model`, `fallback`, `override`, `condition`.
- **manual_value**: Required for `fallback`, `override`, and `condition` sources.
