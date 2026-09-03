---
title: BCF Output
description: Turn LOI-Check failures into a BCF 3.0 issue file.
categories: Output
---

`bcf_output` turns the failed checks from `loi_check` into a **BCF 3.0** issue
file — one **topic per failing check**, each referencing the failing element so
it can be reviewed in a BCF viewer. The file is **markup-only** (no 3D
viewpoint data keeps it small and fast to open). The node never queries
properties itself; it reads `loi_check`'s structured `elements` output and
resolves each element's GUID/name only to reference it.

## Use-case example

Run `loi_check`, connect its `elements` output here, pick a title and
description template (below), then run — a `bcf_output-<timestamp>.bcf` file is
saved next to the workflow file.

## Settings

Both templates are Python `str.format` strings; the expected value from the
check automatically supplies the limit (nothing needs to be typed by hand).

| Setting | Description |
|---------|-------------|
| **Mode** | `auto` (default) applies ready-made, condition-aware templates; `manual` resolves your own template exactly as written. |
| **Title template** | The BCF topic title, filled in for each failing check. |
| **Description template** | The BCF topic message, filled in for each failing check. |

## Placeholders

Element-level: `{id}`, `{guid}`, `{name}`, `{class_name}`.

Per-property (keyed by the failed check's property key, e.g.
`Pset_WallCommon.ThermalTransmittance` or `ThermalTransmittance`):
`{<key>.actual}`, `{<key>.expected}`, `{<key>.condition}`,
`{<key>.property_name}`, `{<key>.expected_min}`, `{<key>.expected_max}`.

Generic aliases: `{actual}`, `{expected}`, `{condition}`, `{property_name}`,
`{expected_min}`, `{expected_max}`.

`{condition_symbol}` — the operator: compact (`=`, `!=`, `<`, `<=`, `>`, `>=`)
or spaced for word conditions (` contains `, ` ∈ `, ` is true`, ` is false`,
` between `, ` outside `), so `{property_name}{condition_symbol}{expected}`
reads naturally (e.g. `Material contains concrete`, `LoadBearing is true`).
`between` / `outside` compare against a range — use `{expected_min}` /
`{expected_max}`.

### Auto-mode placeholders (condition-aware)

Available generically and per-property key (e.g. `{<key>.expectation}`):

| Placeholder | Renders |
|-------------|---------|
| `{expectation}` | How the expectation should read for this condition (see table). |
| `{actual_display}` | The measured value, or `missing` if the element has no value. |
| `{failure_reason}` | Why the check failed, e.g. `property ThermalTransmittance is 0.5 (expected < 0.24)`. |

`{expectation}` per condition:

| Condition | Renders | Condition | Renders |
|-----------|---------|-----------|---------|
| `equals` | `= {expected}` | `contains` | `contains "{expected}"` |
| `not_equals` | `!= {expected}` | `one_of` | `is one of: {expected}` |
| `lt` / `le` | `<` / `<= {expected}` | `is_true` / `is_false` | `is true` / `is false` |
| `gt` / `ge` | `>` / `>= {expected}` | `between` | `between {expected_min} and {expected_max}` |
| | | `outside` | `not between {expected_min} and {expected_max}` |

### Example templates

Auto (recommended):

```
Title:        {class_name} {name} failed {property_name}
Description:  Element #{id} failed because {failure_reason}
```

Manual:

```
Title:        {class_name} {name} failed {property_name}
Description:  Element {guid} ({class_name} {name}) has {property_name}={actual}; expected {property_name}{condition_symbol}{expected}.
```

## Inputs

- **Elements** (required): the element list from `loi_check`
  (`LOI-Check.elements`); the node reports an error if it is missing.
- **Auto-connect**: if you don't pick a source, the node automatically uses the
  single directly-upstream node that provides the expected data. This matches
  by node type (not its display name), so renaming your LOI-Check node has no
  effect. If several directly-upstream nodes could supply it, the run stops and
  asks you to choose — and you can always override the automatic choice in the
  Input Bindings panel.

## Outputs

The node reports `output_path` (where the file was saved), `topic_count` (one
per failing check), `element_count`, `failed_check_count`, and `topics` — the
resolved title and description per failing check for review.

## Behavior & edge cases

- **One topic per failing check** (3 failed rules → 3 topics).
- **Unknown placeholder or missing GUID** → the run fails, naming the offending
  check (element id + property key).
- **No display name** (`{name}`) → renders as an empty string.
- **No failing checks** → still saves a valid, empty issue file.
- **Markup-only output** — each topic has a title, message and creation
  details; no 3D viewpoint data is included.
- **Timestamped filename** (`bcf_output-<yyyyMMdd-HHmmss>.bcf`) so a run never
  overwrites the previous file.
