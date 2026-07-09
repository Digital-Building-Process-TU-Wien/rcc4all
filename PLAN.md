# Plan: Geometry Node + Collision Node (rev. 2)

## Goal

Add two new runner nodes — `get_geometry` and `collision` — that let workflows extract IFC element geometry in worldspace and run **pairwise** (zip, not cartesian) collision detection between two geometry lists. The same collision node works for workflow-generated geometry (e.g. a `generate_3d_cube` cube vs. one door). `trimesh` is the geometry engine; `manifold3d` is the boolean backend.

---

## Locked Decisions (grilling session + adversarial review)

| # | Decision | Choice |
|---|---|---|
| 1 | Geometry port type | **Handle-based** `Geometry` value object: `{key: str, express_id: int \| None}`. Meshes live in a workflow-scoped `geometry_cache` on the execution context, NOT in the port payload. Keeps result JSON small (results flow through stdout → JSON.parse → SSE, see `execute.sse.ts:74-82`). |
| 2 | Missing-geometry handling | `fail_on_missing: bool` setting (default `false` → skip, `true` → raise `ValueError`), mirroring `get_name.py:9-13`. Description must distinguish the two failure modes it covers: (a) express ID not in model, (b) element exists but has no body representation. |
| 3 | Tessellation fidelity | Use the ifcopenshell default (`mesher-linear-deflection = 0.001`, i.e. 1 mm in metres). No user-facing setting — building elements are predominantly prismatic and collision detection depends on watertightness, not mesh fidelity. |
| 4 | Pairing semantics | **Pairwise (zip)**, not cartesian product: pair `A[i]` with `B[i]`. Mismatched lengths raise `ValueError` — no length-1 broadcast (an invalid workflow should surface as an error, not silently fan out). |
| 5 | Collision result shape | `list[CollisionPair]` — one record per zip pair. Pairwise semantics keeps this O(n), so non-colliding pairs are included (no `only_collisions` filter needed). |
| 6 | Geometry port cardinality | **Uniform `list[Geometry]` everywhere.** No `Geometry \| list[Geometry]` unions — unions muddy the generated JSON schema and the (weak) frontend type parsing. `generate_3d_cube` emits a 1-element list. |
| 7 | Collision algorithm | AABB prefilter (numpy) → `trimesh.boolean.intersection([a, b], engine="manifold", check_volume=False)`. `collides = intersection has volume > tol`. NOTE: `trimesh.intersections.intersection` does **not exist**; the boolean module is the correct API. |
| 8 | Non-watertight meshes | Repair ladder (best-effort, shape/volume-preserving): tessellation settings (`weld-vertices`) → trimesh repair (`process(validate=True)`, `merge_vertices`, `repair.fill_holes`, `repair.fix_normals`) → `pymeshfix` → give up: `collides=None`, `error="non-watertight"` on the pair. **Never** silently fall back to convex hull. |
| 9 | Frontend type-checker | **Defer.** No hard type enforcement exists on connections today (`flow.ts:54` does zero type checks; `areTypesCompatible` is advisory-only in `InputBindingsSection.vue:101`). Ship nodes now. |
| 10 | Intersection mesh output | `include_intersection_mesh: bool` setting (default `off`). The boolean result is already computed for the collision test; when on, colliding pairs store it in the geometry cache and carry `intersection_key`. No inline vertices in the result payload. |
| 11 | Cube output migration | **Replace** `vertices`/`faces` outputs with `geometry: list[Geometry]` (1 element, `express_id=None`). Verified safe: nothing in `app/web` or cms reads `vertices`/`faces` field-wise; only generated schema artifacts. |
| 12 | Geometry model + cache location | Shared module `nodes/geometry.py` (avoids a module literally named `types` for traceback clarity). `geometry_cache: dict[str, trimesh.Trimesh]` added to `ExecutionContext`. |
| 13 | CollisionPair fields | `index`, `key_a`, `key_b`, `express_id_a`, `express_id_b`, `collides: bool \| None`, `intersection_volume: float \| None`, `error: str \| None`, and (when enabled) `intersection_key: str \| None`. |
| 14 | Dependencies | Add to `app/runner/pyproject.toml`: `numpy` (used directly — currently only transitive), `manifold3d` (boolean engine), `pymeshfix` (repair ladder step 3). |
| 15 | Performance posture | Prototype-grade: per-element `ifcopenshell.geom.create_shape` loop is acceptable and blocks the (sequential) asyncio loop — tolerated. `ifcopenshell.geom.iterator` (multithreaded) noted as the future fast path. |

---

## Deliverables

### 1. Shared module: `nodes/geometry.py`

Path: `app/runner/src/openbim_runner/nodes/geometry.py`

```python
from __future__ import annotations
from pydantic import Field
from openbim_runner.nodes.base import NodeModel

class Geometry(NodeModel):
    key: str = Field(title="Cache Key",
        description="Key into the workflow-scoped geometry cache holding the trimesh mesh.")
    express_id: int | None = Field(default=None, title="Express ID",
        description="IFC express ID of the source element, or None for workflow-generated geometry.")
```

Also provides helpers used by all three nodes:

```python
def cache_mesh(context, mesh, express_id=None) -> Geometry
    # key = f"ifc:{express_id}" for IFC elements, f"gen:{uuid4()}" otherwise;
    # stores mesh in context.geometry_cache, returns the Geometry handle.

def resolve_mesh(context, geometry: Geometry) -> trimesh.Trimesh
    # KeyError → ValueError with a clear message.

def ensure_watertight(mesh) -> tuple[trimesh.Trimesh | None, str | None]
    # Repair ladder (Decision 8). Returns (repaired_mesh, None) or (None, error_string).
```

### 2. Execution context: geometry cache

Paths: `app/runner/src/openbim_runner/nodes/base.py`, `app/runner/src/openbim_runner/workflow.py`

- `ExecutionContext.__init__` (`base.py:17-20`) gains `geometry_cache: dict[str, "trimesh.Trimesh"] | None = None` (default → fresh `{}` so existing tests keep working).
- `workflow.py` (~`:184`): create **one** cache dict per run and pass it into every `ExecutionContext` so handles survive across nodes. Cache is in-process only (whole workflow runs sequentially in one process, `workflow.py:195-196`) and dies with the run — fine today; the key scheme carries over to file-backed storage / "write back as IFC" later.

### 3. New node: `get_geometry`

Path: `app/runner/src/openbim_runner/nodes/get_geometry/get_geometry.py`

**Purpose:** Tessellate the body geometry of IFC elements in worldspace, cache the meshes, return `list[Geometry]` handles.

**Models:**

```python
class GetGeometrySettings(NodeModel):
    fail_on_missing: bool = Field(default=False, ...)   # covers both: unknown ID, no body representation

class GetGeometryInputs(NodeModel):
    express_ids: list[int] = Field(default=[], ...)

class GetGeometryResult(NodeModel):
    geometries: list[Geometry] = Field(default=[], ...)
```

**Handler:** `async def get_geometry(settings, inputs, context) -> GetGeometryResult`

**Logic:**
- Build ifcopenshell geom settings **once** (first use of `ifcopenshell.geom` in the codebase):
  ```python
  s = ifcopenshell.geom.settings()
  s.set("use-world-coords", True)      # worldspace verts, transform baked in
  s.set("weld-vertices", True)         # repair ladder step 1: watertight at the source
  s.set("context_types", ["Body"])
  # mesher-linear-deflection left at ifcopenshell default (0.001 = 1 mm in metres)
  ```
- For each `express_id`:
  - `element = context.ifc_model.by_id(express_id)` (raises `RuntimeError` on unknown ID — same contract as `get_name.py:38`).
  - `shape = ifcopenshell.geom.create_shape(s, element)` — note: `settings` is the **first** positional arg; the entity from `by_id` is passed directly (no `entity_instance` re-wrap). Raises `RuntimeError` for elements without body representation.
  - `.geometry.verts` / `.geometry.faces` are **flat** tuples → reshape via numpy to `(n,3)` and build `trimesh.Trimesh`.
  - On `RuntimeError` / empty geometry: `fail_on_missing` → raise `ValueError` (message states which of the two failure modes occurred); else skip. Skipping is safe — each handle carries its own `express_id`.
  - `cache_mesh(context, mesh, express_id)` → append handle.
- Perf note (Decision 15): loop-over-`create_shape` is the simple path; `ifcopenshell.geom.iterator` is the documented future optimization. CPU-bound sync work blocks the event loop — acceptable, execution is sequential (`base.py:251`).

**Docs:** `README.en.md` + `README.de.md` with YAML frontmatter (`title`, `description`, `categories: geometry,ifc`).

**Tests:** `tests/test_get_geometry.py` — follow `test_get_name.py` pattern (NOT the stale `test_generate_3d_cube.py`). Fake IFC model is impractical for real tessellation, so monkeypatch `ifcopenshell.geom.create_shape`/`settings` with a fake returning flat vert/face tuples. Cover: happy path (handle emitted, mesh in cache, express_id set), missing element skip, missing element raise, empty body representation skip/raise, geom settings pass-through (`use-world-coords`, `weld-vertices` set; `mesher-linear-deflection` not set).

### 4. New node: `collision`

Path: `app/runner/src/openbim_runner/nodes/collision/collision.py`

**Purpose:** Pairwise (zip) collision detection between two geometry lists.

**Models:**

```python
class CollisionSettings(NodeModel):
    include_intersection_mesh: bool = Field(default=False, ...)

class CollisionInputs(NodeModel):
    geometries_a: list[Geometry] = Field(default=[], ...)
    geometries_b: list[Geometry] = Field(default=[], ...)

class CollisionPair(NodeModel):
    index: int
    key_a: str
    key_b: str
    express_id_a: int | None
    express_id_b: int | None
    collides: bool | None          # None = undecidable (see error)
    intersection_volume: float | None = None
    intersection_key: str | None = None   # geometry-cache handle, only when setting enabled
    error: str | None = None       # e.g. "non-watertight", "boolean failed: ..."

class CollisionResult(NodeModel):
    pairs: list[CollisionPair] = Field(default=[], ...)
```

**Handler:** `async def collision(settings, inputs, context) -> CollisionResult`

**Logic:**
- **Pairing (Decision 4):** `len(A) == len(B)` → zip. Anything else → `ValueError` with both lengths in the message.
- Resolve handles to meshes via `resolve_mesh`. Precompute AABBs (`mesh.bounds`).
- Per pair:
  - AABB overlap check (numpy): no overlap → `collides=False`, done. (Touching-only AABBs may pass; the volume tolerance below settles them.)
  - Repair as needed: `ensure_watertight` on each non-watertight mesh (Decision 8 ladder). Unrepairable → `collides=None`, `error="non-watertight"`, continue.
  - `result = trimesh.boolean.intersection([a, b], engine="manifold", check_volume=False)` wrapped in try/except → on failure `collides=None`, `error=f"boolean failed: {exc}"`.
  - `collides = result is not empty and result.volume > tol` (tol pinned as module constant, e.g. `1e-9` — face-touching pairs produce zero-volume results and count as `False`).
  - `intersection_volume = result.volume` when colliding.
  - If `include_intersection_mesh` and colliding: `intersection_key = cache_mesh(context, result).key` — reuses the already-computed boolean, nothing inlined.
- Repairs never mutate the cached source meshes (they operate on copies).

**Docs:** `README.en.md` + `README.de.md` (`categories: geometry,collision`).

**Tests:** `tests/test_collision.py` — meshes built with `trimesh.creation.box` directly into a fake context's `geometry_cache`. Cover: disjoint pair (`False`), overlapping pair (`True`, volume > 0), face-touching pair (`False` via tolerance), zip pairing, length-1 mismatch raises (1×N and N×1), general mismatched lengths raise, non-watertight → repaired-or-`None`+error, `include_intersection_mesh` on/off (key present, mesh in cache), express_id pass-through.

### 5. Update existing node: `generate_3d_cube`

Path: `app/runner/src/openbim_runner/nodes/generate_3d_cube/generate_3d_cube.py`

- Node already builds a `trimesh` box (`:62-74`) — keep that; instead of `.tolist()` dumps, `cache_mesh(context, box)` and emit:

```python
class Generate3DCubeResult(NodeModel):
    geometry: list[Geometry] = Field(default=[], title="Geometry",
        description="The generated cube as a 1-element geometry list (express_id=None).")
```

- Fix the stale tests: `test_generate_3d_cube.py:9-14` imports a non-existent `Generate3DCubeSettings` and passes 3 args to a 2-arg handler (fails at import today). Rewrite against the real signature + handle output (assert mesh in cache, 8 verts / 12 tri faces).

### 6. Dependencies

`app/runner/pyproject.toml:11-15` — add `numpy`, `manifold3d`, `pymeshfix` (Decision 14). Run `uv sync`.

### 7. Registration

- `app/runner/src/openbim_runner/nodes/__init__.py`: import `get_geometry` and `collision` (match the existing export pattern). The `@node()` decorator auto-registers via function name (`base.py:177-189`).

### 8. Schema regeneration

- `npm run generate:schema` from `app/web` → regenerates `app/web/scripts/schema.json` + `schema.d.ts`; new nodes appear in the UI palette (`nodes.ts:125-142`).

### 9. Frontend (optional this session, but planned)

- `app/web/app/nodes/GetGeometry/GetGeometry.vue`, `app/web/app/nodes/Collision/Collision.vue` — follow `Generate3DCube.vue`; `SchemaNodeType<K>` + `useScopedNode(id)` per `app/web/AGENTS.md`; map in `nodes.ts:64-72`.
- `Generate3DCube.vue` needs no output changes (it renders `node.data.result` generically, `:36`).

### 10. Deferred (out of scope this session)

- **Frontend type-checker enhancement** — `parseTypeSchema` (`schema-helpers.ts:73`) `$ref`/object resolution, structural subtyping. Not needed; no hard enforcement exists today.
- **Array/iteration architecture** — engine-level implicit broadcasting (n8n/Blender-fields style) or a map meta-node. For now: uniform `list[Geometry]` ports (Decision 6).
- **Persist geometry cache / write results back as IFC** (root `README.md:40` roadmap) — a node that reads `intersection_key` meshes from the cache and writes them as IFC geometry. The handle scheme is designed to make this a drop-in.
- **`ifcopenshell.geom.iterator`** fast path for large models.

---

## File Inventory

| Action | Path |
|---|---|
| Create | `app/runner/src/openbim_runner/nodes/geometry.py` |
| Edit   | `app/runner/src/openbim_runner/nodes/base.py` (ExecutionContext: `geometry_cache`) |
| Edit   | `app/runner/src/openbim_runner/workflow.py` (per-run cache) |
| Edit   | `app/runner/pyproject.toml` (numpy, manifold3d, pymeshfix) |
| Create | `app/runner/src/openbim_runner/nodes/get_geometry/get_geometry.py` |
| Create | `app/runner/src/openbim_runner/nodes/get_geometry/README.en.md` / `README.de.md` |
| Create | `app/runner/src/openbim_runner/nodes/get_geometry/tests/test_get_geometry.py` |
| Create | `app/runner/src/openbim_runner/nodes/collision/collision.py` |
| Create | `app/runner/src/openbim_runner/nodes/collision/README.en.md` / `README.de.md` |
| Create | `app/runner/src/openbim_runner/nodes/collision/tests/test_collision.py` |
| Edit   | `app/runner/src/openbim_runner/nodes/generate_3d_cube/generate_3d_cube.py` |
| Edit   | `app/runner/src/openbim_runner/nodes/generate_3d_cube/tests/test_generate_3d_cube.py` |
| Edit   | `app/runner/src/openbim_runner/nodes/__init__.py` |
| Regen  | `app/web/scripts/schema.json` + `schema.d.ts` (via `npm run generate:schema`) |
| Create (optional) | `app/web/app/nodes/GetGeometry/GetGeometry.vue`, `app/web/app/nodes/Collision/Collision.vue` |
| Edit (optional)   | `app/web/app/utils/nodes.ts` |

---

## Verification

- `uv run pytest` (from `app/runner`) — all node tests pass, including the rewritten cube tests.
- `uv run ruff check .` — lint clean.
- `npm run generate:schema` (from `app/web`) — schema regenerates without error.
- `npm run lint && npm run typecheck` (from `app/web`) — frontend clean.
- Smoke workflow: `ifc_element_filter` (doors) → `get_geometry` → `collision.geometries_a`; `generate_3d_cube` → `collision.geometries_b` (equal-length zip, one cube per door) → inspect `pairs`.
- Sanity check on a real IFC model: log how many elements needed each repair-ladder step (informs whether pymeshfix earns its keep).
