---
title: Generate 3D Cube
description: Create a 3D cube geometry with customizable size, position, and rotation for clash detection.
categories: 3D operation,
---

The `generate_3d_cube` node creates a 3D box geometry with configurable dimensions, position, and rotation, and stores it in the geometry cache under a user-supplied `object_id`. The object ID is the address used to reference the cube later, e.g. in a `collision` node.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `position` | `list[float]` | Position of the cube center as `[x, y, z]` coordinates. Default: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation around X, Y, Z axes in degrees (Euler angles). Default: `[0.0, 0.0, 0.0]` |
| `size` | `list[float]` | Dimensions of the cube as `[width, height, depth]`. Default: `[1.0, 1.0, 1.0]` |
| `object_id` | `string` | Unique identifier for the generated cube (required). Duplicates are rejected. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `object_ids` | `list[string]` | 1-element list with the cube's `object_id`. Feed this into a `collision` node's object-ID input. |

## Example

```json
{
  "position": [5.0, 3.0, 0.0],
  "rotation": [0.0, 0.0, 45.0],
  "size": [2.0, 2.0, 2.0],
  "object_id": "box_a"
}
```

This creates a 2×2×2 cube centered at (5, 3, 0), rotated 45 degrees around the Z-axis, cached under the object ID `box_a`.

## Notes

- The cube is created centered at the origin first, then rotated and translated
- All size dimensions must be positive (greater than 0)
- Rotation follows the right-hand rule
- `object_id` must be non-empty and unique within a run; reusing one raises an error
