---
title: Collision Detection
description: Clash detection between two geometry lists via a cartesian product of mesh boolean intersections. An empty list falls back to the whole model.
categories: geometry,collision
---

The `collision` node performs **clash detection** between two lists of cached geometries. Each side is described by references: **express IDs** for internal IFC elements (`ifc:<id>`) and **object IDs** for external/generated elements (`gen:<object_id>`). It tests **list A against list B** (the full cartesian product — every `A[i]` is checked against every `B[j]`), so no length match is required. Each pair is tested with an AABB prefilter followed by a manifold boolean intersection. A pair collides when the intersection has positive volume.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `list_a` | `list[number \| string]` | First list of references — mix of express IDs (`int` → `ifc:<id>`) and object IDs (`str` → `gen:<id>`), in the order to test |
| `list_b` | `list[number \| string]` | Second (optional) list of references — same encoding as `list_a` |

Each element is a reference to a cached geometry: an **int** is an IFC express ID, a **str** is an object ID (e.g. from a cube node). Elements keep their order in the resolved list. A reference with no cached geometry raises an error.

## Pairing

- **Cartesian product**: every element of side A is tested against every element of side B. Unequal list sizes are fine.
- **Whole-model fallback**: if both lists on a side are empty, that side is replaced by **all cached geometries** (the whole model). For example, an empty B side checks every A element against the whole model.
- **Self-pairs** (a geometry vs itself) are always skipped.
- Pairs are not deduplicated: both `X↔Y` and `Y↔X` are emitted.

## Mode

- **`boolean`** (default): reports which pairs collide without storing any intersection geometry.
- **`intersection_mesh`**: additionally stores each colliding pair's intersection mesh in the geometry cache under a **deterministic key** (below), so colliding geometry can be written back (e.g. as IFC) by a future workflow extension.

## Result

`CollisionResult` contains two fields:

- `collisions: dict[key_a, list[key_b]]` — grouped by side-A cache key; only **colliding** pairs are included. `key_a` appears once, and its value lists every side-B cache key it collides with.
- `errors: list[{key_a, key_b, error}]` — pairs whose collision could not be decided (e.g. `non-watertight` or `boolean failed: ...`).

Non-colliding pairs (disjoint or face-touching) are simply absent from the result. `key_a`/`key_b` are the geometry-cache keys (`ifc:<express_id>` or `gen:<object_id>`) and alone identify every element.

## Intersection-mesh keys

In `intersection_mesh` mode each colliding pair `(key_a, key_b)` is additionally cached under the deterministic key:

```
inter:intersection_{key_a}_{key_b}
```

For example, if `ifc:1` collides with `ifc:2`, an entry `inter:intersection_ifc:1_ifc:2` is written to the geometry cache. The key is **not** part of the result — look it up via `resolve_mesh` when needed. It is an `inter:` key, so it is excluded from collision inputs and from the whole-model fallback. Because pairs are not deduplicated, the symmetric pair `X↔Y` and `Y↔X` each receive their own key in the corresponding direction.

## Notes

- Non-watertight meshes are repaired best-effort (vertex welding, hole filling, pymeshfix). Unrepairable meshes are recorded in `errors` with `error="non-watertight"`.
- Face-touching pairs produce zero-volume intersections and count as non-colliding.
