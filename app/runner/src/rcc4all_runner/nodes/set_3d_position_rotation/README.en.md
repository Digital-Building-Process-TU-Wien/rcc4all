---
title: Set 3D Position & Rotation
description: Define a 3D position and rotation via UI settings.
categories: 3D operation
---

The `set_3d_position_rotation` node allows users to manually define a 3D position and Euler rotation through the UI.

## Settings

| Name | Type | Description |
|------|------|-------------|
| `position` | `list[float]` | Position as `[x, y, z]` coordinates in meters. Default: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation around X, Y, Z axes in degrees (Euler angles). Default: `[0.0, 0.0, 0.0]` |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `elements` | `list[ElementResult]` | List with one element containing position and rotation values. The `express_id` field is empty (no IFC element reference). |

## Example

```json
{
  "settings": {
    "position": [5.0, 3.0, 0.0],
    "rotation": [0.0, 0.0, 45.0]
  }
}
```

This creates a single element at position (5, 3, 0) with a 45-degree rotation around the Z-axis.

## Notes

- Position coordinates are in **meters**
- Rotation follows the **right-hand rule** (X, Y, Z in degrees): positive rotation is counter-clockwise when looking along the axis
- The output `express_id` is always empty since this node does not reference an IFC element
