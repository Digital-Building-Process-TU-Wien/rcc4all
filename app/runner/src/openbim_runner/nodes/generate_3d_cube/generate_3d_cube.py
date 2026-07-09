from __future__ import annotations

import math

import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.geometry import Geometry, cache_mesh

class Generate3DCubeInputs(NodeModel):
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


class Generate3DCubeResult(NodeModel):
    geometry: list[Geometry] = Field(
        default=[],
        title="Geometry",
        description="The generated cube as a 1-element geometry list (express_id=None).",
    )


def _euler_degrees_to_matrix(rotation: list[float]) -> trimesh.Transformations:
    x_rad = math.radians(rotation[0])
    y_rad = math.radians(rotation[1])
    z_rad = math.radians(rotation[2])

    rotation_matrix = trimesh.transformations.euler_matrix(x_rad, y_rad, z_rad)
    return rotation_matrix


@node()
async def generate_3d_cube(inputs: Generate3DCubeInputs, context: ExecutionContext) -> Generate3DCubeResult:
    if any(dim <= 0 for dim in inputs.size):
        raise ValueError("Size dimensions must be positive")

    if len(inputs.position) != 3:
        raise ValueError("Position must be a 3D vector [x, y, z]")
    if len(inputs.rotation) != 3:
        raise ValueError("Rotation must be a 3D vector [x, y, z] in degrees")
    if len(inputs.size) != 3:
        raise ValueError("Size must be a 3D vector [width, height, depth]")

    box = trimesh.creation.box(extents=inputs.size)

    rotation_matrix = _euler_degrees_to_matrix(inputs.rotation)

    translation_matrix = trimesh.transformations.translation_matrix(inputs.position)

    transform_matrix = translation_matrix @ rotation_matrix

    box.apply_transform(transform_matrix)

    handle = cache_mesh(context, box)
    return Generate3DCubeResult(geometry=[handle])
