# Node Development Prompt (RCC4ALL) — opening_surface

This file is the persistent memory for the **opening_surface** node. Read it
before starting any session on this node. Compressed copy of the governing
workflow prompt, followed by the node specification and decisions.

## Compressed workflow prompt

- Contribute a node in BOTH places, kept in sync: Python function in the runner
  (source of truth for logic and types) and Vue/Nuxt component in the web app.
- Workflow: read session files first (Rules.md, this file, Plan.md,
  SessionHandoff.md) → clarify spec iteratively (record here) → present plan,
  get approval → implement both sides → `uv sync` (clean env), check unused/
  duplicate deps → run verification → update Plan.md / this file /
  SessionHandoff.md → summarize; no git operations.
- Node layout runner: `nodes/opening_surface/opening_surface.py`, README.en.md
  (frontmatter title/description/categories) + README.de.md,
  `tests/test_opening_surface.py`, registered in `nodes/__init__.py`.
- Node layout web: `app/web/app/nodes/OpeningSurface/OpeningSurface.vue`,
  registered in `app/web/app/utils/nodes.ts`; `npm run generate:schema` in
  app/web after runner registration.
- Verification: runner `uv run pytest`, `uv run ruff check`, `uv run pyright`;
  web `npm run lint`, `npm run typecheck`.
- Constraints: only modify files specific to this node; STOP and ask before
  anything out of scope; follow existing conventions (Rules.md); clean readable
  code; bilingual docs realistic and compact; ask before implementing new
  python packages; NO git operations (user does all git work).
- This file is covered by the scope rule: ONLY modify files within the node's
  directory.

## Node identity
- **Name (registry key):** `opening_surface`
- **Web component:** `OpeningSurface` (PascalCase of snake name)
- **Category:** `geometry`
- **Purpose:** Retrieve the surfaces of openings (voids) of building elements
  (walls, roofs, slabs) that are NOT the cut surfaces — the opening surface(s)
  in the plane of the host's surface — as geometry for downstream
  measurement/checking.

## Decided specification (locked with user)

1. **Input:** `express_ids: list[str]` — required qualified element references
   (`<slug>:expr:<id>`) of host building elements; bind ifc_element_filter
   output here. **No settings model** (inputs + context signature).
2. **Output:** flat list of openings (one entry per opening), each carrying
   opening qualified ref + GUID, host element reference, geometry key, area,
   dimensions (W/H/D). Result also exposes counts + `geometry_keys` list for
   direct binding to measurement/collision.
3. **Retrieved surfaces:** the two cap faces (front + back) lying in the plane
   of the host surface. Both caps are emitted as one generated mesh per
   opening. **Self-contained** (option 2): no spaces input, no host-mesh
   coincidence test.
4. **Face classification:** opening mesh triangles are grouped into planar
   surfaces (normals within ~1°, coplanar within 0.01 model units — mirrors
   the reference `groupTriangles`); the two largest groups with opposing
   normals (≥170°) are the caps; the reveal band is dropped.
5. **Geometry source:** the `IfcOpeningElement`'s Body mesh from the geometry
   cache. Openings without a cached mesh get an error entry ("no cached
   geometry"); no on-demand tessellation.
6. **Geometry key prefix: `gen:`** (NOT `inter:`) — user decision. Keys:
   `gen:opening_surface_<slug>_<opening_expr>`.
7. **No host-type filter** setting; process input elements as-is (elements
   without openings simply contribute no entries).
8. Openings are found per host via the inverse `HasOpenings`
   (`IfcRelVoidsElement` → `RelatedOpeningElement`); handle
   `IfcOpeningStandardCase` via supertype.
9. **`area` = single (larger) cap face** — user decision; the opening area in
   the plane of the host surface. Width/height = extents within the cap plane
   (in-plane vertical-ish axis for height, world Y fallback for horizontal
   caps); depth = distance between the two cap planes (`None` for single cap).

## Reference code

- `LightExposureRule.java` (copied into this node directory): the facade rule
  its `groupTriangles` + surface selection inspired the classification (1°
  normal tolerance, 0.01 coplanarity, max-distance-to-spaces facade pick —
  NOT adopted; option 2 is self-contained). The Java's inner loop could add a
  triangle to two groups; our `_planar_groups` assigns every face exactly once.
- Repo `Digital-Building-Process-TU-Wien/LightEntryModel-IFC-generator` is a
  downstream consumer (Python → IFC4X3 light-entry model); deliberately not
  pulled in (user decision).

## Test models (in `app/runner/tests/testdata/models/`)

- `specific/Testmodell-LightExposureSmall.ifc` — IFC4; 14 IfcWall, 9 IfcSlab,
  2 IfcRoof, 17 IfcOpeningElement, 16 IfcWindow, 17 IfcRelVoidsElement, 16
  IfcRelFillsElement. All 17 openings cached and retrieved. Wall window caps
  match window OverallWidth×OverallHeight exactly (validated by test).
- `large_models/RealWorldTestModel-EscapeRouteAnalysis-ZDB-v2.ifc` — IFC4; 298
  walls, 19 slabs, 18 roofs, 117 openings. All 117 retrieved without errors
  (~53 s, cache build dominant). Not in the test suite (too slow); validated
  via scratch script.

## Implemented behavior / edge cases

- Host without openings → no entries. Host reference resolving to no entity →
  skipped silently (no opening to report).
- Opening without cached Body mesh → entry with `error="no cached geometry"`,
  `geometry_key=None`.
- Opening emitted once even if its host appears multiple times (dedupe by
  opening reference).
- Single-cap voids (recess test fake) → `depth=None`.
- Tapered voids (real model): caps differ in size; `area` reports the larger
  (outer) cap, cached mesh contains both caps.
- Roof-window niches (real model): voids can be larger OR smaller than the
  glazing — void geometry is reported, not the window.
- Curved caps (arched openings): fixed 1° grouping returns the largest flat
  portion (documented limitation).
- Openings of decomposed parts (parts hosting openings themselves) are not
  collected from the parent element (documented limitation).

## Layout & registration
- Runner: `app/runner/src/openbim_runner/nodes/opening_surface/opening_surface.py`
- README.en.md / README.de.md (frontmatter `title`/`description`/`categories`)
- Tests: `tests/test_opening_surface.py`
- Registered in `nodes/__init__.py` (import + `__all__`, alphabetical).
- Web: `app/web/app/nodes/OpeningSurface/OpeningSurface.vue` (+ `types.ts` if
  needed); registered in `app/web/app/utils/nodes.ts`
  (`opening_surface: 'OpeningSurface'`).
- i18n keys `node.openingSurface.*` in `app/web/i18n/locales/en.json` + `de.json`.
- Schema regenerated via `npm run generate:schema` (in app/web).

## Verification

- Runner (in app/runner): `uv run pytest` — 315 passed (12 new, incl. 3
  real-model tests on the small fixture); `uv run ruff check` + `ruff format`
  clean; `uv run pyright` — 0 errors (warning-level unknowns like existing
  nodes).
- Web (in app/web): `npm run lint` clean; `npm run typecheck` exit 0;
  `npm run generate:schema` regenerated schema.json + schema.d.ts with
  `opening_surface` (title "Opening Surface", category geometry, locales de/en).
- Node adds no new Python or npm dependencies (numpy, trimesh, pydantic already
  in use). `app/web/node_modules` had to be installed for the web checks.
