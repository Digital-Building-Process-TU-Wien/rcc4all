---
title: Öffnungsflächen-IFC-Generator
description: Erstellt ein eigenständiges IFC4X3-Modell aus den wasserdichten geschlossenen Öffnungsoberflächen des opening_surface-Nodes und ordnet es der räumlichen Struktur des Quellmodells zu.
categories: geometry
---

Der `opening_surface_ifc_generator`-Node erstellt ein eigenständiges IFC4X3-Modell,
in dem jede vom `opening_surface`-Node ermittelte geschlossene
Öffnungsoberfläche zu einem `IfcBuildingElementProxy` wird.

## Funktionsweise

Für jede Öffnung wird das zwischengespeicherte Netz der geschlossenen Oberfläche
aufgelöst und seine ebenen Flächengruppen werden zu polygonalen Flächen einer
`IfcPolygonalFaceSet` pro Gruppe abgeflacht und als Body eines einzelnen
`IfcBuildingElementProxy` geschrieben. Jede Öffnung ist ein Element.

Das Projekt-/Gelände-/Gebäude-/Geschossgerüst wird aus jedem Quellmodell
übernommen, und jeder Proxy wird in das neue Geschoss eingeordnet, das das
Geschoss seines Bauteils spiegelt. Die geschlossene Öffnungsoberfläche wird als
`IfcQuantityVolume` und die Öffnungsfläche als `IfcQuantityArea` geschrieben.

## Eingänge

- **Öffnungen** (erforderlich): die Öffnungsergebnisse des `opening_surface`-Nodes.
  Binden Sie hier dessen `openings`-Ausgang an. Dies muss an echte Geometrie
  gebunden sein; ein ungebundener Pflichteingang lässt den Node fehlschlagen.
- **Ausgabedateiname** (Einstellungen): der Name der erzeugten IFC-Datei, die in
  das Workflow-Ausgabeverzeichnis geschrieben wird.

## Ausgaben

- `output_path`: absoluter Pfad der erzeugten IFC-Datei
- `element_count`: Anzahl der erzeugten Proxys
- `storey_count`: Anzahl der aus dem Quellmodell übernommenen Geschosse
- `elements`: geordnete Liste mit einem Eintrag pro Öffnung:
  - `opening_ref`: qualifizierte Referenz der Quellöffnung
  - `element_guid`: GlobalId des erzeugten Proxys
  - `face_count`: Anzahl der geschriebenen polygonalen Flächen
  - `method`: wie die geschlossene Quelloberfläche ermittelt wurde
  - `volume`: das Volumen in Kubikmetern (`IfcQuantityVolume`)
  - `host_ref` / `storey_ref`: Referenzen von Quellbauteil und -geschoss
  - `area`: die Öffnungsfläche (`IfcQuantityArea`)
  - `error`: Grund, wenn der Proxy nicht erzeugt werden konnte

## Hinweise und Grenzen

- Für jede Öffnung mit zwischengespeicherter Geometrie wird ein Proxy erzeugt.
  Öffnungen ohne Geometrie werden stattdessen als Fehlereintrag gemeldet.
- Der Proxy wird am Weltursprung geschrieben; seine Geometrie trägt die absoluten
  Koordinaten der geschlossenen Öffnungsoberfläche aus dem Quellmodell.
