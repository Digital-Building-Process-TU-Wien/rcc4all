---
title: Get Property
description: Liest Eigenschaftswerte aus IFC-Elementen für die Weiterverarbeitung.
categories: IFC
---

Der `get_property` Knoten liest Eigenschaftswerte aus IFC-Elementen. Jede Auswahl spezifiziert einen optionalen Entity-Typ, einen optionalen PropertySet und einen erforderlichen Property-Namen. Der Knoten gibt Eigenschaftswerte in einem von drei Modi aus: Per explicit element, Per element class oder Without element class distinction.

## Anwendungsbeispiel

- `FireRating` aus `Pset_WallCommon` für alle Wände lesen, die von einem `ifc_element_filter` gefiltert wurden
- `LoadBearing`-Status von mehreren Elementklassen für die Analyse extrahieren
- Unterschiedliche Eigenschaftswerte mit Vorkommenszählern für modellweite Statistiken sammeln

## Einstellungen

### Output mode

Bestimmt die Granularität der Ausgabe.

| Wert | Label | Wann verwenden |
|------|-------|----------------|
| `elements` | **Per explicit element** | Jedes Element im Eingang erhält einen eigenen Eintrag mit aufgelösten Eigenschaftswerten. Verwenden, wenn Sie jedes Element einzeln nachgelagert verarbeiten möchten. Erfordert eine Input-Bindung. |
| `by_class` | **Per element class** | Elemente werden nach ihrer tatsächlichen Laufzeitklasse gruppiert (z.B. `IFCWALL`, `IFCDOOR`). Jede Klasse zeigt unterschiedliche Eigenschaftswerte mit Vorkommenszählern. Verwenden, wenn Sie Statistiken pro Elementtyp möchten. |
| `model` | **Without element class distinction** | Unterschiedliche Eigenschaftswerte mit Vorkommenszählern über alle Entitäten und PropertySets hinweg. Eigenschaftsschlüssel verwenden einen Wildcard `Pset_*.PropertyName`, um Zähler aus verschiedenen PropertySets zusammenzuführen. Verwenden, wenn Sie modellweite Statistiken möchten. |

### Selections Tabelle

| Spalte | Beschreibung |
|--------|--------------|
| **Entity** (optional) | IFC-Elementtyp (z.B. `IFCWALL`, `IFCDOOR`). Platzhalter: "Any Element". Wenn gesetzt, tragen nur Elemente dieses Typs zur Eigenschaftsausgabe bei (wirkt als Filter). Leer bedeutet jeden Elementtyp. |
| **Pset** (optional) | IFC PropertySet-Name (z.B. `Pset_WallCommon`) oder ein benutzerdefinierter PropertySet-Name. Platzhalter: "Any PSET". Wenn gesetzt, beschränkt die Suche auf diesen PropertySet. Wenn leer, durchsucht alle PropertySets nach dem Property-Namen. |
| **Property** (erforderlich) | Der Name der zu lesenden Eigenschaft aus dem Modell. Platzhalter: "Required". |

## Inputs

- **Express IDs** (optional): Liste von IFC Express-IDs, von denen Eigenschaftswerte gelesen werden sollen. Typischerweise mit dem Ausgang eines `ifc_element_filter` verbunden. Wenn unverbunden, ist die Ausgabe leer (keine Elemente zum Lesen).

## Outputs

Ausgabestruktur hängt vom **Output mode** ab:

### Per explicit element

Liste von Elementen mit ihren Express-IDs und Eigenschaftswerten. Jedes Element enthält:
- `express_id`: Die Express-ID des IFC-Elements
- `properties`: Wörterbuch von Eigenschaftswerten, geschlüsselt nach `PropertySet.PropertyName`. Werte sind Strings oder `null` für fehlende Modellwerte.

### Per element class

Aggregiert nach IFC-Klasse. Ausgabe enthält:
- `classes`: Array von Klassengruppen, jede mit:
  - `id`: IFC-Klassenname (z.B. `IFCWALL`, `IFCDOOR` oder `unknown` für fehlende Entitäten)
  - `properties`: Wörterbuch von unterschiedlichen Werten mit Zählern pro Eigenschaft, sortiert nach Anzahl (absteigend) dann Wert (aufsteigend). Fehlende/null-Werte sind ausgeschlossen.

### Without element class distinction

Unterschiedliche Werte mit Zählern pro Eigenschaft, aggregiert über alle PropertySets und Klassen hinweg. Ausgabe enthält:
- `properties`: Wörterbuch geschlüsselt nach `Pset_*.PropertyName` (Wildcard-PropertySet zur Aggregation über PropertySets hinweg), jedes enthaltend:
  - Array von `{ value, count }` Objekten, sortiert nach Anzahl (absteigend) dann Wert (aufsteigend)
  - Fehlende/null-Werte sind von der Zählung ausgeschlossen

## Beispielkonfiguration

### Beispiel 1: Eigenschaftswerte aus Elementen lesen

**Selections:**
1. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `FireRating`
2. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `IsExternal`

**Ausgabe** für eine Wand mit Express-ID 101 (Modell hat FireRating="F90", IsExternal=false):

```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.IsExternal": "false"
      }
    }
  ]
}
```

### Beispiel 2: Fehlende Eigenschaft gibt null zurück

Wenn das Modell eine Eigenschaft nicht hat, ist der Wert `null`.

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `AcousticRating` (im Modell nicht vorhanden)

**Ausgabe:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.AcousticRating": null
      }
    }
  ]
}
```

### Beispiel 3: Output mode — Per element class

**Szenario:** Drei Entitäten (zwei IFCWALL mit FireRating F90, eine IFCDOOR mit IsExternal true).

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `FireRating`
2. Entity: `IFCDOOR`, Pset: `Pset_DoorCommon`, Property: `IsExternal`

**Ausgabe:**
```json
{
  "mode": "by_class",
  "classes": [
    {
      "id": "IFCDOOR",
      "properties": {
        "Pset_DoorCommon.IsExternal": [{"value": "true", "count": 1}]
      }
    },
    {
      "id": "IFCWALL",
      "properties": {
        "Pset_WallCommon.FireRating": [{"value": "F90", "count": 2}]
      }
    }
  ]
}
```

### Beispiel 4: Output mode — Without element class distinction (mit übergreifender PropertySet-Aggregation)

**Szenario:** Mehrere Wände und Platten mit `Compartmentation` Eigenschaft. Wände speichern sie in `Pset_WallCommon`, Platten in `Pset_SlabCommon`. Sie möchten modellweite Gesamtzähler.

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `Compartmentation`
2. Entity: `IFCSLAB`, Pset: `Pset_SlabCommon`, Property: `Compartmentation`

**Ausgabe:**
```json
{
  "mode": "model",
  "properties": {
    "Pset_*.Compartmentation": [
      { "value": "true", "count": 20 },
      { "value": "false", "count": 5 }
    ]
  }
}
```

Beachten Sie wie Zähler aus beiden PropertySets in `Pset_*.Compartmentation` zusammengeführt werden. Dies ist der Hauptunterschied zum **Per element class** Modus.

## CSV Import/Export

Eigenschaftsauswahlen können als CSV-Dateien importiert und exportiert werden. Das CSV-Format umfasst die folgenden Spalten:

```csv
entity_type,property_set,property_name
IFCWALL,Pset_WallCommon,FireRating
IFCWALL,Pset_WallCommon,IsExternal
```

- **entity_type**: Optional. Dient hauptsächlich der UI-Vorauswahl und Elementfilterung.
- **property_set**: Optional. Leer lassen, um über alle PropertySets zu suchen.
- **property_name**: Erforderlich.
