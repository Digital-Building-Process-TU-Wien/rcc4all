---
title: Comparison
description: Compares numeric values against a target value or range and produces harmonized check elements for BCF output.
categories: validation
---

The `comparison` node compares numeric values (actual values) against
a target value and produces harmonized check elements compatible with the `bcf_output`
node. It is purely numeric and IFC-agnostic: each raw reference (`inter:intersection_...`,
a `<k1>_<k2>` distance pair, or `<slug>:expr:<id>`) is carried through unchanged, and
the `bcf_output` node expands it (via the shared `expand_reference` helper) into IFC
member objects so BCF topics can be created with proper viewpoints.

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
| `condition` | `Literal["equals","not_equals","lt","le","gt","ge","between","outside"]` | `"lt"` | Comparison operator applied to the value |
| `target_value` | `float` | `0.0` | Target value for single-value operators (`equals`, `not_equals`, `lt`, `le`, `gt`, `ge`) |
| `target_min` | `float` | `0.0` | Lower barrier for `between` / `outside` operators |
| `target_max` | `float` | `0.0` | Upper barrier for `between` / `outside` operators |
| `inclusive_min` | `bool` | `True` | If `True`, the range includes values equal to `target_min` (≥); otherwise strictly greater (>) |
| `inclusive_max` | `bool` | `True` | If `True`, the range includes values equal to `target_max` (≤); otherwise strictly less (<) |
| `abs_tol` | `float` | `0.001` | Absolute tolerance to absorb float noise near boundaries. Applied to `equals`/`not_equals`, `le`/`ge`, and `between`/`outside` (inclusive sides only); `lt`/`gt` remain strict. Negative values are normalized to their absolute value. |

## Inputs

| Input | Type | Bound from | Description |
|-------|------|------------|-------------|
| `values` | `list[ComparisonValueItem]` | upstream node | List of values to compare. Each item has a `reference` to its source element and a `value`. Bind to a list output of an upstream node. |
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
- `passed_express_ids`, `failed_express_ids`: one raw reference per passing/failing
  element (so each list length equals the element count).
- `elements`: ordered list of
  - `express_ids` (list with the single raw reference, unchanged — e.g.
    `inter:intersection_...`, a `<k1>_<k2>` pair, or `<slug>:expr:<id>`), `class_name`
    (`""`; derived per member by `bcf_output`)
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

For each `ComparisonValueItem` in `values`:

1. **Emit one element per item (no resolution, no dedup):** every `ComparisonValueItem`
   becomes **one element** carrying its raw `reference` unchanged:
   `express_ids=[item.reference]`, `class_name=""`. The comparison node never resolves
   references and never skips — `bcf_output` expands the raw ref into member objects
   and drops any it cannot expand.

2. **Determine pass/fail:**
   - `missing = value is None or error is set or value is non-finite (NaN, +/-inf)` → `check.missing=True`, `failed=True`
   - Otherwise evaluate numeric comparison based on `condition` using `abs_tol`

Each element carries the single `HarmonizedCheckResult` built from the bound
`check_parameter` / `unit` and the target settings.

**Summary counts:** aggregate passed/failed across elements; `passed_express_ids` /
`failed_express_ids` hold one raw reference per element.

## Validations

- `check_parameter` non-empty → `ValueError` (BCF `check.key` required).
- `target_min > target_max` for `between`/`outside` → `ValueError`.

## Notes

- **Configurable tolerance:** `abs_tol` (default `0.001`) is applied to `equals`/`not_equals` (`math.isclose`), `le`/`ge` (boundary expansion), and `between`/`outside` (inclusive sides only); `lt`/`gt` remain strict. Negative values are normalized to their absolute value.
- **Non-finite values:** `NaN`, `+inf`, `-inf` are classified as `missing=True, failed=True` to surface in BCF.
- **Reference/class resolution:** moved to the `bcf_output` node. The comparison node only passes raw references through; `bcf_output` expands them into members and derives each member's IFC class via the shared `expand_reference` helper in `openbim_runner.util.references`.
