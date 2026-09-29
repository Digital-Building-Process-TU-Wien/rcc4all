from __future__ import annotations

import asyncio
from pathlib import Path

import ifcopenshell
import numpy as np
import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_element_creation_position_door.get_element_creation_position_door import (
    ElementRotation,
    GetElementCreationPositionDoorInputs,
    GetElementCreationPositionDoorResult,
    GetElementCreationPositionDoorSettings,
    ThicknessInfo,
    _build_opening_to_wall_map,
    _clip_edge,
    _clip_opening_to_wall_polygon,
    _extract_4_corners,
    _get_element_centroid,
    _get_element_thickness_direct,
    _get_footprint_points,
    _get_placement_matrix,
    _get_rotation_angles,
    _get_thickness_info,
    _line_intersection_2d,
    _round_position,
    _sort_polygon_ccw,
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
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{express_id}"]),
            context,
        )
    )

    assert isinstance(result, GetElementCreationPositionDoorResult)
    assert len(result.elements) == 1
    assert result.elements[0].express_id == f"main:expr:{express_id}"
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
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{id}" for id in express_ids]),
            context,
        )
    )

    assert len(result.elements) == len(all_doors)
    # All IDs should be present
    result_ids = {int(elem.express_id.split(":")[-1]) for elem in result.elements}
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
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{id}" for id in express_ids]),
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
            GetElementCreationPositionDoorInputs(express_ids=["main:expr:99999", "main:expr:88888"]),
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
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{valid_id}", "main:expr:99999", "main:expr:88888"]),
            context,
        )
    )

    # Only the valid ID should be processed
    assert len(result.elements) == 1
    assert result.elements[0].express_id == f"main:expr:{valid_id}"


def test_get_element_creation_position_door_not_a_door(
    context: ExecutionContext,
) -> None:
    """Test that unsupported entity types are silently skipped."""
    space = context.ifc_model.by_type("IfcSpace")[0]

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{space.id()}"]),
            context,
        )
    )

    # Unsupported entity types should be skipped
    assert len(result.elements) == 0


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
                GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{express_id}"]),
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
    
    # Get all corner points and midpoints
    all_positions = {}
    for point_index in [1, 2, 3, 4, 5, 6]:
        result = asyncio.run(get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=point_index),
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{express_id}"]),
            context,
        ))
        assert len(result.elements) == 1
        all_positions[point_index] = result.elements[0].position
    
    p1 = np.array(all_positions[1])
    p2 = np.array(all_positions[2])
    p3 = np.array(all_positions[3])
    p4 = np.array(all_positions[4])
    p5 = np.array(all_positions[5])
    p6 = np.array(all_positions[6])
    
    # P5 should be midpoint between P1 and P2
    p5_expected = (p1 + p2) / 2
    for i in range(3):
        assert abs(p5[i] - p5_expected[i]) < 0.01  # Within 1cm
    
    # P6 should be midpoint between P3 and P4
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
    
    # Clipped vertices should be valid 3D coordinates (can be fewer than input)
    assert len(clipped_verts) >= 3  # At least a triangle
    
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


def test_get_rotation_angles_with_placement(context: ExecutionContext) -> None:
    """Test rotation angle extraction from element placement."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    
    if door.ObjectPlacement:
        rotation = _get_rotation_angles(door.ObjectPlacement)
        
        assert "rotation_x" in rotation
        assert "rotation_y" in rotation
        assert "rotation_z" in rotation
        
        for key, value in rotation.items():
            assert 0.0 <= value <= 360.0
            assert isinstance(value, float)


def test_get_element_creation_position_door_includes_rotation(
    context: ExecutionContext,
) -> None:
    """Test that rotation is included in result when placement is available."""
    door = context.ifc_model.by_type("IfcDoor")[0]
    express_id = door.id()

    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=[f"main:expr:{express_id}"]),
            context,
        )
    )

    assert len(result.elements) == 1
    if door.ObjectPlacement:
        assert result.elements[0].rotation is not None
        assert isinstance(result.elements[0].rotation, ElementRotation)
        assert hasattr(result.elements[0].rotation, "rotation_x")
        assert hasattr(result.elements[0].rotation, "rotation_y")
        assert hasattr(result.elements[0].rotation, "rotation_z")
    else:
        assert result.elements[0].rotation is None


def test_get_rotation_angles_no_placement() -> None:
    """Test rotation extraction with None placement returns zeros."""
    rotation = _get_rotation_angles(None)
    
    assert rotation["rotation_x"] == 0.0
    assert rotation["rotation_y"] == 0.0
    assert rotation["rotation_z"] == 0.0


def test_get_element_creation_position_door_25887_rotation(
    context: ExecutionContext,
) -> None:
    """Test rotation extraction for door 25887 (180° Z-rotation)."""
    result = asyncio.run(
        get_element_creation_position_door(
            GetElementCreationPositionDoorSettings(point_index=7),
            GetElementCreationPositionDoorInputs(express_ids=["main:expr:25887"]),
            context,
        )
    )

    assert len(result.elements) == 1
    assert result.elements[0].rotation is not None
    # Door 25887 has RefDirection [-1, 0, 0] = 180° rotation around Z
    assert result.elements[0].rotation.rotation_x == 0.0
    assert result.elements[0].rotation.rotation_y == 0.0
    assert result.elements[0].rotation.rotation_z == 180.0


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestRoundPosition:
    """Tests for _round_position helper function."""

    def test_round_position_3_decimals(self) -> None:
        """Test rounding to 3 decimal places (millimeter precision)."""
        position = [1.234567, 2.999999, 3.000444]
        result = _round_position(position)
        assert result == [1.235, 3.0, 3.0]

    def test_round_position_already_rounded(self) -> None:
        """Test position already at 3 decimals remains unchanged."""
        position = [1.0, 2.5, 3.125]
        result = _round_position(position)
        assert result == [1.0, 2.5, 3.125]

    def test_round_position_negative_coordinates(self) -> None:
        """Test rounding with negative coordinates."""
        position = [-1.234567, -2.999999, 0.000444]
        result = _round_position(position)
        assert result == [-1.235, -3.0, 0.0]


class TestGetPlacementMatrix:
    """Tests for _get_placement_matrix helper function."""

    def test_get_placement_matrix_none_returns_identity(self) -> None:
        """Test that None placement returns 4x4 identity matrix."""
        matrix = _get_placement_matrix(None)
        assert matrix.shape == (4, 4)
        np.testing.assert_array_almost_equal(matrix, np.eye(4))

    def test_get_placement_matrix_simple_placement(self, context: ExecutionContext) -> None:
        """Test matrix extraction from a simple IfcLocalPlacement."""
        door = context.ifc_model.by_type("IfcDoor")[0]
        if door.ObjectPlacement:
            matrix = _get_placement_matrix(door.ObjectPlacement)
            assert matrix.shape == (4, 4)
            # Last row should be [0, 0, 0, 1] for homogeneous transform
            np.testing.assert_array_almost_equal(matrix[3], [0, 0, 0, 1])

    def test_get_placement_matrix_invalid_placement(self) -> None:
        """Test handling of non-IfcLocalPlacement objects."""
        class MockPlacement:
            def is_a(self, type_name: str) -> bool:
                return False
        matrix = _get_placement_matrix(MockPlacement())
        assert matrix.shape == (4, 4)
        np.testing.assert_array_almost_equal(matrix, np.eye(4))


class TestExtract4Corners:
    """Tests for _extract_4_corners helper function (PCA/OBB-based corner extraction)."""

    def test_extract_4_corners_exact_4_vertices(self) -> None:
        """Test with exactly 4 vertices (rectangle)."""
        vertices = np.array([
            [0, 0, 0],
            [2, 0, 0],
            [2, 1, 0],
            [0, 1, 0],
        ])
        corners = _extract_4_corners(vertices)
        assert corners.shape == (4, 3)
        # All original vertices should be preserved (order may vary)
        for corner in corners:
            assert any(np.allclose(corner, v) for v in vertices)

    def test_extract_4_corners_more_than_4_vertices(self) -> None:
        """Test with >4 vertices (OBB should find 4 outer corners)."""
        theta = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        vertices = np.column_stack([
            2 * np.cos(theta),
            1 * np.sin(theta),
            np.zeros(8),
        ])
        corners = _extract_4_corners(vertices)
        assert corners.shape == (4, 3)
        # Corners should form a bounding box around the ellipse

    def test_extract_4_corners_less_than_4_vertices(self) -> None:
        """Test with <4 vertices (should still return 4 corners via OBB)."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0.5, 0.5, 0],
        ])
        corners = _extract_4_corners(vertices)
        assert corners.shape == (4, 3)

    def test_extract_4_corners_collinear_points(self) -> None:
        """Test with collinear points (degenerate case)."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [2, 0, 0],
            [3, 0, 0],
        ])
        corners = _extract_4_corners(vertices)
        assert corners.shape == (4, 3)
        assert not np.any(np.isnan(corners))

    def test_extract_4_corners_rotated_rectangle(self) -> None:
        """Test with rotated rectangle (45 degrees)."""
        angle = np.pi / 4
        rotation = np.array([
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ])
        vertices = np.array([
            [0, 0],
            [2, 0],
            [2, 1],
            [0, 1],
        ])
        rotated = (rotation @ vertices.T).T
        vertices_3d = np.column_stack([rotated, np.zeros(4)])
        
        corners = _extract_4_corners(vertices_3d)
        assert corners.shape == (4, 3)


class TestGetFootprintPoints:
    """Tests for _get_footprint_points helper function."""

    def test_get_footprint_points_4_vertices_axis_aligned(self) -> None:
        """Test footprint points for axis-aligned rectangle."""
        vertices = np.array([
            [0, 0, 0],
            [2, 0, 0],
            [2, 1, 0],
            [0, 1, 0],
        ])
        points = _get_footprint_points(vertices, None, 0.0)
        
        # Should have all 7 points
        assert len(points) == 7
        for i in range(1, 8):
            assert i in points
            assert len(points[i]) == 3

    def test_get_footprint_points_p7_is_centroid(self) -> None:
        """Test that P7 is the centroid of P1-P4."""
        vertices = np.array([
            [0, 0, 0],
            [4, 0, 0],
            [4, 2, 0],
            [0, 2, 0],
        ])
        points = _get_footprint_points(vertices, None, 0.0)
        
        p1, p2, p3, p4 = np.array(points[1]), np.array(points[2]), np.array(points[3]), np.array(points[4])
        p7 = np.array(points[7])
        
        expected_centroid = (p1 + p2 + p3 + p4) / 4
        np.testing.assert_array_almost_equal(p7, expected_centroid, decimal=5)

    def test_get_footprint_points_p5_is_midpoint_p1_p2(self) -> None:
        """Test that P5 is the midpoint between P1 and P2."""
        vertices = np.array([
            [0, 0, 0],
            [4, 0, 0],
            [4, 2, 0],
            [0, 2, 0],
        ])
        points = _get_footprint_points(vertices, None, 0.0)
        
        p1 = np.array(points[1])
        p2 = np.array(points[2])
        p5 = np.array(points[5])
        
        expected_midpoint = (p1 + p2) / 2
        np.testing.assert_array_almost_equal(p5, expected_midpoint, decimal=5)

    def test_get_footprint_points_p6_is_midpoint_p3_p4(self) -> None:
        """Test that P6 is the midpoint between P3 and P4."""
        vertices = np.array([
            [0, 0, 0],
            [4, 0, 0],
            [4, 2, 0],
            [0, 2, 0],
        ])
        points = _get_footprint_points(vertices, None, 0.0)
        
        p3 = np.array(points[3])
        p4 = np.array(points[4])
        p6 = np.array(points[6])
        
        expected_midpoint = (p3 + p4) / 2
        np.testing.assert_array_almost_equal(p6, expected_midpoint, decimal=5)

    def test_get_footprint_points_less_than_4_vertices_fallback(self) -> None:
        """Test fallback to centroid only when <4 vertices."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0.5, 0.5, 0],
        ])
        points = _get_footprint_points(vertices, None, 0.0)
        
        # Should only have P7 (centroid)
        assert len(points) == 1
        assert 7 in points


class TestGetElementThicknessDirect:
    """Tests for _get_element_thickness_direct helper function."""

    def test_get_element_thickness_direct_rectangular_wall(self) -> None:
        """Test thickness calculation for rectangular wall."""
        vertices = np.array([
            [0, 0, 0],
            [5, 0, 0],
            [5, 0.24, 0],
            [0, 0.24, 0],
        ])
        thickness = _get_element_thickness_direct(vertices)
        assert thickness > 0.0
        assert abs(thickness - 0.24) < 0.01

    def test_get_element_thickness_direct_insufficient_vertices(self) -> None:
        """Test with <3 vertices returns 0.0."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
        ])
        thickness = _get_element_thickness_direct(vertices)
        assert thickness == 0.0

    def test_get_element_thickness_direct_rotated_wall(self) -> None:
        """Test thickness for rotated wall (SVD should find correct axis)."""
        angle = np.pi / 6
        rotation = np.array([
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ])
        vertices = np.array([
            [0, 0],
            [5, 0],
            [5, 0.24],
            [0, 0.24],
        ])
        rotated = (rotation @ vertices.T).T
        vertices_3d = np.column_stack([rotated, np.zeros(4)])
        
        thickness = _get_element_thickness_direct(vertices_3d)
        assert thickness > 0.0
        assert abs(thickness - 0.24) < 0.01


class TestLineIntersection2d:
    """Tests for _line_intersection_2d helper function."""

    def test_line_intersection_2d_intersecting_lines(self) -> None:
        """Test intersection of two crossing lines."""
        p1, p2 = np.array([0, 0]), np.array([2, 2])
        a1, a2 = np.array([0, 2]), np.array([2, 0])
        
        intersection = _line_intersection_2d(p1, p2, a1, a2)
        
        assert len(intersection) == 2
        np.testing.assert_array_almost_equal(intersection, [1, 1], decimal=5)

    def test_line_intersection_2d_parallel_lines(self) -> None:
        """Test parallel lines (should return p1 as fallback)."""
        p1, p2 = np.array([0, 0]), np.array([2, 0])
        a1, a2 = np.array([0, 1]), np.array([2, 1])
        
        intersection = _line_intersection_2d(p1, p2, a1, a2)
        
        np.testing.assert_array_almost_equal(intersection, p1, decimal=5)

    def test_line_intersection_2d_perpendicular_lines(self) -> None:
        """Test perpendicular lines intersecting at origin."""
        p1, p2 = np.array([-1, 0]), np.array([1, 0])
        a1, a2 = np.array([0, -1]), np.array([0, 1])
        
        intersection = _line_intersection_2d(p1, p2, a1, a2)
        
        np.testing.assert_array_almost_equal(intersection, [0, 0], decimal=5)


class TestClipEdge:
    """Tests for _clip_edge helper function (Sutherland-Hodgman edge clipping)."""

    def test_clip_edge_point_inside(self) -> None:
        """Test clipping when all points are inside the clip edge."""
        # Edge from (0,0) to (0,3) - edge_vec=(0,3), normal=(-3,0) points to negative X
        # Points with x <= 0 are "inside" (dot product >= 0)
        subject = [np.array([-1.0, 0.0]), np.array([-2.0, 0.0]), np.array([-2.0, 1.0]), np.array([-1.0, 1.0])]
        edge_start = np.array([0.0, 0.0])
        edge_end = np.array([0.0, 3.0])
        
        result = _clip_edge(subject, edge_start, edge_end)
        
        assert len(result) == 4

    def test_clip_edge_point_outside(self) -> None:
        """Test clipping when points are outside the clip edge."""
        # Edge from (0,0) to (0,2) - normal points to negative X
        # Points with x > 0 are "outside"
        subject = [np.array([1.0, 0.0]), np.array([2.0, 0.0]), np.array([2.0, 1.0]), np.array([1.0, 1.0])]
        edge_start = np.array([0.0, 0.0])
        edge_end = np.array([0.0, 2.0])
        
        result = _clip_edge(subject, edge_start, edge_end)
        
        assert len(result) == 0  # All points outside, empty result

    def test_clip_edge_empty_input(self) -> None:
        """Test clipping with empty subject list."""
        result = _clip_edge([], np.array([0.0, 0.0]), np.array([1.0, 0.0]))
        assert len(result) == 0


class TestSortPolygonCcw:
    """Tests for _sort_polygon_ccw helper function."""

    def test_sort_polygon_ccw_clockwise_input(self) -> None:
        """Test sorting clockwise polygon to counter-clockwise."""
        vertices = np.array([
            [0, 0, 0],
            [0, 1, 0],
            [1, 1, 0],
            [1, 0, 0],
        ])
        sorted_vertices = _sort_polygon_ccw(vertices)
        assert sorted_vertices.shape == vertices.shape

    def test_sort_polygon_ccw_already_ccw(self) -> None:
        """Test sorting already CCW polygon."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
        ])
        sorted_vertices = _sort_polygon_ccw(vertices)
        assert sorted_vertices.shape == vertices.shape

    def test_sort_polygon_ccw_less_than_3_vertices(self) -> None:
        """Test sorting with <3 vertices returns copy."""
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
        ])
        sorted_vertices = _sort_polygon_ccw(vertices)
        np.testing.assert_array_almost_equal(sorted_vertices, vertices)

