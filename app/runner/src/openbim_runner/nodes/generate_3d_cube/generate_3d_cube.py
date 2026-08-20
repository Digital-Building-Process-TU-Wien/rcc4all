from __future__ import annotations

import math

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import cache_mesh


class Generate3DCubeSettings(NodeModel):
    position: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Position",
        description="3D position [x, y, z] for the cube center in meters.",
    )
    rotation: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Rotation",
        description="Euler angles [x, y, z] in degrees for rotation around each axis.",
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


class Generate3DCubeResult(NodeModel):
    object_ids: list[str] = Field(
        default=[],
        title="Object IDs",
        description="1-element list with the object_id of the generated cube.",
    )


def _euler_degrees_to_matrix(rotation: list[float]) -> np.ndarray:
    x_rad = math.radians(rotation[0])
    y_rad = math.radians(rotation[1])
    z_rad = math.radians(rotation[2])

    return trimesh.transformations.euler_matrix(x_rad, y_rad, z_rad)


@node()
async def generate_3d_cube(
    settings: Generate3DCubeSettings, context: ExecutionContext
) -> Generate3DCubeResult:
    if any(dim <= 0 for dim in settings.size):
        raise ValueError("Size dimensions must be positive")

    if len(settings.position) != 3:
        raise ValueError("Position must be a 3D vector [x, y, z]")
    if len(settings.rotation) != 3:
        raise ValueError("Rotation must be a 3D vector [x, y, z] in degrees")
    if len(settings.size) != 3:
        raise ValueError("Size must be a 3D vector [width, height, depth]")
    if not settings.object_id:
        raise ValueError("object_id must be a non-empty string")

    box = trimesh.creation.box(extents=settings.size)

    rotation_matrix = _euler_degrees_to_matrix(settings.rotation)

    translation_matrix = trimesh.transformations.translation_matrix(settings.position)

    transform_matrix = translation_matrix @ rotation_matrix

    box.apply_transform(transform_matrix)

    cache_mesh(context, box, object_id=settings.object_id)
    return Generate3DCubeResult(object_ids=[settings.object_id])
