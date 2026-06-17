---
title: IfcElementFilter
description: Filtert IFC-Entitaeten mit tabellenbasierten Include- und Exclude-Regeln.
categories: IFC, Filter, Advanced
---

Der `ifc_element_filter` Knoten filtert IFC-Modellelemente ueber eine Komponententabelle. Jede Zeile beschreibt eine Bedingung mit Entity-Typ, optionalem `PredefinedType` und optionalem Attribut- oder PropertySet-Vergleich. Include-Zeilen werden per OR-Logik zusammengefuehrt, danach werden Exclude-Zeilen vom Ergebnis abgezogen.

Verwenden Sie diesen Knoten, wenn Sie:

- Elemente nach IFC-Klasse wie `IFCWALL`, `IFCDOOR` oder `IFCSPACE` filtern moechten
- Elemente pro Zeile einschliessen oder ausschliessen moechten
- Nach `GlobalId`, `Name`, `PredefinedType`, direkten IFC-Attributen oder PropertySet-Werten filtern moechten
- Komplexere Auswahlen aus mehreren Regeln aufbauen moechten

## Einstellungen

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `filter_rows` | `list[FilterRow]` | Liste der Filterzeilen. Jede Zeile beschreibt eine vollstaendige Filterbedingung. |

## FilterRow-Struktur

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `mode` | `include`, `exclude`, `disabled` | Include fuegt Treffer hinzu, exclude entfernt Treffer, disabled ignoriert die Zeile. |
| `entity_type` | `str` | IFC-Entity-Typ, zum Beispiel `IFCWALL` oder `IFCSLAB`. |
| `predefined_type` | `str` | Optionaler `PredefinedType`-Wert. Leer bedeutet beliebiger PredefinedType. Wenn der Wert nicht aus der PredefinedType-Liste ausgewählt, sondern manuell eingegeben wird, soll das Programm ihn als benutzerdefinierten Typ behandeln: `PredefinedType == USERDEFINED` und `ObjectType == <eingegebener Wert>`. |
| `property_set` | `str` | Optionaler IFC-PropertySet-Name, zum Beispiel `Pset_WallCommon`. Wenn `Attributes` ausgewählt ist, sind damit die direkten IFC-Attribute der ausgewählten Entity gemeint. Leer erlaubt direkte Attributsuche oder Suche in allen PropertySets. |
| `property_name` | `str` | Optionaler IFC-Attribut- oder PropertySet-Property-Name. Leer bedeutet kein Wertvergleich. |
| `operator` | `str` | Vergleichsoperator. |
| `value` | `str` | Vergleichswert. |

## Operatoren

- `==` gleich
- `!=` ungleich
- `<` kleiner als
- `>` groesser als
- `<=` kleiner oder gleich
- `>=` groesser oder gleich
- `contains` enthaelt Text
- `starts_with` beginnt mit Text
- `ends_with` endet mit Text

## Ausgaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `express_ids` | `list[int]` | Express-IDs aller passenden Entitaeten. |
| `guids` | `list[str]` | `GlobalId`-Werte aller passenden Entitaeten in derselben Reihenfolge wie `express_ids`. |

## Beispiel

Alle Waende filtern, aber externe Waende ausschliessen:

```json
{
  "filter_rows": [
    {
      "mode": "include",
      "entity_type": "IFCWALL",
      "predefined_type": "",
      "property_set": "",
      "property_name": "",
      "operator": "==",
      "value": ""
    },
    {
      "mode": "exclude",
      "entity_type": "IFCWALL",
      "predefined_type": "",
      "property_set": "Pset_WallCommon",
      "property_name": "IsExternal",
      "operator": "==",
      "value": "True"
    }
  ]
}
```

## Hinweise

- Leere `filter_rows` liefern ein leeres Ergebnis.
- Unbekannte IFC-Entity-Typen liefern keine Treffer.
- Stringvergleiche sind case-insensitive.
- Numerische Vergleichsoperatoren benoetigen numerische Werte.
- Vorschlagslisten fuer PropertySets koennen spaeter ueber JSON-Dateien in `app/web/public/list` angebunden werden, ohne den Runner-Vertrag zu aendern.
