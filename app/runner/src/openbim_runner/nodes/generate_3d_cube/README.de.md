---
title: 3D-Würfel erzeugen
description: Erstellt eine 3D-Quader-Geometrie mit konfigurierbaren Abmessungen, Positions-Offset und Rotations-Offset für die Kollisionserkennung.
categories: 3D operation,
---

Der `generate_3d_cube` Node erstellt eine 3D-Quader-Geometrie mit konfigurierbaren Abmessungen, Positions-Offset und Rotations-Offset und speichert sie im Geometrie-Cache unter einer vom Benutzer angegebenen `object_id`. Der Cache-Schlüssel `gen:<object_id>` ist die Adresse, unter der der Würfel später referenziert wird, z.B. in einem `collision` Node.

## Inputs

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `elements` | `list[dict]` | Elemente von upstream Nodes (z.B. `set_3d_position_rotation.elements` oder `get_element_creation_position_door.elements`). Das erste Element wird für Basis-Position und -Rotation verwendet. Binding aktivieren, um Input-Position/Rotation zu verwenden. |

## Einstellungen

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `position` | `list[float]` | **Offset**, das zur Basis-Position aus dem Input addiert wird. Standard: `[0.0, 0.0, 0.0]` (kein Offset). |
| `rotation` | `list[float]` | **Offset**, das zur Basis-Rotation aus dem Input addiert wird. Standard: `[0.0, 0.0, 0.0]` (kein Offset). |
| `size` | `list[float]` | Abmessungen des Würfels als `[Breite, Höhe, Tiefe]`. Standard: `[1.0, 1.0, 1.0]`. |
| `object_id` | `string` | Eindeutige Kennung für den generierten Würfel (erforderlich). Duplikate werden abgelehnt. |

## Ausgaben

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `object_ids` | `list[string]` | 1-elementige Liste mit dem qualifizierten Cache-Schlüssel des Würfels `gen:<object_id>`. Direkt in den Geometry-Key-Input eines `collision` Nodes einspeisen. |

## Beispiel: Verwendung mit set_3d_position_rotation

### Workflow JSON

```json
{
  "nodes": [
    {
      "id": "pos1",
      "type": "set_3d_position_rotation",
      "data": {
        "settings": {
          "position": [5.0, 3.0, 0.0],
          "rotation": [0.0, 0.0, 45.0]
        }
      }
    },
    {
      "id": "cube1",
      "type": "generate_3d_cube",
      "data": {
        "input_bindings": {
          "elements": "pos1.elements"
        },
        "settings": {
          "position": [0.5, 0.0, 0.0],
          "rotation": [0.0, 0.0, 0.0],
          "size": [1.0, 1.0, 1.0],
          "object_id": "offset_cube"
        }
      }
    }
  ]
}
```

Dies erstellt:
1. Eine Basis-Position bei (5, 3, 0) mit 45° Z-Rotation von `set_3d_position_rotation`
2. Einen Würfel bei (5.5, 3, 0) mit 45° Z-Rotation (0.5m X-Offset von der Basis)

## Beispiel: Eigenständig (ohne Input-Binding)

```json
{
  "settings": {
    "position": [5.0, 3.0, 0.0],
    "rotation": [0.0, 0.0, 45.0],
    "size": [2.0, 2.0, 2.0],
    "object_id": "box_a"
  }
}
```

Dies erstellt einen 2×2×2 Würfel an der Position (5, 3, 0) mit einer 45-Grad-Rotation um die Z-Achse, gespeichert unter `gen:box_a`.

## Hinweise

- Wenn kein Input-Binding bereitgestellt wird, werden Positions-/Rotations-Offsets auf den Ursprung `[0,0,0]` angewendet
- Positionskoordinaten sind in **Metern**
- Rotation folgt der **Rechte-Hand-Regel** (X, Y, Z in Grad): Positive Rotation ist gegen den Uhrzeigersinn, wenn man entlang der Achse blickt
- Alle Größenabmessungen müssen positiv sein (größer als 0)
- `object_id` muss innerhalb eines Durchlaufs nicht leer und eindeutig sein; Wiederverwendung löst einen Fehler aus
- `object_id` darf nicht `:expr:` enthalten (reserviert für qualifizierte IFC-Element-Referenzen)
