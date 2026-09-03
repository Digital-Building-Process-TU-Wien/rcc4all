---
title: Neigung von Bauteilen
description: Misst die Neigung von Bauteilen (Wände/Decken als 2D-Flächen, Stützen/Träger als 1D-Achsen) und kennzeichnet Bauteile, deren Neigung den konfigurierten Vergleichsgrenzwert verletzt.
categories: geometry
---

Der `tilt_of_components`-Knoten misst die Neigung von IFC-Bauteilen relativ zur
horizontalen Ebene und kennzeichnet Bauteile, die außerhalb eines konfigurierten
Grenzwerts liegen. Der Neigungswert entspricht stets dem **kleineren Winkel zwischen
der dominanten Fläche/Achse des Bauteils und der horizontalen Ebene**: eine vertikale
Wand oder Stütze misst `90°`, eine horizontale Decke oder ein Träger `0°`.

Ein **Element-Kategorie**-Auswahlfeld entscheidet, welcher Algorithmus für jedes
Eingabe-Element verwendet wird:

- **2D (Wände & Decken):** Die Dreiecke des Netzes werden anhand ihrer
  Normalenvektoren zu Flächen gruppiert. Die beiden größten Flächen (Vorder- und
  Rückseite) werden gemessen. Die Neigung jeder Fläche ist der Durchschnittswinkel
  ihrer Dreiecks-Normalen zur horizontalen Ebene (komplementiert, um unter `90°`
  zu bleiben).
- **1D (Stützen & Träger):** Die Dreiecke des Netzes werden zu Flächen gruppiert.
  Der flächengewichtete Schwerpunkt jeder Fläche wird berechnet; die beiden am
  weitesten voneinander entfernten Schwerpunkte definieren die Längsachse des
  Bauteils, und die Abweichung der Achse von der horizontalen Ebene wird gemessen.

## Anwendungsbeispiel

- Prüfen, ob alle Wände im Modell vertikal sind (2D-Kategorie, "größer als
  Untergrenze" mit Untergrenze `89°`).
- Prüfen, ob alle Stützen lotrecht sind (1D-Kategorie).
- Prüfen, ob Träger horizontal und nicht durchhängend sind.

## Einstellungen

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|----------|--------------|
| Element-Kategorie | `2d` / `1d` | `2d` | `2d` misst Wände & Decken (zwei größte Flächen); `1d` misst Stützen & Träger (Längsachse). |
| Vergleichsmethode | Auswahl | `greater_than_lower` | Wie die gemessene Neigung mit den Grenzwerten verglichen wird (siehe unten). |
| Untergrenze (°) | Zahl | `0` | Bauteil wird gekennzeichnet, wenn die Neigung größer als dieser Wert ist (Methode `greater_than_lower`). |
| Obergrenze (°) | Zahl | `90` | Bauteil wird gekennzeichnet, wenn die Neigung unter diesem Wert liegt (Methode `less_than_upper`). |
| Intervall-Untergrenze (°) | Zahl | `0` | Untere Grenze für die Intervallmethoden. |
| Intervall-Obergrenze (°) | Zahl | `90` | Obere Grenze für die Intervallmethoden. |
| Horizontaler Trennungswinkel (°) | Zahl | `5` | Maximale horizontale Winkelabweichung zwischen zwei Dreiecken, um noch als dieselbe Fläche zu gelten (fasst Facetten gekrümmter/runder Objekte zusammen). |
| Toleranz (°) | Zahl | `0.1` | Gemeinsame Toleranz, die beim Kennzeichnen zu den Grenzwerten addiert bzw. subtrahiert wird. |

### Vergleichsmethoden

| Wert | Kennzeichnet, wenn |
|------|--------------------|
| `greater_than_lower` | `Neigung > Untergrenze + Toleranz` |
| `less_than_upper` | `Neigung < Obergrenze - Toleranz` |
| `inside_interval` | `Intervall-Untergrenze - Toleranz < Neigung < Intervall-Obergrenze + Toleranz` |
| `outside_interval` | `Neigung < Intervall-Untergrenze - Toleranz` oder `Neigung > Intervall-Obergrenze + Toleranz` |

Ein Intervallpaar wird von beiden Intervallmethoden wiederverwendet, da jeweils
nur eine Vergleichsmethode aktiv ist.

## Eingaben

- **Express-IDs** (optional): Liste der IFC-Express-IDs, die gemessen werden
  sollen. Üblicherweise mit dem Ausgang eines `ifc_element_filter` verbunden. Wenn
  nicht verbunden, werden alle IFC-Elemente im Modell geprüft.

## Ausgaben

Das Ergebnis ist eine schlanke, strukturierte Prüfung pro Element:

- `element_count`: Anzahl der verarbeiteten Elemente
- `check_count`: Anzahl der Elemente mit mindestens einer Flächen-/Achsenprüfung
  (Elemente ohne Geometrie werden übersprungen und nicht gezählt)
- `failed_count`: Anzahl der Elemente mit mindestens einer gekennzeichneten
  Fläche/Achse
- `model_name`: Name des geprüften IFC-Modells (aus dem Dateinamen im IFC-Header)
- `elements`: geordnete Liste aus
  - `express_id`, `class_name` (IFC-Klasse oder `unknown`), `element_category`
  - `failed`: true, wenn mindestens eine Prüfung gekennzeichnet wurde
  - `checks`: Liste von `TiltSurfaceCheck`:
    - `expected`: lesbare Soll-Bedingung, aus Vergleichsmethode und Grenzwerten
      kombiniert (z. B. „kleiner oder gleich X")
    - `tilt_angle` (°), `passed`
    - `geometry_key`: Geometrie-Cache-Schlüssel der Hilfsgeometrie für gekennzeichnete Prüfungen

Ein 2D-Element liefert bis zu zwei Prüfungen (Vorder-/Rückseite); ein
1D-Element eine Prüfung (seine Achse). `check_count` und `failed_count` zählen
Elemente, nicht einzelne Prüfungen.

## Hilfsgeometrie

Gekennzeichnete Prüfungen speichern eine Hilfsgeometrie im Geometrie-Cache zur
Visualisierung:

- 2D: die gekennzeichneten Flächen-Dreiecke unter `inter:tilt_surface_{express_id}_{surface_index}`
- 1D: einen dünnen Achszylinder unter `inter:tilt_axis_{express_id}`

Dies sind `inter:`-Schlüssel, die von den Eingaben des Kollisionsknotens und vom
Modell-Fallback ausgeschlossen sind.

## Hinweise zu Öffnungen

Bei Wänden mit Fenster-/Türöffnungen ist die Öffnungsaussparung bereits vom
Wandnetz subtrahiert, sodass der Ansatz der zwei größten Flächen weiterhin die
korrekten Vorder-/Rückseiten findet. Eine dedizierte Verarbeitung von Öffnungen
(`IfcRelVoidsElement`) ist in dieser Version nicht umgesetzt.

## Verbund- / zerlegte Elemente

Manche Modelle bilden ein Verbundelement (z. B. eine mehrschichtige Wand) als ein
über `IfcRelAggregates` in `IfcBuildingElementPart`-Teilelemente zerlegtes Element
ab, wobei jeder Teil eine eigene Body-Geometrie besitzt. Hat ein solches Element
kein eigenes tesseliertes `Body`-Netz, wird seine Neigung als Ganzes gemessen,
indem die Geometrie aller seiner Teile (rekursiv durch die Aggregation) kombiniert
wird. Die Teile selbst bleiben dabei gelistet und werden unabhängig gemessen, sodass
sowohl die gesamte Wand als auch ihre Schichten im Ergebnis erscheinen.
