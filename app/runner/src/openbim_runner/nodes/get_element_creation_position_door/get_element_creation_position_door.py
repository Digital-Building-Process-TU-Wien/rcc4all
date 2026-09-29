from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.references import ElementRef, parse_element_refs

FOOTPRINT_Z_TOLERANCE = 0.001  # 1mm tolerance for floating-point comparison (bottom vertices, in meters)


def _round_position(position: list[float]) -> list[float]:
    """Rundet Positionskoordinaten auf 3 Dezimalstellen (Millimeter-Genauigkeit)."""
    return [round(coord, 3) for coord in position]


class GetElementCreationPositionDoorSettings(NodeModel):
    point_index: Literal[1, 2, 3, 4, 5, 6, 7] = Field(
        default=7,
        title="Point index",
        description="Which footprint point to return: 1-4 = corners (clockwise from closest to placement), 5-6 = midpoints, 7 = centroid.",
    )


class GetElementCreationPositionDoorInputs(NodeModel):
    express_ids: list[str] = Field(
        default=[],
        title="Express IDs",
        description="Qualified element references (`<slug>:expr:<id>`) to get positions from. Bind ifc_element_filter output here.",
    )


class ElementRotation(NodeModel):
    rotation_x: float = Field(
        title="Rotation X",
        description="Rotation um globale X-Achse in Grad (0-360).",
    )
    rotation_y: float = Field(
        title="Rotation Y",
        description="Rotation um globale Y-Achse in Grad (0-360).",
    )
    rotation_z: float = Field(
        title="Rotation Z",
        description="Rotation um globale Z-Achse in Grad (0-360).",
    )


class ElementPositionResult(NodeModel):
    element_type: str = Field(
        title="Element Type",
        description="IFC entity type (IfcDoor or IfcWall).",
    )
    express_id: str = Field(
        title="Express ID",
        description="The qualified element reference (`<slug>:expr:<id>`).",
    )
    point_index: int = Field(
        title="Point index",
        description="Which point was returned (1-4 for corners, 5-6 for midpoints, 7 for centroid). P1-P6 require at least 4 bottom vertices.",
    )
    position: list[float] = Field(
        title="Position",
        description="World coordinates [x, y, z] in meters (rounded to 3 decimals / millimeter precision).",
    )
    rotation: ElementRotation | None = Field(
        default=None,
        title="Rotation",
        description="Euler-Rotationswinkel (X, Y, Z) in Grad (0-360). None wenn Placement nicht verfügbar.",
    )


class GetElementCreationPositionDoorResult(NodeModel):
    elements: list[ElementPositionResult] = Field(
        default=[],
        title="Elements",
        description="List of element positions (P7) for all processed doors and walls.",
    )





def _get_placement_matrix(placement: Any) -> np.ndarray:
    """
    Berechnet die vollständige 4x4 Transformationsmatrix aus einer Placement-Hierarchie.
    
    Rekursiv auflösen der PlacementRelTo-Kette bis zur Root.
    
    Args:
        placement: IfcLocalPlacement oder None
        
    Returns:
        4x4 numpy array (homogene Transformationsmatrix)
    """
    if not placement:
        return np.identity(4)
    
    if placement.is_a("IfcLocalPlacement"):
        parent_matrix = _get_placement_matrix(placement.PlacementRelTo)
        
        relative = placement.RelativePlacement
        if not relative:
            return parent_matrix
        
        if relative.is_a("IfcAxis2Placement3D"):
            coords = list(relative.Location.Coordinates)
            ref_dir = np.array(list(relative.RefDirection.DirectionRatios))
            axis = np.array(list(relative.Axis.DirectionRatios))
            
            x_axis = ref_dir / np.linalg.norm(ref_dir)
            z_axis = axis / np.linalg.norm(axis)
            y_axis = np.cross(z_axis, x_axis)
            
            rotation = np.array([
                [x_axis[0], y_axis[0], z_axis[0], coords[0]],
                [x_axis[1], y_axis[1], z_axis[1], coords[1]],
                [x_axis[2], y_axis[2], z_axis[2], coords[2]],
                [0, 0, 0, 1],
            ])
            
            return parent_matrix @ rotation
    
    return np.identity(4)


def _get_rotation_angles(placement: Any) -> dict[str, float]:
    """
    Extrahiert die 3 Euler-Rotationswinkel (X-Y-Z Reihenfolge) aus einer Placement-Hierarchie.
    
    Berechnet die Rotation der lokalen Achsen relativ zu den globalen Achsen.
    Winkel werden im Bereich 0° bis 360° zurückgegeben.
    
    Args:
        placement: IfcLocalPlacement oder None
        
    Returns:
        Dictionary mit Winkeln in Grad:
        {
            "rotation_x": 0.0,  # Rotation um globale X-Achse
            "rotation_y": 0.0,  # Rotation um globale Y-Achse
            "rotation_z": 0.0,  # Rotation um globale Z-Achse
        }
        Bei fehlendem Placement werden alle Winkel als 0.0 zurückgegeben.
    """
    if not placement or not placement.is_a("IfcLocalPlacement"):
        return {"rotation_x": 0.0, "rotation_y": 0.0, "rotation_z": 0.0}
    
    full_matrix = _get_placement_matrix(placement)
    
    R = full_matrix[:3, :3]
    
    rotation_x = math.atan2(R[2, 1], R[2, 2])
    rotation_y = math.atan2(-R[2, 0], math.sqrt(R[1, 0]**2 + R[0, 0]**2))
    rotation_z = math.atan2(R[1, 0], R[0, 0])
    
    rotation_x_deg = math.degrees(rotation_x)
    rotation_y_deg = math.degrees(rotation_y)
    rotation_z_deg = math.degrees(rotation_z)
    
    def normalize_angle(angle: float) -> float:
        return angle % 360.0
    
    return {
        "rotation_x": round(normalize_angle(rotation_x_deg), 3),
        "rotation_y": round(normalize_angle(rotation_y_deg), 3),
        "rotation_z": round(normalize_angle(rotation_z_deg), 3),
    }


def _extract_4_corners(bottom_vertices: np.ndarray) -> np.ndarray:
    """
    Extrahiert 4 äußere Eckpunkte aus N Bottom-Vertices mittels PCA.
    
    Verwendet SVD zur Bestimmung der Hauptachsen und bildet ein OBB
    (Oriented Bounding Box) um alle Vertices. Die 4 Ecken des OBB werden
    als neue Bottom-Vertices zurückgegeben.
    
    Args:
        bottom_vertices: N x 3 array of bottom vertices in world coordinates
        
    Returns:
        4 x 3 array mit den 4 extrahierten Eckpunkten (world coordinates)
    """
    center = bottom_vertices.mean(axis=0)
    centered = bottom_vertices - center
    U, S, Vh = np.linalg.svd(centered, full_matrices=False)
    
    x_axis = Vh[0]  # Hauptachse (Länge)
    y_axis = Vh[1]  # Zweitachse (Dicke)
    
    # Projektion auf Achsen → Min/Max → 4 Ecken (zentrierte Koordinaten!)
    x_proj = centered @ x_axis
    y_proj = centered @ y_axis
    
    local_corners = np.array([
        [x_proj.min(), y_proj.min()],
        [x_proj.max(), y_proj.min()],
        [x_proj.max(), y_proj.max()],
        [x_proj.min(), y_proj.max()],
    ])
    
    # Rücktransformation ins Welt-Koordinatensystem
    corners_3d = np.zeros((4, 3))
    for i in range(4):
        corners_3d[i, :3] = (
            center +
            local_corners[i, 0] * x_axis +
            local_corners[i, 1] * y_axis
        )
    
    return corners_3d


def _get_element_centroid(
    element: Any,
    return_bottom_vertices: bool = False,
) -> list[float] | None | tuple[list[float] | None, np.ndarray | None, float | None]:
    """
    Berechnet den geometrischen Schwerpunkt (Centroid) eines Elements als 3D-Punkt.
    Verwendet die 2D-Footprint-Methode wie Solibri: X,Y aus den unteren Eckpunkten,
    Z auf Boden-Level.

    Args:
        element: IfcOpeningElement or IfcWall entity
        return_bottom_vertices: If True, returns (centroid, bottom_vertices) tuple

    Returns:
        [x, y, z] in Weltkoordinaten (Meter), oder None wenn Geometrie nicht verfügbar.
        If return_bottom_vertices is True, returns (centroid, bottom_vertices) tuple.
    """
    # Fallback-Kette für Context-Types: "Body" (3D) → "FootPrint" (2D) → "Axis" → "SurveyPoints"
    context_types_list = [["Body"], ["FootPrint"], ["Axis"], ["SurveyPoints"]]
    
    for context_types in context_types_list:
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("weld-vertices", True)
        settings.set("context-types", context_types)

        try:
            shape = ifcopenshell.geom.create_shape(settings, element)  # pyright: ignore[reportUnknownVariableType]

            # ifcopenshell stubs have incomplete type info; attributes exist at runtime
            geometry = shape.geometry  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
            if len(geometry.verts) == 0 or len(geometry.faces) == 0:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                continue  # Leere Geometrie → nächster Context-Type

            vertices = np.array(geometry.verts).reshape((-1, 3))  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            
            # Finde untere Kante (Boden des Elements)
            min_z = vertices[:, 2].min()
            bottom_mask = np.isclose(vertices[:, 2], min_z, atol=FOOTPRINT_Z_TOLERANCE)
            bottom_vertices = vertices[bottom_mask]
            
            # Bei >4 Vertices: OBB-basierte Eckpunktfindung (nur 4 Ecken)
            if len(bottom_vertices) > 4:
                bottom_vertices = _extract_4_corners(bottom_vertices)
            
            # Brauchen mindestens 4 Punkte für validen 2D-Centroid (rechteckige Öffnung)
            if len(bottom_vertices) >= 4:
                # 2D-Centroid aus unteren Eckpunkten (X, Y Mittelwert)
                centroid_x = bottom_vertices[:, 0].mean()
                centroid_y = bottom_vertices[:, 1].mean()
                centroid_z = min_z
            else:
                # Fallback: 3D-Mesh-Centroid wenn zu wenige Boden-Punkte (<4)
                faces = np.array(geometry.faces).reshape((-1, 3))  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
                centroid_x, centroid_y, centroid_z = mesh.centroid
            
            centroid = [float(centroid_x), float(centroid_y), float(centroid_z)]  # pyright: ignore[reportUnknownMemberType]
            
            if return_bottom_vertices:
                return centroid, bottom_vertices, min_z
            return centroid

        except Exception:
            # Fehler bei diesem Context-Type → versuche nächsten
            continue
    
    # Alle Context-Types fehlgeschlagen → Fallback: Iterator für Bounding Box
    # (funktioniert auch für Curve2D, Axis, etc. ohne 3D-Mesh)
    try:
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("context-types", ["Body", "FootPrint", "Axis", "SurveyPoints"])
        
        iterator = ifcopenshell.geom.iterator(settings, [element])
        iterator.initialize()
        shape = iterator.get()
        
        if shape:
            bounds_min = iterator.bounds_min()  # point3 (x, y, z)
            bounds_max = iterator.bounds_max()  # point3 (x, y, z)
            
            # Centroid aus BBox
            centroid_x = (bounds_min[0] + bounds_max[0]) / 2
            centroid_y = (bounds_min[1] + bounds_max[1]) / 2
            centroid_z = bounds_min[2]  # Bottom-Z
            
            # 4 Bottom-Vertices aus BBox (Rechteck in X/Y, Z = min)
            bottom_vertices = np.array([
                [bounds_min[0], bounds_min[1], bounds_min[2]],
                [bounds_max[0], bounds_min[1], bounds_min[2]],
                [bounds_max[0], bounds_max[1], bounds_min[2]],
                [bounds_min[0], bounds_max[1], bounds_min[2]],
            ])
            
            centroid = [float(centroid_x), float(centroid_y), float(centroid_z)]
            
            if return_bottom_vertices:
                return centroid, bottom_vertices, centroid_z
            return centroid
    except Exception:
        # Auch Iterator-Fallback fehlgeschlagen
        pass
    
    # Alle Methoden fehlgeschlagen
    return (None, None, None) if return_bottom_vertices else None


def _get_footprint_points(
    bottom_vertices: np.ndarray,
    placement: Any,
    min_z: float,
) -> dict[int, list[float]]:
    """
    Calculates all 7 footprint points (P1-P4, P5-P6, P7) for an element with bottom vertices.

    Used for IfcWall and IfcOpeningElement (door openings).

    Args:
        bottom_vertices: N x 3 array of bottom vertices in world coordinates
        placement: IfcLocalPlacement of the element (IfcWall or IfcOpeningElement)
        min_z: Bottom elevation (Z coordinate) in meters

    Returns:
        Dictionary with point indices as keys and [x, y, z] world coordinates as values.
        Points are sorted clockwise in local coordinate system starting from P1:
        - P1: corner closest to placement location (local origin)
        - P2: next corner clockwise
        - P3: next corner clockwise
        - P4: next corner clockwise
        - P5: midpoint between P1 and P2
        - P6: midpoint between P3 and P4
        - P7: centroid (center point)
    """
    if len(bottom_vertices) < 4:
        # Fallback: only centroid (P7) for openings with <4 vertices (e.g., triangular)
        centroid = [
            float(bottom_vertices[:, 0].mean()),
            float(bottom_vertices[:, 1].mean()),
            min_z,
        ]
        return {7: centroid}
    
    # 1. Vollständige Placement-Matrix berechnen
    full_matrix = _get_placement_matrix(placement)
    
    # 2. Inverse Matrix für Welt → Lokal Transformation
    inv_matrix = np.linalg.inv(full_matrix)
    
    # 3. Alle Vertices ins lokale System transformieren
    ones = np.ones((len(bottom_vertices), 1))
    verts_homogeneous = np.hstack([bottom_vertices, ones])
    local_verts_homogeneous = (inv_matrix @ verts_homogeneous.T).T
    local_verts_array = local_verts_homogeneous[:, :3]
    
    # 4. Bei >4 Vertices: Sollte nicht mehr vorkommen (OBB in _get_element_centroid)
    # Fallback: Centroid berechnen
    if len(bottom_vertices) > 4:
        centroid = [
            float(bottom_vertices[:, 0].mean()),
            float(bottom_vertices[:, 1].mean()),
            min_z,
        ]
        return {7: centroid}
    
    # Bei exakt 4 Vertices: direkte Verwendung mit Sortierung
    # P1 finden: Ecke mit geringstem Abstand zu Location (lokaler Ursprung 0,0)
    def distance_to_origin(p: np.ndarray) -> float:
        return math.sqrt(p[0]**2 + p[1]**2)
    
    # Alle 4 Punkte nach Winkel um Centroid sortieren (clockwise)
    centroid_x = np.mean(local_verts_array[:, 0])
    centroid_y = np.mean(local_verts_array[:, 1])
    
    def angle_from_centroid(p: np.ndarray) -> float:
        return math.atan2(p[1] - centroid_y, p[0] - centroid_x)
    
    # Sortiere nach Winkel (counter-clockwise), dann reverse für clockwise
    local_verts_sorted = sorted(local_verts_array, key=angle_from_centroid)
    local_verts_sorted.reverse()  # Clockwise
    
    # P1 finden (nächste Ecke zum Ursprung) und Liste rotieren
    p1_index = min(range(4), key=lambda i: distance_to_origin(local_verts_sorted[i]))
    local_verts_final = local_verts_sorted[p1_index:] + local_verts_sorted[:p1_index]
    
    # 5. P5 und P6 berechnen (Mittelpunkte)
    p1_local = local_verts_final[0]
    p2_local = local_verts_final[1]
    p3_local = local_verts_final[2]
    p4_local = local_verts_final[3]
    
    # P5 = Mittelpunkt zwischen P1 und P2
    p5_local = (
        (p1_local[0] + p2_local[0]) / 2,
        (p1_local[1] + p2_local[1]) / 2,
        p1_local[2],
    )
    
    # P6 = Mittelpunkt zwischen P3 und P4
    p6_local = (
        (p3_local[0] + p4_local[0]) / 2,
        (p3_local[1] + p4_local[1]) / 2,
        p3_local[2],
    )
    
    # 6. Helper-Funktion: Lokale Koordinaten zurück ins Weltkoordinatensystem
    def to_world(local_point: np.ndarray) -> list[float]:
        lx, ly, lz = local_point[0], local_point[1], local_point[2]
        world = full_matrix @ np.array([lx, ly, lz, 1])
        return [float(world[0]), float(world[1]), float(world[2])]
    
    # 7. Alle Punkte zurückgeben
    p1_world = to_world(p1_local)
    p2_world = to_world(p2_local)
    p3_world = to_world(p3_local)
    p4_world = to_world(p4_local)
    
    # P7 = Centroid der 4 Ecken (Weltkoordinaten)
    p7_world = [
        (p1_world[0] + p2_world[0] + p3_world[0] + p4_world[0]) / 4,
        (p1_world[1] + p2_world[1] + p3_world[1] + p4_world[1]) / 4,
        (p1_world[2] + p2_world[2] + p3_world[2] + p4_world[2]) / 4,
    ]
    
    return {
        1: p1_world,  # P1: nächste Ecke zu Location
        2: p2_world,  # P2: clockwise weiter
        3: p3_world,  # P3: clockwise weiter
        4: p4_world,  # P4: clockwise weiter
        5: to_world(p5_local),  # P5: Mittelpunkt P1-P2
        6: to_world(p6_local),  # P6: Mittelpunkt P3-P4
        7: p7_world,  # Centroid
    }



@node()
async def get_element_creation_position_door(
    settings: GetElementCreationPositionDoorSettings,
    inputs: GetElementCreationPositionDoorInputs,
    context: ExecutionContext,
) -> GetElementCreationPositionDoorResult:
    if not inputs.express_ids:
        return GetElementCreationPositionDoorResult(elements=[])

    # Build mappings once before the loop (O(n) instead of O(n²))
    door_to_opening_map: dict[int, Any] = {}
    for rel in context.ifc_model.by_type("IfcRelFillsElement"):
        door = rel.RelatedBuildingElement
        opening = rel.RelatingOpeningElement
        if door and door.is_a("IfcDoor") and opening:
            door_to_opening_map[door.id()] = opening

    opening_to_wall_map: dict[int, Any] = {}
    for rel in context.ifc_model.by_type("IfcRelVoidsElement"):
        opening = rel.RelatedOpeningElement
        wall = rel.RelatingBuildingElement
        if opening and wall:
            opening_to_wall_map[opening.id()] = wall

    elements = []
    for element_ref in parse_element_refs(inputs.express_ids, node="get_element_creation_position_door"):
        try:
            model = context.resolve_model(element_ref.slug)
            entity = model.by_id(element_ref.express_id)
        except (RuntimeError, ValueError):
            continue

        if entity.is_a("IfcDoor"):
            element_type = "IfcDoor"
            
            # Get opening from pre-built map (O(1) lookup)
            opening = door_to_opening_map.get(entity.id())
            if opening is None:
                continue

            centroid, bottom_vertices, min_z = _get_element_centroid(opening, return_bottom_vertices=True)
            if centroid is None or bottom_vertices is None or min_z is None:
                continue
            
            # For openings with 4+ vertices, support all 7 points (P1-P7)
            if len(bottom_vertices) >= 4 and opening.ObjectPlacement:
                # === Thickness detection & clipping ===
                wall = opening_to_wall_map.get(opening.id())
                wall_bottom_vertices = None
                if wall is not None:
                    _, wall_bottom_vertices, _ = _get_element_centroid(wall, return_bottom_vertices=True)
                
                thickness_info = _get_thickness_info(
                    bottom_vertices,
                    wall_bottom_vertices,
                    tolerance=0.01,
                )
                
                if thickness_info.needs_clipping and wall_bottom_vertices is not None:
                    bottom_vertices = _clip_opening_to_wall_polygon(
                        bottom_vertices,
                        wall_bottom_vertices,
                    )
                # === End thickness detection & clipping ===
                
                all_points = _get_footprint_points(bottom_vertices, opening.ObjectPlacement, min_z)
                position = all_points.get(settings.point_index, centroid)
            else:
                # Fallback: only centroid (P7)
                position = centroid

        elif entity.is_a("IfcWall"):
            element_type = "IfcWall"
            centroid, bottom_vertices, min_z = _get_element_centroid(entity, return_bottom_vertices=True)
            if centroid is None or bottom_vertices is None or min_z is None:
                continue
            
            if len(bottom_vertices) >= 4 and entity.ObjectPlacement:
                all_points = _get_footprint_points(bottom_vertices, entity.ObjectPlacement, min_z)
                position = all_points.get(settings.point_index, centroid)
            else:
                position = centroid

        else:
            continue

        rotation: ElementRotation | None = None
        if entity.ObjectPlacement:
            rotation_angles = _get_rotation_angles(entity.ObjectPlacement)
            rotation = ElementRotation(
                rotation_x=rotation_angles["rotation_x"],
                rotation_y=rotation_angles["rotation_y"],
                rotation_z=rotation_angles["rotation_z"],
            )

        elements.append(
            ElementPositionResult(
                element_type=element_type,
                express_id=element_ref.reference,
                point_index=settings.point_index,
                position=_round_position(position),
                rotation=rotation,
            )
        )

    return GetElementCreationPositionDoorResult(elements=elements)


# =============================================================================
# THICKNESS DETECTION & CLIPPING HELPERS (for Todo #2)
# =============================================================================


@dataclass
class ThicknessInfo:
    """Internal dataclass for thickness analysis results."""
    opening_thickness: float
    wall_thickness: float | None
    needs_clipping: bool


def _build_opening_to_wall_map(ifc_model: Any) -> dict[int, Any]:
    """
    Build O(1) lookup map: opening_id → wall entity via IfcRelVoidsElement.
    
    Args:
        ifc_model: IFC model instance
        
    Returns:
        Dictionary mapping opening express IDs to their associated wall entities
    """
    mapping: dict[int, Any] = {}
    for rel in ifc_model.by_type("IfcRelVoidsElement"):
        opening = rel.RelatedOpeningElement
        wall = rel.RelatingBuildingElement
        if opening and wall:
            mapping[opening.id()] = wall
    return mapping


def _get_element_thickness_direct(bottom_vertices: np.ndarray) -> float:
    """
    Berechnet Dicke direkt aus Bottom-Vertices im Welt-Space.
    
    Verwendet SVD zur Bestimmung der Wand-Orientierung.
    Dicke = tatsächliche Ausdehnung entlang der Dicke-Achse (nicht SVD-Singularwert!).
    
    Args:
        bottom_vertices: N x 3 array of bottom vertices in world coordinates
        
    Returns:
        Thickness in meters (always >= 0). Returns 0.0 if insufficient vertices.
    """
    if len(bottom_vertices) < 3:
        return 0.0
    
    try:
        # SVD für Achsen-Bestimmung
        center = bottom_vertices.mean(axis=0)
        centered = bottom_vertices - center
        U, S, Vh = np.linalg.svd(centered, full_matrices=False)
        
        # Vh[0] = Längsachse, Vh[1] = Dicke-Achse
        thickness_axis = Vh[1]
        
        # Echte Dicke = Projektion aller Vertices auf Dicke-Achse
        projections = centered @ thickness_axis
        thickness = float(projections.max() - projections.min())
        
        return max(0.0, thickness)
        
    except Exception:
        return 0.0


def _get_thickness_info(
    opening_bottom_vertices: np.ndarray,
    wall_bottom_vertices: np.ndarray | None,
    tolerance: float = 0.01,
) -> ThicknessInfo:
    """
    Ermittelt Dicken-Informationen für Opening und Wand direkt aus Bottom-Vertices.
    
    Opening-Dicke wird nicht aus sich selbst berechnet (SVD würde ggf. die falsche
    Achse finden). Stattdessen werden die Opening-Vertices auf die Wand-Dickenachse
    projiziert und die Ausdehnung dort gemessen.
    
    Args:
        opening_bottom_vertices: N x 3 array of opening bottom vertices (world coordinates)
        wall_bottom_vertices: M x 3 array of wall bottom vertices (world coordinates) or None
        tolerance: Relative tolerance for thickness comparison (default: 1%)
        
    Returns:
        ThicknessInfo with needs_clipping flag (True if opening > wall * 1.01)
    """
    if wall_bottom_vertices is None or len(wall_bottom_vertices) == 0:
        return ThicknessInfo(
            opening_thickness=0.0,
            wall_thickness=None,
            needs_clipping=False,
        )
    
    # Wand-Dicke berechnen (SVD auf Wand-Bottom)
    wall_thickness = _get_element_thickness_direct(wall_bottom_vertices)
    
    # Wand-Dickenachse bestimmen (SVD auf Wand-Bottom)
    wall_center = wall_bottom_vertices.mean(axis=0)
    wall_centered = wall_bottom_vertices - wall_center
    U, S, Vh = np.linalg.svd(wall_centered, full_matrices=False)
    thickness_axis = Vh[1]
    
    # Opening-Ausdehnung auf der Wand-Dickenachse projizieren
    opening_centered = opening_bottom_vertices - wall_center
    opening_proj = opening_centered @ thickness_axis
    opening_extent = float(opening_proj.max() - opening_proj.min())
    
    # needs_clipping = Opening geht über Wand-Dicke hinaus
    needs_clipping = opening_extent > wall_thickness * (1.0 + tolerance)
    
    return ThicknessInfo(
        opening_thickness=opening_extent,
        wall_thickness=wall_thickness,
        needs_clipping=needs_clipping,
    )


def _line_intersection_2d(p1: np.ndarray, p2: np.ndarray, a1: np.ndarray, a2: np.ndarray) -> np.ndarray:
    """
    Berechnet 2D-Schnittpunkt der Linie (p1,p2) mit der Linie (a1,a2).
    
    Parametrische Form:
        P = p1 + t * (p2 - p1)
        A = a1 + s * (a2 - a1)
    
    Löse P = A nach t auf → setze t in P ein.
    
    Args:
        p1, p2: Endpunkte der ersten Linie (2D)
        a1, a2: Endpunkte der zweiten Linie (2D)
        
    Returns:
        np.ndarray([x, y]) - Schnittpunkt in 2D
    """
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    x3, y3 = a1[0], a1[1]
    x4, y4 = a2[0], a2[1]
    
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        # Parallele Linien → Rückgabe von p1
        return p1[:2].copy()
    
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    
    return np.array([
        x1 + t * (x2 - x1),
        y1 + t * (y2 - y1),
    ])


def _clip_edge(subject_list: list[np.ndarray], edge_start: np.ndarray, edge_end: np.ndarray) -> list[np.ndarray]:
    """
    Sutherland-Hodgman: Clipp-Logik für eine Wand-Kante.
    
    Für jede Kante im Polygon:
    - Full Inside → Ecken übernehmen
    - Inside → Outside → Schnittpunkt + Ecke
    - Outside → Inside → Schnittpunkt
    - Full Outside → nichts
    
    Args:
        subject_list: Liste von 2D-Vertices des Opening-Polygons
        edge_start, edge_end: Start/Ende der Clip-Edge (Wand-Kante)
        
    Returns:
        Liste von 2D-Vertices nach dem Clipping gegen diese Kante
    """
    output_list = []
    
    if len(subject_list) == 0:
        return output_list
    
    # Edge-Vektor und Normalenvektor (zeigt nach innen)
    edge_vec = edge_end - edge_start
    edge_normal = np.array([-edge_vec[1], edge_vec[0]])
    
    def is_inside(point: np.ndarray) -> bool:
        # Punkt ist inside wenn er auf der "inneren" Seite der Kante liegt
        # Normalzeiger zeigt nach innen (CCW) → dot product >= 0 means inside
        return np.dot(point - edge_start, edge_normal) >= 0
    
    for i in range(len(subject_list)):
        current = subject_list[i]
        previous = subject_list[(i - 1) % len(subject_list)]
        
        current_inside = is_inside(current)
        previous_inside = is_inside(previous)
        
        if current_inside:
            if not previous_inside:
                # Eintritt: Schnittpunkt berechnen
                intersection = _line_intersection_2d(previous, current, edge_start, edge_end)
                output_list.append(intersection)
            output_list.append(current)
        elif previous_inside:
            # Austritt: Schnittpunkt berechnen
            intersection = _line_intersection_2d(previous, current, edge_start, edge_end)
            output_list.append(intersection)
    
    return output_list


def _sort_polygon_ccw(vertices: np.ndarray) -> np.ndarray:
    """
    Sortiert Polygon-Punkte counter-clockwise um den Mittelpunkt.
    
    Wichtig für Sutherland-Hodgman: Das Clipping-Polygon muss korrekt
    sortiert sein (nicht überkreuzt), sonst entstehen falsche Kanten.
    
    Args:
        vertices: N x 3 array of vertices (world coordinates)
        
    Returns:
        N x 3 array mit nach Winkel sortierten Vertices (counter-clockwise)
    """
    if len(vertices) < 3:
        return vertices.copy()
    
    center = vertices.mean(axis=0)
    angles = np.arctan2(vertices[:, 1] - center[1], vertices[:, 0] - center[0])
    sorted_indices = np.argsort(angles)
    return vertices[sorted_indices]


def _clip_opening_to_wall_polygon(
    opening_bottom_vertices: np.ndarray,
    wall_bottom_vertices: np.ndarray,
) -> np.ndarray:
    """
    Clippt Opening-Polygon gegen Wand-Rechteck mittels Sutherland-Hodgman.
    
    1. Sortiere beide Polygone counter-clockwise (wichtig für korrekte Kanten!)
    2. Wand-4-Corners als 2D-Rechteck (X/Y)
    3. Sutherland-Hodgman gegen 4 Wand-Kanten (jeweils Linie)
    4. Fallback wenn <4 Opening-Vertices → original zurück
    5. Fehler wenn <4 Wall-Vertices
    6. Fallback wenn kein Überlappung → original zurück
    
    Args:
        opening_bottom_vertices: N x 3 array of opening bottom vertices (world coordinates)
        wall_bottom_vertices: M x 3 array of wall bottom vertices (world coordinates)
        
    Returns:
        N x 3 array of clipped vertices (world coordinates)
        
    Raises:
        ValueError: If wall has fewer than 4 bottom vertices.
    """
    # Wall < 4 → ValueError
    if len(wall_bottom_vertices) < 4:
        raise ValueError(f"Wall must have at least 4 bottom vertices, got {len(wall_bottom_vertices)}")
    
    # <4 Opening-Vertices → Fallback (original)
    if len(opening_bottom_vertices) < 4:
        return opening_bottom_vertices.copy()
    
    # Beide Polygone sortieren (counter-clockwise) für korrekte Kanten-Reihenfolge
    opening_sorted = _sort_polygon_ccw(opening_bottom_vertices)
    wall_sorted = _sort_polygon_ccw(wall_bottom_vertices)
    
    # Wand-Corners als 2D-Rechteck (X/Y)
    wall_rect = wall_sorted[:, :2]
    
    # Öffne mit sortierten Opening-Ecken (2D)
    output_vertices = [v[:2].copy() for v in opening_sorted]
    
    # Sutherland-Hodgman gegen jede der 4 Wand-Kanten
    for i in range(4):
        p1 = wall_rect[i]
        p2 = wall_rect[(i + 1) % 4]
        output_vertices = _clip_edge(output_vertices, p1, p2)
    
    # Check ob Ergebnis leer (kein Überlappung)
    if len(output_vertices) == 0:
        return opening_bottom_vertices.copy()  # Fallback
    
    # Zurück nach 3D (Z = Bodenhöhe)
    z = min(opening_bottom_vertices[:, 2].min(), wall_bottom_vertices[:, 2].min())
    return np.column_stack([output_vertices, np.full(len(output_vertices), z)])




