---
title: Geometrie abrufen
description: Tesselliert die Körpergeometrie von IFC-Elementen im Weltkoordinatensystem und gibt Cache-Handles zurück.
categories: geometry,ifc
---

Der `get_geometry` Knoten liest IFC-Entitäten nach Express-ID, tesselliert deren Körperdarstellung in Weltkoordinaten und gibt Geometrie-Handles zurück, die auf im workflow-weiten Geometrie-Cache gespeicherte Netze verweisen.

Verwenden Sie diesen Knoten, um Geometrie für Kollisionserkennung oder andere geometrische Operationen vorzubereiten. Folgt typischerweise auf einen `ifc_element_filter`, der Express-IDs bereitstellt.

## Einstellungen

- **Fail on missing**: Wenn aktiviert, wird ein Fehler ausgelöst, wenn eine Express-ID nicht im Modell existiert oder ein Element keine Körpergeometrie-Darstellung hat. Wenn deaktiviert, werden fehlende Elemente übersprungen.

## Hinweise

- Die Geometrie wird prozessintern für die Dauer des Workflow-Laufs zwischengespeichert. Die zurückgegebenen Handles tragen einen Cache-Schlüssel und die Express-ID der Quelle.
- Scheitelpunkte werden zur Tessellierungszeit verschweißt, um die Wasserdichtigkeit zu verbessern.
