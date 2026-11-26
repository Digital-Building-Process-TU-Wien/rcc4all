from pydantic import Field

from openbim_runner.nodes.base import NodeModel, node


class Set3DPositionRotationSettings(NodeModel):
    position: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Position",
        description="3D position [x, y, z] in meters.",
    )
    rotation: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        title="Rotation",
        description="Euler angles [x, y, z] in degrees for rotation around each axis.",
    )


class ElementRotation(NodeModel):
    rotation_x: float = Field(
        title="Rotation X",
        description="Rotation around global X-axis in degrees.",
    )
    rotation_y: float = Field(
        title="Rotation Y",
        description="Rotation around global Y-axis in degrees.",
    )
    rotation_z: float = Field(
        title="Rotation Z",
        description="Rotation around global Z-axis in degrees.",
    )


class ElementResult(NodeModel):
    express_id: str = Field(
        default="",
        title="Express ID",
        description="Empty string (no IFC element reference).",
    )
    position: list[float] = Field(
        title="Position",
        description="World coordinates [x, y, z] in meters.",
    )
    rotation: ElementRotation = Field(
        title="Rotation",
        description="Euler angles (X, Y, Z) in degrees.",
    )


class Set3DPositionRotationResult(NodeModel):
    elements: list[ElementResult] = Field(
        default=[],
        title="Elements",
        description="List with one element containing position and rotation values.",
    )


@node()
async def set_3d_position_rotation(
    settings: Set3DPositionRotationSettings,
) -> Set3DPositionRotationResult:
    if len(settings.position) != 3:
        raise ValueError("Position must be a 3D vector [x, y, z]")
    if len(settings.rotation) != 3:
        raise ValueError("Rotation must be a 3D vector [x, y, z] in degrees")

    return Set3DPositionRotationResult(
        elements=[
            ElementResult(
                express_id="",
                position=settings.position,
                rotation=ElementRotation(
                    rotation_x=settings.rotation[0],
                    rotation_y=settings.rotation[1],
                    rotation_z=settings.rotation[2],
                ),
            )
        ]
    )
