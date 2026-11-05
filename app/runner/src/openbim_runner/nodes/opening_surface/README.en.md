---
title: Opening Surface
description: Retrieves the surfaces of openings that lie in the plane of the host surface (walls, slabs, roofs) and caches them as generated geometry for downstream nodes.
categories: geometry
---

The `opening_surface` node retrieves, for every opening of the input building
elements, the void faces that lie in the plane of the host surface — the two cap
faces of the opening — and caches them as generated geometry for downstream
nodes such as measurement or collision.

## How it works

For each input element, the openings (`IfcRelVoidsElement`) and their cached
Body meshes are resolved. The opening mesh triangles are grouped into planar
surfaces: triangles join a group when their normal deviates by less than ~1°
and they lie on the same plane. The two largest groups with opposing normals
are the cap faces in the plane of the host surface; the remaining groups (the
reveal band cut into the host) are dropped.

## Use case example

- Measure the window opening area of exterior walls for daylight or fire-safety
  checks: connect `ifc_element_filter` (walls) → `opening_surface` →
  `measurement` (surface area) via the `geometry_keys` output.
- Retrieve the opening geometry of roofs and slabs (skylights, shafts) for
  clash or clearance checks against other elements.

## Inputs

- **Express IDs** (required): a list of fully qualified element references
  (`<slug>:expr:<id>`) of host building elements (e.g. walls, slabs, roofs).
  Typically connected to the output of an `ifc_element_filter`. Each reference
  resolves against the model named inside it, so mixed-model lists are allowed.
  An unbound required input fails validation; an empty bound list processes
  zero elements.

## Outputs

The result is a flat list with one entry per opening:

- `opening_count`: number of openings found on the input elements
- `surface_count`: number of openings whose surfaces were retrieved into the
  geometry cache
- `geometry_keys`: the `gen:` geometry-cache keys of the retrieved opening
  surfaces, in opening order — bind directly to geometry consumers such as
  measurement or collision
- `openings`: ordered list of
  - `express_id` (the qualified opening reference), `guid` (GlobalId of the
    opening), `host_express_id` (the qualified host reference)
  - `geometry_key`: geometry-cache key of the retrieved cap faces
  - `area`: opening area in the plane of the host surface (the larger cap face;
    both caps are congruent for straight through-openings)
  - `width` / `height`: extents of the opening surfaces within the host plane
    (horizontal / vertical for wall openings)
  - `depth`: distance between the two cap faces along the host surface normal;
    `None` when the void exposes only one dominant flat face
  - `error`: reason when the surfaces could not be retrieved (e.g. "no cached
    geometry")

## Generated geometry

Each retrieved opening surface is cached as generated geometry under
`gen:opening_surface_<slug>_<express_id>`, where `<express_id>` is the opening
element's express ID. These are user-referencable `gen:` keys — valid geometry
cache keys for the measurement and collision nodes.

## Notes and limitations

- Only openings with a cached Body mesh are processed; openings without
  tessellated geometry are reported with an error entry instead.
- Each opening appears once, even when its host element is passed multiple
  times. References that resolve to no entity contribute no openings.
- The two-largest-opposing-surfaces heuristic matches openings whose cap faces
  dominate the void. Strongly tapered voids report the larger (outer) cap as
  `area`; niches whose back face rivals the cap (e.g. deep rectangular
  recesses) can pick up the back face as the second cap.
- Curved cap faces (e.g. arched openings) are grouped with a fixed ~1° normal
  tolerance, so the largest flat portion of the curve is retrieved.
- Openings are only collected from the input elements themselves, not from
  parts of decomposed elements.
