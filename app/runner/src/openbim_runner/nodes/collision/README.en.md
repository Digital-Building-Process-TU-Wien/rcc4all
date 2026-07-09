---
title: Collision Detection
description: Pairwise collision detection between two geometry lists via mesh boolean intersection.
categories: geometry,collision
---

The `collision` node performs pairwise (zip) collision detection between two lists of geometry handles. Each pair is tested using an AABB prefilter followed by a manifold boolean intersection. A pair collides when the intersection has positive volume.

## Pairing

- Equal-length lists: elements are paired by index (`A[i]` with `B[i]`).
- Mismatched lengths raise an error.

## Result

Each pair produces a `CollisionPair` record with `collides` (`true`/`false`/`null`), `intersection_volume`, and an `error` field when the result is undecidable (e.g. non-watertight meshes or boolean failure).

## Settings

- **Include intersection mesh**: When enabled, colliding pairs store the intersection mesh in the geometry cache and carry an `intersection_key` handle. This enables a future workflow extension that writes intersection geometry back as IFC.

## Notes

- Non-watertight meshes are repaired best-effort (vertex welding, hole filling, pymeshfix). Unrepairable meshes report `collides=null` with `error="non-watertight"`.
- Face-touching pairs produce zero-volume intersections and count as non-colliding.
