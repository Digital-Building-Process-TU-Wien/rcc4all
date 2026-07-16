from __future__ import annotations

import math
from typing import cast

import numpy as np
import numpy.typing as npt
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node

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
    vertices: list[list[float]] = Field(
        default=[],
        title="Vertices",
        description="List of 3D vertex coordinates [[x, y, z], ...] defining the cube geometry.",
    )
    faces: list[list[int]] = Field(
        default=[],
        title="Faces",
        description="List of face definitions [[v1, v2, v3], ...] as vertex indices forming triangles.",
    )


def _euler_degrees_to_matrix(rotation: list[float]) -> npt.NDArray[np.float64]:
    x_rad = math.radians(rotation[0])
    y_rad = math.radians(rotation[1])
    z_rad = math.radians(rotation[2])

    return cast(
        npt.NDArray[np.float64],
        trimesh.transformations.euler_matrix(x_rad, y_rad, z_rad),  # pyright: ignore[reportUnknownMemberType]
    )


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

    box = trimesh.creation.box(extents=inputs.size)  # pyright: ignore[reportUnknownMemberType]

    rotation_matrix = _euler_degrees_to_matrix(inputs.rotation)

    translation_matrix = cast(
        npt.NDArray[np.float64],
        trimesh.transformations.translation_matrix(inputs.position),  # pyright: ignore[reportUnknownMemberType]
    )

    transform_matrix: npt.NDArray[np.float64] = translation_matrix @ rotation_matrix

    box.apply_transform(transform_matrix)  # pyright: ignore[reportUnknownMemberType]

    return Generate3DCubeResult(
        vertices=cast(list[list[float]], box.vertices.tolist()),
        faces=cast(list[list[int]], box.faces.tolist()),
    )
