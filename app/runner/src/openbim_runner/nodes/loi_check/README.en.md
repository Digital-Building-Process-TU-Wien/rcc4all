---
title: LOI-Check
description: Check IFC property values against expected target values with table-based rules.
categories: IFC
---

The `loi_check` node runs table-based property checks against IFC
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

- **Express IDs** (required): a list of fully qualified element references
  (`<slug>:expr:<id>`), usually bound to `ifc_element_filter`'s `express_ids`
  output. Each reference resolves against the model named inside it, so
  mixed-model lists are allowed. An unbound required input fails input
  validation; an empty bound list runs vacuously (zero elements checked).

## Outputs

The executor wraps every node result in an envelope `{ label, type, result }`,
where `label` (runtime-assigned name) and `type` (`"loi_check"`) live on the
outer envelope. The node's `result` object carries only the fields below:

- `summary_element_count`, `summary_passed_count`, `summary_failed_count`
  (element-level), and `summary_check_count` (total number of checks).
- `passed_express_ids`, `failed_express_ids`: flat lists of the qualified
  element references of the checked elements — those whose checks all passed,
  and those with at least one failed check. Elements with no applied checks are
  excluded from both lists.
- `elements`: each with `express_ids` (a list of qualified references), `class_name`
  (or `unknown`), `failed`, and `checks` — each check has `key`, `check_parameter`
  (the property name), `expected_value`, `actual_value` (string, empty when
  missing), `unit` (empty when unknown), `missing` (true when the property is
  absent), `passed`, plus `expected_value_condition` (the comparison operator),
  `expected_value_min` / `expected_value_max` (range barriers for
  `between`/`outside`, empty otherwise).

A reference naming a missing id yields an `unknown` element (with no applied
checks) when no component type is specified in the comparison table.

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
  "summary_element_count": 2,
  "summary_passed_count": 1,
  "summary_failed_count": 1,
  "summary_check_count": 6,
  "passed_express_ids": ["main:expr:1235"],
  "failed_express_ids": ["main:expr:1234"],
  "elements": [
    {
      "express_ids": ["main:expr:1235"],
      "class_name": "IFCWALL",
      "failed": false,
      "checks": [
        { "key": "Pset_WallCommon.LoadBearing", "check_parameter": "LoadBearing", "expected_value": "true", "actual_value": "true", "unit": "", "missing": false, "passed": true, "expected_value_condition": "equals", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.ThermalTransmittance", "check_parameter": "ThermalTransmittance", "expected_value": "0.4", "actual_value": "0.25", "unit": "", "missing": false, "passed": true, "expected_value_condition": "lt", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.FireRating", "check_parameter": "FireRating", "expected_value": "F30, F60", "actual_value": "F30", "unit": "", "missing": false, "passed": true, "expected_value_condition": "one_of", "expected_value_min": "", "expected_value_max": "" }
      ]
    },
    {
      "express_ids": ["main:expr:1234"],
      "class_name": "IFCWALL",
      "failed": true,
      "checks": [
        { "key": "Pset_WallCommon.LoadBearing", "check_parameter": "LoadBearing", "expected_value": "true", "actual_value": "true", "unit": "", "missing": false, "passed": true, "expected_value_condition": "equals", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.ThermalTransmittance", "check_parameter": "ThermalTransmittance", "expected_value": "0.4", "actual_value": "0.8", "unit": "", "missing": false, "passed": false, "expected_value_condition": "lt", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.FireRating", "check_parameter": "FireRating", "expected_value": "F30, F60", "actual_value": "F90", "unit": "", "missing": false, "passed": false, "expected_value_condition": "one_of", "expected_value_min": "", "expected_value_max": "" }
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
