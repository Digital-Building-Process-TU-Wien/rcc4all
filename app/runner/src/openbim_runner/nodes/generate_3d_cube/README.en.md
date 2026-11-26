---
title: Generate 3D Cube
description: Create a 3D box geometry with configurable size, position offset, and rotation offset for clash detection.
categories: 3D operation,
---

The `generate_3d_cube` node creates a 3D box geometry with configurable dimensions, position offset, and rotation offset, and stores it in the geometry cache under a user-supplied `object_id`. The cache key `gen:<object_id>` is the address used to reference the cube later, e.g. in a `collision` node.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `elements` | `list[dict]` | Elements from upstream node (e.g., `set_3d_position_rotation.elements` or `get_element_creation_position_door.elements`). The first element's position and rotation are used as base values. Bind to use input position/rotation. |

## Settings

| Name | Type | Description |
|------|------|-------------|
| `position` | `list[float]` | **Offset** added to base position from input. Default: `[0.0, 0.0, 0.0]` (no offset). |
| `rotation` | `list[float]` | **Offset** added to base rotation from input. Default: `[0.0, 0.0, 0.0]` (no offset). |
| `size` | `list[float]` | Dimensions of the cube as `[width, height, depth]`. Default: `[1.0, 1.0, 1.0]`. |
| `object_id` | `string` | Unique identifier for the generated cube (required). Duplicates are rejected. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `object_ids` | `list[string]` | 1-element list with the cube's qualified cache key `gen:<object_id>`. Feed this directly into a `collision` node's geometry-key input. |

## Example: Using with set_3d_position_rotation

### Workflow JSON

```json
{
  "nodes": [
    {
      "id": "pos1",
      "type": "set_3d_position_rotation",
      "data": {
        "settings": {
          "position": [5.0, 3.0, 0.0],
          "rotation": [0.0, 0.0, 45.0]
        }
      }
    },
    {
      "id": "cube1",
      "type": "generate_3d_cube",
      "data": {
        "input_bindings": {
          "elements": "pos1.elements"
        },
        "settings": {
          "position": [0.5, 0.0, 0.0],
          "rotation": [0.0, 0.0, 0.0],
          "size": [1.0, 1.0, 1.0],
          "object_id": "offset_cube"
        }
      }
    }
  ]
}
```

This creates:
1. A base position at (5, 3, 0) with 45° Z-rotation from `set_3d_position_rotation`
2. A cube at (5.5, 3, 0) with 45° Z-rotation (0.5m X-offset from base)

## Example: Standalone (no input binding)

```json
{
  "settings": {
    "position": [5.0, 3.0, 0.0],
    "rotation": [0.0, 0.0, 45.0],
    "size": [2.0, 2.0, 2.0],
    "object_id": "box_a"
  }
}
```

This creates a 2×2×2 cube at position (5, 3, 0) with a 45-degree rotation around the Z-axis, cached under `gen:box_a`.

## Notes

- If no input binding is provided, position/rotation offsets are applied to origin `[0,0,0]`
- Position coordinates are in **meters**
- Rotation follows the **right-hand rule** (X, Y, Z in degrees): positive rotation is counter-clockwise when looking along the axis
- All size dimensions must be positive (greater than 0)
- `object_id` must be non-empty and unique within a run; reusing one raises an error
- `object_id` must not contain `:expr:` (reserved for qualified IFC element references)
