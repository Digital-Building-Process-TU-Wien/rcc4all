---
title: Opening Surface IFC Generator
description: Builds a self-contained IFC4X3 model of watertight opening closed surfaces from the opening_surface node, placed into the source model's spatial structure.
categories: geometry
---

The `opening_surface_ifc_generator` node builds a self-contained IFC4X3 model in
which each opening closed surface retrieved by the `opening_surface` node becomes
one `IfcBuildingElementProxy`.

## How it works

For each opening, the cached volume mesh is resolved and its planar face groups
are flattened into polygonal faces of one `IfcPolygonalFaceSet` per group, written
as the Body of a single `IfcBuildingElementProxy`. Each opening is one element.

The project/site/building/storey skeleton is replicated from every source model,
and each proxy is contained in the new storey that mirrors the storey holding its
host element. The opening closed surface is written as an `IfcQuantityVolume` and
the opening area as an `IfcQuantityArea`.

## Inputs

- **Openings** (required): the opening results of the `opening_surface` node. Bind
  its `openings` output here. This must be bound to real geometry; an unbound
  required input fails the node.
- **Output filename** (settings): the name of the generated IFC file, written into
  the workflow output directory.

## Outputs

- `output_path`: absolute path of the generated IFC file
- `element_count`: number of generated proxies
- `storey_count`: number of building storeys replicated from the source model
- `elements`: ordered list with one entry per opening:
  - `opening_ref`: the source opening's qualified reference
  - `element_guid`: GlobalId of the generated proxy
  - `face_count`: number of polygonal faces written
  - `method`: how the source closed surface was derived
  - `volume`: the volume in cubic metres (`IfcQuantityVolume`)
  - `host_ref` / `storey_ref`: source host and storey references
  - `area`: the opening area (`IfcQuantityArea`)
  - `error`: reason when the proxy could not be generated

## Notes and limitations

- A proxy is generated for every opening that has cached geometry. Openings
  without geometry are reported with an error entry instead and count toward
  `element_count` only when they have an error.
- The proxy is written at the world origin; its geometry carries the absolute
  coordinates of the opening closed surface from the source model.
