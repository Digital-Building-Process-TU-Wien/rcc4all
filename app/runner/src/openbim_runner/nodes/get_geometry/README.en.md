---
title: Get Geometry
description: Tessellate IFC element body geometry in worldspace and return cache handles.
categories: geometry,ifc
---

The `get_geometry` node reads IFC entities by express ID, tessellates their body representation in worldspace coordinates, and returns geometry handles referencing meshes stored in the workflow-scoped geometry cache.

Use this node to prepare geometry for collision detection or other geometric operations. Typically follows an `ifc_element_filter` that provides express IDs.

## Settings

- **Fail on missing**: When enabled, raises an error if an express ID does not exist in the model or an element has no body geometry representation. When disabled, missing elements are skipped.

## Notes

- Geometry is cached in-process for the duration of the workflow run. The returned handles carry a cache key and the source express ID.
- Vertices are welded at tessellation time to improve watertightness.
