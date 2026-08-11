# Plan: Collision Node (refined)

## Goal

Refine the `collision` runner node. It performs **clash detection** between cached geometries. A side is described by references and tested **list A against list B** (cartesian product, not zip). When a side is empty, it falls back to the **whole model** (everything in the workflow geometry cache). A new `mode` setting switches the node between **boolean** collision reporting and **intersection mesh** generation.

## OPEN TODO

- Web implementation
- Testing by user

---

## Node contract

### Settings

- `mode: Literal["boolean", "intersection_mesh"]`, default `"boolean"`.
  - `boolean`: output is true/false — true if any geometry in A overlaps any geometry in B, otherwise false.
  - `intersection_mesh`: output is the mesh of the overlap (or null).

Replaces the previous `include_intersection_mesh` setting (subsumed by `mode`).

### Inputs

- `list_a: list[int | str]`, default `[]` — first list of references: mix of express IDs (`int` → `ifc:<id>`) and object IDs (`str` → `gen:<id>`), in order to test.
- `list_b: list[int | str]`, default `[]` — second (optional) list, same encoding as `list_a`.

An `int` element is an IFC express ID, a `str` element is an object ID. Elements keep their order in the resolved list. When a side's list is empty that side falls back to the whole model.

### Output

`CollisionResult` = `collisions: dict[key_a, list[key_b]]` + `errors: list[CollisionError]` (always, regardless of mode).

---

## Locked Decisions

1. **Pairing semantics**: **Cartesian product**, not zip — every `A[i]` is tested against every `B[j]`. No length requirement.

2. **Reference-based inputs**: No `Geometry` handle construct and no `get_geometry` node. Collision is the single place that maps references → cache keys → meshes. Express IDs map to `ifc:<id>`, object IDs to `gen:<object_id>`. Missing references raise `ValueError`.

3. **Empty-side fallback**: When a side's list (`list_a`/`list_b`) is empty, that side becomes **all user-referencable keys in the geometry cache** (whole model), in cache insertion order. The whole-model expansion — and the reference→key mapping — lives in `util/geometry.py` (`resolve_side`) so the collision node stays clean. Intermediates (reserved `inter:` prefix) are excluded from the expansion.

4. **Mode setting**: `mode: Literal["boolean", "intersection_mesh"]`, default `"boolean"`. `boolean` detects collisions without storing intersection geometry. `intersection_mesh` also caches each colliding pair's intersection mesh under the deterministic key `inter:intersection_{key_a}_{key_b}` (strict loop order, mirrored per symmetric direction).

5. **Self-pairs**: Always skip a pair where `key_a == key_b`.

6. **Symmetric pairs**: Not deduplicated — both `X↔Y` and `Y↔X` are emitted.

7. **Only collisions are emitted**: non-colliding pairs (disjoint, face-touching) are absent from the result. The intersection-mesh key is not returned as data — it is derived deterministically (`inter:intersection_{key_a}_{key_b}`) and documented, not carried on a record.

8. **Collision algorithm**: AABB prefilter (numpy) → `trimesh.boolean.intersection([a, b], engine="manifold", check_volume=False)` per pair. `collides = intersection has faces and volume > tol`.

9. **Non-watertight meshes**: Repair ladder best-effort (weld → `process(validate=True)`, `merge_vertices`, `fill_holes`, `fix_normals`, `fix_winding` → `pymeshfix`). Unrepairable → recorded in `errors` as `"non-watertight"`. Never silently fall back to a convex hull.

10. **Errors are data**: undecidable pairs land in `errors: list[CollisionError{key_a, key_b, error}]`. Hard contract violations (e.g. missing cache key) still raise `ValueError`.

11. **Result model**: `CollisionResult.collisions: dict[str, list[str]]` grouped by side-A key (each value lists colliding side-B keys) plus `errors`. `CollisionPair` is dropped. `key_a`/`key_b` alone identify each element.

12. **Performance posture**: Prototype-grade; cartesian product is O(N×M) plus the per-pair AABB prefilter (cheap for most pairs). When both sides are empty both fall back to the cache → O(N²). Accepted for the prototype.

---

## File changes

### 0. Geometry caching + reference utils (`util/geometry.py`)

- Keep `build_geometry_cache(ifc_model, *, settings_factory, shape_iterator, geometry_library)` → `dict[str, trimesh.Trimesh]`, called at workflow init (keys `ifc:{express_id}`).
- **Remove the `Geometry` model.**
- `cache_mesh(context, mesh, *, express_id=None, object_id=None, intermediate=False, key=None) -> str` stores a mesh and returns its key:
  - `express_id` → `ifc:<id>`
  - `object_id` → `gen:<object_id>`
  - `intermediate` → `inter:<uuid>` (internal helpers, excluded from whole-model expansion)
  - `key` → stores under an explicit, fully-specified key (used for deterministic `inter:intersection_{key_a}_{key_b}`)
  - Exactly one kind must be given; a duplicate key raises.
- `resolve_mesh(context, key) -> trimesh.Trimesh` (raises on missing).
- `is_model_key(key) -> bool` (user-referencable: `ifc:`/`gen:`, not `inter:`).
- `resolve_side(context, *, refs) -> list[str]` maps a mixed `list[int | str]` of references to ordered keys (`int` → `ifc:<id>`, `str` → `gen:<id>`); when the list is empty returns the whole-model keys. This is the util home for the fallback so collision stays clean.

### 1. Remove `get_geometry`

- Delete `nodes/get_geometry/` (module, tests, both READMEs) and its import in `nodes/__init__.py`.
- `ifc_element_filter` feeds `express_ids` directly to collision.

### 2. `nodes/generate_3d_cube/generate_3d_cube.py`

- Add input `object_id: str` (required, non-empty, unique per run).
- Cache under `gen:{object_id}` via `cache_mesh(..., object_id=...)` (duplicate → error).
- Result becomes `object_ids: list[str]` (1 element). Update READMEs (`README.en.md`/`README.de.md`) and tests.

### 3. `nodes/collision/collision.py`

- `CollisionSettings`: `mode: Literal["boolean", "intersection_mesh"]`.
- `CollisionInputs`: `list_a`, `list_b` — each `list[int | str]` mixing express IDs (`int`) and object IDs (`str`), default `[]`.
- `CollisionResult`: `collisions: dict[str, list[str]]` + `errors: list[CollisionError]`. `CollisionPair` is dropped; `key_a`/`key_b` alone identify each element.
- Handler: resolve side A via `resolve_side(refs=list_a)`, side B likewise; nested cartesian loop; skip `key_a == key_b`; AABB prefilter → `ensure_watertight` → boolean intersection; if colliding, append `key_b` to `collisions[key_a]` and, when `mode == "intersection_mesh"`, store the mesh via `cache_mesh(..., key=f"inter:intersection_{key_a}_{key_b}")`; undecidable pairs go to `errors`.

### 4. Tests

- `nodes/collision/tests/test_collision.py`: grouped collisions dict (overlap, disjoint absent, face-touching absent, multiple per key), `errors` (non-watertight), cartesian product, empty-A and empty-B whole-model fallback, self-pair skip, mode boolean (no cache) / intersection_mesh (deterministic key present), missing express/object reference raises.
- `nodes/generate_3d_cube/tests/test_generate_3d_cube.py`: object_id input, `gen:<id>` cache, empty/duplicate object_id errors.
- `tests/test_geometry_cache.py`: keep `build_geometry_cache` tests; add `cache_mesh` (explicit `key`, duplicate raises)/`resolve_mesh`/`is_model_key`/`resolve_side` (whole-model fallback, missing-reference raises).
- Delete `test_get_geometry.py` (removed with the node).

### 5. Docs + schema

- Rewrite `collision/README.en.md` + `README.de.md` (references, fallback, mode, grouped result + errors, deterministic intersection-mesh key convention).
- Rewrite `generate_3d_cube/README.en.md` + `README.de.md` (object_id).
- Regenerate `app/web/scripts/schema.json` + `schema.d.ts` via `npm run generate:schema`. `GetGeometry` disappears; `CollisionDetection` inputs become `list_a`/`list_b` (each `list[number|string]`) and its result becomes `collisions + errors` (no `CollisionPair`/index fields); `Generate3DCube` result becomes `object_ids`.
- Check `app/web/app/nodes/Generate3DCube/Generate3DCube.vue` for result-field usage.

---

## Verification

- `uv run pytest` (from `app/runner`) — collision/cube/geometry tests pass.
- `uv run ruff check .` — lint clean.
- `npm run generate:schema` (from `app/web`) — schema regenerates without error.
- `npm run lint && npm run typecheck` (from `app/web`) — frontend clean.
