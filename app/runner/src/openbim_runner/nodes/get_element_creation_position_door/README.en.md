---
title: Get Element Creation Position Door
description: Retrieves footprint points (P1-P7) of IFC door openings at bottom elevation. Automatically handles edge case when openings are thicker than the wall.
categories: IFC, Geometry
---

The `get_element_creation_position_door` node extracts footprint points from the footprint of IFC door openings. It uses each opening's `ObjectPlacement` to calculate world coordinates at bottom elevation.

**New in v2.0:** Automatic detection and correction when door openings are modeled thicker than the adjacent wall (via `IfcRelVoidsElement`).

## The 7 Points

```
     Front
     ┌───────┬───────┐
    P1      P2      P3
     │   P6  │  P5   │
     │       P7      │
     │       ●       │  ← Center (Centroid)
     │       │       │
    P4      P5      P6
     └───────┴───────┘
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

## Settings

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `point_index` | `1-7` | `7` | Which footprint point to return: 1-4 = corners (clockwise), 5-6 = midpoints, 7 = center point. P1-P6 require at least 4 bottom vertices. |

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[int]` | List of IFC door express IDs (IfcDoor). All IDs in the list are processed. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `elements` | `list[ElementPositionResult]` | List of door positions. One entry per processed door. |

## ElementPositionResult Structure

| Name | Type | Description |
|------|------|-------------|
| `element_type` | `str` | The IFC entity type (IfcDoor). |
| `express_id` | `int` | The express ID of the processed door. |
| `point_index` | `int` | Which point was returned (1-7). P1-P6 require at least 4 bottom vertices. |
| `position` | `list[float]` | World coordinates `[x, y, z]` in meters at bottom elevation. |

## Example

### Single Door (P7)

Input:
```json
{
  "settings": {
    "point_index": 7
  },
  "inputs": {
    "express_ids": [18334]
  }
}
```

Output:
```json
{
  "elements": [
    {
      "element_type": "IfcDoor",
      "express_id": 18334,
      "point_index": 7,
      "position": [0.906, 0.0, 0.0]
    }
  ]
}
```

## Algorithm

1. Load each `IfcDoor` entity by express ID from the input list
2. For each door, find the associated `IfcOpeningElement` via `IfcRelFillsElement` relation
3. Find associated wall via `IfcRelVoidsElement` relation (for thickness detection)
4. Tessellate 3D geometry of the opening
5. Find bottom vertices (all vertices at minimum Z elevation)
6. For 4+ bottom vertices:
   - Extract local axes from `ObjectPlacement.RelativePlacement`
   - Transform vertices to local coordinate system
   - Sort clockwise (starting from corner closest to placement location)
   - P1-P4 = 4 corners, P5-P6 = midpoints, P7 = centroid
   - Transform back to world coordinates
7. For >4 bottom vertices:
   - Calculate OBB (Oriented Bounding Box) in local coordinate system
   - Determine 4 extreme corners via min/max on local axes
   - P1-P4 = OBB corners, P5-P6 = midpoints, P7 = centroid of all vertices
8. **Thickness Detection (new in v2.0):**
   - Calculate opening thickness (extent on local Y-axis)
   - Calculate wall thickness (via `IfcRelVoidsElement`)
   - If `opening_thickness > wall_thickness * 1.01` (>1% tolerance):
     - Clip opening vertices to wall bounds (placement-aligned)
     - Use clipped vertices for footprint calculation
9. For <4 bottom vertices:
   - Only P7 (centroid) is calculated
10. Return requested point

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
