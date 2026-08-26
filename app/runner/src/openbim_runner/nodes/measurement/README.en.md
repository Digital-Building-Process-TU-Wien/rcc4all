---
title: Measurement
description: Compute geometric measurements (volume, surface area, projected area, component height) of IFC elements or cached geometries.
categories: Measurement
---

The `measurement` node computes geometric measurements of IFC elements or other cached geometries (e.g., intersection meshes from the collision node). Each measurement is reported per element with its reference, value, and any error. In v2, the node supports volume, surface area, projected area, and component height computations.

## Use case example

- Compute the volume of all walls in a model
- Measure surface areas of elements for material estimation
- Measure the volume of collision intersection meshes to quantify overlap

## Settings

### Measurement type

The type of measurement to compute. In v2, `volume`, `surface_area`, `projected_area`, and `component_height` are implemented.

| Value | Label | When to use |
|-------|-------|-------------|
| `volume` | **Volume** | Compute the 3D volume of each element. Requires watertight geometry; non-watertight meshes are repaired or reported as errors. |
| `surface_area` | **Surface area** | Compute the total surface area of each element. Works on any mesh. |
| `projected_area` | **Projected area** | Compute the area of an element projected onto a plane perpendicular to the specified normal vector. Default normal [0,0,1] computes the footprint (top-down view). Works on any mesh. |
| `component_height` | **Component height** | Compute the extent of an element along a direction vector. Default direction [0,0,1] computes vertical height. Works on any mesh. |
| `distance_between` | **Distance between** | (Coming soon) Compute the minimal distance between pairs of elements. |
| `distance_to_reference` | **Distance to reference** | (Coming soon) Compute the distance from elements to a reference point or plane. |

### Projection normal (v2+)

Only used when **Measurement type** is `projected_area`. Specifies the normal vector of the projection plane.

- **Default**: `[0.0, 0.0, 1.0]` (XY plane, top-down footprint)
- **Format**: List of 3 floats `[x, y, z]`
- **Examples**:
  - `[0, 0, 1]` → Project onto XY plane (footprint)
  - `[1, 0, 0]` → Project onto YZ plane (side view)
  - `[0, 1, 0]` → Project onto XZ plane (front view)

### Direction (v2+)

Only used when **Measurement type** is `component_height`. Specifies the direction vector for extent computation.

- **Default**: `[0.0, 0.0, 1.0]` (vertical height)
- **Format**: List of 3 floats `[x, y, z]`
- **Normalization**: The direction is normalized internally; only the direction matters, not the magnitude
- **Examples**:
  - `[0, 0, 1]` → Vertical height (Z extent)
  - `[1, 0, 0]` → Horizontal extent along X axis
  - `[0, 1, 0]` → Horizontal extent along Y axis
  - `[1, 1, 0]` → Extent along diagonal direction (normalized internally)

## Inputs

- **Elements** (optional): List of element references to measure. Accepts:
  - Express IDs (int → `ifc:<id>`)
  - Object IDs (str → `gen:<id>`)
  - Full geometry-cache keys (`ifc:`, `gen:`, `inter:`) — useful for measuring intersection meshes from collision
  - When empty, the whole model is used (all cached geometries)
  - **Dict input**: Also accepts a dict (e.g., the `intersection_meshes` output from the collision node). In this case, the dict's non-null values (intersection mesh cache keys like `inter:...`) are measured; null entries (FCL-decided collisions without stored geometry) are skipped.

## Outputs

- **Type**: The measurement type used (e.g., `volume`, `surface_area`, `projected_area`, `component_height`)
- **Unit**: The unit of measurement (`volume_unit` for volume, `area_unit` for surface area and projected area, `length_unit` for component height, in model units)
- **Measurements**: List of per-element measurements, each containing:
  - `reference`: The geometry cache key (e.g., `ifc:123`, `gen:abc`)
  - `value`: The measured value (null if geometry missing or measurement failed)
  - `error`: Error reason if measurement failed (e.g., `no cached geometry`, `non-watertight`)

## Example Configuration

### Example 1: Volume of specific elements

**Settings:**
- Measurement type: `volume`

**Inputs:**
- Elements: `[101, 102, 103]` (express IDs of three walls)

**Output:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.5, "error": null },
    { "reference": "ifc:102", "value": 3.1, "error": null },
    { "reference": "ifc:103", "value": 1.8, "error": null }
  ]
}
```

### Example 2: Surface area of whole model

**Settings:**
- Measurement type: `surface_area`

**Inputs:**
- Elements: `[]` (empty = whole model)

**Output:**
```json
{
  "type": "surface_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:1", "value": 45.2, "error": null },
    { "reference": "ifc:2", "value": 12.8, "error": null },
    ...
  ]
}
```

### Example 3: Projected area (footprint) of a wall

**Settings:**
- Measurement type: `projected_area`
- Projection normal: `[0.0, 0.0, 1.0]` (default, top-down view)

**Inputs:**
- Elements: `[101]` (express ID of a wall)

**Output:**
```json
{
  "type": "projected_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 3.5, "error": null }
  ]
}
```

### Example 4: Projected area with custom normal (side view)

**Settings:**
- Measurement type: `projected_area`
- Projection normal: `[1.0, 0.0, 0.0]` (project onto YZ plane)

**Inputs:**
- Elements: `[101]` (express ID of a wall)

**Output:**
```json
{
  "type": "projected_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 8.2, "error": null }
  ]
}
```

### Example 5: Volume of collision intersection meshes

**Scenario:** A `collision` node (in `intersection_mesh` mode) produced intersection meshes. You want to measure the volume of each overlap by connecting its `intersection_meshes` output directly to the `elements` input.

**Settings:**
- Measurement type: `volume`

**Inputs:**
- Elements: `{"ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2", "ifc:3__ifc:4": "inter:intersection_ifc:3_ifc:4", "ifc:5__ifc:6": null}`

**Output:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "inter:intersection_ifc:1_ifc:2", "value": 0.05, "error": null },
    { "reference": "inter:intersection_ifc:3_ifc:4", "value": 0.12, "error": null }
  ]
}
```

Note: The null entry (`ifc:5__ifc:6`) is skipped because no intersection mesh was stored for that collision pair.

### Example 6: Missing geometry handled gracefully

**Settings:**
- Measurement type: `volume`

**Inputs:**
- Elements: `[101, 999]` (999 has no cached geometry)

**Output:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.5, "error": null },
    { "reference": "999", "value": null, "error": "no cached geometry" }
  ]
}
```

### Example 7: Non-watertight mesh volume error

**Settings:**
- Measurement type: `volume`

**Inputs:**
- Elements: `["gen:broken_mesh"]` (a non-repairable mesh)

**Output:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "gen:broken_mesh", "value": null, "error": "non-watertight: ..." }
  ]
}
```

Note: `surface_area` mode still works on non-watertight meshes.

### Example 8: Component height (vertical) of a wall

**Settings:**
- Measurement type: `component_height`
- Direction: `[0.0, 0.0, 1.0]` (default, vertical height)

**Inputs:**
- Elements: `[101]` (express ID of a wall)

**Output:**
```json
{
  "type": "component_height",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.8, "error": null }
  ]
}
```

### Example 9: Component height with custom direction

**Settings:**
- Measurement type: `component_height`
- Direction: `[1.0, 0.0, 0.0]` (extent along X axis)

**Inputs:**
- Elements: `[101]` (express ID of a wall)

**Output:**
```json
{
  "type": "component_height",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 0.3, "error": null }
  ]
}
```

## Units

Measurements are reported in **model units** (the native units of the IFC model's geometry). If the IFC model uses meters:
- Volume is in m³
- Surface area is in m²

If the model uses millimeters:
- Volume is in mm³
- Surface area is in mm²

## Notes

- **Watertight requirement for volume**: Volume computation requires watertight geometry. The node attempts to repair non-watertight meshes automatically. If repair fails, the measurement is reported with an error.
- **Surface area works on any mesh**: Surface area is computed from the mesh triangles and does not require watertight geometry.
- **Projected area works on any mesh**: Like surface area, projected area computation works on any mesh regardless of watertightness.
- **Component height works on any mesh**: Extent is computed from vertex projections and does not require watertight geometry.
- **Whole-model fallback**: When `elements` is empty, the node measures all cached geometries (IFC elements and generated geometries).
- **Future modes**: The `distance_between` and `distance_to_reference` modes are planned for future releases. Selecting them will raise an error in v2.
