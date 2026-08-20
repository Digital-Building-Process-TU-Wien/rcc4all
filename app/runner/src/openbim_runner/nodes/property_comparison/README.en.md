---
title: Property Comparison
description: Check IFC property values against expected target values with table-based rules.
categories: IFC
---

The `property_comparison` node runs table-based property checks against IFC
entities. Each row defines a property to read and a condition to evaluate
against a target value, and is checked against every input element.

## Use-case example

- Check that every wall `Pset_WallCommon.LoadBearing` equals `true`
- Verify wall insulation (`Pset_WallCommon.ThermalTransmittance < 0.4`)
- Flag elements missing a required property (e.g. `FireRating`)

## Settings

### Comparison table

| Column | Description |
|--------|-------------|
| **Component** (optional, "Any Element" default) | IFC entity type (e.g. `IFCWALL`, `IFCDOOR`) that limits which checks apply. If **any** row is "Any Element" (empty Component or the `any` token), **all** input elements are tested and emitted. Otherwise only elements matching at least one specified type appear in the output. |
| **Pset** (optional) | PropertySet to look in (e.g. `Pset_WallCommon`); empty searches all property sets. |
| **Property** (required) | The property name to compare. |
| **Condition** (required) | The comparison operator (see below). |
| **Target value** | The expected value. For `between`/`outside` this holds Min/Max + inclusivity toggles; for `one_of` the accepted values. Disabled for `is_true`/`is_false`. |

String conditions (`equals`, `not_equals`, `contains`, `one_of`) are case- and
whitespace-insensitive. Numeric conditions (`lt`/`le`/`gt`/`ge`) and ranges need
numeric values — non-numeric ones fail the check, as do missing properties.

### Conditions

| Condition | Meaning |
|-----------|---------|
| `equals` / `not_equals` | actual == / != expected (string) |
| `lt` `le` `gt` `ge` | actual < / <= / > / >= expected (numeric) |
| `contains` | expected is a substring of actual |
| `one_of` | actual equals any accepted value |
| `between` / `outside` | actual inside / outside `[Min, Max]` (per-barrier inclusivity) |
| `is_true` / `is_false` | actual is truthy (`true`/`1`/`yes`…) / falsy (`false`/`0`/`no`…) |

### Accepted values (`one_of`)

Switches the target cell to a value-list editor. The check passes when the
property value matches any accepted value. Requires at least one accepted value.

### Numeric ranges (`between` / `outside`)

| Field | Options |
|-------|---------|
| **Min** / **Max** | The numeric barriers (must be set and numeric). |
| **incl. Min** / **incl. Max** | checked → `>=` / `<=`, unchecked → `>` / `<` |

`between` passes when the value is inside `[Min, Max]` (per the toggles);
`outside` passes when it is outside.

## Inputs

- **Express IDs** (optional): the express IDs to check, usually from
  `ifc_element_filter`. Unconnected/empty → all `IfcElement`s in the model are
  checked.

## Outputs

- `element_count`, `total_checks`, `failed_count`
- `elements`: each with `express_id`, `class_name` (or `unknown`), `failed`, and
  `checks` — each check has `id`/`property_key`, `property_name`, `condition`,
  `expected`, optional `expected_min`/`expected_max` (range barriers), `actual`
  (`null` if missing), and `passed`.

## Example

**Check table:**
| Component | Pset | Property | Condition | Target |
|-----------|------|----------|-----------|--------|
| IFCWALL | Pset_WallCommon | LoadBearing | equals | true |
| IFCWALL | Pset_WallCommon | ThermalTransmittance | lt | 0.4 |
| IFCWALL | Pset_WallCommon | FireRating | one_of | F30\|F60 |

**Output** for one wall with `ThermalTransmittance = 0.25` and one with `0.8`:

```json
{
  "element_count": 2,
  "total_checks": 6,
  "failed_count": 2,
  "elements": [
    {
      "express_id": 1235,
      "class_name": "IFCWALL",
      "failed": false,
      "checks": [
        { "id": "Pset_WallCommon.LoadBearing", "property_key": "Pset_WallCommon.LoadBearing", "property_name": "LoadBearing", "condition": "equals", "expected": "true", "actual": "true", "passed": true },
        { "id": "Pset_WallCommon.ThermalTransmittance", "property_key": "Pset_WallCommon.ThermalTransmittance", "property_name": "ThermalTransmittance", "condition": "lt", "expected": "0.4", "actual": "0.25", "passed": true },
        { "id": "Pset_WallCommon.FireRating", "property_key": "Pset_WallCommon.FireRating", "property_name": "FireRating", "condition": "one_of", "expected": "F30, F60", "actual": "F30", "passed": true }
      ]
    },
    {
      "express_id": 1234,
      "class_name": "IFCWALL",
      "failed": true,
      "checks": [
        { "id": "Pset_WallCommon.LoadBearing", "property_key": "Pset_WallCommon.LoadBearing", "property_name": "LoadBearing", "condition": "equals", "expected": "true", "actual": "true", "passed": true },
        { "id": "Pset_WallCommon.ThermalTransmittance", "property_key": "Pset_WallCommon.ThermalTransmittance", "property_name": "ThermalTransmittance", "condition": "lt", "expected": "0.4", "actual": "0.8", "passed": false },
        { "id": "Pset_WallCommon.FireRating", "property_key": "Pset_WallCommon.FireRating", "property_name": "FireRating", "condition": "one_of", "expected": "F30, F60", "actual": "F90", "passed": false }
      ]
    }
  ]
}
```

## CSV Import/Export

Rows can be imported/exported as CSV:

```csv
sep=;
entity_type;property_set;property_name;condition;expected_value;allowed_values;range_min;range_max;inclusive_min;inclusive_max
IFCWALL;Pset_WallCommon;LoadBearing;equals;true
IFCWALL;Pset_WallCommon;ThermalTransmittance;lt;0.4
IFCWALL;Pset_WallCommon;FireRating;one_of;;F30|F60
IFCWALL;Pset_WallCommon;ThermalTransmittance;between;;;0.2;0.6;true;true
```

- **entity_type**: Optional; also used for UI preselection.
- **property_set**: Optional; empty searches all property sets.
- **property_name**: Required.
- **condition**: Required, one of `equals`, `not_equals`, `lt`, `le`, `gt`, `ge`,
  `contains`, `one_of`, `between`, `outside`, `is_true`, `is_false`.
- **expected_value**: Optional single-value target.
- **allowed_values**: Pipe-delimited list for `one_of` (e.g. `F30|F60`).
- **range_min** / **range_max**: Required for `between`/`outside`.
- **inclusive_min** / **inclusive_max**: `true`/`false` per-barrier inclusivity.
