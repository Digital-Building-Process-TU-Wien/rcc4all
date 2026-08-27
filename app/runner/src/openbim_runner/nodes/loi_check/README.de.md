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

- **Express IDs** (optional): die Express-IDs, gegen die geprüft wird,
  üblicherweise vom `ifc_element_filter`. Ohne Verbindung/leer → alle
  `IfcElement`s im Modell werden geprüft.

## Ausgaben

- `element_count`, `total_checks`, `failed_count`
- `passed_express_ids`, `failed_express_ids`: flache Listen der Express-IDs der
  geprüften Elemente – jene, deren Prüfungen alle bestanden haben, und jene mit
  mindestens einer fehlgeschlagenen Prüfung. Elemente ohne angewandte Prüfungen
  sind von beiden Listen ausgeschlossen.
- `elements`: jeweils mit `express_id`, `class_name` (oder `unknown`), `failed`
  und `checks` – jede Prüfung hat `id`/`property_key`, `property_name`,
  `condition`, `expected`, optional `expected_min`/`expected_max`
  (Bereichsgrenzen), `actual` (`null` bei fehlender Eigenschaft) und `passed`.

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
  "element_count": 2,
  "total_checks": 6,
  "failed_count": 2,
  "elements": [
    {
      "express_id": 1235,
      "class_name": "IFCWALL",
      "failed": false,
      "checks": [
        { "id": "Pset_WallCommon.LoadBearing", "property_key": "Pset_WallCommon.LoadBearing", "property_name": "LoadBearing", "condition": "equals", "expected": "true", "actual": "true", "passed": true },
        { "id": "Pset_WallCommon.ThermalTransmittance", "property_key": "Pset_WallCommon.ThermalTransmittance", "property_name": "ThermalTransmittance", "condition": "lt", "expected": "0.4", "actual": "0.25", "passed": true },
        { "id": "Pset_WallCommon.FireRating", "property_key": "Pset_WallCommon.FireRating", "property_name": "FireRating", "condition": "one_of", "expected": "F30, F60", "actual": "F30", "passed": true }
      ]
    },
    {
      "express_id": 1234,
      "class_name": "IFCWALL",
      "failed": true,
      "checks": [
        { "id": "Pset_WallCommon.LoadBearing", "property_key": "Pset_WallCommon.LoadBearing", "property_name": "LoadBearing", "condition": "equals", "expected": "true", "actual": "true", "passed": true },
        { "id": "Pset_WallCommon.ThermalTransmittance", "property_key": "Pset_WallCommon.ThermalTransmittance", "property_name": "ThermalTransmittance", "condition": "lt", "expected": "0.4", "actual": "0.8", "passed": false },
        { "id": "Pset_WallCommon.FireRating", "property_key": "Pset_WallCommon.FireRating", "property_name": "FireRating", "condition": "one_of", "expected": "F30, F60", "actual": "F90", "passed": false }
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
