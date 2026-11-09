---
title: Öffnungsflächen-IFC-Generator
description: Erstellt ein eigenständiges IFC4X3-Modell aus den Deckelflächen des opening_surface-Nodes und ordnet es der räumlichen Struktur des Quellmodells zu.
categories: geometry
---

Der Node `opening_surface_ifc_generator` schreibt ein neues IFC4X3-Modell aus
den Öffnungsflächen, die der Node `opening_surface` ermittelt. Jede der beiden
Deckelflächen einer Öffnung (vorne und hinten) wird als eigenständiger
polygonaler Flächenverbund auf einem eigenen `IfcBuildingElementProxy`
ausgegeben, zusammen mit einem `IfcQuantityArea` für die Öffnungsfläche. Das
erzeugte Modell bildet die Struktur Projekt/Standort/Gebäude/Geschoss des
Quellmodells nach und ordnet jeden Proxy dem Geschoss zu, das sein Bauteil
enthält.

## Funktionsweise

- Liest den Ausgang `openings` eines `opening_surface`-Nodes (keine
  Nach-Tessellierung — die `gen:`-Geometrie kommt aus dem Workflow-Cache).
- **Jedes gecachte Deckelnetz enthält bereits beide Deckelflächen eines
  Durchbruchs.** Für jede Öffnung wird das Netz in seine Deckelflächen-Gruppen
  zerlegt (vorne + hinten, bei einer Nische nur eine Gruppe), jede Gruppe in
  die Ebene der Bauteiloberfläche gelegt und ihre Kontur (Außenrand und
  etwaige Löcher) in `IfcIndexedPolygonalFaceSet`-Geometrie überführt.
- Erstellt je Deckelfläche einen `IfcBuildingElementProxy` — benannt
  `OpeningSurface_0` (größere Deckelfläche) und `OpeningSurface_1` (die
  gegenüberliegende) — platziert am Weltursprung (die gecachte
  Deckelgeometrie liegt bereits in Weltkoordinaten) und weist das Mengenset
  `OpeningSurfaceQuantities` mit `IfcQuantityArea` `OpeningArea` zu.
- Kopiert das räumliche Gerüst des Quellmodells in die neue Datei
  (`IfcProject` → `IfcSite` → `IfcBuilding` → `IfcBuildingStorey`) samt
  Platzierungskette und erzeugt `IfcRelContainedInSpatialStructure`-Verweise
  vom Proxy zum Geschoss, das sein Bauteil enthält.

## Eingaben

- **Öffnungen** (erforderlich): der Ausgang `openings` des `opening_surface`-
  Nodes. Ohne Verbindung schlägt die Validierung fehl; eine leere Liste löst
  einen Node-Fehler aus.

## Einstellungen

- **Ausgabedateiname** (Standard `opening_surface_model.ifc`): die erzeugte
  Datei. Sie wird im Workflow-Ausgabeverzeichnis (Ordner der Workflow-Datei)
  gespeichert.

## Ausgaben

- `output_path`: absoluter Pfad der erzeugten IFC-Datei
- `element_count`: Anzahl der erzeugten `IfcBuildingElementProxy`-Elemente
- `storey_count`: Anzahl der nachgebildeten `IfcBuildingStorey`-Elemente
- `elements`: geordnete Liste je erzeugtem Proxy (zwei je Durchbruch, eine je
  Nische) mit `opening_ref`, `element_guid`, `cap` (0 = größere Deckelfläche,
  1 = gegenüberliegende), `host_ref`, `storey_ref`, `area` und `error`.

## Hinweise und Einschränkungen

- Nur Öffnungen mit gecachter Deckelfläche werden ausgegeben; Öffnungen ohne
  Geometrie erhalten einen `error`-Eintrag und kein Element.
- Erzeugt wird ausschließlich die Deckelgeometrie der Öffnungsflächen. Die
  Lichtprismen (Sichtfeld / Lichteinfall) entfallen, da die benötigten Winkel
  und Distanzen aus dem `opening_surface`-Node nicht verfügbar sind.
- Es werden keine Property-Sets erzeugt; nur das Mengenset `OpeningArea` wird
  hinzugefügt.
- Ein Bauteil, das keinem Geschoss zugeordnet ist, ergibt einen Proxy ohne
  räumliche Einordnung (`storey_ref = None`).
