---
title: Measurement
description: Compute geometric measurements (volume, surface area, projected area, component height, minimum distance between elements, distance to reference) of IFC elements or cached geometries.
categories: Measurement
---

The `measurement` node computes geometric measurements of IFC elements or other cached geometries (e.g., intersection meshes from the collision node). Each measurement is reported per element with its reference, value, and any error. In v4, the node supports volume, surface area, projected area, component height, minimum distance between elements, and distance to reference computations.

## Use case example

- Compute the volume of all walls in a model
- Measure surface areas of elements for material estimation
- Measure the volume of collision intersection meshes to quantify overlap
- Measure the minimum distance between elements (e.g., to verify clearance between components)

## Settings

### Measurement type

The type of measurement to compute.

| Value | Label | When to use |
|-------|-------|-------------|
| `volume` | **Volume** | Compute the 3D volume of each element. Requires watertight geometry; non-watertight meshes are repaired or reported as errors. |
| `surface_area` | **Surface area** | Compute the total surface area of each element. Works on any mesh. |
| `projected_area` | **Projected area** | Compute the area of an element projected onto a plane perpendicular to the specified normal vector. Default normal [0,0,1] computes the footprint (top-down view). Works on any mesh. |
| `component_height` | **Component height** | Compute the extent of an element along a direction vector. Default direction [0,0,1] computes vertical height. Works on any mesh. |
| `distance_between` | **Minimum distance between elements** | Compute the minimal surface-to-surface distance between element pairs using the List A / List B pattern. See Notes for details. Works on any mesh. |
| `distance_to_reference` | **Distance to reference** | Compute the minimal distance from each element to a reference point or plane. See Notes for details. Works on any mesh. |

### Projection normal

Only used when **Measurement type** is `projected_area`. Specifies the normal vector of the projection plane.

- **Default**: `[0.0, 0.0, 1.0]` (XY plane, top-down footprint)
- **Format**: List of 3 floats `[x, y, z]`
- **Examples**:
  - `[0, 0, 1]` → Project onto XY plane (footprint)
  - `[1, 0, 0]` → Project onto YZ plane (side view)
  - `[0, 1, 0]` → Project onto XZ plane (front view)

### Direction

Only used when **Measurement type** is `component_height`. Specifies the direction vector for extent computation.

- **Default**: `[0.0, 0.0, 1.0]` (vertical height)
- **Format**: List of 3 floats `[x, y, z]`
- **Normalization**: The direction is normalized internally; only the direction matters, not the magnitude
- **Zero direction**: If the direction is zero-length (e.g., `[0.0, 0.0, 0.0]`), an error entry `undefined direction` is produced per element
- **Examples**:
  - `[0, 0, 1]` → Vertical height (Z extent)
  - `[1, 0, 0]` → Horizontal extent along X axis
  - `[0, 1, 0]` → Horizontal extent along Y axis

### Reference type

Only used when **Measurement type** is `distance_to_reference`. Specifies whether to compute distance to a point or a plane.

- **Default**: `point`
- **Format**: String enum: `"point"` | `"plane"`

### Reference point

Only used when **Measurement type** is `distance_to_reference`. Specifies the reference point for distance computation.

- **Default**: `[0.0, 0.0, 0.0]` (world origin)
- **Format**: List of 3 floats `[x, y, z]`
- **Usage**:
  - For `reference_type: point` → Distance computed to this point
  - For `reference_type: plane` → This point serves as the plane origin

### Reference normal

Only used when **Measurement type** is `distance_to_reference` and **Reference type** is `plane`. Specifies the normal vector of the reference plane.

- **Default**: `[0.0, 0.0, 1.0]` (XY plane, horizontal)
- **Format**: List of 3 floats `[x, y, z]`
- **Normalization**: The normal is normalized internally; only the direction matters, not the magnitude
- **Zero normal**: If the normal is zero-length (e.g., `[0.0, 0.0, 0.0]`), an error entry `undefined normal` is produced per element

## Inputs

- **List A** (optional): First list of element references. Accepts:
  - Express IDs (int → `ifc:<id>`)
  - Object IDs (str → `gen:<id>`)
  - Full geometry-cache keys (`ifc:`, `gen:`, `inter:`)
  - When empty, the whole model is used (all cached geometries)
  - **Dict input**: Also accepts a dict (e.g., the `intersection_meshes` output from the collision node). The dict's non-null values (intersection mesh cache keys) are used.
- **List B** (optional): Second list of element references (same format as List A). When empty, pairs are formed within List A (both directions). When non-empty, computes cartesian product A×B (one direction per pair). **Only used in `minimum distance between elements` mode; ignored in all other modes.**

## Outputs

- **Type**: The measurement type used (e.g., `volume`, `surface_area`, `projected_area`, `component_height`, `distance_between`, `distance_to_reference`)
- **Unit**: The unit of measurement (`volume_unit` for volume, `area_unit` for surface area and projected area, `length_unit` for component height, minimum distance between elements, and distance to reference, in model units)
- **Measurements**: List of measurements, each containing:
  - `reference`: The geometry cache key (e.g., `ifc:123`, `gen:abc`), or for `distance_between`: `<keyA>_<keyB>` (directional, **NOT** sorted)
  - `value`: The measured value (null if geometry missing or measurement failed)
  - `error`: Error reason if measurement failed (e.g., `no cached geometry`, `non-watertight`)

## Example Configuration

### Example 1: Volume of specific elements

**Settings:**
- Measurement type: `volume`

**Inputs:**
- List A: `[101, 102, 103]` (express IDs of three walls)

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
- List A: `[]` (empty = whole model)

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

### Example 3: Projected area (footprint)

**Settings:**
- Measurement type: `projected_area`
- Projection normal: `[0.0, 0.0, 1.0]` (top-down footprint)

**Inputs:**
- List A: `[101]` (express ID of a wall)

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

### Example 4: Component height (vertical)

**Settings:**
- Measurement type: `component_height`
- Direction: `[0.0, 0.0, 1.0]` (vertical height)

**Inputs:**
- List A: `[101]` (express ID of a wall)

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

### Example 5: Volume of collision intersection meshes

**Scenario:** A `collision` node (in `intersection_mesh` mode) produced intersection meshes. You want to measure the volume of each overlap.

**Settings:**
- Measurement type: `volume`

**Inputs:**
- List A: `{"ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2", "ifc:3__ifc:4": "inter:intersection_ifc:3_ifc:4"}`

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

### Example 6: Distance between two elements (both directions)

**Settings:**
- Measurement type: `distance_between`

**Inputs:**
- List A: `[101, 102]` (express IDs of two separated walls)
- List B: `[]` (empty → pairs within List A, both directions)

**Output:**
```json
{
  "type": "distance_between",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101_ifc:102", "value": 2.5, "error": null },
    { "reference": "ifc:102_ifc:101", "value": 2.5, "error": null }
  ]
}
```

### Example 7: Distance to reference point

**Settings:**
- Measurement type: `distance_to_reference`
- Reference type: `point`
- Reference point: `[0.0, 0.0, 0.0]` (world origin)

**Inputs:**
- List A: `[101, 102]`

**Output:**
```json
{
  "type": "distance_to_reference",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 5.2, "error": null },
    { "reference": "ifc:102", "value": 8.7, "error": null }
  ]
}
```

### Example 8: Error handling

**Settings:**
- Measurement type: `volume`

**Inputs:**
- List A: `[101, 999]` (999 has no cached geometry)

**Output:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.5, "error": null },
    { "reference": "ifc:999", "value": null, "error": "no cached geometry" }
  ]
}
```

Other error cases:
- `non-watertight: ...` — Volume computation failed due to non-repairable mesh
- `undefined normal` — Distance to reference with plane + zero-length normal
- `undefined direction` — Component height with zero-length direction

## Units

Measurements are reported in **model units** (the native units of the IFC model's geometry).

- **Volume**: reported in `volume_unit` (e.g., m³ for a meter-based model, mm³ for a millimeter-based model)
- **Area** (surface area and projected area): reported in `area_unit` (e.g., m² for a meter-based model, mm² for a millimeter-based model)
- **Distance** (component height, minimum distance between elements, distance to reference): reported in `length_unit` (e.g., m for a meter-based model, mm for a millimeter-based model)

## Notes

- **Watertight requirement**: Volume computation requires watertight geometry. The node attempts to repair non-watertight meshes automatically. If repair fails, the measurement is reported with an error. All other modes work on any mesh.
- **Distance between**: References follow `<keyA>_<keyB>` (directional, **NOT** sorted). With empty List B, each unordered pair is emitted in **both directions**. With non-empty List B, one direction per A×B pair. Intersecting pairs return `0.0` (detected via AABB + FCL collision). Only elements with tessellated Body geometry are measurable.
- **Distance to reference**: For `plane` mode, if the plane crosses the mesh (min ≤ 0 ≤ max over vertices), distance = 0. Zero normal (e.g. `[0.0, 0.0, 0.0]`) produces error `undefined normal`. Only elements with tessellated Body geometry are measurable.
- **Whole-model fallback**: When `List A` is empty, the node measures all cached geometries.
