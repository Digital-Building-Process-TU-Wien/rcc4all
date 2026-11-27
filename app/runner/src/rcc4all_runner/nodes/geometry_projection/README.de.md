---
title: Geometrieprojektion
description: Projiziert zwischengespeicherte Geometrien (z. B. Bauteilgrundrisse) auf eine Ebene durch den Weltursprung und speichert den flachen projizierten Grundriss als generierte Geometrie. Berechnet keine Flächen.
categories: Geometry
---

Der `geometry_projection`-Node projiziert die Geometrie jeder Eingangsreferenz auf eine
Ebene durch den **Weltursprung** und speichert die resultierende **flache Grundrissfläche** als
neue generierte Geometrie im Cache. Um die projizierte Fläche zu messen, übergeben Sie den
resultierenden Grundriss an den `surface_area`-Modus des `measurement`-Nodes. Dieser Node
erzeugt ein tatsächliches ebenes Mesh, das Sie downstream verwenden können (z. B. als Eingabe
für `collision`, `measurement` oder eine weitere `geometry_projection`).

Die projizierte Geometrie wird unter einem deterministischen `gen:proj_<reference>`-Schlüssel
gespeichert, der jede Eingangsreferenz im Ergebnis auf ihren generierten Schlüssel abbildet.
Der Node berechnet **keine** Flächen.

Alle Mesh-Flächen werden projiziert, unabhängig von ihrer Windung und davon, ob das Mesh
wasserdicht ist. Durchgehende Löcher und getrennte Regionen bleiben erhalten. Die Projektion
verwendet keine skalenabhängige Rundung oder Erweiterung der Polygone, sodass auch schmale Löcher
und kleine Zwischenräume zwischen Regionen erhalten bleiben.

## Anwendungsbeispiel

- Einen Grundriss (Draufsicht) eines Gebäudes oder Bauteils erzeugen und als Eingabe für
  einen Kollisions- oder Messungs-Check verwenden.
- Eine Schnittmenge (aus dem `collision`-Node) für weitere Analysen auf eine Ebene projizieren.

## Einstellungen

### Projektionsnormale

Der Normalenvektor der Projektionsebene. Die Ebene verläuft immer durch den **Weltursprung**.

- **Standard**: `[0.0, 0.0, 1.0]` (XY-Ebene, Draufsicht)
- **Format**: Liste von genau 3 Floats `[x, y, z]`
- **Normalisierung**: Die Normale wird intern normalisiert; nur die Richtung ist relevant, nicht
  die Länge. Die Normalisierung ist auch für sehr große und sehr kleine endliche Werte numerisch
  stabil.
- **Endliche Werte**: Alle drei Komponenten müssen endlich sein. `NaN` und unendliche Werte werden
  bei der Validierung der Einstellungen abgelehnt.
- **Null-Normale**: Wenn die Normale keine Länge hat (z. B. `[0.0, 0.0, 0.0]`), wird ein
  Fehlereintrag `undefined normal` für jede Eingabe erzeugt.
- **Beispiele**:
  - `[0, 0, 1]` → Projektion auf die XY-Ebene (Grundriss; `z=0`, `x/y`-Lage bleibt erhalten)
  - `[1, 0, 0]` → Projektion auf die YZ-Ebene
  - `[0, 1, 0]` → Projektion auf die XZ-Ebene

## Eingaben

- **Liste** (erforderlich): Liste voll qualifizierter Geometrie-Cache-Schlüssel
  (`<slug>:expr:<id>` für IFC-Elemente, `gen:<object_id>` für generierte Geometrie,
  `inter:<id>` für Hilfs-/Schnittgeometrie). Eine leere Liste liefert ein leeres Ergebnis.
  - **Dict-Eingabe**: Akzeptiert auch ein Dict (z. B. die `intersection_meshes`-Ausgabe des
    collision-Nodes). Die Nicht-Null-Werte des Dicts (Cache-Schlüssel) werden verwendet.

## Ausgaben

- **Projizierte Geometrien**: Ein Dict, das jeden eingegebenen Geometrie-Cache-Schlüssel auf
  den generierten `gen:proj_<...>`-Schlüssel abbildet, unter dem der Grundriss im Cache
  gespeichert wurde.
- **Fehler**: Eine Liste von `{reference, error}`-Fehlern pro Eingabe.

### Generierter Schlüssel

Der generierte Schlüssel ist `gen:proj_<reference>`, wobei jedes `:` und `/` in der Referenz
zu `_` reduziert wird. Innerhalb eines einzelnen Node-Aufrufs bildet dieselbe Referenz immer auf
denselben Schlüssel ab (idempotent); zwei verschiedene Referenzen, die auf dieselbe Basis reduziert
werden, erhalten `_1`, `_2`, … sodass ihre Grundrisse nie kollidieren. Ein bereits im Cache
vorhandener Schlüssel (z. B. von einem früheren Node) wird nicht wiederverwendet, sondern
mit `_n` ergänzt. Da der generierte Schlüssel nie eine saubere `:expr:<int>`-Sequenz enthält,
kann er downstream nie fälschlich als IFC-Referenz geparst werden.

| Eingangsreferenz | Generierter Schlüssel |
|------------------|----------------------|
| `main:expr:170` | `gen:proj_main_expr_170` |
| `inter:intersection_main:expr:766_main:expr:347` | `gen:proj_inter_intersection_main_expr_766_main_expr_347` |
| `gen:a_b` (dann `gen:a:b`) | `gen:proj_gen_a_b`, dann `gen:proj_gen_a_b_1` |

## Beispielkonfiguration

**Einstellungen:**
- Projektionsnormale: `[0.0, 0.0, 1.0]` (Draufsicht)

**Eingaben:**
- Liste: `["main:expr:101", "main:expr:102"]` (zwei Wände)

**Ausgabe:**
```json
{
  "projected_geometries": {
    "main:expr:101": "gen:proj_main_expr_101",
    "main:expr:102": "gen:proj_main_expr_102"
  },
  "errors": []
}
```

### Fehlerbehandlung

- `no cached geometry` — Die Referenz ist kein gültiger Geometrie-Cache-Schlüssel oder hat
  keine zwischengespeicherte Geometrie (z. B. `main:expr:999`).
- `no projected geometry` — Die Projektion ist leer/degeneriert (das Mesh liegt kantenparallel zur
  Projektionsebene), oder die Projektion/Triangulierung ist fehlgeschlagen. Unerwartete Fehler
  werden mit der betroffenen Referenz und dem Ausnahmetyp in stderr protokolliert.
- `undefined normal` — Die Projektionsnormale ist null. Wird für jede Eingabe ausgegeben.

**Eingaben:**
- Liste: `["main:expr:101", "main:expr:999"]`

**Ausgabe:**
```json
{
  "projected_geometries": {
    "main:expr:101": "gen:proj_main_expr_101"
  },
  "errors": [
    { "reference": "main:expr:999", "error": "no cached geometry" }
  ]
}
```

## Hinweise

- **Windung / Ausrichtung**: Bei negativen oder rotierten Normalen ist der Grundriss
  geometrisch korrekt, aber die Richtung der Flächennormalen kann invertiert sein. Verwenden
  Sie das Mesh rein als ebene Fläche.
- **Idempotenz**: Innerhalb eines einzelnen Node-Aufrufs erzeugt dieselbe, zweimal gelistete
  Referenz denselben generierten Schlüssel (eine Projektion und kein doppelter Grundriss). Eine
  erneute Ausführung gegen einen frischen
  Cache erzeugt ebenfalls dieselben Schlüssel — sie häuft kein `_1`, `_2`, … an. Ein bereits im
  gemeinsamen Cache vorhandener Schlüssel (z. B. von einem früheren Node) wird nicht
  wiederverwendet; er erhält einen `_n`-Suffix.
- **Leere Liste**: Eine leere **Liste** liefert ein leeres Ergebnis (keine Fehler).
