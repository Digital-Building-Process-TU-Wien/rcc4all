---
title: LOI-Check
description: Prüft IFC-Eigenschaftswerte gegen erwartete Zielwerte mit tabellenbasierten Regeln.
categories: IFC
---

Der `loi_check`-Node führt tabellenbasierte Eigenschaftsprüfungen an
IFC-Elementen durch. Jede Zeile definiert eine zu lesende Eigenschaft und eine
Bedingung, die gegen einen Zielwert ausgewertet wird, und wird gegen jedes
Eingabeelement geprüft.

## Anwendungsbeispiel

- Prüfen, dass bei jeder Wand `Pset_WallCommon.LoadBearing` gleich `true` ist
- Wärmedämmung prüfen (`Pset_WallCommon.ThermalTransmittance < 0.4`)
- Fehlende Pflichteigenschaften kennzeichnen (z.B. fehlendes `FireRating`)

## Einstellungen

### Vergleichstabelle

| Spalte | Beschreibung |
|--------|--------------|
| **Component** (optional, Standard "Any Element") | IFC-Entity-Typ (z.B. `IFCWALL`, `IFCDOOR`), der begrenzt, welche Prüfungen gelten. Wenn **irgendeine** Zeile "Any Element" ist (leere Component oder der Token `any`), werden **alle** Eingabeelemente geprüft und ausgegeben. Andernfalls erscheinen nur Elemente, die mindestens einem angegebenen Typ entsprechen. |
| **Pset** (optional) | PropertySet, in dem gesucht wird (z.B. `Pset_WallCommon`); leer sucht über alle PropertySets. |
| **Property** (erforderlich) | Name der zu vergleichenden Eigenschaft. |
| **Condition** (erforderlich) | Der Vergleichsoperator (siehe unten). |
| **Target value** | Der erwartete Wert. Bei `between`/`outside` enthält die Spalte Min/Max + Inklusivitäts-Schalter, bei `one_of` die akzeptierten Werte. Bei `is_true`/`is_false` deaktiviert. |

Zeichenketten-Bedingungen (`equals`, `not_equals`, `contains`, `one_of`) sind
Groß-/Kleinschreibungs- und Leerzeichen-unabhängig. Numerische Bedingungen
(`lt`/`le`/`gt`/`ge`) und Bereiche benötigen numerische Werte – nicht numerische
Werte schlagen fehl, ebenso fehlende Eigenschaften.

### Bedingungen

| Bedingung | Bedeutung |
|-----------|-----------|
| `equals` / `not_equals` | actual == / != expected (Zeichenkette) |
| `lt` `le` `gt` `ge` | actual < / <= / > / >= expected (numerisch) |
| `contains` | expected ist Teilstring von actual |
| `one_of` | actual entspricht einem akzeptierten Wert |
| `between` / `outside` | actual innerhalb / außerhalb von `[Min, Max]` (Inklusivität pro Grenze) |
| `is_true` / `is_false` | actual ist wahr (`true`/`1`/`yes`…) / falsch (`false`/`0`/`no`…) |

### Akzeptierte Werte (`one_of`)

Wechselt die Zielwert-Spalte zu einem Wertelisten-Editor. Die Prüfung besteht,
wenn der Eigenschaftswert einem akzeptierten Wert entspricht. Mindestens ein
akzeptierter Wert ist erforderlich.

### Numerische Bereiche (`between` / `outside`)

| Feld | Optionen |
|------|----------|
| **Min** / **Max** | Die numerischen Grenzen (müssen gesetzt und numerisch sein). |
| **incl. Min** / **incl. Max** | aktiviert → `>=` / `<=`, deaktiviert → `>` / `<` |

`between` besteht, wenn der Wert innerhalb von `[Min, Max]` liegt (gemäß den
Schaltern); `outside` besteht, wenn er außerhalb liegt.

## Eingaben

- **Express IDs** (erforderlich): Liste voll qualifizierter Referenzen
  (`<slug>:expr:<id>`), gegen die geprüft wird — üblicherweise
  `ifc_element_filter.express_ids` gebunden. Jede Referenz wird gegen das in ihr
  genannte Modell aufgelöst; gemischte Listen aus mehreren Modellen sind erlaubt.
  Eine leere gebundene Liste läuft ohne geprüfte Elemente (vakuum bestanden) —
  es gibt keinen Ganzmodell-Fallback. Eine fehlende ID liefert ein
  `unknown`-Element ohne angewandte Prüfungen, solange kein Component-Typ
  angegeben ist.

## Ausgaben

Der Executor umhüllt jede Node-Ausgabe mit `{ label, type, result }`, wobei
`label` (Laufzeitname) und `type` (`"loi_check"`) im äußeren Envelope liegen.
Das `result`-Objekt der Node selbst enthält nur die folgenden Felder:

- `summary_element_count`, `summary_passed_count`, `summary_failed_count` (auf
  Elementebene) und `summary_check_count` (Gesamtzahl der Prüfungen).
- `passed_express_ids`, `failed_express_ids`: flache Listen der voll
  qualifizierten Referenzen (`<slug>:expr:<id>`) der geprüften Elemente – jene,
  deren Prüfungen alle bestanden haben, und jene mit mindestens einer
  fehlgeschlagenen Prüfung. Elemente ohne angewandte Prüfungen sind von beiden
  Listen ausgeschlossen.
- `elements`: jeweils mit `express_ids` (Liste voll qualifizierter
  Referenzen), `class_name` (oder `unknown`), `failed` und `checks` – jede
  Prüfung hat `key`, `check_parameter` (Eigenschaftsname), `expected_value`,
  `actual_value` (String, leer bei fehlender Eigenschaft), `unit` (leer bei
  unbekannt), `missing` (true, wenn die Eigenschaft fehlt), `passed`, sowie
  `expected_value_condition` (Vergleichsoperator) und
  `expected_value_min` / `expected_value_max` (Bereichsgrenzen bei
  `between`/`outside`, sonst leer).

## Beispiel

**Prüftabelle:**
| Component | Pset | Property | Condition | Target |
|-----------|------|----------|-----------|--------|
| IFCWALL | Pset_WallCommon | LoadBearing | equals | true |
| IFCWALL | Pset_WallCommon | ThermalTransmittance | lt | 0.4 |
| IFCWALL | Pset_WallCommon | FireRating | one_of | F30\|F60 |

**Ausgabe** für eine Wand mit `ThermalTransmittance = 0.25` und eine mit `0.8`:

```json
{
  "summary_element_count": 2,
  "summary_passed_count": 1,
  "summary_failed_count": 1,
  "summary_check_count": 6,
  "passed_express_ids": ["main:expr:1235"],
  "failed_express_ids": ["main:expr:1234"],
  "elements": [
    {
      "express_ids": ["main:expr:1235"],
      "class_name": "IFCWALL",
      "failed": false,
      "checks": [
        { "key": "Pset_WallCommon.LoadBearing", "check_parameter": "LoadBearing", "expected_value": "true", "actual_value": "true", "unit": "", "missing": false, "passed": true, "expected_value_condition": "equals", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.ThermalTransmittance", "check_parameter": "ThermalTransmittance", "expected_value": "0.4", "actual_value": "0.25", "unit": "", "missing": false, "passed": true, "expected_value_condition": "lt", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.FireRating", "check_parameter": "FireRating", "expected_value": "F30, F60", "actual_value": "F30", "unit": "", "missing": false, "passed": true, "expected_value_condition": "one_of", "expected_value_min": "", "expected_value_max": "" }
      ]
    },
    {
      "express_ids": ["main:expr:1234"],
      "class_name": "IFCWALL",
      "failed": true,
      "checks": [
        { "key": "Pset_WallCommon.LoadBearing", "check_parameter": "LoadBearing", "expected_value": "true", "actual_value": "true", "unit": "", "missing": false, "passed": true, "expected_value_condition": "equals", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.ThermalTransmittance", "check_parameter": "ThermalTransmittance", "expected_value": "0.4", "actual_value": "0.8", "unit": "", "missing": false, "passed": false, "expected_value_condition": "lt", "expected_value_min": "", "expected_value_max": "" },
        { "key": "Pset_WallCommon.FireRating", "check_parameter": "FireRating", "expected_value": "F30, F60", "actual_value": "F90", "unit": "", "missing": false, "passed": false, "expected_value_condition": "one_of", "expected_value_min": "", "expected_value_max": "" }
      ]
    }
  ]
}
```

## CSV Import/Export

Zeilen können als CSV importiert/exportiert werden:

```csv
sep=;
entity_type;property_set;property_name;condition;expected_value;allowed_values;range_min;range_max;inclusive_min;inclusive_max
IFCWALL;Pset_WallCommon;LoadBearing;equals;true
IFCWALL;Pset_WallCommon;ThermalTransmittance;lt;0.4
IFCWALL;Pset_WallCommon;FireRating;one_of;;F30|F60
IFCWALL;Pset_WallCommon;ThermalTransmittance;between;;;0.2;0.6;true;true
```

- **entity_type**: Optional; auch für die UI-Vorauswahl.
- **property_set**: Optional; leer sucht über alle PropertySets.
- **property_name**: Erforderlich.
- **condition**: Erforderlich, einer von `equals`, `not_equals`, `lt`, `le`,
  `gt`, `ge`, `contains`, `one_of`, `between`, `outside`, `is_true`, `is_false`.
- **expected_value**: Optionales Einzelwert-Ziel.
- **allowed_values**: Mit `|` getrennte Liste für `one_of` (z.B. `F30|F60`).
- **range_min** / **range_max**: Erforderlich bei `between`/`outside`.
- **inclusive_min** / **inclusive_max**: `true`/`false`, Inklusivität pro Grenze.
