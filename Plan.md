# Plan — `bcf_output` Node (LOI-Check → BCF 3.0)

Date: 2026-08-21
Branch: `feat/BCF-Node`

## Goal
Add a runner node `bcf_output` that turns LOI-Check failures into a
BCF 3.0 file, plus its web editor component. It consumes
`LOI-Check.elements` as its input, reusing the LOI-Check
`ComparisonElement` / `PropertyCheckResult` models (single source of truth).
It never queries properties or defines conditions itself — pure output node.

## Decisions (locked with user)
- **Name:** `bcf_output` (display "BCF Output"). The older draft in
  `loi_check.md` called it `bcf_export`; the final name is `bcf_output`.
- **One BCF topic per failing check.** An element failing 3 rules → 3 topics,
  each referencing the element's GUID and carrying its own sentence
  (from the templates).
- **Templates:** settings `title_template` / `description_template`, resolved
  per check with Python `string.Formatter`. Placeholders:
  - element-level: `{id}`, `{guid}`, `{name}`, `{class_name}`
  - per-property-key values (keyed by the check's `property_key`, e.g.
    `Pset_WallCommon.Area`): `{<key>.actual}`, `{<key>.expected}`,
    `{<key>.condition}`, `{<key>.property_name}`, `{<key>.expected_min}`,
    `{<key>.expected_max}`
  - Unknown/unresolvable placeholder → **fail** the node, naming the
    placeholder and the offending check (element id + property key).
  - Missing element `Name` (`{name}`) renders as an **empty string**.
  - Unresolvable element GUID → **fail** (identity link cannot be missing).
- **GUID/name resolution:** identity-only lookup via
  `context.ifc_model.by_id(express_id)` (`GlobalId`, `Name`).
- **Result model (Rich):** `output_path`, `topic_count`, `element_count`,
  `failed_check_count`, and a `topics: list[BcfTopic]` with `guid`,
  `property_key`, `title`, `description` (visible in the results view).
- **Output file:** written to `context.output_dir` (workflow file's parent) as
  `bcf_output-<timestamp>.bcf` (no overwrite between runs).
- **BCF 3.0 format:** stdlib `zipfile` + `xml.etree.ElementTree` + `uuid`
  (ifcopenshell has **no** BCF writer; new deps avoided). Root `bcf.version`
  (`<Version VersionId="3.0"/>`), `project.bcfp`, and per topic
  `<guid>/markup.bcf`. No viewpoint files (user choice).
- **Empty input:** raise a clear error instructing the user to connect
  `LOI-Check.elements`.
- **Terminal node:** hide the canvas output handle for `bcf_output` (edit to
  shared `WorkflowNode.vue`). Must be documented + reminder before commit/push.

## Runner layout
`app/runner/src/openbim_runner/nodes/bcf_output/`
- `bcf_output.py` — models + `@node()` function + BCF writing helpers
- `__init__.py`
- `README.en.md` / `README.de.md`
- `tests/test_bcf_output.py`
- `bcf_output.md` — node memory file

## Shared runner changes (spec-authorized)
- `base.py`: add `output_dir: Path | None = None` to `ExecutionContext`.
- `workflow.py`: pass `output_dir=workflow_path.parent` when constructing the
  `ExecutionContext`.

## Registration
- `nodes/__init__.py` — import `bcf_output` + `__all__`.
- `app/web/app/utils/nodes.ts` — `bcf_output: 'BcfOutput'`.
- `app/web/app/nodes/BcfOutput/BcfOutput.vue` — settings templates UI.

## Generated schema
- `npm run generate:schema` in `app/web` (regenerates `scripts/schema.json`
  and `scripts/schema.d.ts`).

## Verification
- Runner (in `app/runner`): `uv run pytest`, `uv run ruff check`,
  `uv run pyright`.
- Web (in `app/web`): `npm run lint`, `npm run typecheck`.

## Open items (resolved at implementation time)
- `TopicType=ERROR`, `TopicStatus=Open`, `CreationAuthor=RCC4All` (fixed in code).
- No `<Header><Files>` and no viewpoint files (user chose no viewpoint; header omitted for a minimal valid markup).

## Status
Implemented and verified (2026-08-21): runner 145 tests passed (8 new for
`bcf_output`), `ruff check` clean, `pyright` 0 errors; web `lint` + `typecheck`
clean; `npm run generate:schema` regenerated. Ready for review/commit.
