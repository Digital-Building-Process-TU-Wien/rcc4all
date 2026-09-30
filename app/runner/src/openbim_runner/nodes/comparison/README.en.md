---
title: Comparison
description: Compares measured numeric values against a target value or range and produces harmonized check elements for BCF output.
categories: validation
---

The `comparison` node compares computed measurement values (actual values) against
a target value and produces harmonized check elements compatible with the `bcf_output`
node. The comparison node resolves helper geometry references (`inter:intersection_...`,
distance pair refs) back to IFC element references so BCF topics can be created with
proper viewpoints.

## Use case example

```
collision → measurement → comparison → bcf_output
```

1. **Collision node** detects intersecting elements and produces `intersection_meshes`
2. **Measurement node** computes the volume of each intersection mesh
3. **Comparison node** compares each volume against a target (e.g., `0.0` for any collision) and emits harmonized elements
4. **BCF output** creates BCF 3.0 topics with viewpoints for each colliding element

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `condition` | `Literal["equals","not_equals","lt","le","gt","ge","between","outside"]` | `"lt"` | Comparison operator applied to the measured value |
| `target_value` | `float` | `0.0` | Target value for single-value operators (`equals`, `not_equals`, `lt`, `le`, `gt`, `ge`) |
| `target_min` | `float` | `0.0` | Lower barrier for `between` / `outside` operators |
| `target_max` | `float` | `0.0` | Upper barrier for `between` / `outside` operators |
| `inclusive_min` | `bool` | `True` | If `True`, the range includes values equal to `target_min` (≥); otherwise strictly greater (>) |
| `inclusive_max` | `bool` | `True` | If `True`, the range includes values equal to `target_max` (≤); otherwise strictly less (<) |
| `abs_tol` | `float` | `0.001` | Absolute tolerance to absorb float noise near boundaries. Applied to `equals`/`not_equals`, `le`/`ge`, and `between`/`outside` (inclusive sides only); `lt`/`gt` remain strict. Negative values are normalized to their absolute value. |

## Inputs

| Input | Type | Bound from | Description |
|-------|------|------------|-------------|
| `values` | `list[MeasurementItem]` | upstream node | List of values to compare. Bind to a list output of an upstream node. |
| `unit` | `str` | upstream node | Unit of the compared values. Bind to a unit output of an upstream node, e.g. `measurement.unit`. |
| `check_parameter` | `str` | upstream node | Label naming the check (becomes the BCF check key). Bind to a type/check_parameter output of an upstream node, e.g. `measurement.type`. |

## Outputs

The result is a slim, structured check per element. The executor wraps every node
result in an envelope `{ label, type, result }`, where `label` (runtime-assigned
name) and `type` (`"comparison"`) live on the outer envelope — the node's `result`
object itself carries only the fields below:

- `summary_element_count` (elements processed), `summary_passed_count` /
  `summary_failed_count` (element-level: elements with passed/failed check), and
  `summary_check_count` (total number of checks, equals element count).
- `passed_express_ids`, `failed_express_ids`: flat lists of qualified references
  partitioning the checked elements.
- `elements`: ordered list of
  - `express_ids` (list, normally a single qualified reference), `class_name`
    (IFC class or `unknown`), `intersection` (original `inter:intersection_...`
    reference for collision intersections; `""` otherwise)
  - `failed`: true when the check failed
  - `checks`: list of `HarmonizedCheckResult` (one per element):
    - `key`: the bound `check_parameter` (e.g., `volume`)
    - `check_parameter`: the bound input
    - `expected_value`: `str(target_value)` (single operators) or `""` (range)
    - `actual_value`: `str(value)` or `""` (missing)
    - `unit`: bound input
    - `missing`: `True` when value is `None`, has an error, or is non-finite (`NaN`, `+/-inf`)
    - `passed`: not missing and comparison passes
    - `expected_value_condition`: `condition`
    - `expected_value_min`: `str(target_min)` (between/outside) or `""`
    - `expected_value_max`: `str(target_max)` (between/outside) or `""`

## Behavior

For each `MeasurementItem` in `values`:

1. **Resolve reference → IFC element(s):**
   - `<slug>:expr:<id>` → single element with `express_ids=[ref]`
   - `inter:intersection_<k1>_<k2>` (collision intersection) → parse both underlying keys; if both are `:expr:` refs, emit **one element** with `express_ids=[refA, refB]` (both members); otherwise skip
   - `<expr1>_<expr2>` (distance pair ref, e.g., `main:expr:17_main:expr:45`) → parse both keys; if both are `:expr:` refs, emit **one element** with `express_ids=[refA, refB]`; otherwise skip
   - `gen:...`, `inter:` (non-intersection), or malformed → skip (no element emitted)

2. **Determine pass/fail:**
   - `missing = value is None or error is set or value is non-finite (NaN, +/-inf)` → `check.missing=True`, `failed=True`
   - Otherwise evaluate numeric comparison based on `condition` using `abs_tol`

3. **Emit `HarmonizedElement`** per `MeasurementItem` (no dedup) with the single check.

4. **Summary counts:** aggregate passed/failed from all elements.

## Validations

- `check_parameter` non-empty → `ValueError` (BCF `check.key` required).
- `target_min > target_max` for `between`/`outside` → `ValueError`.

## Notes

- **Configurable tolerance:** `abs_tol` (default `0.001`) is applied to `equals`/`not_equals` (`math.isclose`), `le`/`ge` (boundary expansion), and `between`/`outside` (inclusive sides only); `lt`/`gt` remain strict. Negative values are normalized to their absolute value.
- **Non-finite values:** `NaN`, `+inf`, `-inf` are classified as `missing=True, failed=True` to surface in BCF.
- **class_name resolution:** resolved from the IFC model by slug; falls back to `"unknown"` if the element is not found.
