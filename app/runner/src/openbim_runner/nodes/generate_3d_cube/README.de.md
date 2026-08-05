---
title: 3D-Würfel generieren
description: Erstellt eine 3D-Würfelgeometrie mit anpassbarer Größe, Position und Rotation für die Kollisionserkennung.
categories: 3D operation
---

Der `generate_3d_cube` Knoten erstellt eine 3D-Box-Geometrie mit konfigurierbaren Abmessungen, Position und Rotation und speichert sie unter einer vom Benutzer vergebenen `object_id` im Geometrie-Cache. Die Objekt-ID ist die Adresse, über die der Würfel später referenziert wird, z. B. in einem `collision`-Knoten.

## Eingaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `position` | `list[float]` | Position des Würfelzentrums als `[x, y, z]` Koordinaten. Standard: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation um X, Y, Z Achsen in Grad (Euler-Winkel). Standard: `[0.0, 0.0, 0.0]` |
| `size` | `list[float]` | Abmessungen des Würfels als `[Breite, Höhe, Tiefe]`. Standard: `[1.0, 1.0, 1.0]` |
| `object_id` | `string` | Eindeutige Kennung für den generierten Würfel (erforderlich). Duplikate werden abgelehnt. |

## Ausgaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `object_ids` | `list[string]` | 1-elementige Liste mit der `object_id` des Würfels. Geben Sie dies in den Objekt-ID-Eingang eines `collision`-Knotens. |

## Beispiel

```json
{
  "position": [5.0, 3.0, 0.0],
  "rotation": [0.0, 0.0, 45.0],
  "size": [2.0, 2.0, 2.0],
  "object_id": "box_a"
}
```

Dies erstellt einen 2×2×2 Würfel zentriert bei (5, 3, 0), um 45 Grad um die Z-Achse rotiert, zwischengespeichert unter der Objekt-ID `box_a`.

## Hinweise

- Der Würfel wird zuerst zentriert am Ursprung erstellt, dann rotiert und verschoben
- Alle Größenabmessungen müssen positiv sein (größer als 0)
- Rotation folgt der Rechte-Hand-Regel
- `object_id` muss nicht leer und innerhalb eines Laufs eindeutig sein; eine Wiederverwendung löst einen Fehler aus
