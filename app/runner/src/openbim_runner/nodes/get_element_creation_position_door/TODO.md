# Ausstehende Verbesserungen

## 1. Fokus auf Türen ✅ ABGESCHLOSSEN
- [x] Aktuell unterstützt der Node IfcDoor UND IfcWall
- [x] Primärer Use-Case: IfcDoor (über IfcOpeningElement)
- [x] IfcWall-Unterstützung bleibt als optionales Feature erhalten

## 2. Extrem dicke Öffnungen ✅ ABGESCHLOSSEN (v2.0)
- [x] Öffnungen mit größerer Dicke als Wanddicke erkennen
- [x] Footprint-Punkte auf tatsächliche Wanddicke zuschneiden
- [x] Algorithmus: Dicke aus Opening-Geometrie extrahieren und validieren
- [x] Edge-Case: Öffnung dicker als angrenzende Wand(en)
- [x] 1% Toleranz für Floating-Point-Ungenauigkeiten
- [x] Sutherland-Hodgman Polygon Clipping implementiert

**Bekannte Limitationen:**
- ⚠️ Erfordert 3D-tessellierte Wand-Geometrie (Body Representation)
- ⚠️ Funktioniert NICHT mit IfcAxis2Placement oder IfcBuildingElementPart
- ⚠️ Nur placement-aligned Clipping (nicht symmetrisch)

### 2.1 Clipping-Info als Output ⏳ OFFEN
- [ ] Neue Output-Felder: `opening_thickness`, `wall_thickness`, `was_clipped`
- [ ] Doku: Wann wurde geclippt und warum
- [ ] Test: Clipping-Info validieren

### 2.2 Edge-Case: Wand ohne Geometrie ⏳ OFFEN
- [ ] Fallback wenn `wall_bottom_vertices is None`
- [ ] Option A: Opening-Placement verwenden (keine Wand-Info)
- [ ] Option B: Warning loggen und Clipping überspringen
- [ ] Option C: User-Configurable Behavior (skip/warn/error)

## 3. Türrichtung / Rotation bestimmen ⏳ OFFEN

### Ansatz D (PRIMÄR): Opening-Placement verwenden
```python
if opening.ObjectPlacement:
    if opening.ObjectPlacement.is_a('IfcLocalPlacement'):
        relative = opening.ObjectPlacement.RelativePlacement
        if relative.is_a('IfcAxis2Placement3D'):
            # RefDirection = lokale X-Achse (Tür "vorne")
            ref_dir = relative.RefDirection.DirectionRatios
            axis = relative.Axis.DirectionRatios
            
            # Normalisiere Vektoren
            x_axis = np.array(ref_dir) / np.linalg.norm(ref_dir)
            z_axis = np.array(axis) / np.linalg.norm(axis)
            
            # Y-Achse berechnen (cross product für rechtshändiges System)
            y_axis = np.cross(z_axis, x_axis)
            
            # Rotation um Z-Achse (Yaw)
            yaw_angle = math.atan2(x_axis[1], x_axis[0])
```

**Vorteile:**
- ✅ Opening-Placement ist zuverlässiger als Door-Placement
- ✅ Funktioniert auch wenn Door kein eigenes Placement hat
- ✅ Öffnungsrichtung ist konsistent mit Wand-Orientierung

**Nachteile:**
- ❌ Erfordert `IfcAxis2Placement3D` (nicht bei LOD 100)
- ❌ Nur 2D-Rotation (X/Y-Ebene)

---

### Ansatz A (FALLBACK 1): Door-Placement verwenden
```python
# Vollständige Placement-Matrix berechnen (rekursiv über PlacementRelTo)
full_matrix = _get_placement_matrix(door.ObjectPlacement)

# Rotationsmatrix extrahieren (3x3)
rotation_matrix = full_matrix[:3, :3]

# Winkel um Z-Achse (Yaw für Tür-Rotation)
yaw_angle = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
```

**Vorteile:**
- ✅ Exakte Rotation aus IFC-Placement
- ✅ Unterstützt volle 3D-Rotation (nicht nur Z-Achse)
- ✅ Unabhängig von Geometrie-Tessellation

**Nachteile:**
- ❌ Erfordert `ObjectPlacement` (kann bei LOD 100 fehlen)
- ❌ RelativePlacement muss IfcAxis2Placement3D sein
- ❌ Rotation ist relativ zur Placement Location (nicht absolut)

---

### Ansatz B (FALLBACK 2): Footprint-Punkte verwenden
```python
# P1 → P2 Vektor als "Vorne"-Referenz (lokale X-Achse)
p1 = all_points[1]  # Nächste Ecke zu Placement Location
p2 = all_points[2]  # Clockwise weiter

# Türrichtung (Normalenvektor in X/Y-Ebene)
door_normal = np.array([p2[0] - p1[0], p2[1] - p1[1]])
door_normal = door_normal / np.linalg.norm(door_normal)

# Winkel in X/Y-Ebene (0° = Osten, clockwise)
yaw_angle = math.atan2(door_normal[1], door_normal[0])
```

**Vorteile:**
- ✅ Einfach zu implementieren
- ✅ Funktioniert immer wenn Footprint-Punkte verfügbar sind
- ✅ Unabhängig von Placement-Matrix

**Nachteile:**
- ❌ Nur 2D-Rotation (X/Y-Ebene)
- ❌ Erfordert 4+ Bottom-Vertices für P1/P2
- ❌ Rotation ist relativ zur Placement-Orientation (nicht absolute Himmelsrichtung)

---

### Ansatz C (ZUSÄTZLICH): IfcDoor.Attribute verwenden
```python
# IfcDoor Attribute prüfen (IFC4)
if hasattr(door, 'Orientation'):
    orientation = door.Orientation  # IfcOrientationSelect
    
if hasattr(door, 'Eingangsrichtung'):  # IFC2x3
    direction = door.Eingangsrichtung  # IfcDirectionLabel
    
# IfcDoorType hat oft Standard-Orientation
if hasattr(door, 'DoorType'):
    door_type = door.DoorType
    if hasattr(door_type, 'HasPropertySets'):
        # PSet_DoorCommon enthält Orientation Angle
        for pset in door_type.HasPropertySets:
            if pset.is_a('IfcPropertySet'):
                for prop in pset.HasProperties:
                    if prop.Name == 'OrientationAngle':
                        yaw_angle = prop.NominalValue.wrappedValue
```

**Vorteile:**
- ✅ Semantisch korrekte Information (vom Modellierer definiert)
- ✅ Unabhängig von Geometrie und Placement
- ✅ Enthält oft zusätzliche Info (Öffnungswinkel, Drehpunkt)

**Nachteile:**
- ❌ Nicht alle IFC-Dateien enthalten diese Attribute
- ❌ Unterschiedliche Schemata (IFC2x3 vs IFC4)
- ❌ PropertySets sind optional und inkonsistent

---

### Implementierungs-Strategie

**Priorisierte Reihenfolge:**
```
1. Ansatz D (Opening-Placement) → PRIMÄR
   ↓ (falls nicht verfügbar)
2. Ansatz A (Door-Placement) → FALLBACK 1
   ↓ (falls nicht verfügbar)
3. Ansatz B (Footprint-Punkte) → FALLBACK 2
   ↓ (falls nicht verfügbar)
4. Ansatz C (IfcDoor.Attribute) → ZUSÄTZLICHE INFO
```

**Geplante Output-Felder:**
```python
class ElementPositionResult(NodeModel):
    element_type: str
    express_id: int
    point_index: int
    position: list[float]
    
    # NEU: Tür-Rotation
    rotation_yaw: float | None = None  # Winkel in Radiant (-π bis +π)
    rotation_source: str | None = None  # "opening_placement", "door_placement", "footprint", "attribute"
    
    # NEU: Clipping-Info (Abschnitt 2.1)
    opening_thickness: float | None = None
    wall_thickness: float | None = None
    was_clipped: bool = False
```

**Aufgaben:**
- [ ] **Ansatz D (PRIMÄR):** Opening-Placement verwenden
  - [ ] RefDirection als X-Achse extrahieren
  - [ ] Yaw-Winkel berechnen: `atan2(x_axis[1], x_axis[0])`
  - [ ] Output: `rotation_yaw` (Radiant, -π bis +π)
  
- [ ] **Ansatz A (FALLBACK 1):** Door-Placement verwenden
  - [ ] Vollständige Placement-Matrix berechnen
  - [ ] Rotation um Z-Achse extrahieren
  
- [ ] **Ansatz B (FALLBACK 2):** Footprint-Punkte verwenden
  - [ ] P1→P2 Vektor als Tür-"vorne"
  - [ ] 2D-Winkel in X/Y-Ebene
  
- [ ] **Ansatz C (ZUSÄTZLICH):** IfcDoor.Attribute
  - [ ] Orientation Angle aus PropertySets
  - [ ] Eingangsrichtung (IFC2x3)
  
- [ ] Output-Felder:
  - [ ] `rotation_yaw: float | None`
  - [ ] `rotation_source: str | None` ("opening_placement", "door_placement", "footprint", "attribute")
  - [ ] Optional: `rotation_pitch`, `rotation_roll` (für 3D-Türen)

## 4. Wand-Repräsentation Fallback ⏳ OFFEN (kritisch)
- [ ] **Problem:** Aktuell nur Body Representation unterstützt
- [ ] **Nicht unterstützt:**
  - [ ] IfcAxis2Placement (2D-Achse)
  - [ ] IfcBuildingElementPart
  - [ ] LOD 100/200 Modelle ohne 3D-Geometrie
- [ ] **Lösung:** Fallback-Kaskade implementieren
  - [ ] Stufe 1: Body (3D tesselliert) → `_get_element_centroid()`
  - [ ] Stufe 2: Axis (2D) → Bounding Box aus AxisCurve
  - [ ] Stufe 3: FootPrint → 2D-Footprint extrahieren
  - [ ] Stufe 4: SurveyPoints → Punkte interpolieren

## Quellen
- Leos Diplomarbeit: [Pfad/Link einfügen]
