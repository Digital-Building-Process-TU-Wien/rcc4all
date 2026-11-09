---
title: Opening Surface IFC Generator
description: Builds a self-contained IFC4X3 model of opening-surface cap faces from the opening_surface node, placed into the source model's spatial structure.
categories: geometry
---

The `opening_surface_ifc_generator` node writes a fresh IFC4X3 model from the
opening surfaces retrieved by the `opening_surface` node. Each of an opening's
cap faces (front and back) is emitted as an independent polygonal face set on
its own `IfcBuildingElementProxy`, together with an `IfcQuantityArea` carrying
the opening area. The generated model replicates the project/site/building/
storey hierarchy of the source model and contains every proxy in the storey
that holds its host element.

## How it works

- Takes the `openings` output of an `opening_surface` node (does not tessellate
  on demand — it reads the `gen:` geometry from the workflow cache).
- **Each cached cap mesh already contains both cap faces of a through-opening.**
  For every opening it splits the mesh into its cap-face groups (front + back,
  or a single group for a recess), flattens each group into the plane of the
  host surface, and snaps its outline (outer boundary and any holes) into
  `IfcIndexedPolygonalFaceSet` geometry.
- Creates one `IfcBuildingElementProxy` per cap face, named `OpeningSurface_0`
  (larger cap) and `OpeningSurface_1` (its opposing cap), each placed at the
  world origin (the cached cap geometry is already in world coordinates) and
  assigned a quantity set `OpeningSurfaceQuantities` with `IfcQuantityArea`
  `OpeningArea`.
- Copies the source model's spatial skeleton into the new file
  (`IfcProject` → `IfcSite` → `IfcBuilding` → `IfcBuildingStorey`) including
  the placement chain, and creates `IfcRelContainedInSpatialStructure` links
  from each proxy to the storey containing its host.

## Inputs

- **Openings** (required): the `openings` output of the `opening_surface` node.
  An unbound input fails validation; an empty list raises a node error.

## Settings

- **Output filename** (default `opening_surface_model.ifc`): the generated
  file. It is written into the workflow output directory (the folder containing
  the workflow file).

## Outputs

- `output_path`: absolute path of the generated IFC file
- `element_count`: number of generated `IfcBuildingElementProxy` elements
- `storey_count`: number of replicated `IfcBuildingStorey` elements
- `elements`: ordered list, one entry per generated proxy (two per
  through-opening, one per recess), with `opening_ref`, `element_guid`, `cap`
  (0 = larger cap, 1 = opposing), `host_ref`, `storey_ref`, `area` and `error`.

## Notes and limitations

- Only openings with a cached cap-face mesh are emitted; openings without
  geometry are reported with an `error` entry and no element.
- Only the opening-surface cap-face geometry is generated. The light prisms
  (clear-view / light-incidence) are omitted because the required angles and
  distances are not available from the `opening_surface` node.
- Property sets are not created; only the `OpeningArea` quantity set is added.
- A host element that is not contained in any building storey yields a proxy
  without a spatial containment link (`storey_ref = None`).
