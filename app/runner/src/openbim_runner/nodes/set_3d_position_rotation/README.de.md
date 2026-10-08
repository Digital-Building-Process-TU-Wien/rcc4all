---
title: 3D-Position und Rotation setzen
description: Definiert eine 3D-Position und Rotation über UI-Einstellungen.
categories: 3D operation
---

Der `set_3d_position_rotation` Node ermöglicht es Benutzern, manuell eine 3D-Position und Euler-Rotation über das UI zu definieren.

## Einstellungen

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `position` | `list[float]` | Position als `[x, y, z]` Koordinaten in Metern. Standard: `[0.0, 0.0, 0.0]` |
| `rotation` | `list[float]` | Rotation um X, Y, Z Achsen in Grad (Euler-Winkel). Standard: `[0.0, 0.0, 0.0]` |

## Ausgaben

| Name | Typ | Beschreibung |
|------|-----|-------------|
| `elements` | `list[ElementResult]` | Liste mit einem Element, das Positions- und Rotationswerte enthält. Das Feld `express_id` ist leer (kein IFC-Element-Referenz). |

## Beispiel

```json
{
  "settings": {
    "position": [5.0, 3.0, 0.0],
    "rotation": [0.0, 0.0, 45.0]
  }
}
```

Dies erstellt ein einzelnes Element an der Position (5, 3, 0) mit einer 45-Grad-Rotation um die Z-Achse.

## Hinweise

- Positionskoordinaten sind in **Metern**
- Rotation folgt der **Rechte-Hand-Regel** (X, Y, Z in Grad): Positive Rotation ist gegen den Uhrzeigersinn, wenn man entlang der Achse blickt
- Die Ausgabe `express_id` ist immer leer, da dieser Node kein IFC-Element referenziert
