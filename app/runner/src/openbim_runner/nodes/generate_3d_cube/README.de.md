---
title: 3D-Würfel generieren
description: Erstellt eine 3D-Würfelgeometrie mit anpassbarer Größe, Position und Rotation für die Kollisionserkennung.
categories: 3D operation
---

Der `generate_3d_cube` Knoten erstellt eine 3D-Box-Geometrie mit konfigurierbaren Abmessungen, Position und Rotation. Die Ausgabe sind trimesh-kompatible Geometriedaten, die für die Kollisionserkennung, Visualisierung oder weitere geometrische Operationen verwendet werden können.

## Eingaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `position` | `list[float]` | Position des Würfelzentrums als `[x, y, z]` Koordinaten. Standard: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation um X, Y, Z Achsen in Grad (Euler-Winkel). Standard: `[0.0, 0.0, 0.0]` |
| `size` | `list[float]` | Abmessungen des Würfels als `[Breite, Höhe, Tiefe]`. Standard: `[1.0, 1.0, 1.0]` |

## Ausgaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `vertices` | `list[list[float]]` | Liste von 8 Vertex-Koordinaten als `[x, y, z]` Listen |
| `faces` | `list[list[int]]` | Liste von 6 Flächendefinitionen als Vertex-Index-Listen |

## Beispiel

```json
{
  "position": [5.0, 3.0, 0.0],
  "rotation": [0.0, 0.0, 45.0],
  "size": [2.0, 2.0, 2.0]
}
```

Dies erstellt einen 2×2×2 Würfel zentriert bei (5, 3, 0), um 45 Grad um die Z-Achse rotiert.

## Hinweise

- Der Würfel wird zuerst zentriert am Ursprung erstellt, dann rotiert und verschoben
- Alle Größenabmessungen müssen positiv sein (größer als 0)
- Rotation folgt der Rechte-Hand-Regel
- Ausgabeformat ist kompatibel mit `trimesh.Trimesh(vertices, faces)` Konstruktor
