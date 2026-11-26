---
title: Geometry Projection
description: Project cached geometries (e.g. building footprints) onto a plane through the world origin and store the flat projected footprint as generated geometry. Does not compute areas.
categories: Geometry
---

The `geometry_projection` node projects the geometry of each input reference onto a plane
passing through the world origin and stores the resulting **flat footprint surface** as new
generated geometry in the cache. To measure the projected area, feed the resulting footprint
into `measurement`'s `surface_area` mode. This node produces an actual planar mesh you can
use downstream (e.g. feed into `collision`, `measurement`, or a later `geometry_projection`).

The projected geometry is stored under a deterministic `gen:proj_<reference>` key that maps
each input reference back to its generated key in the result. It does **not** compute areas.

## Use case example

- Generate a footprint (top-down projection) of a building or element and use it as the
  input to a collision or measurement check.
- Project an intersection mesh (from the `collision` node) onto a plane for further analysis.

## Settings

### Projection normal

The normal vector of the projection plane. The plane always passes through the **world
origin**.

- **Default**: `[0.0, 0.0, 1.0]` (XY plane, top-down footprint)
- **Format**: List of exactly 3 floats `[x, y, z]`
- **Normalization**: The normal is normalized internally; only the direction matters, not the
  magnitude.
- **Zero normal**: If the normal is zero-length (e.g. `[0.0, 0.0, 0.0]`), an error entry
  `undefined normal` is produced for every input.
- **Examples**:
  - `[0, 0, 1]` → Project onto the XY plane (footprint; `z=0`, keeps `x/y` plan position)
  - `[1, 0, 0]` → Project onto the YZ plane
  - `[0, 1, 0]` → Project onto the XZ plane

## Inputs

- **List** (required): A list of fully qualified geometry cache keys
  (`<slug>:expr:<id>` for IFC elements, `gen:<object_id>` for generated geometry,
  `inter:<id>` for helper/intersection geometry). An empty list yields an empty result.
  - **Dict input**: Also accepts a dict (e.g., the `intersection_meshes` output from the
    collision node). The dict's non-null values (cache keys) are used.

## Outputs

- **Projected geometries**: A dict mapping each input geometry cache key to the generated
  `gen:proj_<...>` key under which its footprint was stored in the geometry cache.
- **Errors**: A list of per-input `{reference, error}` failures.

### Generated key

The generated key is `gen:proj_<reference>` where every `:` and `/` in the reference is
reduced to `_`. Within a single run the same reference always maps to the same key (idempotent);
two different references that reduce to the same base get `_1`, `_2`, … so their footprints never
collide, and a key already in the cache (e.g. from an earlier node) gets a `_n` suffix. Because
the generated key never contains a clean `:expr:<int>` sequence, it can never be misparsed as
an IFC reference downstream.

| Input reference | Generated key |
|-----------------|---------------|
| `main:expr:170` | `gen:proj_main_expr_170` |
| `inter:intersection_main:expr:766_main:expr:347` | `gen:proj_inter_intersection_main_expr_766_main_expr_347` |
| `gen:a_b` (then `gen:a:b`) | `gen:proj_gen_a_b`, then `gen:proj_gen_a_b_1` |

## Example Configuration

**Settings:**
- Projection normal: `[0.0, 0.0, 1.0]` (top-down footprint)

**Inputs:**
- List: `["main:expr:101", "main:expr:102"]` (two walls)

**Output:**
```json
{
  "projected_geometries": {
    "main:expr:101": "gen:proj_main_expr_101",
    "main:expr:102": "gen:proj_main_expr_102"
  },
  "errors": []
}
```

### Error handling

- `no cached geometry` — The reference is not a valid geometry cache key or has no cached
  geometry (e.g. `main:expr:999`).
- `no projected geometry` — The projection is empty/degenerate: the mesh is edge-on to the
  projection plane, so it has no area in that plane.
- `undefined normal` — The projection normal is zero-length. Emitted for every input.

**Inputs:**
- List: `["main:expr:101", "main:expr:999"]`

**Output:**
```json
{
  "projected_geometries": {
    "main:expr:101": "gen:proj_main_expr_101"
  },
  "errors": [
    { "reference": "main:expr:999", "error": "no cached geometry" }
  ]
}
```

## Notes

- **Winding / orientation**: For negative or rotated normals the footprint is geometrically
  correct, but the face normal direction may be inverted. Use the mesh purely as a planar
  surface.
- **Idempotency**: Within a single run, listing the same reference twice produces the same
  generated key (no duplicate footprint). Re-running the same workflow against a fresh cache
  also yields the same keys — it does not accumulate `_1`, `_2`, … A key that already exists in
  the shared cache (e.g. produced by an earlier node) is not reused; it gets a `_n` suffix.
- **Empty list**: An empty **List** yields an empty result (no errors).
