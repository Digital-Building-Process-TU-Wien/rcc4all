from __future__ import annotations

import asyncio

import pytest

from openbim_runner.nodes.set_3d_position_rotation.set_3d_position_rotation import (
    Set3DPositionRotationSettings,
    set_3d_position_rotation,
)


def test_single_element() -> None:
    result = asyncio.run(
        set_3d_position_rotation(
            Set3DPositionRotationSettings(
                position=[1.0, 2.0, 3.0],
                rotation=[0.0, 0.0, 45.0],
            ),
        ),
    )
    assert len(result.elements) == 1
    assert result.elements[0].position == [1.0, 2.0, 3.0]
    assert result.elements[0].rotation.rotation_x == 0.0
    assert result.elements[0].rotation.rotation_y == 0.0
    assert result.elements[0].rotation.rotation_z == 45.0
    assert result.elements[0].express_id == ""


def test_default_values() -> None:
    result = asyncio.run(
        set_3d_position_rotation(
            Set3DPositionRotationSettings(),
        ),
    )
    assert len(result.elements) == 1
    assert result.elements[0].position == [0.0, 0.0, 0.0]
    assert result.elements[0].rotation.rotation_x == 0.0
    assert result.elements[0].rotation.rotation_y == 0.0
    assert result.elements[0].rotation.rotation_z == 0.0


def test_invalid_position_length() -> None:
    with pytest.raises(ValueError, match="Position must be a 3D vector"):
        asyncio.run(
            set_3d_position_rotation(
                Set3DPositionRotationSettings(
                    position=[1.0, 2.0],
                    rotation=[0.0, 0.0, 0.0],
                ),
            ),
        )


def test_invalid_rotation_length() -> None:
    with pytest.raises(ValueError, match="Rotation must be a 3D vector"):
        asyncio.run(
            set_3d_position_rotation(
                Set3DPositionRotationSettings(
                    position=[0.0, 0.0, 0.0],
                    rotation=[0.0, 0.0],
                ),
            ),
        )
