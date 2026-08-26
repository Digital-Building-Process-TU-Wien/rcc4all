---
title: Measurement
description: Compute geometric measurements (volume, surface area, projected area, component height) of IFC elements or cached geometries.
categories: Measurement
---

The `measurement` node computes geometric measurements of IFC elements or other cached geometries (e.g., intersection meshes from the collision node). Each measurement is reported per element with its reference, value, and any error. In v3, the node supports volume, surface area, projected area, component height, and distance between computations.

## Use case example

- Compute the volume of all walls in a model
- Measure surface areas of elements for material estimation
- Measure the volume of collision intersection meshes to quantify overlap

## Settings

### Measurement type

The type of measurement to compute. In v3, `volume`, `surface_area`, `projected_area`, `component_height`, and `distance_between` are implemented.

| Value | Label | When to use |
|-------|-------|-------------|
| `volume` | **Volume** | Compute the 3D volume of each element. Requires watertight geometry; non-watertight meshes are repaired or reported as errors. |
| `surface_area` | **Surface area** | Compute the total surface area of each element. Works on any mesh. |
| `projected_area` | **Projected area** | Compute the area of an element projected onto a plane perpendicular to the specified normal vector. Default normal [0,0,1] computes the footprint (top-down view). Works on any mesh. |
| `component_height` | **Component height** | Compute the extent of an element along a direction vector. Default direction [0,0,1] computes vertical height. Works on any mesh. |
| `distance_between` | **Distance between** | Compute the minimal surface-to-surface distance between element pairs using the List A / List B pattern. **List B empty:** all unordered pairs within List A (n choose 2), each emitted in **both directions**. **List B non-empty:** cartesian product A×B (skip self-pairs), one direction per pair. Reference format: `dist:distance_<keyA>_<keyB>` (directional, **NOT** sorted). Works on any mesh. **Intersecting pairs return `0.0`** (detected via AABB + FCL triangle-triangle collision before distance query). **Note:** Only elements with tessellated Body geometry are measurable. Parametric elements like alignments (IfcAlignment) without Body representations will produce error entries. |
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

- **List A** (optional): First list of element references. Accepts:
  - Express IDs (int → `ifc:<id>`)
  - Object IDs (str → `gen:<id>`)
  - Full geometry-cache keys (`ifc:`, `gen:`, `inter:`)
  - When empty, the whole model is used (all cached geometries)
  - **Dict input**: Also accepts a dict (e.g., the `intersection_meshes` output from the collision node). The dict's non-null values (intersection mesh cache keys) are used.
- **List B** (optional): Second list of element references (same format as List A). When empty, pairs are formed within List A (both directions). When non-empty, computes cartesian product A×B (one direction per pair).

## Outputs

- **Type**: The measurement type used (e.g., `volume`, `surface_area`, `projected_area`, `component_height`, `distance_between`)
- **Unit**: The unit of measurement (`volume_unit` for volume, `area_unit` for surface area and projected area, `length_unit` for component height and distance between, in model units)
- **Measurements**: List of measurements, each containing:
  - `reference`: The geometry cache key (e.g., `ifc:123`, `gen:abc`), or for `distance_between`: `dist:distance_<keyA>_<keyB>` (directional, NOT sorted)
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

### Example 10: Distance between two elements

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
    { "reference": "dist:distance_ifc:101_ifc:102", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:101", "value": 2.5, "error": null }
  ]
}
```

Note: For empty List B, each unordered pair is emitted in both directions.

### Example 11: Distance between multiple elements (all pairs, both directions)

**Settings:**
- Measurement type: `distance_between`

**Inputs:**
- List A: `[101, 102, 103]` (express IDs of three elements)
- List B: `[]` (empty → pairs within List A, both directions)

**Output:**
```json
{
  "type": "distance_between",
  "unit": "length_unit",
  "measurements": [
    { "reference": "dist:distance_ifc:101_ifc:102", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:101", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:101_ifc:103", "value": 5.1, "error": null },
    { "reference": "dist:distance_ifc:103_ifc:101", "value": 5.1, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:103", "value": 3.2, "error": null },
    { "reference": "dist:distance_ifc:103_ifc:102", "value": 3.2, "error": null }
  ]
}
```

Note: For n elements with empty List B, the node computes all n choose 2 unordered pairs (3 pairs for 3 elements) and emits each in both directions (6 measurements total).

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
- **Distance between works on any mesh**: Minimal surface-to-surface distance is computed using BVH-based nearest-point queries. Intersecting pairs are detected first via AABB + FCL triangle-triangle collision and return `0.0` immediately. Works on any mesh (convex or non-convex).
- **Distance between pair format**: References follow the format `dist:distance_<keyA>_<keyB>` (directional, **NOT** sorted). With empty List B, each unordered pair is emitted in **both directions**. With non-empty List B, one direction per A×B pair.
- **Distance between missing geometry**: Pairs involving elements without cached geometry produce error entries (`value=null`, `error='no cached geometry'`). With empty List B, error entries are emitted in both directions.
- **Distance between limitation**: Only elements with tessellated Body geometry can be measured. Parametric elements like alignments (`IfcAlignment`) without Body representations will produce error entries when paired with other elements.
- **Distance between intersecting elements**: When two meshes intersect (overlap in volume or surfaces cross), the distance is `0.0`. Intersection is detected via AABB + FCL triangle-triangle collision before the distance query, ensuring accurate results even when no vertex lies inside the other mesh.
- **Whole-model fallback**: When `List A` is empty, the node measures all cached geometries, computing all pairwise distances for `distance_between` mode (empty List B → both directions for each pair).
- **Future modes**: The `distance_to_reference` mode is planned for future releases. Selecting it will raise an error in v3.
