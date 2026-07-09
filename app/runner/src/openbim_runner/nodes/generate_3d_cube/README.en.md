---
title: Generate 3D Cube
description: Create a 3D cube geometry with customizable size, position, and rotation for clash detection.
categories: 3D operation,
---

The `generate_3d_cube` node creates a 3D box geometry with configurable dimensions, position, and rotation. The output is a geometry handle referencing a cached trimesh mesh that can be used for collision detection, visualization, or further geometric operations.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `position` | `list[float]` | Position of the cube center as `[x, y, z]` coordinates. Default: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation around X, Y, Z axes in degrees (Euler angles). Default: `[0.0, 0.0, 0.0]` |
| `size` | `list[float]` | Dimensions of the cube as `[width, height, depth]`. Default: `[1.0, 1.0, 1.0]` |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `geometry` | `list[Geometry]` | 1-element geometry list (express_id=None) referencing the cached cube mesh |

## Example

```json
{
  "position": [5.0, 3.0, 0.0],
  "rotation": [0.0, 0.0, 45.0],
  "size": [2.0, 2.0, 2.0]
}
```

This creates a 2×2×2 cube centered at (5, 3, 0), rotated 45 degrees around the Z-axis.

## Notes

- The cube is created centered at the origin first, then rotated and translated
- All size dimensions must be positive (greater than 0)
- Rotation follows the right-hand rule
- The output geometry handle can be fed directly into a `collision` node
