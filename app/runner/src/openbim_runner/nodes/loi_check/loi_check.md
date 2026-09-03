# Node Development Prompt (RCC4ALL) — loi_check

This file is the persistent memory for the **LOI-Check** node. Read it
before starting any session on this node.

## Node identity
- **Name (registry key):** `loi_check`
- **Display name:** LOI-Check
- **Category:** IFC
- **Purpose:** Table-based property checks. Pure logic node that
  emits a slim structured result (NO human-readable `message` field); the
  downstream `bcf_output` node generates messages.
- **Relationship:** Part 1 of the LOI-Check + BCF effort. The downstream BCF
  node is `bcf_output` (built; see `../bcf_output/bcf_output.md`). The earlier
  draft name `bcf_export` was renamed to `bcf_output`.

## Decided architecture
- Comparison node = pure logic, emits slim structured result (no messages).
- BCF generation = separate downstream `bcf_output` node (built; see
  `../bcf_output/bcf_output.md`).
- The BCF node resolves the GlobalId from the `express_id` via the model
  (`ExecutionContext.ifc_model.by_id(express_id).GlobalId`); comparisons therefore
  do NOT emit a `ifc_guid` field (kept slim).
- 3D BCF Viewpoints out of scope; components linked by IfcGuid only.

## Node specification
### Settings — table rows (`rows: list[ComparisonRow]`)
`ComparisonRow`:
- `entity_type` (optional filter, like get_property)
- `property_set` (optional)
- `property_name` (required)
- `condition` (required): `equals | not_equals | lt | le | gt | ge | contains |
  one_of | is_true | is_false | between | outside`
- `expected_value` (string, ignored for is_true/is_false/one_of/between/outside)

Each row is checked against every input element → supports multiple entities AND
multiple checks per element simultaneously.

### Inputs
- `express_ids: list[int]` (same as get_property) — OPTIONAL. When empty
  (unconnected), the node gathers all elements from the model context via
  `context.ifc_model.by_type("IfcElement")` (consistent with the element filter's
  default). The Component (`specified_types`) filter then narrows the set.

### Result (slim — NO message field)
- `element_count`, `total_checks`, `failed_count` (failed_count = count of failed
  *checks* across all elements, confirmed via design example)
- `passed_express_ids`, `failed_express_ids`: flat lists of express IDs of the
  elements that were actually checked (had ≥1 applied check). An element whose
  checks all passed is in `passed_express_ids`; an element with ≥1 failed check
  is in `failed_express_ids` (the two lists partition the checked elements).
  Elements with zero applied checks (e.g. missing/invalid express IDs emitted as
  class `unknown`) are excluded from both lists. Order follows `elements`.
- `elements`: ordered list of
  - `express_id`, `class_name`, `failed`
  - `checks`: list of `PropertyCheckResult`
    - `id` (= `property_key`, per user decision — note: can collide if two rows
      share the same property)
    - `property_key` ("Pset.X" or "X"), `property_name`, `condition`, `expected`,
      `actual` (str | None; None = missing), `passed`
    - optional `expected_min` / `expected_max` (set for between/outside range rows)
- Values are strings (get_property convention); coercion to float happens only
  when applying numeric operators.

## Behavior decisions (locked in with user)
1. **Numeric (lt/le/gt/ge):** if `actual` or `expected` cannot be coerced to a
   number → the check is **failed**. If both numeric → compare numerically.
2. **is_true / is_false:** ignore `expected_value`. Truthy set:
   `true/1/yes/y/t`; falsy set: `false/0/no/n/f` (case-insensitive,
   whitespace-trimmed). Anything else → failed.
3. **Non-matching rows:** a row whose Component type does not match the element
   produces no check for that element (see Output filtering below for how the
   Component column changes which elements are emitted). A row that DOES apply but
   whose property is missing on the element still emits a check with
   `actual=None, passed=False` (missing property → failed). Element with zero
   applicable checks → `failed=False`.
4. **Check `id`:** equals `property_key` (user chose over row-based).
5. **equals / not_equals / contains / one_of:** all string conditions compare
   **case-insensitively AND whitespace-insensitively** (user decision — both
   discarded entirely; leading/trailing whitespace trimmed, then lowercased on
   both sides). `contains` is a substring check; missing actual (None) → failed
   for all operators.

## Output filtering by Component (user decision)
The Component (`entity_type`) column now FILTERS the elements emitted in the
output (in addition to limiting which checks apply per row):
- If ANY row uses an "Any Element" signal — empty Component (the default / the
  `Any Element` dropdown choice) OR the literal `any` token (case-insensitive) —
  output filtering is DISABLED and ALL input elements are tested/emitted. That
  row's check applies to every element.
- Otherwise, if every row specifies an explicit Component, only elements matching
  at least one of those types are emitted (union of specified types).
  Non-matching elements are excluded entirely (they no longer appear with 0
  checks).
- Missing/invalid express IDs are excluded when a filter is active (their type is
  unknown); otherwise included as class `unknown` (e.g. when an Any Element row
  disables filtering, or when no row specifies a Component).
Implementation: `_is_any_entity_type()` recognizes empty / `ANY`;
`specified_types = set()` when any row is Any Element (filter disabled), else the
union of explicit types; element skipped when the filter is active and it matches
none. Runner-only change.

## Numeric range checks (per-barrier inclusivity, condition-driven)
User requirements: numeric properties support a two-sided range with top and
bottom barriers; choose between **between / outside** as explicit Condition
options and per-barrier **inclusive / exclusive**. The Min/Max/incl. controls
live in the Target value column, shown when `condition` is between/outside.

ComparisonRow additions:
- `condition` literal gains `between` and `outside` (removed the separate
  `range_relation` field — condition is now the single source).
- `range_min: str = ""`, `range_max: str = ""`
- `inclusive_min: bool = True`, `inclusive_max: bool = True`

Evaluation (numeric only; used when `condition ∈ {between, outside}`):
- inside = (incl_min ? a>=min : a>min) AND (incl_max ? a<=max : a<max)
- passed = inside (between) | not inside (outside)
- non-numeric actual → failed.
Validation (run-time ValueError): when condition is between/outside, both
barriers must be set and numeric; missing/non-numeric barrier → ValueError.
Result: PropertyCheckResult gains optional `expected_min`/`expected_max`;
`condition` is `between`/`outside` for range rows (drives future BCF messages).

Web: the Condition dropdown includes `between`/`outside`. When selected, the
Target value cell shows Min + Max number inputs + incl. Min / incl. Max
checkboxes; otherwise the single value input (datalist for boolean/enum) or
disabled for is_true/is_false. CSV gains
`range_min, range_max, inclusive_min, inclusive_max` columns.

## Accepted values (one_of) — user decision
User requirement: provide a list of accepted values (e.g. wall material in
{concrete, wood, masonry}). New `one_of` condition (label "one of (∈)").

- `ComparisonRow.allowed_values: list[str] = []`.
- `condition` literal gains `one_of`.
- Matching is **case-insensitive** (trimmed, lowercased); missing actual (None)
  → failed. Empty accepted values ignored.
- Validation: `condition == "one_of"` requires ≥ 1 non-empty value else
  ValueError.
- Result: `condition="one_of"`, `expected` = accepted values joined by ", ".
- Web: Target value cell becomes a dynamic value-list editor when one_of
  selected — auto-adds an empty input as soon as the last is filled (trailing
  empty edit slot), per-item ✕ remove, Enter adds; datalist suggestions when the
  property is an enum. `addRow` default `allowed_values: ['']`.
- CSV: `allowed_values` column, pipe-delimited on export (`concrete|wood|...`),
  split on import.

## Edge cases handled
- Missing property (actual=None) → failed.
- Missing/invalid express_id → element with class_name="unknown",
  empty checks, failed=False.
- No rows → raises `ValueError`; row without property_name → raises `ValueError`.
- Bool property values stringified as "true"/"false" (get_property convention).

## Layout & registration
- Runner file: `app/runner/src/openbim_runner/nodes/loi_check/loi_check.py`
- README.en.md / README.de.md (frontmatter title/description/categories).
- tests: `tests/test_loi_check.py`
- Registered in `nodes/__init__.py` (import + `__all__`).
- Web component: `app/web/app/nodes/LoiCheck/LoiCheck.vue`
  (+ `types.ts`, `utils/csv-import-export.ts`, `utils/property-type.ts`).
- Registered in `app/web/app/utils/nodes.ts` (`loi_check: 'LoiCheck'`).
- Schema regenerated via `npm run generate:schema` (Python is source of truth).

## UI decision — type-aware target value widget
- Resolve each row's property `dataType` + `allowedValues` from
  `ifc-4.3-filter-index.json` (`utils/property-type.ts`, matching
  entity_type -> property_set -> property_name, case-insensitive). Ambiguous or
  unknown/custom -> empty type (plain textbox).
- Boolean -> datalist combobox (single editable input + native dropdown of
  `True`/`False`, values lowercase `'true'` / `'false'` to match runner bool
  stringification so `equals` passes); user can still type manually.
- String with non-empty `allowedValues` -> datalist-backed textbox seeded with
  enum values (native dropdown + free-text fallback).
- Default (String w/o enums, empty, custom pset, Integer/Real, unknown) -> plain
  textbox.
- Target input is disabled for `is_true` / `is_false`.
- This is a web-only change: `expected_value` remains a plain string in the
  runner; the runner logic was NOT modified.

## Verification
- Runner (in `app/runner`): `uv run pytest`, `uv run ruff check`, `uv run pyright`.
- Web (in `app/web`): `npm run lint`, `npm run typecheck`.

## Constraints
- Only modify files within/for this node + its two registration points. Never
  touch general/shared/unrelated files. No git operations.
