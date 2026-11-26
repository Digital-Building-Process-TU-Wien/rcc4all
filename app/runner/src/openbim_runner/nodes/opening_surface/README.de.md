---
title: Öffnungsflächen
description: Ermittelt pro Öffnung eine wasserdichte geschlossene Oberfläche und speichert sie als generierte Geometrie.
categories: geometry
---

Der `opening_surface`-Node ermittelt für jede Öffnung der Eingabe-Elemente genau
eine **wasserdichte geschlossene Oberfläche**, die den Öffnungsraum füllt. Er
kombiniert entweder die Deckelflächen mit den Schnittflächen, wenn diese einen
geschlossenen Ring bilden (bei Fenstern), oder verbindet die Deckelflächen der
Öffnung linear, wenn die Schnittflächen einen offenen Ring bilden (bei Türen), sodass beide 
als geschlossener Körper mit positivem Volumen enden.

## Funktionsweise

Für jedes Eingabe-Element werden die Öffnungen (`IfcRelVoidsElement`) und ihre
zwischengespeicherten Body-Netze sowie das Netz des Bauteils aufgelöst. Danach:

- **Geschlossener Ring (Fenster, ebene Ränder):** Die Schnittflächen werden 
  zu einem geschlossenen Ring geschlossen. Wenn er an den offenen Seiten 
  wasserdicht geschlossen werden kann, wird er unverändert ausgegeben
  (`method = "closed_cut_surface"`).
- **Offener Ring (Tür / nicht-ebener Rand / gekrümmtes Bauteil):** Der
  Schnittflächenring bleibt offen. Stattdessen werden die Deckelflächen der
  Öffnung aus den Oberflächenebenen des Bauteils analysiert. Werden **zwei**
  Deckelflächen gefunden, werden beide verwendet; wird **nur eine** gefunden,
  wird eine zweite synthetisiert, indem die gefundene Deckelfläche um die
  Wandstärke kopiert und gegen die Laibungsflächen des Rings beschnitten wird.
  Die beiden Deckelflächen werden dann **verbunden** (durch neue Seitenflächen
  zwischen korrespondierenden Randpunkten im 3D-Raum) und bilden ein wasserdichtes
  Volumen (`method = "lofted_caps"`).
- **Kein Volumen:** Wenn weder ein geschlossener Ring noch zwei verbindbare
  Deckelflächen gebaut werden können, wird die Deckel-/Ringgeometrie unverändert
  ausgegeben (`method = "caps_only"`, `watertight = false`); es wird keine
  erfundene Geometrie erzeugt.

Die Verbindung verknüpft korrespondierende Randpunkte im 3D-Raum und toleriert
daher Bauteile, deren beiden dominanten Oberflächen nicht parallel sind (eine
Wand oder Decke mit linear veränderlicher Dicke) sowie gekrümmte Bauteile.

## Anwendungsbeispiel

- Querschnitts- / Brandabschnittsprüfungen: Ermitteln Sie das geschlossene
  Volumen einer Tür, eines Fensters oder Schachts, um es zu vermessen und mit dem
  Bauteil zu vergleichen.
- Kollisions- oder Abstandsprüfungen gegen den tatsächlichen Hohlraum, den eine
  Öffnung in Wand, Decke oder Dach schneidet.

## Eingänge

- **Express-IDs** (erforderlich): eine Liste voll qualifizierter
  Elementreferenzen (`<slug>:expr:<id>`) von Bauteilen (z. B. Wände, Decken,
  Dächer). Üblicherweise mit dem Ausgang eines `ifc_element_filter` verbunden.
  Jede Referenz wird gegen das in ihr benannte Modell aufgelöst, daher sind
  modellübergreifende Listen erlaubt. Ein ungebundener Pflichteingang schlägt die
  Validierung fehl; eine leere gebundene Liste verarbeitet null Elemente.

## Ausgaben

Das Ergebnis ist eine flache Liste mit einem Eintrag pro Öffnung:

- `opening_count`: Anzahl der gefundenen Öffnungen
- `surface_count`: Anzahl der Öffnungen, deren geschlossene Oberfläche in den
  Geometrie-Cache übernommen wurde
- `geometry_keys`: die `gen:`-Geometrie-Cache-Schlüssel der ermittelten
  geschlossenen Öffnungsflächen in Öffnungsreihenfolge
- `openings`: geordnete Liste mit
  - `express_id` (qualifizierte Öffnungsreferenz), `guid` (GlobalId der
    Öffnung), `host_express_id` (qualifizierte Bauteilreferenz)
  - `geometry_key`: Geometrie-Cache-Schlüssel der ermittelten geschlossenen
    Öffnungsfläche
  - `method`: `"closed_cut_surface"`, `"lofted_caps"` oder `"caps_only"`
  - `watertight`: ob die ausgegebene Geometrie ein geschlossener, konsistent
    gewickelter Körper mit positivem Volumen ist
  - `area` / `width` / `height`: Ausdehnung der Öffnung in der Ebene der
    Bauteiloberfläche (die größere Deckelfläche)
  - `depth`: Abstand zwischen den beiden Deckelflächen entlang der Normalen der
    Bauteiloberfläche
  - `error`: Grund, wenn die geschlossene Oberfläche nicht ermittelt werden konnte

## Generierte Geometrie

Jede ermittelte geschlossene Öffnungsoberfläche wird als generierte Geometrie
unter `gen:opening_surface_<slug>_<express_id>` gespeichert. Das
zwischengespeicherte Netz ist ein wasserdichter Körper, wenn `watertight` wahr
ist; ein
`caps_only`-Eintrag ist die unveränderte Deckelgeometrie. Die Schlüssel sind
benutzerreferenzierbare `gen:`-Schlüssel und können an Geometriekonsumenten wie
measurement oder collision gebunden werden.

## Hinweise und Grenzen

- Nur Öffnungen mit einem zwischengespeicherten Body-Netz werden verarbeitet;
  Öffnungen ohne Tessellierungsgeometrie werden stattdessen als Fehlereintrag
  gemeldet.
- Jede Öffnung erscheint genau einmal, auch wenn ihr Bauteil mehrfach übergeben
  wird. Referenzen, die auf keine Entität auflösen, liefern keine Öffnungen.
- Gekrümmte Bauteile werden mit Oberflächenregion-Logik analysiert; eine runde
  Wand, die nur eine Deckelfläche zeigt, erhält ihre gegenüberliegende
  Deckelfläche synthetisiert.
- Öffnungen werden nur aus den Eingabe-Elementen selbst gesammelt, nicht aus
  Teilen zerlegter Elemente.
