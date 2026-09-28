from __future__ import annotations

import asyncio
from pathlib import Path

import ifcopenshell
import numpy as np
import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_element_creation_position_door.get_element_creation_position_door import (
    GetElementCreationPositionDoorInputs,
    GetElementCreationPositionDoorResult,
    GetElementCreationPositionDoorSettings,
    ThicknessInfo,
    _build_opening_to_wall_map,
    _clip_opening_to_wall_polygon,
    _get_element_thickness_direct,
    _get_thickness_info,
    get_element_creation_position_door,
)


TEST_DATA_DIR = Path(__file__).parent


@pytest.fixture
def test_model_with_door() -> ifcopenshell.file:
    """Load a real IFC model with doors that have geometry."""
    ifc_path = TEST_DATA_DIR / "CustomTestModel-EscapeRouteAnalysis-ZDB-v3.ifc"
    return ifcopenshell.open(str(ifc_path))


@pytest.fixture
def context(test_model_with_door: ifcopenshell.file) -> ExecutionContext:
    return ExecutionContext(ifc_model=test_model_with_door, node_outputs={})


def test_get_element_creation_position_door_p7_center(
    context: ExecutionContext,
) -> None:
    """Test P7 center point extraction for a single door using centroid method."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[express_id]),
            context,
        )
    )

    assert isinstance(result, GetElementCreationPositionDoorResult)
    assert len(result.elements) == 1
    assert result.elements[0].express_id == express_id
    assert result.elements[0].point_index == 7
    # Centroid returns 3D coordinates [x, y, z]
    assert len(result.elements[0].position) == 3
    assert all(isinstance(coord, float) for coord in result.elements[0].position)


def test_get_element_creation_position_door_multiple_doors(
    context: ExecutionContext,
) -> None:
    """Test processing multiple doors at once."""
    all_doors = context.ifc_model.by_type("IfcDoor")
    express_ids = [door.id() for door in all_doors]

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=express_ids),
            context,
        )
    )

    assert len(result.elements) == len(all_doors)
    # All IDs should be present
    result_ids = {elem.express_id for elem in result.elements}
    assert set(express_ids) == result_ids
    # All should have point_index 7
    assert all(elem.point_index == 7 for elem in result.elements)


def test_get_element_creation_position_door_centroid_returns_3d_point(
    context: ExecutionContext,
) -> None:
    """Test that centroid method returns proper 3D coordinates."""
    all_doors = context.ifc_model.by_type("IfcDoor")
    express_ids = [door.id() for door in all_doors[:3]]  # Test first 3 doors

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=express_ids),
            context,
        )
    )

    # All doors with geometry should return positions
    assert len(result.elements) > 0
    for elem in result.elements:
        assert len(elem.position) == 3
        # Coordinates should be reasonable (not NaN or infinite)
        assert all(not (coord != coord) for coord in elem.position)  # NaN check
        assert all(abs(coord) < 1e6 for coord in elem.position)  # Reasonable bounds


def test_get_element_creation_position_door_empty_input(
    context: ExecutionContext,
) -> None:
    """Test with empty express_ids list."""
    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[]),
            context,
        )
    )

    assert len(result.elements) == 0


def test_get_element_creation_position_door_invalid_express_id(
    context: ExecutionContext,
) -> None:
    """Test that invalid express IDs are silently skipped."""
    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[99999, 88888]),
            context,
        )
    )

    # Invalid IDs should be skipped, resulting in empty list
    assert len(result.elements) == 0


def test_get_element_creation_position_door_mixed_valid_invalid(
    context: ExecutionContext,
) -> None:
    """Test that valid IDs are processed even with invalid IDs in the list."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    valid_id = door.id()

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[valid_id, 99999, 88888]),
            context,
        )
    )

    # Only the valid ID should be processed
    assert len(result.elements) == 1
    assert result.elements[0].express_id == valid_id


def test_get_element_creation_position_door_not_a_door(
    context: ExecutionContext,
) -> None:
    """Test that unsupported entity types are silently skipped."""
    space = context.ifc_model.by_type("IfcSpace")[0]

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[space.id()]),
            context,
        )
    )

    # Unsupported entity types should be skipped
    assert len(result.elements) == 0


@pytest.mark.skip(reason="Wall functionality deprecated - focusing on doors only")
def test_get_element_creation_position_wall_p7_center(
    context: ExecutionContext,
) -> None:
    """Test P7 center point extraction for a single wall with 4 vertices."""
    # Find a wall with exactly 4 bottom vertices
    import ifcopenshell.geom
    import numpy as np
    
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    wall_4_vertices = None
    for wall in context.ifc_model.by_type("IfcWall"):
        shape = ifcopenshell.geom.create_shape(settings, wall)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        min_z = verts[:, 2].min()
        bottom = verts[np.isclose(verts[:, 2], min_z, atol=0.001)]
        if len(bottom) == 4:
            wall_4_vertices = wall
            break
    
    if wall_4_vertices is None:
        pytest.skip("No wall with 4 bottom vertices found")
    
    express_id = wall_4_vertices.id()

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[express_id]),
            context,
        )
    )

    assert isinstance(result, GetElementCreationPositionDoorResult)
    assert len(result.elements) == 1
    assert result.elements[0].express_id == express_id
    assert result.elements[0].element_type == "IfcWall"
    assert result.elements[0].point_index == 7
    assert len(result.elements[0].position) == 3
    assert all(isinstance(coord, float) for coord in result.elements[0].position)


@pytest.mark.skip(reason="Wall functionality deprecated - focusing on doors only")
def test_get_element_creation_position_wall_all_corners(
    context: ExecutionContext,
) -> None:
    """Test all corner points (P1-P4) for a wall with 4 vertices."""
    import ifcopenshell.geom
    import numpy as np
    
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    wall_4_vertices = None
    for wall in context.ifc_model.by_type("IfcWall"):
        shape = ifcopenshell.geom.create_shape(settings, wall)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        min_z = verts[:, 2].min()
        bottom = verts[np.isclose(verts[:, 2], min_z, atol=0.001)]
        if len(bottom) == 4:
            wall_4_vertices = wall
            break
    
    if wall_4_vertices is None:
        pytest.skip("No wall with 4 bottom vertices found")
    
    express_id = wall_4_vertices.id()
    
    # Test all 5 points (P1-P4, P7)
    all_positions = {}
    for point_index in [1, 2, 3, 4, 7]:
        result = asyncio.run(
            get_element_creation_position_door(
                GetElementCreationPositionDoorSettings(point_index=point_index),
                GetElementCreationPositionDoorInputs(express_ids=[express_id]),
                context,
            )
        )
        assert len(result.elements) == 1
        assert result.elements[0].point_index == point_index
        all_positions[point_index] = result.elements[0].position
    
    # P7 (centroid) should be approximately the average of P1-P4
    import numpy as np
    p1_p4 = np.array([all_positions[i] for i in [1, 2, 3, 4]])
    centroid_expected = p1_p4.mean(axis=0).tolist()
    p7_actual = all_positions[7]
    
    # Check that centroid is close to average of corners (within 1cm)
    for i in range(3):
        assert abs(centroid_expected[i] - p7_actual[i]) < 0.01


@pytest.mark.skip(reason="Wall functionality deprecated - focusing on doors only")
def test_get_element_creation_position_wall_multiple_walls(
    context: ExecutionContext,
) -> None:
    """Test processing multiple walls at once with different point indices."""
    import ifcopenshell.geom
    import numpy as np
    
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    # Find walls with 4 vertices
    wall_ids = []
    for wall in context.ifc_model.by_type("IfcWall"):
        shape = ifcopenshell.geom.create_shape(settings, wall)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        min_z = verts[:, 2].min()
        bottom = verts[np.isclose(verts[:, 2], min_z, atol=0.001)]
        if len(bottom) == 4:
            wall_ids.append(wall.id())
            if len(wall_ids) >= 3:  # Test first 3 walls
                break
    
    if len(wall_ids) < 3:
        pytest.skip("Not enough walls with 4 bottom vertices found")
    
    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=1),  # Test P1
            GetElementCreationPositionDoorInputs(express_ids=wall_ids),
            context,
        )
    )
    
    assert len(result.elements) == 3
    result_ids = {elem.express_id for elem in result.elements}
    assert set(wall_ids) == result_ids
    assert all(elem.point_index == 1 for elem in result.elements)
    assert all(elem.element_type == "IfcWall" for elem in result.elements)


def test_get_element_creation_position_door_all_corners(
    context: ExecutionContext,
) -> None:
    """Test all corner points (P1-P4) for a door opening."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Test all 5 points (P1-P4, P7)
    all_positions = {}
    for point_index in [1, 2, 3, 4, 7]:
        result = asyncio.run(
            get_element_creation_position_door(
                GetElementCreationPositionDoorSettings(point_index=point_index),
                GetElementCreationPositionDoorInputs(express_ids=[express_id]),
                context,
            )
        )
        assert len(result.elements) == 1
        assert result.elements[0].point_index == point_index
        all_positions[point_index] = result.elements[0].position
    
    # P7 (centroid) should be approximately the average of P1-P4
    p1_p4 = np.array([all_positions[i] for i in [1, 2, 3, 4]])
    centroid_expected = p1_p4.mean(axis=0).tolist()
    p7_actual = all_positions[7]
    
    # Check that centroid is close to average of corners (within 1cm)
    for i in range(3):
        assert abs(centroid_expected[i] - p7_actual[i]) < 0.01


def test_get_element_creation_position_door_p5_p6_midpoints(
    context: ExecutionContext,
) -> None:
    """Test P5 and P6 midpoint calculation for a door opening."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Get P1, P2, P5
    p1_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=1),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p2_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=2),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p5_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=5),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    
    p1 = np.array(p1_result.elements[0].position)
    p2 = np.array(p2_result.elements[0].position)
    p5 = np.array(p5_result.elements[0].position)
    
    # P5 should be midpoint between P1 and P2
    p5_expected = (p1 + p2) / 2
    
    for i in range(3):
        assert abs(p5[i] - p5_expected[i]) < 0.01  # Within 1cm


def test_get_element_creation_position_door_p6_midpoint(
    context: ExecutionContext,
) -> None:
    """Test P6 midpoint calculation for a door opening."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Get P3, P4, P6
    p3_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=3),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p4_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=4),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p6_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=6),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    
    p3 = np.array(p3_result.elements[0].position)
    p4 = np.array(p4_result.elements[0].position)
    p6 = np.array(p6_result.elements[0].position)
    
    # P6 should be midpoint between P3 and P4
    p6_expected = (p3 + p4) / 2
    
    for i in range(3):
        assert abs(p6[i] - p6_expected[i]) < 0.01  # Within 1cm


@pytest.mark.skip(reason="Wall functionality deprecated - focusing on doors only")
def test_get_element_creation_position_wall_p5_p6_midpoints(
    context: ExecutionContext,
) -> None:
    """Test P5 and P6 midpoint calculation for a wall with 4 vertices."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    wall_4_vertices = None
    for wall in context.ifc_model.by_type("IfcWall"):
        shape = ifcopenshell.geom.create_shape(settings, wall)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        min_z = verts[:, 2].min()
        bottom = verts[np.isclose(verts[:, 2], min_z, atol=0.001)]
        if len(bottom) == 4:
            wall_4_vertices = wall
            break
    
    if wall_4_vertices is None:
        pytest.skip("No wall with 4 bottom vertices found")
    
    express_id = wall_4_vertices.id()
    
    # Get P1, P2, P5
    p1_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=1),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p2_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=2),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    p5_result = asyncio.run(get_element_creation_position_door(
        GetElementCreationPositionDoorSettings(point_index=5),
        GetElementCreationPositionDoorInputs(express_ids=[express_id]),
        context,
    ))
    
    p1 = np.array(p1_result.elements[0].position)
    p2 = np.array(p2_result.elements[0].position)
    p5 = np.array(p5_result.elements[0].position)
    
    # P5 should be midpoint between P1 and P2
    p5_expected = (p1 + p2) / 2
    
    for i in range(3):
        assert abs(p5[i] - p5_expected[i]) < 0.01  # Within 1cm


@pytest.mark.skip(reason="Wall functionality deprecated - focusing on doors only")
def test_get_element_creation_position_wall_more_than_4_vertices(
    context: ExecutionContext,
) -> None:
    """Test OBB corner finding for a wall with >4 bottom vertices."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    # Find a wall with >4 bottom vertices
    wall_more_vertices = None
    for wall in context.ifc_model.by_type("IfcWall"):
        shape = ifcopenshell.geom.create_shape(settings, wall)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        min_z = verts[:, 2].min()
        bottom = verts[np.isclose(verts[:, 2], min_z, atol=0.001)]
        if len(bottom) > 4:
            wall_more_vertices = wall
            break
    
    if wall_more_vertices is None:
        pytest.skip("No wall with >4 bottom vertices found")
    
    express_id = wall_more_vertices.id()
    
    # Test that all 7 points can be retrieved
    all_positions = {}
    for point_index in [1, 2, 3, 4, 5, 6, 7]:
        result = asyncio.run(
            get_element_creation_position_door(
                GetElementCreationPositionDoorSettings(point_index=point_index),
                GetElementCreationPositionDoorInputs(express_ids=[express_id]),
                context,
            )
        )
        assert len(result.elements) == 1
        assert result.elements[0].point_index == point_index
        all_positions[point_index] = result.elements[0].position
    
    # All positions should be valid 3D coordinates
    for point_index in [1, 2, 3, 4, 5, 6, 7]:
        pos = all_positions[point_index]
        assert len(pos) == 3
        assert all(not (coord != coord) for coord in pos)  # NaN check
        assert all(abs(coord) < 1e6 for coord in pos)  # Reasonable bounds
    
    # P5 should be midpoint between P1 and P2
    p1 = np.array(all_positions[1])
    p2 = np.array(all_positions[2])
    p5 = np.array(all_positions[5])
    p5_expected = (p1 + p2) / 2
    for i in range(3):
        assert abs(p5[i] - p5_expected[i]) < 0.01  # Within 1cm
    
    # P6 should be midpoint between P3 and P4
    p3 = np.array(all_positions[3])
    p4 = np.array(all_positions[4])
    p6 = np.array(all_positions[6])
    p6_expected = (p3 + p4) / 2
    for i in range(3):
        assert abs(p6[i] - p6_expected[i]) < 0.01  # Within 1cm


def test_thickness_detection_equal(
    context: ExecutionContext,
) -> None:
    """Test thickness detection when opening thickness == wall thickness."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Find opening and wall
    opening = None
    for rel in context.ifc_model.by_type("IfcRelFillsElement"):
        if rel.RelatedBuildingElement and rel.RelatedBuildingElement.id() == express_id:
            opening = rel.RelatingOpeningElement
            break
    
    assert opening is not None
    
    wall = None
    for rel in context.ifc_model.by_type("IfcRelVoidsElement"):
        if rel.RelatedOpeningElement and rel.RelatedOpeningElement.id() == opening.id():
            wall = rel.RelatingBuildingElement
            break
    
    assert wall is not None
    
    # Get bottom vertices directly (world coordinates)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    opening_shape = ifcopenshell.geom.create_shape(settings, opening)
    opening_verts = np.array(opening_shape.geometry.verts).reshape((-1, 3))
    min_z = opening_verts[:, 2].min()
    opening_bottom = opening_verts[np.isclose(opening_verts[:, 2], min_z, atol=0.001)]
    
    wall_shape = ifcopenshell.geom.create_shape(settings, wall)
    wall_verts = np.array(wall_shape.geometry.verts).reshape((-1, 3))
    min_z = wall_verts[:, 2].min()
    wall_bottom = wall_verts[np.isclose(wall_verts[:, 2], min_z, atol=0.001)]
    
    # Get thickness info (direct from bottom vertices)
    thickness_info = _get_thickness_info(
        opening_bottom,
        wall_bottom,
        tolerance=0.01,
    )
    
    # Both thicknesses should be detected
    assert thickness_info.opening_thickness > 0.0
    assert thickness_info.wall_thickness is not None
    assert thickness_info.wall_thickness > 0.0
    
    # In test model, opening and wall have similar thickness (~30cm)
    # With 1% tolerance, should not need clipping
    assert thickness_info.needs_clipping is False


def test_thickness_detection_wall_not_found(
    context: ExecutionContext,
) -> None:
    """Test thickness detection when wall is not found."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Find opening
    opening = None
    for rel in context.ifc_model.by_type("IfcRelFillsElement"):
        if rel.RelatedBuildingElement and rel.RelatedBuildingElement.id() == express_id:
            opening = rel.RelatingOpeningElement
            break
    
    assert opening is not None
    
    # Get bottom vertices directly (world coordinates)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    opening_shape = ifcopenshell.geom.create_shape(settings, opening)
    opening_verts = np.array(opening_shape.geometry.verts).reshape((-1, 3))
    min_z = opening_verts[:, 2].min()
    opening_bottom = opening_verts[np.isclose(opening_verts[:, 2], min_z, atol=0.001)]
    
    # Get thickness info with wall_bottom_vertices=None
    # Without a wall, we cannot compute opening thickness (no wall axis for projection)
    thickness_info = _get_thickness_info(
        opening_bottom,
        None,  # No wall
        tolerance=0.01,
    )
    
    # Opening thickness is 0.0 when no wall is available (cannot project onto wall axis)
    assert thickness_info.opening_thickness == 0.0
    
    # Wall thickness should be None
    assert thickness_info.wall_thickness is None
    
    # No clipping needed (no wall to clip to)
    assert thickness_info.needs_clipping is False


def test_build_opening_to_wall_map(
    context: ExecutionContext,
) -> None:
    """Test building opening-to-wall mapping."""
    mapping = _build_opening_to_wall_map(context.ifc_model)
    
    # Should have at least one mapping (test model has doors)
    assert len(mapping) > 0
    
    # All values should be IfcWall entities
    for opening_id, wall in mapping.items():
        assert isinstance(opening_id, int)
        assert wall.is_a("IfcWall")


def test_clip_opening_to_wall_polygon(
    context: ExecutionContext,
) -> None:
    """Test vertex clipping using Sutherland-Hodgman polygon clipping (2D intersection-based)."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()
    
    # Find opening and wall
    opening = None
    for rel in context.ifc_model.by_type("IfcRelFillsElement"):
        if rel.RelatedBuildingElement and rel.RelatedBuildingElement.id() == express_id:
            opening = rel.RelatingOpeningElement
            break
    
    assert opening is not None
    
    wall = None
    for rel in context.ifc_model.by_type("IfcRelVoidsElement"):
        if rel.RelatedOpeningElement and rel.RelatedOpeningElement.id() == opening.id():
            wall = rel.RelatingBuildingElement
            break
    
    assert wall is not None
    
    # Get bottom vertices (world coordinates)
    import ifcopenshell.geom
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context-types", ["Body"])
    
    opening_shape = ifcopenshell.geom.create_shape(settings, opening)
    opening_verts = np.array(opening_shape.geometry.verts).reshape((-1, 3))
    min_z = opening_verts[:, 2].min()
    opening_bottom = opening_verts[np.isclose(opening_verts[:, 2], min_z, atol=0.001)]
    
    wall_shape = ifcopenshell.geom.create_shape(settings, wall)
    wall_verts = np.array(wall_shape.geometry.verts).reshape((-1, 3))
    min_z = wall_verts[:, 2].min()
    wall_bottom = wall_verts[np.isclose(wall_verts[:, 2], min_z, atol=0.001)]
    
    # Clip vertices (Sutherland-Hodgman, no placement matrix needed)
    clipped_verts = _clip_opening_to_wall_polygon(
        opening_bottom,
        wall_bottom,
    )
    
    # Same number or more vertices (clipping can add intersection points)
    assert len(clipped_verts) >= len(opening_bottom)
    
    # All vertices should be valid 3D coordinates
    assert clipped_verts.shape == (len(clipped_verts), 3)
    assert not np.any(np.isnan(clipped_verts))
    assert not np.any(np.isinf(clipped_verts))
    
    # Validate: all clipped vertices should be within wall rectangle (2D point-in-polygon test)
    # Simple approach: project onto wall axes and check bounds
    wall_center = wall_bottom.mean(axis=0)
    wall_centered = wall_bottom - wall_center
    U, S, Vh = np.linalg.svd(wall_centered, full_matrices=False)
    length_axis = Vh[0]
    thickness_axis = Vh[1]
    
    # Wall bounds
    wall_length_proj = wall_centered @ length_axis
    wall_thickness_proj = wall_centered @ thickness_axis
    wall_length_min, wall_length_max = float(wall_length_proj.min()), float(wall_length_proj.max())
    wall_thickness_min, wall_thickness_max = float(wall_thickness_proj.min()), float(wall_thickness_proj.max())
    
    # Check all clipped vertices are within bounds (with 2mm tolerance for numerical precision)
    clipped_centered = clipped_verts - wall_center
    for i in range(len(clipped_verts)):
        length_coord = float(clipped_centered[i] @ length_axis)
        thickness_coord = float(clipped_centered[i] @ thickness_axis)
        assert wall_length_min - 0.002 <= length_coord <= wall_length_max + 0.002
        assert wall_thickness_min - 0.002 <= thickness_coord <= wall_thickness_max + 0.002