---
title: Tilt of Components
description: Measures the tilt of building components (walls/slabs as 2D surfaces, columns/beams as 1D axes) and flags components whose tilt violates the configured comparison threshold.
categories: geometry
---

The `tilt_of_components` node measures the tilt of IFC building components relative
to the horizontal plane and flags components that fall outside a configured limit.
The tilt value always represents the **smaller angle between the component's
dominant surface/axis and the horizontal plane**: a vertical wall or column
measures `90°`, a horizontal slab or beam measures `0°`.

An **element category** selector decides which algorithm is used for every input
element:

- **2D (walls & slabs):** the mesh triangles are grouped into surfaces by their
  normal vectors. The two largest surfaces (front/back) are measured. Each
  surface's tilt is the average angle of its triangle normals against the
  horizontal plane (complemented to stay under `90°`).
- **1D (columns & beams):** the mesh triangles are grouped into surfaces. The
  area-weighted centroid of each surface is computed, the two centroids furthest
  apart define the element's longitudinal axis, and the axis's deviation from the
  horizontal plane is measured.

## Use case example

- Check whether all walls in a model are vertical (2D category, "greater than
  lower limit" with lower limit `89°`).
- Check whether all columns are plumb (1D category).
- Verify that beams are horizontal rather than sagging.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Element category | `2d` / `1d` | `2d` | `2d` measures walls & slabs (two largest surfaces); `1d` measures columns & beams (longitudinal axis). |
| Comparison method | enum | `greater_than_lower` | How the measured tilt is checked against the limits (see below). |
| Lower limit (°) | `number` | `0` | Tilt is flagged when it is greater than this value (method `greater_than_lower`). |
| Upper limit (°) | `number` | `90` | Tilt is flagged when it is below this value (method `less_than_upper`). |
| Interval lower (°) | `number` | `0` | Lower barrier for the interval methods. |
| Interval upper (°) | `number` | `90` | Upper barrier for the interval methods. |
| Horizontal separation angle (°) | `number` | `5` | Maximum horizontal angle deviation between two triangles to still count as the same surface (merges facets of curved/round objects). |
| Tolerance (°) | `number` | `0.1` | Shared tolerance added to/subtracted from the limits when flagging. |

### Comparison methods

| Value | Flags when |
|-------|-----------|
| `greater_than_lower` | `tilt > lower_limit + tolerance` |
| `less_than_upper` | `tilt < upper_limit - tolerance` |
| `inside_interval` | `interval_lower - tolerance < tilt < interval_upper + tolerance` |
| `outside_interval` | `tilt < interval_lower - tolerance` or `tilt > interval_upper + tolerance` |

A single interval pair is reused by both interval methods because only one
comparison method is active at a time.

## Inputs

- **Express IDs** (optional): List of IFC express IDs to measure. Typically
  connected to the output of an `ifc_element_filter`. When unconnected, all IFC
  elements in the model are checked.

## Outputs

The result is a slim, structured check per element:

- `element_count`: number of elements processed
- `check_count`: number of elements with at least one surface/axis check (elements
  without tessellated geometry are skipped and not counted)
- `failed_count`: number of elements with at least one flagged surface/axis
- `model_name`: name of the checked IFC model (taken from the IFC header file name)
- `elements`: ordered list of
  - `express_id`, `class_name` (IFC class or `unknown`), `element_category`
  - `failed`: true when at least one check was flagged
  - `checks`: list of `TiltSurfaceCheck`:
    - `expected`: human-readable pass condition combined from the comparison
      method and limits (e.g. "less than or equal to X")
    - `tilt_angle` (°), `passed`
    - `geometry_key`: geometry-cache key of the helper geometry for flagged checks

A 2D element yields up to two checks (front/back surfaces); a 1D element yields
one check (its axis). The `check_count` and `failed_count` totals count elements,
not individual checks.

## Helper geometry

Flagged checks store a helper geometry in the geometry cache for visualization:

- 2D: the flagged surface triangles under `inter:tilt_surface_{express_id}_{surface_index}`
- 1D: a thin axis cylinder under `inter:tilt_axis_{express_id}`

These are `inter:` keys, so they are excluded from collision inputs and the
whole-model fallback.

## Notes on openings

For walls containing window/door openings, the opening void is already subtracted
from the wall mesh, so the two-largest-surfaces approach still identifies the
correct front/back faces. Dedicated openings (`IfcRelVoidsElement`) handling is
not implemented in this version.

## Composite / decomposed elements

Some models express a composite element (e.g. a multi-layer wall) as an element
decomposed via `IfcRelAggregates` into `IfcBuildingElementPart` sub-elements, each
with its own Body geometry. When such an element has no own tessellated `Body`
mesh, its tilt is measured as a whole by combining the geometry of all its parts
(recursively through the aggregation). The parts themselves remain listed and
measured independently, so a whole wall and its layers both appear in the result.
