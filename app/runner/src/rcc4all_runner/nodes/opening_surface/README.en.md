---
title: Opening Surface
description: Retrieves a watertight closed surface per opening and caches it as generated geometry.
categories: geometry
---

The `opening_surface` node retrieves, for every opening of the input
elements, one **watertight closed surface** that fills the opening void. It
either combines the cap faces with the cut surfaces when they form a closed
ring (windows), or linearly connects the opening's cap faces when the cut
surfaces form an open ring (doors), so both end up as a closed, positive-volume
solid.

## How it works

For each input element, the openings (`IfcRelVoidsElement`) and their cached Body
meshes are resolved, along with the host element's mesh. Then:

- **Closed ring (window, planar rims):** the cut surfaces are closed into a
  closed ring. When it can be closed watertight on the open sides, it is emitted
  unchanged (`method = "closed_cut_surface"`).
- **Open ring (door / non-planar rim / curved host):** the cut-surface ring
  stays open. The opening's cap faces are analysed from the host surface planes
  instead. When **two** caps are found, both are used; when **only one** cap is
  found, a second cap is synthesised by copying the found cap across the wall
  thickness and clipping the copy against the ring's reveal faces. The two caps
  are then **connected** (by new side faces between corresponding boundary
  points in 3D) and form a watertight volume (`method = "lofted_caps"`).
- **No volume:** when neither a closed ring nor two connectable caps can be
  built, the cap/ring geometry is emitted unchanged (`method = "caps_only"`,
  `watertight = false`); no fabricated geometry is produced.

The connection links corresponding boundary points in 3D, so it tolerates hosts
whose two dominant surfaces are not parallel (a wall or slab of linearly varying
thickness) and curved hosts.

## Use case example

- Cross-section / fire-compartment checks: extract the closed volume of a door,
  window or shaft so it can be measured and compared against the host element.
- Clash or clearance checks against the actual void an opening cuts in a wall,
  slab or roof.

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
- `surface_count`: number of openings whose closed surface was retrieved into the
  geometry cache
- `geometry_keys`: the `gen:` geometry-cache keys of the retrieved opening
  closed surfaces, in opening order
- `openings`: ordered list of
  - `express_id` (the qualified opening reference), `guid` (GlobalId of the
    opening), `host_express_id` (the qualified host reference)
  - `geometry_key`: geometry-cache key of the retrieved opening closed surface
  - `method`: `"closed_cut_surface"`, `"lofted_caps"` or `"caps_only"`
  - `watertight`: whether the emitted geometry is a closed, winding-consistent,
    positive-volume solid
  - `area` / `width` / `height`: opening extent in the plane of the host surface
    (the larger cap face)
  - `depth`: distance between the two cap faces along the host surface normal
  - `error`: reason when the closed surface could not be retrieved

## Generated geometry

Each retrieved opening closed surface is cached as generated geometry under
`gen:opening_surface_<slug>_<express_id>`. The cached mesh is a watertight solid
when `watertight` is true; a `caps_only` entry is the cap geometry unchanged. The
keys are user-referencable `gen:` keys, so they can be bound to geometry
consumers such as measurement or collision.

## Notes and limitations

- Only openings with a cached Body mesh are processed; openings without
  tessellated geometry are reported with an error entry instead.
- Each opening appears once, even when its host element is passed multiple
  times. References that resolve to no entity contribute no openings.
- Curved hosts are analysed with surface-region logic; a round wall that exposes
  only one cap gets its opposing cap synthesised.
- Openings are only collected from the input elements themselves, not from parts
  of decomposed elements.
