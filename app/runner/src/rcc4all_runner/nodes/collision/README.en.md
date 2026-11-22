---
title: Collision Detection
description: Clash detection between two geometry lists via AABB prefilter, boolean intersection, and FCL fallback for non-repairable meshes.
categories: geometry,collision
---

The `collision` node detects clashes between two lists of cached geometries. References are **fully qualified geometry cache keys**: `<slug>:expr:<id>` for IFC elements, `gen:<object_id>` for generated geometry, or `inter:<id>` for helper/intersection geometry. IFC references resolve against the model named inside them, while `gen:` and `inter:` keys are read directly from the shared geometry cache. The two lists may therefore come from different IFC files. Every element of list A is tested against every element of list B (cartesian product). Each pair goes through a three-stage pipeline:

1. **AABB prefilter** — skip pairs with non-overlapping bounding boxes.
2. **Boolean intersection** — repair both meshes to watertight, compute the intersection. A pair collides when the intersection has positive volume.
3. **FCL fallback** — when repair or boolean fails, use FCL triangle-based collision detection on the raw meshes. FCL-decided collisions are reported but cannot produce intersection meshes.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `list_a` | `list[str]` | First list of fully qualified geometry cache keys (required) |
| `list_b` | `list[str]` | Second list of fully qualified geometry cache keys (required) |

Both inputs are required and unbound inputs fail input validation. An empty list means zero geometry keys, so no pairs are tested. A malformed reference or one with no cached geometry raises an error.

## Pairing

- **Self-pairs** are skipped. Ancestor/descendant pairs via `IfcRelAggregates`/`IfcRelNests` are also skipped (intra-model only). Pairs are not deduplicated: both `X↔Y` and `Y↔X` are emitted.

## Mode

- **`boolean`** (default): reports which pairs collide, no intersection geometry stored.
- **`intersection_mesh`**: additionally stores each colliding pair's intersection mesh in the geometry cache under a deterministic key.

## Result

`CollisionResult` contains three fields:

- `collisions: dict[key_a, list[key_b]]` — colliding pairs, grouped by side-A key.
- `errors: list[{key_a, key_b, error}]` — pairs that could not be decided (both boolean and FCL failed, or FCL unavailable).
- `intersection_meshes: dict[pair_key, cache_key | null]` — only in `intersection_mesh` mode. Maps `"{key_a}__{key_b}"` to the cache key `inter:intersection_{key_a}_{key_b}`. `null` for FCL-decided collisions (no mesh generated). Empty in `boolean` mode.

Non-colliding pairs are absent from the result.

## Intersection-mesh keys

In `intersection_mesh` mode, each boolean-decided colliding pair is cached under:

```
inter:intersection_{key_a}_{key_b}
```

It is an `inter:` key and can be passed to geometry consumers such as the measurement node. Because pairs are not deduplicated, `X↔Y` and `Y↔X` each get their own key. FCL-decided collisions appear with a `null` value; no mesh is stored.

## Notes

- Non-watertight meshes are repaired best-effort (vertex welding, hole filling, pymeshfix). When repair or boolean fails, FCL (Flexible Collision Library) provides triangle-based collision detection on raw triangle soups. Pairs reach `errors` only when both boolean and FCL fail (requires `python-fcl`).
- Face-touching pairs produce zero-volume intersections and count as non-colliding.
