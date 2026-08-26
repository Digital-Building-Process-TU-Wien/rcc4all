---
title: Measurement (Messung)
description: Berechnet geometrische Messungen (Volumen, Oberfläche, projizierte Fläche, Bauteilhöhe) von IFC-Elementen oder zwischengespeicherten Geometrien.
categories: Measurement
---

Der `measurement`-Knoten berechnet geometrische Messungen von IFC-Elementen oder anderen zwischengespeicherten Geometrien (z. B. Schnittmengen aus dem collision-Knoten). Jede Messung wird pro Element mit Referenz, Wert und ggf. Fehler ausgegeben. In v3 unterstützt der Knoten Volumen-, Oberflächen-, projizierte Flächen-, Bauteilhöhen- und Abstand-zwischen-Berechnungen.

## Anwendungsbeispiel

- Volumen aller Wände in einem Modell berechnen
- Oberflächen von Elementen für die Materialschätzung messen
- Volumen von Kollisionsschnittmengen messen, um Überlappungen zu quantifizieren

## Einstellungen

### Messungstyp (measurement_type)

Der Typ der zu berechnenden Messung. In v3 sind `volume`, `surface_area`, `projected_area`, `component_height` und `distance_between` implementiert.

| Wert | Bezeichnung | Wann verwenden |
|------|-------------|----------------|
| `volume` | **Volumen** | Berechnet das 3D-Volumen jedes Elements. Erfordert wasserdichte Geometrie; nicht wasserdichte Meshes werden repariert oder als Fehler gemeldet. |
| `surface_area` | **Oberfläche** | Berechnet die Gesamtoberfläche jedes Elements. Funktioniert mit jedem Mesh. |
| `projected_area` | **Projizierte Fläche** | Berechnet die Fläche eines Elements, projiziert auf eine Ebene senkrecht zum angegebenen Normalenvektor. Standardnormal [0,0,1] berechnet die Grundrissfläche (Draufsicht). Funktioniert mit jedem Mesh. |
| `component_height` | **Bauteilhöhe** | Berechnet die Ausdehnung eines Elements entlang eines Richtungsvektors. Standardrichtung [0,0,1] berechnet die vertikale Höhe. Funktioniert mit jedem Mesh. |
| `distance_between` | **Abstand zwischen** | Berechnet den minimalen Oberflächenabstand zwischen Elementpaaren mit dem List A / List B-Muster. **List B leer:** alle ungeordneten Paare innerhalb von List A (n über 2), jedes in **beiden Richtungen** ausgegeben. **List B nicht leer:** kartesisches Produkt A×B (Selbstpaare überspringen), eine Richtung pro Paar. Referenzformat: `dist:distance_<SchlüsselA>_<SchlüsselB>` (directional, **NICHT** sortiert). Funktioniert mit jedem Mesh. **Sich schneidende Paare geben `0.0` zurück** (erkannt via AABB + FCL Dreieck-Dreieck-Kollision vor der Abstandsabfrage). **Hinweis:** Nur Elemente mit tessellierter Body-Geometrie sind messbar. Parametrische Elemente wie Alignments (IfcAlignment) ohne Body-Repräsentationen erzeugen Fehlereinträge. |
| `distance_to_reference` | **Abstand zur Referenz** | (Geplant) Berechnet den Abstand von Elementen zu einem Referenzpunkt oder einer Ebene. |

### Projektionsnormal (v2+)

Nur verwendet, wenn **Messungstyp** `projected_area` ist. Gibt den Normalenvektor der Projektionsebene an.

- **Standard**: `[0.0, 0.0, 1.0]` (XY-Ebene, Draufsicht)
- **Format**: Liste von 3 Floats `[x, y, z]`
- **Beispiele**:
  - `[0, 0, 1]` → Projektion auf XY-Ebene (Grundriss)
  - `[1, 0, 0]` → Projektion auf YZ-Ebene (Seitenansicht)
  - `[0, 1, 0]` → Projektion auf XZ-Ebene (Frontansicht)

### Richtung (v2+)

Nur verwendet, wenn **Messungstyp** `component_height` ist. Gibt den Richtungsvektor für die Ausdehnungsberechnung an.

- **Standard**: `[0.0, 0.0, 1.0]` (vertikale Höhe)
- **Format**: Liste von 3 Floats `[x, y, z]`
- **Normalisierung**: Die Richtung wird intern normalisiert; nur die Richtung ist relevant, nicht die Länge
- **Beispiele**:
  - `[0, 0, 1]` → Vertikale Höhe (Z-Ausdehnung)
  - `[1, 0, 0]` → Horizontale Ausdehnung entlang der X-Achse
  - `[0, 1, 0]` → Horizontale Ausdehnung entlang der Y-Achse
  - `[1, 1, 0]` → Ausdehnung entlang diagonaler Richtung (intern normalisiert)

## Eingaben

- **List A** (optional): Erste Liste von Elementreferenzen. Akzeptiert:
  - Express-IDs (int → `ifc:<id>`)
  - Objekt-IDs (str → `gen:<id>`)
  - Vollständige Geometrie-Cache-Schlüssel (`ifc:`, `gen:`, `inter:`)
  - Leer = gesamtes Modell (alle zwischengespeicherten Geometrien)
  - **Dict-Eingabe**: Akzeptiert auch ein Dict (z. B. die `intersection_meshes`-Ausgabe des collision-Knotens). Die Nicht-Null-Werte des Dicts (Schnittmengen-Cache-Schlüssel) werden verwendet.
- **List B** (optional): Zweite Liste von Elementreferenzen (gleiches Format wie List A). Leer = Paare innerhalb von List A (beide Richtungen). Nicht leer = kartesisches Produkt A×B (eine Richtung pro Paar).

## Ausgaben

- **Type**: Der verwendete Messungstyp (z. B. `volume`, `surface_area`, `projected_area`, `component_height`, `distance_between`)
- **Unit**: Die Maßeinheit (`volume_unit` für Volumen, `area_unit` für Oberfläche und projizierte Fläche, `length_unit` für Bauteilhöhe und Abstand zwischen, in Modell-Einheiten)
- **Measurements**: Liste der Messungen, jeweils mit:
  - `reference`: Der Geometrie-Cache-Schlüssel (z. B. `ifc:123`, `gen:abc`) oder für distance_between: `dist:distance_<SchlüsselA>_<SchlüsselB>` (directional, NICHT sortiert)
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

### Beispiel 3: Projizierte Fläche (Grundriss) einer Wand

**Einstellungen:**
- Messungstyp: `projected_area`
- Projektionsnormal: `[0.0, 0.0, 1.0]` (Standard, Draufsicht)

**Eingaben:**
- Elements: `[101]` (Express-ID einer Wand)

**Ausgabe:**
```json
{
  "type": "projected_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 3.5, "error": null }
  ]
}
```

### Beispiel 4: Projizierte Fläche mit benutzerdefiniertem Normal (Seitenansicht)

**Einstellungen:**
- Messungstyp: `projected_area`
- Projektionsnormal: `[1.0, 0.0, 0.0]` (Projektion auf YZ-Ebene)

**Eingaben:**
- Elements: `[101]` (Express-ID einer Wand)

**Ausgabe:**
```json
{
  "type": "projected_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 8.2, "error": null }
  ]
}
```

### Beispiel 5: Volumen von Kollisionsschnittmengen

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

### Beispiel 6: Fehlende Geometrie wird gracefully behandelt

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

### Beispiel 7: Nicht wasserdichtes Mesh-Volumenfehler

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

### Beispiel 8: Bauteilhöhe (vertikal) einer Wand

**Einstellungen:**
- Messungstyp: `component_height`
- Richtung: `[0.0, 0.0, 1.0]` (Standard, vertikale Höhe)

**Eingaben:**
- Elements: `[101]` (Express-ID einer Wand)

**Ausgabe:**
```json
{
  "type": "component_height",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 2.8, "error": null }
  ]
}
```

### Beispiel 9: Bauteilhöhe mit benutzerdefinierter Richtung

**Einstellungen:**
- Messungstyp: `component_height`
- Richtung: `[1.0, 0.0, 0.0]` (Ausdehnung entlang X-Achse)

**Eingaben:**
- Elements: `[101]` (Express-ID einer Wand)

**Ausgabe:**
```json
{
  "type": "component_height",
  "unit": "length_unit",
  "measurements": [
    { "reference": "ifc:101", "value": 0.3, "error": null }
  ]
}
```

### Beispiel 10: Abstand zwischen zwei Elementen

**Einstellungen:**
- Messungstyp: `distance_between`

**Eingaben:**
- List A: `[101, 102]` (Express-IDs von zwei getrennten Wänden)
- List B: `[]` (leer → Paare innerhalb von List A, beide Richtungen)

**Ausgabe:**
```json
{
  "type": "distance_between",
  "unit": "length_unit",
  "measurements": [
    { "reference": "dist:distance_ifc:101_ifc:102", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:101", "value": 2.5, "error": null }
  ]
}
```

Hinweis: Bei leerer List B wird jedes ungeordnete Paar in beiden Richtungen ausgegeben.

### Beispiel 11: Abstand zwischen mehreren Elementen (alle Paare, beide Richtungen)

**Einstellungen:**
- Messungstyp: `distance_between`

**Eingaben:**
- List A: `[101, 102, 103]` (Express-IDs von drei Elementen)
- List B: `[]` (leer → Paare innerhalb von List A, beide Richtungen)

**Ausgabe:**
```json
{
  "type": "distance_between",
  "unit": "length_unit",
  "measurements": [
    { "reference": "dist:distance_ifc:101_ifc:102", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:101", "value": 2.5, "error": null },
    { "reference": "dist:distance_ifc:101_ifc:103", "value": 5.1, "error": null },
    { "reference": "dist:distance_ifc:103_ifc:101", "value": 5.1, "error": null },
    { "reference": "dist:distance_ifc:102_ifc:103", "value": 3.2, "error": null },
    { "reference": "dist:distance_ifc:103_ifc:102", "value": 3.2, "error": null }
  ]
}
```

Hinweis: Für n Elemente mit leerer List B berechnet der Knoten alle n über 2 ungeordneten Paare (3 Paare für 3 Elemente) und gibt jedes in beiden Richtungen aus (insgesamt 6 Messungen).

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
- **Projizierte Fläche funktioniert mit jedem Mesh**: Wie die Oberfläche funktioniert auch die projizierte Flächenberechnung mit jedem Mesh, unabhängig von der Wasserdichtigkeit.
- **Bauteilhöhe funktioniert mit jedem Mesh**: Die Ausdehnung wird aus Vertex-Projektionen berechnet und erfordert keine wasserdichte Geometrie.
- **Abstand zwischen funktioniert mit jedem Mesh**: Der minimale Oberflächenabstand wird mit BVH-basierten Nächster-Punkt-Abfragen berechnet. Sich schneidende Paare werden zuerst via AABB + FCL Dreieck-Dreieck-Kollision erkannt und geben sofort `0.0` zurück. Funktioniert mit jedem Mesh (konvex oder nicht-konvex).
- **Abstand zwischen Paarformat**: Referenzen folgen dem Format `dist:distance_<SchlüsselA>_<SchlüsselB>` (directional, **NICHT** sortiert). Bei leerer List B wird jedes ungeordnete Paar in **beiden Richtungen** ausgegeben. Bei nicht-leerer List B eine Richtung pro A×B-Paar.
- **Abstand zwischen fehlende Geometrie**: Paare mit Elementen ohne zwischengespeicherte Geometrie erzeugen Fehlereinträge (`value=null`, `error='no cached geometry'`). Bei leerer List B werden Fehlereinträge in beiden Richtungen ausgegeben.
- **Abstand zwischen Einschränkung**: Nur Elemente mit tessellierter Body-Geometrie können gemessen werden. Parametrische Elemente wie Alignments (`IfcAlignment`) ohne Body-Repräsentationen erzeugen Fehlereinträge wenn sie mit anderen Elementen gepaart werden.
- **Abstand zwischen sich schneidenden Elementen**: Wenn sich zwei Meshes schneiden (Volumenüberlappung oder sich kreuzende Oberflächen), ist der Abstand `0.0`. Die Schnittmenge wird via AABB + FCL Dreieck-Dreieck-Kollision vor der Abstandsabfrage erkannt, was genaue Ergebnisse sicherstellt, selbst wenn kein Vertex im anderen Mesh liegt.
- **Gesamtmodell-Fallback**: Wenn `List A` leer ist, misst der Knoten alle zwischengespeicherten Geometrien und berechnet alle paarweisen Abstände im `distance_between`-Modus (leere List B → beide Richtungen für jedes Paar).
- **Zukünftige Modi**: Der Modus `distance_to_reference` ist für zukünftige Versionen geplant. Die Auswahl führt in v3 zu einem Fehler.
