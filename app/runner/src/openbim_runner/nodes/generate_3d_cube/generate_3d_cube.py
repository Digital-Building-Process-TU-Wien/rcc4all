from __future__ import annotations

import math
from typing import Any

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import cache_mesh


class Generate3DCubeSettings(NodeModel):
    position: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Position Offset",
        description="Position offset [x, y, z] in meters added to base position from input. Default [0,0,0] means no offset.",
    )
    rotation: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Rotation Offset",
        description="Rotation offset [x, y, z] in degrees added to base rotation from input. Default [0,0,0] means no offset.",
    )
    size: list[float] = Field(
        default=[1.0, 1.0, 1.0],
        title="Size",
        description="Dimensions [width, height, depth] in meters.",
    )
    object_id: str = Field(
        title="Object ID",
        description="Unique identifier for the generated cube, used to reference it e.g. in a collision node.",
    )


class Generate3DCubeInputs(NodeModel):
    elements: list[Any] = Field(
        default=[],
        title="Base Elements",
        description="Elements from upstream node (e.g., set_3d_position_rotation or get_element_creation_position_door). First element is used for base position/rotation.",
    )


class Generate3DCubeResult(NodeModel):
    object_ids: list[str] = Field(
        default=[],
        title="Object IDs",
        description="1-element list with the qualified geometry cache key (`gen:<object_id>`) of the generated cube.",
    )


def _euler_degrees_to_matrix(rotation: list[float]) -> np.ndarray:
    x_rad = math.radians(rotation[0])
    y_rad = math.radians(rotation[1])
    z_rad = math.radians(rotation[2])

    rotation_matrix = trimesh.transformations.euler_matrix(x_rad, y_rad, z_rad)
    return rotation_matrix  # noqa: RET504 - typed local keeps pyright strict happy (bare ndarray generic)


def _extract_position_rotation(element: Any) -> tuple[list[float], list[float]]:
    """Extract position and rotation from an element (dict or Pydantic model)."""
    if hasattr(element, "model_dump"):
        # Pydantic model → convert to dict
        data = element.model_dump()
    elif isinstance(element, dict):
        data = element
    else:
        # Fallback: try attribute access
        return (
            getattr(element, "position", [0.0, 0.0, 0.0]),
            [
                getattr(element.rotation, "rotation_x", 0.0) if hasattr(element, "rotation") else 0.0,
                getattr(element.rotation, "rotation_y", 0.0) if hasattr(element, "rotation") else 0.0,
                getattr(element.rotation, "rotation_z", 0.0) if hasattr(element, "rotation") else 0.0,
            ],
        )

    # Position extrahieren
    base_pos = data.get("position", [0.0, 0.0, 0.0])

    # Rotation extrahieren (kann nested Object oder flache Felder sein)
    rot_obj = data.get("rotation", {})
    if hasattr(rot_obj, "model_dump"):
        # Pydantic model
        rot_data = rot_obj.model_dump()
        base_rot = [
            rot_data.get("rotation_x", 0.0),
            rot_data.get("rotation_y", 0.0),
            rot_data.get("rotation_z", 0.0),
        ]
    elif isinstance(rot_obj, dict):
        # Dict
        base_rot = [
            rot_obj.get("rotation_x", 0.0),
            rot_obj.get("rotation_y", 0.0),
            rot_obj.get("rotation_z", 0.0),
        ]
    else:
        # Fallback
        base_rot = [0.0, 0.0, 0.0]

    return base_pos, base_rot


@node()
async def generate_3d_cube(
    settings: Generate3DCubeSettings,
    inputs: Generate3DCubeInputs,
    context: ExecutionContext,
) -> Generate3DCubeResult:
    if any(dim <= 0 for dim in settings.size):
        raise ValueError("Size dimensions must be positive")

    if len(settings.position) != 3:
        raise ValueError("Position offset must be a 3D vector [x, y, z]")
    if len(settings.rotation) != 3:
        raise ValueError("Rotation offset must be a 3D vector [x, y, z] in degrees")
    if len(settings.size) != 3:
        raise ValueError("Size must be a 3D vector [width, height, depth]")
    if not settings.object_id:
        raise ValueError("object_id must be a non-empty string")
    if ":expr:" in settings.object_id:
        raise ValueError(
            "object_id must not contain ':expr:' so it can never parse as an IFC element reference."
        )

    # 1. Base Position aus Input (oder [0,0,0] Fallback)
    if inputs.elements:
        base_pos, base_rot = _extract_position_rotation(inputs.elements[0])
    else:
        base_pos = [0.0, 0.0, 0.0]
        base_rot = [0.0, 0.0, 0.0]

    # 2. Delta-Werte addieren
    final_position = [
        base_pos[0] + settings.position[0],
        base_pos[1] + settings.position[1],
        base_pos[2] + settings.position[2],
    ]

    final_rotation = [
        base_rot[0] + settings.rotation[0],
        base_rot[1] + settings.rotation[1],
        base_rot[2] + settings.rotation[2],
    ]

    # 3. Validierung
    if len(final_position) != 3:
        raise ValueError("Final position must be a 3D vector")
    if len(final_rotation) != 3:
        raise ValueError("Final rotation must be a 3D vector")

    # 4. Cube erstellen
    box = trimesh.creation.box(extents=settings.size)

    rotation_matrix = _euler_degrees_to_matrix(final_rotation)

    translation_matrix = trimesh.transformations.translation_matrix(final_position)

    transform_matrix = translation_matrix @ rotation_matrix

    box.apply_transform(transform_matrix)

    cache_key = cache_mesh(context, box, object_id=settings.object_id)
    return Generate3DCubeResult(object_ids=[cache_key])
