---
title: Erstelle Elementposition Tür
description: Ruft Fußpunktpunkte (P1-P7) von IFC-Türöffnungen auf Bodenhöhe ab. Behandelt automatisch den Edge-Case wenn Öffnungen dicker als die Wand sind.
categories: IFC, Geometrie
---

Der `get_element_creation_position_door` Node extrahiert Fußpunktpunkte aus der Grundfläche von IFC-Türöffnungen. Er verwendet das `ObjectPlacement` jeder Öffnung, um die Weltkoordinaten auf Bodenhöhe zu berechnen.

**Neu in v2.0:** Automatische Erkennung und Korrektur wenn Türöffnungen dicker modelliert sind als die angrenzende Wand (via `IfcRelVoidsElement`).

## Die 7 Punkte

```
     Vorne
     ┌───────┬───────┐
    P1      P2      P3
     │   P6  │  P5   │
     │       P7      │
     │       ●       │  ← Zentrum (Centroid)
     │       │       │
    P4      P5      P6
     └───────┴───────┘
     Hinten
```

**Hinweis:** 
- P1-P4: 4 Eckpunkte (clockwise sortiert, Startpunkt: nächste Ecke zur Placement Location)
- P5: Mittelpunkt zwischen P1 und P2
- P6: Mittelpunkt zwischen P3 und P4
- P7: Centroid (geometrischer Mittelpunkt)
- P1-P6 erfordern mindestens 4 Bottom-Vertices
- Für Öffnungen mit 3 Bottom-Vertices wird nur P7 berechnet
- Bei >4 Bottom-Vertices: OBB-basierte (Oriented Bounding Box) Eckpunktbestimmung

## Einstellungen

| Name | Typ | Standard | Beschreibung |
|------|-----|----------|--------------|
| `point_index` | `1-7` | `7` | Welcher Fußpunkt zurückgegeben werden soll: 1-4 = Eckpunkte (clockwise), 5-6 = Mittelpunkte, 7 = Zentrumspunkt. P1-P6 erfordern mindestens 4 Bottom-Vertices. |

## Eingänge

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `express_ids` | `list[int]` | Liste von IFC-Tür-Express-IDs (IfcDoor). Alle IDs in der Liste werden verarbeitet. |

## Ausgänge

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `elements` | `list[ElementPositionResult]` | Liste von Tür-Positionen. Ein Eintrag pro verarbeiteter Tür. |

## ElementPositionResult-Struktur

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `element_type` | `str` | Der IFC-Entitätstyp (IfcDoor). |
| `express_id` | `int` | Die Express-ID der verarbeiteten Tür. |
| `point_index` | `int` | Welcher Punkt zurückgegeben wurde (1-7). P1-P6 erfordern mindestens 4 Bottom-Vertices. |
| `position` | `list[float]` | Weltkoordinaten `[x, y, z]` in Metern auf Bodenhöhe. |

## Beispiel

### Einzelne Tür (P7)

Eingabe:
```json
{
  "settings": {
    "point_index": 7
  },
  "inputs": {
    "express_ids": [18334]
  }
}
```

Ausgabe:
```json
{
  "elements": [
    {
      "element_type": "IfcDoor",
      "express_id": 18334,
      "point_index": 7,
      "position": [0.906, 0.0, 0.0]
    }
  ]
}
```

## Algorithmus

1. Jede `IfcDoor`-Entität per Express-ID aus der Eingabeliste laden
2. Für jede Tür das zugehörige `IfcOpeningElement` über `IfcRelFillsElement`-Relation finden
3. Zugehörige Wand über `IfcRelVoidsElement`-Relation finden (für Thickness Detection)
4. 3D-Geometrie des Openings tessellieren
5. Bottom-Vertices finden (alle Vertices auf minimaler Z-Höhe)
6. Bei 4+ Bottom-Vertices:
   - Lokale Achsen aus `ObjectPlacement.RelativePlacement` extrahieren
   - Vertices ins lokale Koordinatensystem transformieren
   - Clockwise sortieren (Startpunkt: nächste Ecke zur Placement Location)
   - P1-P4 = 4 Eckpunkte, P5-P6 = Mittelpunkte, P7 = Centroid
   - Zurück ins Weltkoordinatensystem transformieren
7. Bei >4 Bottom-Vertices:
   - OBB (Oriented Bounding Box) im lokalen Koordinatensystem berechnen
   - 4 äußerste Eckpunkte via Min/Max auf lokalen Achsen bestimmen
   - P1-P4 = OBB-Eckpunkte, P5-P6 = Mittelpunkte, P7 = Centroid aller Vertices
8. **Thickness Detection (neu in v2.0):**
   - Opening-Dicke berechnen (Ausdehnung auf lokaler Y-Achse)
   - Wand-Dicke berechnen (via `IfcRelVoidsElement`)
   - Wenn `opening_thickness > wall_thickness * 1.01` (>1% Toleranz):
     - Opening-Vertices auf Wand-Grenzen clippen (placement-aligned)
     - Geclippte Vertices für Footprint-Berechnung verwenden
9. Bei <4 Bottom-Vertices:
   - Nur P7 (Centroid) wird berechnet
10. Angeforderten Punkt zurückgeben

## Hinweise

- Alle Express-IDs in der Eingabeliste werden verarbeitet
- Ungültige Express-IDs werden stillschweigend übersprungen
- Nicht-IfcDoor Entitätstypen werden stillschweigend übersprungen
- Türen ohne zugehörige Öffnungen werden stillschweigend übersprungen
- **P1-P6:** Erfordern mindestens 4 Bottom-Vertices
- **P7:** Verfügbar für alle Öffnungen (auch mit 3 Bottom-Vertices)
- Der Algorithmus unterstützt IFC2x3 und IFC4-Schemata
- Vollständige 3D-Rotation wird über Placement-Matrix-Berechnung unterstützt
- Eckpunkte sind clockwise sortiert (Startpunkt: nächste Ecke zur Placement Location)
- **Thickness Detection:** Öffnungen die dicker als die Wand sind (>1% Toleranz) werden automatisch auf Wanddicke geclippt
- **Clipping-Methode:** Placement-aligned (orientiert sich an Wand-Placement, nicht symmetrisch)
