---
title: Ermittle Einfügepunkt Tür
description: Ermittelt Fußpunktpunkte (P1-P7) von IFC-Türöffnungen für die Elementerstellung.
categories: IFC, Geometrie
---

Der `get_element_creation_position_door` Node extrahiert Fußpunktpunkte aus der Grundfläche von IFC-Türöffnungen. Er verwendet das `ObjectPlacement` jeder Öffnung, um die Weltkoordinaten auf Bodenhöhe zu berechnen.

## Die 7 Punkte

```
     Vorne
     ┌───────────┬───────────┐
    P1           P5          P2
     │           │           │
     │   ╲       │       ╱   │
     │     ╲     │     ╱     │
     │       ╲   │   ╱       │
     │         ╲ │ ╱         │
     │     P7  ● │           │  ← Zentrum (Centroid)
     │         ╱ │ ╲         │
     │       ╱   │   ╲       │
     │     ╱     │     ╲     │
     │   ╱       │       ╲   │
     │           │           │
    P4           P6          P3
     └───────────┴───────────┘
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
```

## Einstellungen

| Name | Typ | Standard | Beschreibung |
|------|-----|----------|--------------|
| `point_index` | `1-7` | `7` | Welcher Fußpunkt zurückgegeben werden soll. P1-P6 erfordern mindestens 4 Bottom-Vertices. |

## Eingänge

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `express_ids` | `list[str]` | Liste von IFC-Tür-Referenzen im Format `<slug>:expr:<id>` (z.B. `main:expr:18334`). Alle IDs in der Liste werden verarbeitet. |

## Ausgänge

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `elements` | `list[ElementPositionResult]` | Liste von Tür-Positionen. Ein Eintrag pro verarbeiteter Tür. |

## ElementPositionResult-Struktur

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `element_type` | `str` | Der IFC-Entitätstyp (IfcDoor). |
| `express_id` | `str` | Die qualifizierte Referenz (`<slug>:expr:<id>`). |
| `point_index` | `int` | Welcher Punkt zurückgegeben wurde (1-7). P1-P6 erfordern mindestens 4 Bottom-Vertices. |
| `position` | `list[float]` | Weltkoordinaten `[x, y, z]` in Metern auf Bodenhöhe (auf 3 Dezimalstellen gerundet). |
| `rotation` | `ElementRotation \| None` | Euler-Rotationswinkel (X°, Y°, Z°) in Grad (0-360). None wenn Placement nicht verfügbar. |

## ElementRotation-Struktur

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `rotation_x` | `float` | Rotation um globale X-Achse in Grad (0-360). |
| `rotation_y` | `float` | Rotation um globale Y-Achse in Grad (0-360). |
| `rotation_z` | `float` | Rotation um globale Z-Achse in Grad (0-360). |

## Beispiel

### Einzelne Tür (P7)

Eingabe:
```json
{
  "settings": {
    "point_index": 7
  },
  "inputs": {
    "express_ids": ["main:expr:18334"]
  }
}
```

Ausgabe:
```json
{
  "elements": [
    {
      "element_type": "IfcDoor",
      "express_id": "main:expr:18334",
      "point_index": 7,
      "position": [0.906, 0.0, 0.0],
      "rotation": {
        "rotation_x": 0.0,
        "rotation_y": 0.0,
        "rotation_z": 90.0
      }
    }
  ]
}
```

## Algorithmus

1. Jede `IfcDoor`-Entität per Express-ID laden und das zugehörige `IfcOpeningElement` über `IfcRelFillsElement` finden
2. Zugehörige Wand über `IfcRelVoidsElement` finden (für Thickness Detection)
3. 3D-Geometrie des Openings tessellieren und Bottom-Vertices (minimale Z-Höhe) extrahieren
4. Bei 4+ Bottom-Vertices: Vertices ins lokale Koordinatensystem transformieren, Centroid-Y als Trennlinie für Vorder-/Rückseite verwenden, P1-P4 via X-min/max Zuordnung, P5-P6 als Mittelpunkte, P7 als Centroid berechnen und zurück ins Weltkoordinatensystem transformieren
5. Bei >4 Bottom-Vertices: OBB (Oriented Bounding Box) berechnen und 4 extreme Eckpunkte via Min/Max bestimmen
6. Thickness Detection: Opening- und Wand-Dicke vergleichen, bei >1% Toleranz Opening-Vertices auf Wand-Grenzen clippen (placement-aligned)
7. Bei <4 Bottom-Vertices: Nur P7 (Centroid) berechnen
8. Rotation: Vollständige Placement-Matrix aus `ObjectPlacement` berechnen, Euler-Winkel (X, Y, Z) extrahieren und im Ergebnis speichern
9. Angeforderten Punkt zurückgeben

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
- Rotation wird nur berechnet wenn `ObjectPlacement` verfügbar ist
- `express_id` Format: `<slug>:expr:<id>` (z.B. `main:expr:18334`)
- Positionskoordinaten sind auf 3 Dezimalstellen gerundet (Millimeter-Genauigkeit)
