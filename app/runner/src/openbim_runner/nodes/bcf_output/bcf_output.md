# Node Development Prompt (RCC4ALL) — bcf_output

This file is the persistent memory for the **BCF Output** node. Read it
before starting any session on this node.

## Node identity
- **Name (registry key):** `bcf_output`
- **Display name:** BCF Output
- **Category:** Output
- **Purpose:** Terminal node that turns failed checks from a harmonized checking
  node (LOI-Check or Tilt of Components) into a BCF 3.0 file. Pure output node —
  it never queries properties or defines checks itself.
- **Relationship:** Downstream consumer of the shared harmonized check output.
  `loi_check` / `tilt_of_components` produce the slim structured result;
  `bcf_output` generates the messages/BCF.

## Decided architecture (locked with user)
- Consume the **harmonized** element shape defined in
  `openbim_runner.nodes.bcf_output.harmonized.HarmonizedElement` /
  `HarmonizedCheckResult`. Both `loi_check` and `tilt_of_components` expose this
  exact shape (their `PropertyCheckResult`/`ComparisonElement` and
  `TiltCheck`/`TiltsElement` are aliases of the harmonized types). The BCF node
  input is `elements: list[HarmonizedElement]`, so it binds to either.
- GUID/name/entity resolved from each qualified reference through
  `context.resolve_model(reference.slug).by_id(reference.express_id)` →
  `GlobalId`, `Name`.
- **BCF writing uses the `bcf-client` package** (`from bcf.v3.bcfxml import
  BcfXml`) — NOT a hand-rolled zip/xml writer. Declared as a direct dependency
  `bcf-client>=0.8.4` in `pyproject.toml`.
- **One BCF topic per element** — all of an element's failing checks are merged
  into a single topic (there is no "per check" grouping option; output is
  always per element).
- **Viewpoint per resolvable affected element** via
  `topic_handler.add_viewpoint(entity)` within a single topic (no snapshot
  handling required).
- Output file: `context.output_dir / output_filename` (default
  `check-results.bcf`); a `{timestamp}` placeholder in the filename is replaced
  per run.
- Level of concern: the harmonized type makes `expected_value_condition` an
  optional `str` (LOI previously had it as a required enum) — data output
  unchanged because LOI always sets it. Tilt surfaces the unused optional
  `expected_value_condition/min/max` fields as empty defaults.

## Node specification
### Settings
- `mode: Literal["auto", "manual"]` (default `"auto"`) — UI-only toggle that
  switches which default templates the editor applies. The backend always
  resolves the same placeholders in both modes; `mode` is never read by the
  runner.
- `title_template: str` — BCF topic `Title`, resolved per topic.
- `description_template: str` — BCF topic `Description`, resolved per topic.
- `project_name: str` — BCF project name (empty → none).
- `author: str` (default `Default Author`) — CreationAuthor on every topic.
- `topic_type: str` (default `Model Check`) — BCF TopicType.
- `topic_status: str` (default `Open`) — BCF TopicStatus.
- `output_filename: str` (default `check-results.bcf`) — relative filename;
  `{timestamp}` placeholder replaced per run.
- `included_elements: Literal["failed", "passed", "all"]` (default `"failed"`) —
  which elements the BCF contains. `failed`: only elements with a failing check
  (their failing checks -> topics). `passed`: only fully-passed elements (one
  info topic each). `all`: every element (failing checks -> topics; fully-passed
  elements -> one info topic each).

### Inputs
- `elements: list[HarmonizedElement]` — REQUIRED, bound from
  `LOI-Check.elements` or `Tilt-of-Components.elements`. Marked with the
  `AutoBind` opt-in marker (see `base.py`): when left unbound at runtime it
  auto-resolves to the single, directly-upstream node whose result exposes a
  compatible `elements` field. Explicit `input_bindings` always win. Resolution
  is by node **type**, never by display `label` (labels aren't transmitted
  anyway).

### Placeholders (Python `string.Formatter`)
Element-level: `{id}`, `{guid}`, `{name}`, `{class_name}`. `{id}` renders the
bare IFC express ID (BCF does not know qualified references).
`{node_label}`, `{check_type}`, `{node_id}` are accepted but always resolve to
`""` and produce a warning (upstream label/type/id are not on result models).

Check-level generic: `{key}`, `{check_parameter}` (alias `{property_name}`),
`{value}`/`{actual}`/`{actual_value}`, `{expected}`/`{expected_value}`,
`{unit}`, `{missing}`, `{passed}`, `{condition}`/`{expected_value_condition}`,
`{expected_min}`/`{expected_value_min}`,
`{expected_max}`/`{expected_value_max}`, `{condition_symbol}` (compact via
`_CONDITION_SYMBOLS`; word/phrase values carry surrounding whitespace),
plus auto-mode `{expectation}`, `{actual_display}`, `{failure_reason}`.

Keyed-by-key variants (e.g. `Pset.actual`, `surface_0.expected`,
`<key>.expectation`) expose the same fields under `<key>.<field>`.

Resolution uses a custom `Namespace` (attribute access) + `ResolvingFormatter`
(string.Formatter subclass) so dotted keys resolve via attribute traversal.
`build_namespace` sets keyed AND generic top-level fields per check.

### Result
- `output_path`, `topic_count`, `viewpoint_count`, `processed_result_count`
  (checks processed), `element_count`, `failure_count` (failed checks),
  `skipped` (failed checks on unresolvable elements), `warnings: list[str]`,
  `topics: list[BcfTopic]` — each `{guids (list), key, element_count, title,
  description}`.

## Files
- `bcf_output.py` — orchestrator (settings/inputs/result models, identity
  resolution, topic emit loop, warn/skip, save).
- `normalize.py` — flattens harmonized elements into topic groups (one topic
  per element); applies the `included` element filter (`failure_topics` for
  failing checks, `info_topics` for fully-passed elements); dedupes check keys
  across elements (`check_keys` union, first-appearance order).
- `render.py` — `Namespace`, `ResolvingFormatter`, `build_namespace`,
  `resolve_template`, `_CONDITION_SYMBOLS`, adaptive values.
- `bcf_writer.py` — thin `BcfWriter` wrapper over `BcfXml` (isolates the
  bcf-client dependency).

## Behavior decisions
1. **Empty `elements`** → raise ValueError naming harmonized check elements as
   the required input (a source checking node must be connected/bound).
2. **Unknown placeholder** → fail, naming the placeholder and the offending
   check (element id + check key).
3. **`{node_label}` / `{check_type}` / `{node_id}`** → render `""`, record one
   warning listing them.
4. **Unresolvable element** (entity not found or no `GlobalId`) → skip the
   topic, record a warning, increment `skipped` (counts unique elements). Keeps
   runs robust.
5. **Missing element `Name`** (`{name}`) → renders as empty string (does NOT
   fail).
6. **No failing checks** (or no selected elements) → still writes a valid
   (empty) BCF; `topic_count` = 0.
7. Require `context.output_dir` (workflow always provides it); else fail.
8. **Included fully-passed elements** (in `all`/`passed` modes) emit one info
   topic each, rendered from the element's first check (only when the element
   has ≥1 check).

## Layout & registration
- Runner dir: `app/runner/src/openbim_runner/nodes/bcf_output/`
  - `bcf_output.py`, `normalize.py`, `render.py`, `bcf_writer.py`,
    `harmonized.py` (shared check schema, owned by this feature), `__init__.py`
    (exports `bcf_output`)
  - `README.en.md` / `README.de.md` (frontmatter title/description/categories)
  - `tests/test_bcf_output.py` (mocks the `BcfWriter`; no real BCF written)
  - `bcf_output.md` (this file)
- Shared harmonized types: `app/runner/src/openbim_runner/nodes/bcf_output/harmonized.py`.
- Registered in `nodes/__init__.py` (import + `__all__`).
- Web component: `app/web/app/nodes/BcfOutput/BcfOutput.vue` — Auto/Manual mode
  toggle + template inputs (datalist), plus project/author/type/status/
  filename/included-elements settings.
- Registered in `app/web/app/utils/nodes.ts` (`bcf_output: 'BcfOutput'`).
- Schema regenerated via `npm run generate:schema` (Python is source of truth).

## Shared files changed
- `app/runner/src/openbim_runner/nodes/bcf_output/harmonized.py` — shared check
  types (moved here: they are owned by this feature and consumed by
  `loi_check` / `tilt_of_components` / `bcf_output`).
- `app/runner/src/openbim_runner/nodes/loi_check/loi_check.py` — result models
  aliased to harmonized types.
- `app/runner/src/openbim_runner/nodes/tilt_of_components/tilt_of_components.py`
  — result models aliased to harmonized types; `TiltCheck` now sets
  `check_parameter="angle"` / `unit="deg"` explicitly.
- `app/runner/pyproject.toml` — added `bcf-client>=0.8.4`.
- `app/web/app/nodes/BcfOutput/BcfOutput.vue`, `app/web/i18n/locales/{en,de}.json`.

## Verification
- Runner (in `app/runner`): `uv run pytest`, `uv run ruff check`,
  `uv run pyright`.
- Web (in `app/web`): `npm run check`, and `npm run generate:schema` after any
  runner schema change.

## Edge cases handled (tests)
- Empty input raises; unknown placeholder raises; `{node_label}` renders empty
  with warning; unresolvable element skipped (count + warning); one topic per
  element merges an element's failing checks; `included_elements` failed/passed/all
  (info topics for fully-passed elements, viewpoints for both); settings
  forwarded to writer; custom filename used; `{timestamp}` replaced; identity
  resolved from reference's own (non-main) model.
