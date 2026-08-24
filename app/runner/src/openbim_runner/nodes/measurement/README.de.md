---
title: Measurement (Messung)
description: Berechnet geometrische Messungen (Volumen, Oberfläche) von IFC-Elementen oder zwischengespeicherten Geometrien.
categories: Measurement
---

Der `measurement`-Knoten berechnet geometrische Messungen von IFC-Elementen oder anderen zwischengespeicherten Geometrien (z. B. Schnittmengen aus dem collision-Knoten). Jede Messung wird pro Element mit Referenz, Wert und ggf. Fehler ausgegeben.

## Anwendungsbeispiel

- Volumen aller Wände in einem Modell berechnen
- Oberflächen von Elementen für die Materialschätzung messen
- Volumen von Kollisionsschnittmengen messen, um Überlappungen zu quantifizieren

## Einstellungen

### Messungstyp (measurement_type)

Der Typ der zu berechnenden Messung. In v1 sind nur `volume` und `surface_area` implementiert.

| Wert | Bezeichnung | Wann verwenden |
|------|-------------|----------------|
| `volume` | **Volumen** | Berechnet das 3D-Volumen jedes Elements. Erfordert wasserdichte Geometrie; nicht wasserdichte Meshes werden repariert oder als Fehler gemeldet. |
| `surface_area` | **Oberfläche** | Berechnet die Gesamtoberfläche jedes Elements. Funktioniert mit jedem Mesh. |
| `projected_area` | **Projizierte Fläche** | (Geplant) Berechnet die Fläche eines Elements, projiziert auf eine Ebene (z. B. Grundrissfläche). |
| `component_height` | **Bauteilhöhe** | (Geplant) Berechnet die Ausdehnung eines Elements entlang eines Richtungsvektors (z. B. Z-Höhe). |
| `distance_between` | **Abstand zwischen** | (Geplant) Berechnet den minimalen Abstand zwischen Elementpaaren. |
| `distance_to_reference` | **Abstand zur Referenz** | (Geplant) Berechnet den Abstand von Elementen zu einem Referenzpunkt oder einer Ebene. |

## Eingaben

- **Elements** (optional): Liste der zu messenden Elementreferenzen. Akzeptiert:
  - Express-IDs (int → `ifc:<id>`)
  - Objekt-IDs (str → `gen:<id>`)
  - Vollständige Geometrie-Cache-Schlüssel (`ifc:`, `gen:`, `inter:`) — nützlich zum Messen von Schnittmengen aus collision
  - Leer = gesamtes Modell (alle zwischengespeicherten Geometrien)
  - **Dict-Eingabe**: Akzeptiert auch ein Dict (z. B. die `intersection_meshes`-Ausgabe des collision-Knotens). In diesem Fall werden die Nicht-Null-Werte des Dicts (Schnittmengen-Cache-Schlüssel wie `inter:...`) gemessen; Null-Einträge (FCL-entschiedene Kollisionen ohne gespeicherte Geometrie) werden übersprungen.

## Ausgaben

- **Type**: Der verwendete Messungstyp (z. B. `volume`, `surface_area`)
- **Unit**: Die Maßeinheit (`volume_unit` für Volumen, `area_unit` für Oberfläche, in Modell-Einheiten)
- **Measurements**: Liste der Messungen pro Element, jeweils mit:
  - `reference`: Der Geometrie-Cache-Schlüssel (z. B. `ifc:123`, `gen:abc`)
  - `value`: Der gemessene Wert (null wenn Geometrie fehlt oder Messung fehlgeschlagen)
  - `error`: Fehlergrund falls Messung fehlgeschlagen (z. B. `no cached geometry`, `non-watertight`)

## Beispielkonfiguration

### Beispiel 1: Volumen spezifischer Elemente

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- Elements: `[101, 102, 103]` (Express-IDs von drei Wänden)

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.5, "error": null },
    { "reference": "ifc:102", "value": 3.1, "error": null },
    { "reference": "ifc:103", "value": 1.8, "error": null }
  ]
}
```

### Beispiel 2: Oberfläche des gesamten Modells

**Einstellungen:**
- Messungstyp: `surface_area`

**Eingaben:**
- Elements: `[]` (leer = gesamtes Modell)

**Ausgabe:**
```json
{
  "type": "surface_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:1", "value": 45.2, "error": null },
    { "reference": "ifc:2", "value": 12.8, "error": null },
    ...
  ]
}
```

### Beispiel 3: Volumen von Kollisionsschnittmengen

**Szenario:** Ein `collision`-Knoten (im Modus `intersection_mesh`) hat Schnittmengen erzeugt. Sie möchten das Volumen jeder Überlappung messen, indem Sie dessen `intersection_meshes`-Ausgabe direkt mit der `elements`-Eingabe verbinden.

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- Elements: `{"ifc:1__ifc:2": "inter:intersection_ifc:1_ifc:2", "ifc:3__ifc:4": "inter:intersection_ifc:3_ifc:4", "ifc:5__ifc:6": null}`

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "inter:intersection_ifc:1_ifc:2", "value": 0.05, "error": null },
    { "reference": "inter:intersection_ifc:3_ifc:4", "value": 0.12, "error": null }
  ]
}
```

Hinweis: Der Null-Eintrag (`ifc:5__ifc:6`) wird übersprungen, da für dieses Kollisionspaar keine Schnittmenge gespeichert wurde.

### Beispiel 4: Fehlende Geometrie wird gracefully behandelt

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- Elements: `[101, 999]` (999 hat keine zwischengespeicherte Geometrie)

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.5, "error": null },
    { "reference": "999", "value": null, "error": "no cached geometry" }
  ]
}
```

### Beispiel 5: Nicht wasserdichtes Mesh-Volumenfehler

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- Elements: `["gen:broken_mesh"]` (ein nicht reparierbares Mesh)

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "gen:broken_mesh", "value": null, "error": "non-watertight: ..." }
  ]
}
```

Hinweis: Der Modus `surface_area` funktioniert weiterhin mit nicht wasserdichten Meshes.

## Einheiten

Messungen werden in **Modell-Einheiten** (den nativen Einheiten der IFC-Modellgeometrie) ausgegeben. Wenn das IFC-Modell Meter verwendet:
- Volumen ist in m³
- Oberfläche ist in m²

Wenn das Modell Millimeter verwendet:
- Volumen ist in mm³
- Oberfläche ist in mm²

## Hinweise

- **Wasserdichtigkeit für Volumen erforderlich**: Die Volumenberechnung erfordert wasserdichte Geometrie. Der Knoten versucht automatisch, nicht wasserdichte Meshes zu reparieren. Wenn die Reparatur fehlschlägt, wird die Messung mit Fehler gemeldet.
- **Oberfläche funktioniert mit jedem Mesh**: Die Oberfläche wird aus den Mesh-Dreiecken berechnet und erfordert keine wasserdichte Geometrie.
- **Gesamtmodell-Fallback**: Wenn `elements` leer ist, misst der Knoten alle zwischengespeicherten Geometrien (IFC-Elemente und generierte Geometrien).
- **Zukünftige Modi**: Die Modi `projected_area`, `component_height`, `distance_between` und `distance_to_reference` sind für zukünftige Versionen geplant. Die Auswahl führt in v1 zu einem Fehler.
