# Ausstehende Verbesserungen

## 1. Fokus auf Türen ✅ ABGESCHLOSSEN
- [x] Primärer Use-Case: IfcDoor (über IfcOpeningElement)
- [x] IfcWall-Unterstützung als optionales Feature erhalten

## 2. Extrem dicke Öffnungen ✅ ABGESCHLOSSEN (v2.0)
- [x] Öffnungen mit größerer Dicke als Wanddicke erkennen
- [x] Footprint-Punkte auf tatsächliche Wanddicke zuschneiden
- [x] Sutherland-Hodgman Polygon Clipping implementiert
- [x] 1% Toleranz für Floating-Point-Ungenauigkeiten

**Bekannte Limitationen:**
- ⚠️ Erfordert 3D-tessellierte Wand-Geometrie (Body Representation)
- ⚠️ Funktioniert NICHT mit IfcAxis2Placement oder IfcBuildingElementPart
- ⚠️ Nur placement-aligned Clipping (nicht symmetrisch)

## 3. Türrichtung / Rotation bestimmen ✅ ABGESCHLOSSEN
- [x] Rotation aus Placement-Hierarchie extrahiert (`_get_rotation_angles`)
- [x] Euler-Winkel (X, Y, Z) im Bereich 0-360° normalisiert
- [x] Row-major Matrix-Konvention dokumentiert
- [x] Rotation in `ElementPositionResult` zurückgegeben

**Implementierung:**
- Ansatz D + A kombiniert: Öffnungs-Placement Matrix → 3×3 Rotationsmatrix → Euler-Winkel extrahiert
- Yaw-Winkel via `atan2(-R[2,0], sqrt(R[1,0]² + R[0,0]²))`
- Pitch via `atan2(R[2,1], R[2,2])`
- Roll via `atan2(R[1,0], R[0,0])`

## 4. Wand-Repräsentation Fallback ⏳ OFFEN (kritisch)
- [ ] Problem: Aktuell nur Body Representation unterstützt
- [ ] Nicht unterstützt: IfcAxis2Placement, IfcBuildingElementPart, LOD 100/200 ohne 3D-Geometrie
- [ ] Lösung: Fallback-Kaskade implementieren
  - [ ] Stufe 1: Body (3D tesselliert)
  - [ ] Stufe 2: Axis (2D) → Bounding Box aus AxisCurve
  - [ ] Stufe 3: FootPrint → 2D-Footprint extrahieren
  - [ ] Stufe 4: SurveyPoints → Punkte interpolieren

## Quellen
- Leos Diplomarbeit: [Pfad/Link einfügen]
