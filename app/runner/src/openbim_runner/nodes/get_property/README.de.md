---
title: Get Property
description: Definiert Eigenschaftswerte manuell oder liest sie aus IFC-Elementen für die Weiterverarbeitung.
categories: IFC
---

Der `get_property` Knoten verbindet **manuell definierte Werte** und **Werte aus dem Modell**, wodurch er sowohl als reiner Wertelieferant für nachgelagerte Knoten als auch als Extraktionsschritt aus dem IFC-Modell verwendet werden kann.

- **Werte manuell definieren** — Kein Eingang erforderlich. Geben Sie Eigenschaftswerte von Hand an, um Daten zu injizieren, die das Modell nicht enthält, oder um benutzerdefinierte Werte für nachgelagerte Knoten bereitzustellen.
- **Werte aus dem Modell lesen** — Verbinden Sie einen Eingang (Express IDs, typischerweise von einem `ifc_element_filter`). Der Knoten liest Eigenschaftswerte aus diesen IFC-Elementen.

Jede Auswahl spezifiziert einen optionalen Entity-Typ, einen optionalen PropertySet, einen erforderlichen Property-Namen und eine **Value Source**, die bestimmt, wie der Wert aufgelöst wird. Der Knoten gibt Eigenschaftswerte in einem von drei Modi aus: Per explicit element, Per element class oder Without element class distinction.

## Anwendungsbeispiel

- Eine benutzerdefinierte Eigenschaft (z.B. `CostCategory`) für Wände ohne Modelldaten definieren und dann in der nachgelagerten Analyse verwenden
- `FireRating` aus `Pset_WallCommon` für alle Wände lesen, die von einem `ifc_element_filter` gefiltert wurden
- `Fallback` verwenden, um einen Standard-`AcousticRating`-Wert bereitzustellen, wenn der Modellwert fehlt
- Wände als "large" oder "small" klassifizieren using `Override if condition` basierend auf der Fläche

## Einstellungen

### Output mode

Bestimmt die Granularität der Ausgabe. Der Modus kann automatisch wechseln, abhängig davon, ob ein Eingang verbunden ist oder eine Entity ausgewählt ist.

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
| **Property** (erforderlich) | Der Name der zu lesenden oder zu definierenden Eigenschaft. Platzhalter: "Required". |
| **Value Source** | Bestimmt, wie der Wert aufgelöst wird. Siehe die vier Optionen unten. |
| **Manual Value** | Der Wert, der verwendet wird, wenn Value Source `Fallback`, `Manual` oder `Override if condition` ist. Erforderlich für `Fallback` und `Manual`. Wird von `Override if condition` verwendet, wenn die Bedingung erfüllt ist. |

### Value Source Optionen

| Value Source | Beschreibung | Beispiel |
|--------------|--------------|----------|
| **From model** | Liest den Wert aus der IFC-Entität via `get_psets`. Gibt `null` zurück, wenn die Eigenschaft nicht gefunden wird. Verwenden, wenn Sie immer den rohen Modellwert möchten. | Modell hat `FireRating = "F90"` → Ausgabe ist `"F90"`. Eigenschaft existiert nicht → Ausgabe ist `null`. |
| **Fallback** | Verwendet den Modellwert falls vorhanden; verwendet den manuellen Wert wenn der Modellwert fehlt (`null`) oder leer (`""`) ist. Verwenden, wenn Sie Lücken in den Modelldaten füllen möchten. | Modell hat `AcousticRating = "Rw45"` → Ausgabe ist `"Rw45"`. Modell hat kein `AcousticRating` oder es ist `""` → Ausgabe ist der manuelle Fallback-Wert (z.B. `"Rw0"`). |
| **Manual** | Verwendet immer den manuellen Wert und ignoriert den Modellwert vollständig. Dies ist die Quelle, die Sie verwenden, wenn Sie Eigenschaften ohne Eingabedaten definieren möchten. Verwenden, wenn Sie einen spezifischen Wert unabhängig vom Modell erzwingen möchten. | Modell hat `IsExternal = "true"`, aber Sie setzen manuellen Wert `"false"` → Ausgabe ist `"false"`. |
| **Override if condition** | Verwendet den manuellen Wert wenn der Modellwert eine Bedingung erfüllt; andernfalls den Modellwert. Erfordert einen **Operator** und einen **Condition value**. Verwenden für Klassifizierung, Compliance-Prüfungen oder Datenqualitätsregeln. | Modell hat `Area = 45`. Bedingung: `>` `30`, manueller Wert: `"large"` → Ausgabe ist `"large"`. Ein anderes Element hat `Area = 20` → Bedingung nicht erfüllt, Ausgabe ist `"20.0"` (der Modellwert). |

**Condition Operatoren:** `>` (größer als), `≥` (größer oder gleich), `<` (kleiner als), `≤` (kleiner oder gleich), `=` (gleich), `≠` (ungleich).

## Inputs

- **Express IDs** (optional): Liste von IFC Express-IDs, von denen Eigenschaftswerte gelesen werden sollen. Typischerweise mit dem Ausgang eines `ifc_element_filter` verbunden. Kann unverbunden bleiben, wenn manuelle Werte mit **Per element class** oder **Without element class distinction** Output-Modi verwendet werden. Wenn unverbunden, produzieren nur `Fallback` und `Manual` Quellen eine Ausgabe (in **Per element class** und **Without element class distinction** Modi). Der **Per explicit element** Modus erfordert tatsächliche Eingabeelemente und erzeugt eine leere Ausgabe, wenn keine Elemente verbunden sind.

## Outputs

Ausgabestruktur hängt vom **Output mode** ab:

### Per explicit element

Liste von Elementen mit ihren Express-IDs und Eigenschaftswerten. Jedes Element enthält:
- `express_id`: Die Express-ID des IFC-Elements
- `properties`: Wörterbuch von Eigenschaftswerten, geschlüsselt nach `PropertySet.PropertyName`. Werte sind Strings oder `null` für fehlende Modellwerte (wenn Value Source `From model` ist und die Eigenschaft fehlt).

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

### Beispiel 1: Gemischte Value Sources (From model, Fallback, Manual)

**Selections:**
1. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `FireRating`, Value Source: `From model`
2. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `AcousticRating`, Value Source: `Fallback`, Manual value: `Rw45`
3. Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `IsExternal`, Value Source: `Manual`, Manual value: `false`

**Ausgabe** für eine Wand mit Express-ID 101 (Modell hat FireRating="F90", kein AcousticRating, IsExternal="true"):

```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.FireRating": "F90",
        "Pset_WallCommon.AcousticRating": "Rw45",
        "Pset_WallCommon.IsExternal": "false"
      }
    }
  ]
}
```

### Beispiel 2: Fallback bei leerem String

Wenn das Modell `Comments: ""` (leerer String) hat, verwendet eine `Fallback`-Auswahl für `Comments` den manuellen Wert.

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `Comments`, Value Source: `Fallback`, Manual value: `No comments`

**Ausgabe:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.Comments": "No comments"
      }
    }
  ]
}
```

### Beispiel 3: Override if condition

**Szenario:** Zwei Wände mit Flächen 45 m² und 20 m². Klassifiziere Wände größer als 30 m² als "large".

**Selection:** Entity: `Any Element`, Pset: `Pset_WallCommon`, Property: `Area`, Value Source: `Override if condition`, Operator: `>`, Condition value: `30`, Manual value: `large`

**Ausgabe:**
```json
{
  "mode": "elements",
  "elements": [
    {
      "express_id": 101,
      "properties": {
        "Pset_WallCommon.Area": "large"
      }
    },
    {
      "express_id": 205,
      "properties": {
        "Pset_WallCommon.Area": "20.0"
      }
    }
  ]
}
```

Die erste Wand (45 > 30) wird zu "large" überschrieben; die zweite Wand (20 ≤ 30) behält ihren Modellwert.

### Beispiel 4: Output mode — Per element class

**Szenario:** Drei Entitäten (zwei IFCWALL mit FireRating F90, eine IFCDOOR mit IsExternal true).

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `FireRating`, Value Source: `From model`
2. Entity: `IFCDOOR`, Pset: `Pset_DoorCommon`, Property: `IsExternal`, Value Source: `From model`

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

### Beispiel 5: Output mode — Without element class distinction (mit übergreifender PropertySet-Aggregation)

**Szenario:** Mehrere Wände und Platten mit `Compartmentation` Eigenschaft. Wände speichern sie in `Pset_WallCommon`, Platten in `Pset_SlabCommon`. Sie möchten modellweite Gesamtzähler.

**Selections:**
1. Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `Compartmentation`, Value Source: `From model`
2. Entity: `IFCSLAB`, Pset: `Pset_SlabCommon`, Property: `Compartmentation`, Value Source: `From model`

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

### Beispiel 6: Manuelle Werte ohne Eingabeelemente

Wenn keine Elemente an **Express IDs** angeschlossen sind, erzeugen Auswahlen mit `Fallback` oder `Manual` Source dennoch eine Ausgabe in **Per element class** und **Without element class distinction** Modi. Dies ermöglicht das Definieren von Eigenschaftswerten manuell, ohne Elemente aus dem Modell zu filtern.

**Selection:** Entity: `IFCWALL`, Pset: `Pset_WallCommon`, Property: `LoadBearing`, Value Source: `Manual`, Manual value: `true`

**Ausgabe** mit **Per element class** Modus:
```json
{
  "mode": "by_class",
  "classes": [
    {
      "id": "IFCWALL",
      "properties": {
        "Pset_WallCommon.LoadBearing": [{ "value": "true", "count": 1 }]
      }
    }
  ]
}
```

**Ausgabe** mit **Without element class distinction** Modus:
```json
{
  "mode": "model",
  "properties": {
    "Pset_*.LoadBearing": [{ "value": "true", "count": 1 }]
  }
}
```

Hinweis: Der **Per explicit element** Modus erfordert tatsächliche Eingabeelemente und erzeugt eine leere Ausgabe, wenn keine Elemente verbunden sind.

## CSV Import/Export

Eigenschaftsauswahlen können als CSV-Dateien importiert und exportiert werden. Das CSV-Format umfasst die folgenden Spalten:

```csv
entity_type,property_set,property_name,source,manual_value
IFCWALL,Pset_WallCommon,FireRating,from_model,
IFCWALL,Pset_WallCommon,AcousticRating,fallback,Rw45
IFCWALL,Pset_WallCommon,IsExternal,override,false
```

- **entity_type**: Optional. Dient hauptsächlich der UI-Vorauswahl und Elementfilterung.
- **property_set**: Optional. Leer lassen, um über alle PropertySets zu suchen.
- **property_name**: Erforderlich.
- **source**: Standardisiert auf `from_model` wenn weggelassen. Einer von: `from_model`, `fallback`, `override`, `condition`.
- **manual_value**: Erforderlich für `fallback`, `override` und `condition` Quellen.
