---
title: Messung
description: Berechnet geometrische Messungen (Volumen, Oberfläche, Bauteilhöhe, minimaler Abstand zwischen Elementen, Abstand zur Referenz) von IFC-Elementen oder zwischengespeicherten Geometrien.
categories: Measurement
---

Der `measurement`-Node berechnet geometrische Messungen von IFC-Elementen oder anderen zwischengespeicherten Geometrien (z. B. Schnittmengen aus dem collision-Node). Jede Messung wird pro Element mit Referenz, Wert und ggf. Fehler ausgegeben. Der Node unterstützt Volumen-, Oberflächen-, Bauteilhöhen-, minimaler Abstand zwischen Elementen- und Abstand-zur-Referenz-Berechnungen.

## Anwendungsbeispiel

- Volumen aller Wände in einem Modell berechnen
- Oberflächen von Elementen für die Materialschätzung messen
- Volumen von Kollisionsschnittmengen messen, um Überlappungen zu quantifizieren
- Minimalen Abstand zwischen Elementen messen (z. B. zur Überprüfung von Abständen zwischen Bauteilen)

## Einstellungen

### Messungstyp

Der Typ der zu berechnenden Messung.

| Wert | Bezeichnung | Wann verwenden |
|------|-------------|----------------|
| `volume` | **Volumen** | Berechnet das 3D-Volumen jedes Elements. Erfordert wasserdichte Geometrie; nicht wasserdichte Meshes werden repariert oder als Fehler gemeldet. |
| `surface_area` | **Oberfläche** | Berechnet die Gesamtoberfläche jedes Elements. Funktioniert mit jedem Mesh. |
| `component_height` | **Bauteilhöhe** | Berechnet die Ausdehnung eines Elements entlang eines Richtungsvektors. Standardrichtung [0,0,1] berechnet die vertikale Höhe. Funktioniert mit jedem Mesh. |
| `distance_between` | **Minimaler Abstand zwischen Elementen** | Berechnet den minimalen Oberflächenabstand zwischen Elementpaaren mit dem List A / List B-Muster. Siehe Hinweise für Details. Funktioniert mit jedem Mesh. |
| `distance_to_reference` | **Abstand zur Referenz** | Berechnet den minimalen Abstand jedes Elements zu einem Referenzpunkt oder einer Referenzebene. Siehe Hinweise für Details. Funktioniert mit jedem Mesh. |

### Richtung

Nur verwendet, wenn **Messungstyp** `component_height` ist. Gibt den Richtungsvektor für die Ausdehnungsberechnung an.

- **Standard**: `[0.0, 0.0, 1.0]` (vertikale Höhe)
- **Format**: Liste von 3 endlichen Floats `[x, y, z]` (falsche Längen und nicht-endliche Werte werden bei der Validierung abgelehnt)
- **Normalisierung**: Die Richtung wird intern normalisiert; nur die Richtung ist relevant, nicht die Länge
- **Null-Richtung**: Wenn die Richtung keine Länge hat (z. B. `[0.0, 0.0, 0.0]`), wird ein Fehlereintrag `undefined direction` pro Element erzeugt
- **Beispiele**:
  - `[0, 0, 1]` → Vertikale Höhe (Z-Ausdehnung)
  - `[1, 0, 0]` → Horizontale Ausdehnung entlang der X-Achse
  - `[0, 1, 0]` → Horizontale Ausdehnung entlang der Y-Achse

### Referenztyp

Nur verwendet, wenn **Messungstyp** `distance_to_reference` ist. Gibt an, ob der Abstand zu einem Punkt oder einer Ebene berechnet wird.

- **Standard**: `point`
- **Format**: String-Enum: `"point"` | `"plane"`

### Referenzpunkt

Nur verwendet, wenn **Messungstyp** `distance_to_reference` ist. Gibt den Referenzpunkt für die Abstandsberechnung an.

- **Standard**: `[0.0, 0.0, 0.0]` (Weltursprung)
- **Format**: Liste von 3 endlichen Floats `[x, y, z]` in Metern (falsche Längen und nicht-endliche Werte werden bei der Validierung abgelehnt)
- **Verwendung**:
  - Für `reference_type: point` → Abstand zu diesem Punkt berechnen
  - Für `reference_type: plane` → Dieser Punkt dient als Ebenenursprung

### Referenznormal

Nur verwendet, wenn **Messungstyp** `distance_to_reference` und **Referenztyp** `plane` ist. Gibt den Normalenvektor der Referenzebene an.

- **Standard**: `[0.0, 0.0, 1.0]` (horizontale Ebene, XY-Ebene)
- **Format**: Liste von 3 endlichen Floats `[x, y, z]` (falsche Längen und nicht-endliche Werte werden bei der Validierung abgelehnt)
- **Normalisierung**: Die Normale wird intern normalisiert; nur die Richtung ist relevant, nicht die Länge
- **Null-Normale**: Wenn die Normale keine Länge hat (z. B. `[0.0, 0.0, 0.0]`), wird ein Fehlereintrag `undefined normal` pro Element erzeugt

## Eingaben

- **List A** (optional): Erste Liste voll qualifizierter Geometrie-Cache-Schlüssel
  (`<slug>:expr:<id>` für IFC-Elemente, `gen:<object_id>` für generierte Geometrie,
  `inter:<id>` für Hilfs-/Schnittgeometrie). IFC-Referenzen werden gegen das darin genannte
  Modell aufgelöst. `gen:`- und `inter:`-Keys werden aus dem gemeinsamen Geometrie-Cache
  gelesen. Gemischte Listen aus mehreren Modellen sind erlaubt. Eine leere Liste liefert
  null Messungen.
  - **Dict-Eingabe**: Akzeptiert auch ein Dict (z. B. die `intersection_meshes`-Ausgabe des collision-Nodes). Die Nicht-Null-Werte des Dicts (Schnittmengen-Cache-Schlüssel) werden verwendet.
- **List B** (optional): Zweite Liste von Elementreferenzen (gleiches Format wie List A). Leer = Paare innerhalb von List A (beide Richtungen). Nicht leer = kartesisches Produkt A×B (eine Richtung pro Paar). Ein Dict, dessen Werte alle null sind, wird wie eine leere List B behandelt. **Nur verwendet im Modus `minimaler Abstand zwischen Elementen`; in allen anderen Modi ignoriert.**

## Ausgaben

- **Type**: Der verwendete Messungstyp (z. B. `volume`, `surface_area`, `component_height`, `distance_between`, `distance_to_reference`)
- **Unit**: Die Maßeinheit (`volume_unit` für Volumen, `area_unit` für Oberfläche, `length_unit` für Bauteilhöhe, minimaler Abstand zwischen Elementen und Abstand zur Referenz; Werte in Metern bzw. m³ und m²)
- **Measurements**: Liste der Messungen, jeweils mit:
  - `reference`: Der Geometrie-Cache-Schlüssel (z. B. `main:expr:123`, `gen:abc`) oder für `distance_between`: `<keyA>_<keyB>` (directional, **NICHT** sortiert)
  - `value`: Der gemessene Wert (null wenn Geometrie fehlt oder Messung fehlgeschlagen)
  - `error`: Fehlergrund falls Messung fehlgeschlagen (z. B. `no cached geometry`, `non-watertight`, `empty geometry`)

## Beispielkonfiguration

### Beispiel 1: Volumen spezifischer Elemente

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- List A: `["main:expr:101", "main:expr:102", "main:expr:103"]` (drei Wände)

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "main:expr:101", "value": 2.5, "error": null },
    { "reference": "main:expr:102", "value": 3.1, "error": null },
    { "reference": "main:expr:103", "value": 1.8, "error": null }
  ]
}
```

### Beispiel 2: Oberfläche mehrerer Elemente

**Einstellungen:**
- Messungstyp: `surface_area`

**Eingaben:**
- List A: `["main:expr:1", "main:expr:2"]`

**Ausgabe:**
```json
{
  "type": "surface_area",
  "unit": "area_unit",
  "measurements": [
    { "reference": "main:expr:1", "value": 45.2, "error": null },
    { "reference": "main:expr:2", "value": 12.8, "error": null },
    ...
  ]
}
```

### Beispiel 3: Bauteilhöhe (vertikal)

**Einstellungen:**
- Messungstyp: `component_height`
- Richtung: `[0.0, 0.0, 1.0]` (vertikale Höhe)

**Eingaben:**
- List A: `["main:expr:101"]` (eine Wand)

**Ausgabe:**
```json
{
  "type": "component_height",
  "unit": "length_unit",
  "measurements": [
    { "reference": "main:expr:101", "value": 2.8, "error": null }
  ]
}
```

### Beispiel 4: Volumen von Kollisionsschnittmengen

**Szenario:** Ein `collision`-Node (im Modus `intersection_mesh`) hat Schnittmengen erzeugt. Sie möchten das Volumen jeder Überlappung messen.

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- List A: `{"main:expr:1__main:expr:2": "inter:intersection_main:expr:1_main:expr:2", "main:expr:3__main:expr:4": "inter:intersection_main:expr:3_main:expr:4"}`

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "inter:intersection_main:expr:1_main:expr:2", "value": 0.05, "error": null },
    { "reference": "inter:intersection_main:expr:3_main:expr:4", "value": 0.12, "error": null }
  ]
}
```

### Beispiel 5: Abstand zwischen zwei Elementen (beide Richtungen)

**Einstellungen:**
- Messungstyp: `distance_between`

**Eingaben:**
- List A: `["main:expr:101", "main:expr:102"]` (zwei getrennte Wände)
- List B: `[]` (leer → Paare innerhalb von List A, beide Richtungen)

**Ausgabe:**
```json
{
  "type": "distance_between",
  "unit": "length_unit",
  "measurements": [
    { "reference": "main:expr:101_main:expr:102", "value": 2.5, "error": null },
    { "reference": "main:expr:102_main:expr:101", "value": 2.5, "error": null }
  ]
}
```

### Beispiel 6: Abstand zu Referenzpunkt

**Einstellungen:**
- Messungstyp: `distance_to_reference`
- Referenztyp: `point`
- Referenzpunkt: `[0.0, 0.0, 0.0]` (Weltursprung)

**Eingaben:**
- List A: `["main:expr:101", "main:expr:102"]`

**Ausgabe:**
```json
{
  "type": "distance_to_reference",
  "unit": "length_unit",
  "measurements": [
    { "reference": "main:expr:101", "value": 5.2, "error": null },
    { "reference": "main:expr:102", "value": 8.7, "error": null }
  ]
}
```

### Beispiel 7: Fehlerbehandlung

**Einstellungen:**
- Messungstyp: `volume`

**Eingaben:**
- List A: `["main:expr:101", "main:expr:999"]` (`main:expr:999` hat keine zwischengespeicherte Geometrie)

**Ausgabe:**
```json
{
  "type": "volume",
  "unit": "volume_unit",
  "measurements": [
    { "reference": "main:expr:101", "value": 2.5, "error": null },
    { "reference": "main:expr:999", "value": null, "error": "no cached geometry" }
  ]
}
```

Weitere Fehlerfälle:
- `non-watertight` — Volumenberechnung fehlgeschlagen aufgrund nicht reparierbarem Mesh
- `undefined normal` — Abstand zur Referenz mit Ebene + Null-Normale
- `undefined direction` — Bauteilhöhe mit Null-Richtung
- `empty geometry` — Das zwischengespeicherte Mesh hat keine Vertices oder keine Faces (Bauteilhöhe, Abstand zur Referenz, Abstand zwischen Elementen)
- `distance computation failed` — Das Backend für den exakten Oberflächenabstand (FCL) ist für ein Paar fehlgeschlagen; der Grund wird auf stderr protokolliert
- `measurement failed` — Unerwarteter Fehler bei der Berechnung eines Elements; der Grund wird auf stderr protokolliert

## Einheiten

Die zwischengespeicherte IFC-Geometrie wird von IfcOpenShell in **Metern** tesselliert (der Geometrie-Cache wandelt Koordinaten nicht zurück in die nativen Einheiten des Modells), daher basieren alle Messwerte auf Metern:

- **Volumen**: wird als `volume_unit` ausgegeben — Kubikmeter (m³)
- **Fläche** (Oberfläche): wird als `area_unit` ausgegeben — Quadratmeter (m²)
- **Abstand** (Bauteilhöhe, minimaler Abstand zwischen Elementen, Abstand zur Referenz): wird als `length_unit` ausgegeben — Meter (m)

## Hinweise

- **Projizierte Fläche**: Um die flache Grundrissfläche (projizierte Fläche) eines Elements zu messen, verwenden Sie den `geometry_projection`-Node, um das projizierte Grundriss-Mesh zu erzeugen, und messen Sie es anschließend hier mit dem Modus `surface_area`.
- **Wasserdichtigkeit für Volumen erforderlich**: Die Volumenberechnung erfordert wasserdichte Geometrie. Der Node versucht automatisch, nicht wasserdichte Meshes zu reparieren. Wenn die Reparatur fehlschlägt, wird die Messung mit Fehler gemeldet. Alle anderen Modi funktionieren mit jedem Mesh.
- **Abstand zwischen**: Referenzen folgen dem Format `<keyA>_<keyB>` (directional, **NICHT** sortiert). Bei leerer List B wird jedes ungeordnete Paar in **beiden Richtungen** ausgegeben (der Abstand selbst wird pro ungeordnetem Paar einmal berechnet und für beide wiederverwendet). Bei nicht-leerer List B eine Richtung pro A×B-Paar. Abstände sind exakte Oberflächen-zu-Oberflächen-Abstände via FCL-Dreiecks-BVHs: sich berührende oder überlappende Oberflächen geben exakt `0.0` zurück, und ein vollständig in einem anderen liegendes Mesh (ohne Berührung) meldet seinen positiven Oberflächenabstand. Die nächsten Punkte können in Face-/Edge-Interior liegen — Vertexpositionen werden nie als Näherung verwendet. Nur Elemente mit tessellierter Body-Geometrie sind messbar.
- **Abstand zur Referenz**: Im `plane`-Modus wird der Abstand von den Vertices gemessen, die von den Faces des Meshes referenziert werden (nicht referenzierte Vertices werden ignoriert); wenn die Ebene das Mesh schneidet (min ≤ 0 ≤ max über referenzierte Vertices), ist Abstand = 0. Null-Normale (z. B. `[0.0, 0.0, 0.0]`) erzeugt Fehler `undefined normal`. Nur Elemente mit tessellierter Body-Geometrie sind messbar.
- **Leere Liste**: Eine leere `List A` liefert null Messungen.
