# Node Development Prompt (RCC4ALL) — bcf_output

This file is the persistent memory for the **BCF Output** node. Read it
before starting any session on this node.

## Node identity
- **Name (registry key):** `bcf_output`
- **Display name:** BCF Output
- **Category:** Output
- **Purpose:** Terminal node that turns `loi_check` failures into a BCF 3.0
  file. Consumes `LOI-Check.elements` as input. Pure output node — it never
  queries properties or defines conditions itself.
- **Relationship:** Part 2 of the LOI-Check + BCF effort. `loi_check` produces
  the slim structured result; `bcf_output` generates the messages/BCF.
- The older draft in `loi_check.md` called this node `bcf_export`; the final
  name decided with the user is **`bcf_output`**.

## Decided architecture (locked with user)
- Reuse `ComparisonElement` / `PropertyCheckResult` from
  `openbim_runner.nodes.loi_check.loi_check` — single source of truth for what
  was checked. No re-typing of conditions/limits.
- GUID/name resolved by identity lookup only:
  `context.ifc_model.by_id(express_id)` → `GlobalId`, `Name`.
- One BCF topic per **failing check** (an element failing 3 rules → 3 topics).
- **Markup-only output (no viewpoints)**: the `.bcf` contains only
  `bcf.version`, `project.bcfp` and one `markup.bcf` per topic. No `.bcfv`
  view files, no camera, and no `<Header>` are written (viewpoint/camera/header
  generation was removed as out of scope).
- BCF 3.0 written with stdlib `zipfile` + `xml.etree.ElementTree` + `uuid`
  (ifcopenshell has NO BCF writer; no new dependencies).
- Output file: `context.output_dir / bcf_output-<yyyyMMdd-HHmmss>.bcf`
  (workflow file's parent; timestamped so runs never overwrite).
- Terminal node: canvas output handle hidden for `bcf_output` (edit to shared
  `app/web/app/components/nodes/WorkflowNode.vue`).

## Node specification
### Settings
- `mode: Literal["auto", "manual"]` (default `"auto"`) — a UI-only toggle that
  switches which default templates the editor applies (`auto` applies the
  condition-aware standard templates; `manual` lets the user type their own
  from raw placeholders). The backend always resolves the same placeholders in
  both modes; `mode` is never read by the runner.
- `title_template: str` — BCF topic `Title`, resolved per check.
- `description_template: str` — BCF topic `Description` (sentence), resolved
  per check.

### Inputs
- `elements: list[ComparisonElement]` — REQUIRED, bound from
  `LOI-Check.elements`. Marked with the `AutoBind` opt-in marker (see
  `base.py` / `workflow.resolve_auto_bindings`): when left unbound at runtime
  it auto-resolves to the single, directly-upstream node whose result exposes a
  compatible `elements` field (i.e. the connected `loi_check`). Explicit
  `input_bindings` always win. Resolution is by node **type**, never by display
  `label`, so renaming the LOI-Check node does not affect it.

### Placeholders (Python `string.Formatter`)
Element-level: `{id}`, `{guid}`, `{name}`, `{class_name}`.
Per-property (keyed by the failed check's `property_key`, e.g.
`Pset_WallCommon.ThermalTransmittance` or `ThermalTransmittance`):
`{<key>.actual}`, `{<key>.expected}`, `{<key>.condition}`,
`{<key>.property_name}`, `{<key>.expected_min}`, `{<key>.expected_max}`.
Generic check-level aliases (drive the UI suggestion dropdowns):
`{actual}`, `{expected}`, `{condition}`, `{property_name}`, `{expected_min}`,
`{expected_max}`, plus `{condition_symbol}` (compact operator via
`_CONDITION_SYMBOLS`: `=` `!=` `<` `<=` `>` `>=` compact; word/phrase values
carry surrounding whitespace — ` contains ` ` ∈ ` ` is true` ` is false`
` between ` ` outside ` — so concatenation reads cleanly; unknown falls back
to the token).

Resolution uses a custom `_Namespace` (attribute access) + `_ResolvingFormatter`
(string.Formatter subclass) so dotted keys resolve via attribute traversal.
`_build_namespace` sets keyed fields AND generic top-level fields per check.

### Result
- `output_path`, `topic_count`, `element_count`, `failed_check_count`
- `topics: list[BcfTopic]` — each `{guid (element GlobalId), property_key,
  title, description}`.

## Behavior decisions (locked with user)
1. **Empty `elements`** → raise ValueError telling user to connect
   `LOI-Check.elements`. Exception: when an upstream `loi_check` is directly
   connected by an edge and `elements` is unbound, the `AutoBind` mechanism
   supplies it automatically (see Inputs).
2. **Runtime auto-binding** (`AutoBind` on `elements`) — general opt-in engine
   feature in `base.py` + `workflow.py`. Rules: only the **directly-upstream**
   neighbor(s) of the node (via workflow edges) are considered; a single
   compatible source auto-binds, zero leaves the input unbound (falls through
   to rule 1), and multiple is an error telling the user to bind explicitly.
   Explicit `input_bindings` always override. Only inputs tagged `AutoBind`
   participate — unmarked inputs (e.g. `loi_check.express_ids`) keep their
   "unbound = whole model" semantics.
2. **Unknown/unresolvable placeholder** → fail, naming the placeholder and the
   offending check (element id + property key).
3. **Missing/unresolvable element GUID** (entity not found or no `GlobalId`) →
   fail, naming the check.
4. **Missing element `Name`** (`{name}`) → renders as empty string (does NOT
   fail).
5. **No failing checks** → still writes an empty (valid) BCF with 0 topics;
   `topic_count` = 0.
6. Require `context.output_dir` (workflow always provides it); else fail.

## BCF 3.0 layout (written)
```
bcf.version              -> <Version VersionId="3.0"/>
project.bcfp             -> <ProjectInfo><Project ProjectId="<uuid>"/></ProjectInfo>
<topic-uuid>/markup.bcf  -> <Markup><Topic Guid="<topic-uuid>" TopicType="ERROR" TopicStatus="Open">
                              <Title/><CreationDate/><CreationAuthor="RCC4All"/><Description?>
```
Fixed values: `_TOPIC_TYPE="ERROR"`, `_TOPIC_STATUS="Open"`,
`_CREATION_AUTHOR="RCC4All"`.
No `<Header>`, `<Viewpoints>` or `.bcfv` files are produced (markup-only).

## Layout & registration
- Runner dir: `app/runner/src/openbim_runner/nodes/bcf_output/`
  - `bcf_output.py`, `__init__.py`
  - `README.en.md` / `README.de.md` (frontmatter title/description/categories)
  - `tests/test_bcf_output.py`
  - `bcf_output.md` (this file)
- Registered in `nodes/__init__.py` (import + `__all__`).
- Web component: `app/web/app/nodes/BcfOutput/BcfOutput.vue`
  - Settings `title_template` / `description_template` are single-line
    `<input>` + `<datalist>` combos (like LOI-Check) with standard suggestion
    templates (3 titles, 3 descriptions in `BcfOutput.vue`). Free typing still
    allowed. Datalist needs single-line inputs (not textareas).
- Registered in `app/web/app/utils/nodes.ts` (`bcf_output: 'BcfOutput'`).
- Schema regenerated via `npm run generate:schema` (Python is source of truth).

## Shared files changed (spec-authorized / flagged)
- `app/runner/src/openbim_runner/nodes/base.py` — `ExecutionContext` gained
  `output_dir: Path | None = None`.
- `app/runner/src/openbim_runner/workflow.py` — passes
  `output_dir=workflow_path.parent`.
- `app/web/app/components/nodes/WorkflowNode.vue` — hide output handle for
  terminal `bcf_output` (and `JsonOutput`). **Remind user before commit/push.**

## Verification
- Runner (in `app/runner`): `uv run pytest`, `uv run ruff check`,
  `uv run pyright`.
- Web (in `app/web`): `npm run lint`, `npm run typecheck`.

## Edge cases handled (tests)
- Empty input raises; unknown placeholder raises; missing entity raises;
  missing GlobalId raises; missing name renders empty; no failing checks →
  empty BCF; one topic per failing check; valid zip layout assertion (version +
  project + one `markup.bcf` per topic, no `.bcfv` files); markup topic fields
  (type/status/title/date/author, no `<Viewpoints>`).

## Constraints
- Only modify files within/for this node + the two registration points + the
  explicitly authorized shared files above. Never touch unrelated/general files
  without permission. No git operations.
