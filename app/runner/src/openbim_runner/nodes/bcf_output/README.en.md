---
title: BCF Output
description: Turn checking-node failures into a BCF 3.0 issue file.
categories: Output
---

`bcf_output` turns failed checks from an upstream checking node (LOI-Check or
Tilt of Components) into a **BCF 3.0** issue file — one topic per element,
merging all of the element's failing checks, each referencing the affected
element so it can be reviewed in a BCF viewer. The BCF is written with the
IfcOpenShell ecosystem `bcf-client` package and includes a viewpoint for each
resolvable affected element.

The node never queries data itself; it reads the harmonized `elements` output
shared by LOI-Check and Tilt of Components, and resolves each element's
GlobalId, Name and IFC entity from the model named inside the element's
qualified reference — only to reference it.

## Use-case example

Run `loi_check` or `tilt_of_components`, connect its `elements` output here,
pick a title and description template (below), then run — a BCF file is saved
into the workflow's output directory (default `check-results.bcf`).

## Settings

| Setting | Description |
|---------|-------------|
| **Mode** | `auto` (default) applies ready-made, condition-aware templates; `manual` resolves your own template exactly as written. |
| **Title template** | The BCF topic title, filled in for each failing check. |
| **Description template** | The BCF topic message, filled in for each failing check. |
| **Project name** | Name written into the BCF project information (default `Default Project`). |
| **Creation author** | Author recorded on every topic's creation data (default `Default Author`). |
| **Topic type** | BCF `TopicType` (default `Model Check`). |
| **Topic status** | BCF `TopicStatus` (default `Open`). |
| **Output filename** | Filename (relative to the output directory; default `check-results.bcf`). A `{timestamp}` placeholder is replaced per run. |
| **Included elements** | Which elements the BCF contains: `failed` (default) only elements with a failing check; `passed` only fully-passed elements (one info topic each); `all` every element (each element becomes one topic). |

## Placeholders

Element-level: `{id}`, `{guid}`, `{name}`, `{class_name}`. `{id}` renders the
element's bare IFC express ID — BCF has no notion of qualified references — and
`{guid}` renders the raw IFC `GlobalId`. BCF output never contains qualified
references.

The placeholders `{node_label}`, `{check_type}` and `{node_id}` are accepted but
always resolve to an empty string (with a warning), because an upstream node's
label / type / id are not transmitted on its result model.

Per-check placeholders (available generically):

`{key}`, `{check_parameter}` (alias `{property_name}`), `{value}`/`{actual}`/
`{actual_value}`, `{expected}`/`{expected_value}`, `{unit}`, `{missing}`,
`{passed}`, `{condition}`/`{expected_value_condition}`, `{expected_min}`/
`{expected_value_min}`, `{expected_max}`/`{expected_value_max}`.

Keyed by the check's key (e.g. `Pset_WallCommon.ThermalTransmittance` or
`surface_0`): the same set under `<key>.<field>`, e.g. `{<key>.expected}`,
`{<key>.actual}`, `{<key>.condition}`.

`{condition_symbol}` — the operator: compact (`=`, `!=`, `<`, `<=`, `>`, `>=`)
or spaced for word conditions (` contains `, ` ∈ `, ` is true`, ` is false`,
` between `, ` outside `), so `{check_parameter}{condition_symbol}{expected}`
reads naturally (e.g. `Material contains concrete`, `LoadBearing is true`).
`between` / `outside` compare against a range — use `{expected_min}` /
`{expected_max}`.

### Auto-mode placeholders (condition-aware)

Available generically and per check key (e.g. `{<key>.expectation}`):

| Placeholder | Renders |
|-------------|---------|
| `{expectation}` | How the expectation should read for this condition (see table). |
| `{actual_display}` | The measured value, or `missing` if the element has no value. |
| `{failure_reason}` | Why the check failed, e.g. `value for ThermalTransmittance is 0.5 (expected < 0.24)`. |

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
Title:        {class_name} {name} failed {check_parameter}
Description:  Element #{id} failed because {failure_reason}
```

Manual:

```
Title:        {class_name} {name} failed {check_parameter}
Description:  Element {guid} ({class_name} {name}) has {check_parameter}={actual}; expected {check_parameter}{condition_symbol}{expected}.
```

## Inputs

- **Elements** (required): the harmonized element list from `loi_check`
  (`LOI-Check.elements`) or `tilt_of_components`
  (`Tilt-of-Components.elements`); the node reports an error if it is missing.
- **Auto-connect**: if you don't pick a source, the node automatically uses the
  single directly-upstream node that provides the expected data. This matches
  by node type (not its display name), so renaming your checking node has no
  effect. If several directly-upstream nodes could supply it, the run stops and
  asks you to choose — and you can always override the automatic choice in the
  Input Bindings panel.

## Outputs

The node reports `output_path` (where the file was saved), `topic_count`,
`viewpoint_count`, `processed_result_count` (checks processed), `element_count`,
`failure_count` (failed checks), `skipped` (failed checks whose element could
not be resolved to a BCF viewpoint — either its IFC entity/GlobalId could not
be resolved, or its raw references expand to no IFC members), `warnings`, and
`topics` — the resolved title and description per topic for review.

## Behavior & edge cases

- **One topic per element** — each element with a failing check becomes a
  single topic merging all of its failing checks; a viewpoint is added per
  resolvable affected element. For elements with multiple `express_ids` (e.g.,
  from the `comparison` node's pair output), one topic is created with
  viewpoints for **all** listed elements.
- **Multi-id elements** — upstream nodes may emit elements with multiple
  `express_ids` (e.g., a collision pair `[main:expr:170, main:expr:766]`).
  The BCF output creates **one topic** referencing all members, with one
  viewpoint per resolvable element. This enables proper documentation of
  pair-based checks (intersection volume, distance between) where the check
  pertains to multiple elements jointly.
- **Included elements** filters which elements are emitted: `failed` (default),
  `passed` (only fully-passed elements → one info topic each), or `all`.
- A **viewpoint** is added per resolvable failing element.
- **Viewpoint element coloring** — each viewpoint highlights **every member of
  the topic** by adding a single `Components.Coloring` entry (opaque red
  `FF0000FF`) listing all resolved IFC GlobalIds. Multi-member topics (collision
  intersections, distance pairs) therefore show all their elements highlighted in
  every viewpoint, while the frame camera still focuses on one. The rest of the
  model stays visible and uncolored.
- **Unknown placeholder** → the run fails, naming the offending check.
- **`{node_label}` / `{check_type}` / `{node_id}`** → accepted, render empty,
  with a warning (upstream metadata is not transmitted).
- **Unresolvable element** (missing entity or GlobalId) → its failed check is
  skipped (counted in `skipped`) and a warning recorded, keeping the run robust.
- **Helper/generated references** (raw `inter:intersection_...` over `gen:`
  keys, malformed refs, or pairs with non-`expr` members) cannot expand to IFC
  members, so they have no BCF viewpoint. Their elements are dropped at
  normalize-time: reported as one warning per dropped reference and folded into
  the `skipped` count. For example, a collision detected on generated geometry
  (`inter:intersection_gen:1_gen:2`) still writes **no** topic (correct — there
  is no IFC entity to reference) but now surfaces `skipped=1` with an
  explanatory warning instead of disappearing silently.
- **No display name** (`{name}`) → renders as an empty string.
- **No failing checks** → still saves a valid, empty issue file.
- **Filename** — `output_filename`, default `check-results.bcf`; use a
  `{timestamp}` placeholder to avoid overwriting previous files.
