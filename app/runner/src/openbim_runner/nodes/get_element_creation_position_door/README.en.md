---
title: Get Element Creation Position Door
description: Retrieves footprint points (P1-P7) of IFC door openings for element creation.
categories: IFC, Geometry
---

The `get_element_creation_position_door` node extracts footprint points from the footprint of IFC door openings. It uses each opening's `ObjectPlacement` to calculate world coordinates at bottom elevation.

## The 7 Points

```
     Front
     ┌───────────┬───────────┐
    P1           P5          P2
     │           │           │
     │   ╲       │       ╱   │
     │     ╲     │     ╱     │
     │       ╲   │   ╱       │
     │         ╲ │ ╱         │
     │     P7  ● │           │  ← Center (Centroid)
     │         ╱ │ ╲         │
     │       ╱   │   ╲       │
     │     ╱     │     ╲     │
     │   ╱       │       ╲   │
     │           │           │
    P4           P6          P3
     └───────────┴───────────┘
     Back
```

**Notes:**
- P1-P4: 4 corner points (clockwise sorted, starting from corner closest to placement location)
- P5: Midpoint between P1 and P2
- P6: Midpoint between P3 and P4
- P7: Centroid (geometric center)
- P1-P6 require at least 4 bottom vertices
- For openings with 3 bottom vertices, only P7 is calculated
- For >4 bottom vertices: OBB-based (Oriented Bounding Box) corner finding
```

## Settings

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `point_index` | `1-7` | `7` | Which footprint point to return: 1-4 = corners (clockwise), 5-6 = midpoints, 7 = center point. P1-P6 require at least 4 bottom vertices. |

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[str]` | List of IFC door references in format `<slug>:expr:<id>` (e.g. `main:expr:18334`). All IDs in the list are processed. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `elements` | `list[ElementPositionResult]` | List of door positions. One entry per processed door. |

## ElementPositionResult Structure

| Name | Type | Description |
|------|------|-------------|
| `element_type` | `str` | The IFC entity type (IfcDoor). |
| `express_id` | `str` | The qualified element reference (`<slug>:expr:<id>`). |
| `point_index` | `int` | Which point was returned (1-7). P1-P6 require at least 4 bottom vertices. |
| `position` | `list[float]` | World coordinates `[x, y, z]` in meters at bottom elevation (rounded to 3 decimals). |
| `rotation` | `ElementRotation \| None` | Euler rotation angles (X°, Y°, Z°) in degrees (0-360). None if placement not available. |

## ElementRotation Structure

| Name | Type | Description |
|------|------|-------------|
| `rotation_x` | `float` | Rotation around global X-axis in degrees (0-360). |
| `rotation_y` | `float` | Rotation around global Y-axis in degrees (0-360). |
| `rotation_z` | `float` | Rotation around global Z-axis in degrees (0-360). |

## Example

### Single Door (P7)

Input:
```json
{
  "settings": {
    "point_index": 7
  },
  "inputs": {
    "express_ids": ["main:expr:18334"]
  }
}
```

Output:
```json
{
  "elements": [
    {
      "element_type": "IfcDoor",
      "express_id": "main:expr:18334",
      "point_index": 7,
      "position": [0.906, 0.0, 0.0],
      "rotation": {
        "rotation_x": 0.0,
        "rotation_y": 0.0,
        "rotation_z": 90.0
      }
    }
  ]
}
```

## Algorithm

1. Load each `IfcDoor` entity by express ID and find the associated `IfcOpeningElement` via `IfcRelFillsElement` relation
2. Find associated wall via `IfcRelVoidsElement` relation (for thickness detection)
3. Tessellate 3D geometry of the opening and extract bottom vertices (minimum Z elevation)
4. For 4+ bottom vertices: Transform vertices to local coordinate system, use Centroid-Y as front/back separator, assign P1-P4 via X-min/max, calculate P5-P6 midpoints and P7 centroid, transform back to world coordinates
5. For >4 bottom vertices: Calculate OBB (Oriented Bounding Box) and determine 4 extreme corners via min/max
6. Thickness Detection: Compare opening and wall thickness, clip opening vertices to wall bounds (>1% tolerance, placement-aligned)
7. For <4 bottom vertices: Only calculate P7 (centroid)
8. Rotation: Calculate full placement matrix from `ObjectPlacement`, extract Euler angles (X, Y, Z) and store in result
9. Return requested point

## Notes

- All express IDs in the input list are processed
- Invalid express IDs are silently skipped
- Non-IfcDoor entity types are silently skipped
- Doors without associated openings are silently skipped
- **P1-P6:** Require at least 4 bottom vertices
- **P7:** Available for all openings (including those with 3 bottom vertices)
- The algorithm supports IFC2x3 and IFC4 schemas
- Full 3D rotation is supported via placement matrix calculation
- Corner points are sorted clockwise (starting from corner closest to placement location)
- **Thickness Detection:** Openings thicker than the wall (>1% tolerance) are automatically clipped to wall thickness
- **Clipping Method:** Placement-aligned (oriented to wall placement, not symmetric)
- Rotation is only calculated if `ObjectPlacement` is available
- `express_id` format: `<slug>:expr:<id>` (e.g. `main:expr:18334`)
- Position coordinates are rounded to 3 decimals (millimeter precision)
