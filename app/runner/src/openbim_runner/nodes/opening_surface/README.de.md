---
title: Öffnungsflächen
description: Ermittelt die Öffnungsflächen, die in der Ebene der Bauteiloberfläche liegen (Wände, Decken, Dächer), und speichert sie als generierte Geometrie für nachfolgende Nodes.
categories: geometry
---

Der `opening_surface`-Node ermittelt für jede Öffnung der Eingabe-Elemente die
Leerraum-Flächen, die in der Ebene der Bauteiloberfläche liegen — die beiden
Deckelflächen der Öffnung — und speichert sie als generierte Geometrie für
nachfolgende Nodes wie measurement oder collision.

## Funktionsweise

Für jedes Eingabe-Element werden die Öffnungen (`IfcRelVoidsElement`) und ihre
zwischengespeicherten Body-Netze aufgelöst. Die Dreiecke des Öffnungsnetzes
werden zu ebenen Flächen gruppiert: Dreiecke gehören zur gleichen Gruppe, wenn
ihre Normale um weniger als ~1° abweicht und sie in derselben Ebene liegen.
Die beiden größten Gruppen mit entgegengesetzten Normalen sind die
Deckelflächen in der Ebene der Bauteiloberfläche; die übrigen Gruppen (die in
das Bauteil geschnittene Laibung) werden verworfen.

Da ein `IfcOpeningElement` ein Schneidekörper ist, der oft weit über das
durchbrochene Element hinausragt, sind die größten entgegengesetzten Flächen
nicht immer das Loch im Bauteil. Der Node beschnitten daher den Öffnungskörper
auf die Oberflächenplatte des Bauteils und wählt dessen bauteilparallelen
Flächen aus, damit die ermittelte Fläche das tatsächliche Loch ist, die
Deckelflächen in der Ebene der Bauteiloberfläche liegen und `depth` der Dicke
der Bauteiloberfläche entspricht. Das dominante (größte) gegensinnige
Oberflächenpaar des Bauteils definiert die Platte; liegt eine Öffnung in einer
anderen Oberfläche eines vielflächigen Bauteils (z. B. der sekundären Schräge
eines Satteldachs), wird stattdessen das benachbarte, tatsächlich durchstoßene
Flächenpaar verwendet. Kann das Bauteil nicht analysiert werden (kein
zwischengespeichertes Netz, kein dominantes gegensinniges Paar) oder schneidet
der Zuschnitt keinen Durchbruch (eine Nische, ein Nut mit nur einer Deckelfläche),
wird als Fallback die Heuristik der zwei größten entgegengesetzten Flächen
verwendet.

## Anwendungsbeispiel

- Fensteröffnungsflächen von Außenwänden für Tageslicht- oder
  Brandschutzprüfungen messen: `ifc_element_filter` (Wände) →
  `opening_surface` → `measurement` (surface area) über den `geometry_keys`-Ausgang.
- Öffnungsgeometrie von Dächern und Decken (Oberlichter, Schächte) für
  Kollisions- oder Freiheitsprüfungen gegenüber anderen Elementen ermitteln.

## Eingaben

- **Express-IDs** (erforderlich): Liste voll qualifizierter Referenzen
  (`<slug>:expr:<id>`) der tragenden Bauteile (z. B. Wände, Decken, Dächer).
  Üblicherweise mit dem Ausgang eines `ifc_element_filter` verbunden. Jede
  Referenz wird gegen das in ihr genannte Modell aufgelöst; gemischte Listen
  aus mehreren Modellen sind erlaubt. Ohne Verbindung schlägt die
  Eingabevalidierung fehl.

## Ausgaben

Das Ergebnis ist eine flache Liste mit einem Eintrag pro Öffnung:

- `opening_count`: Anzahl der auf den Eingabe-Elementen gefundenen Öffnungen
- `surface_count`: Anzahl der Öffnungen, deren Flächen in den Geometrie-Cache
  übernommen wurden
- `geometry_keys`: die `gen:`-Geometrie-Cache-Schlüssel der ermittelten
  Öffnungsflächen, in Öffnungsreihenfolge — direkt an Geometrie-Consumer wie
  measurement oder collision bindbar
- `openings`: geordnete Liste aus
  - `express_id` (voll qualifizierte Öffnungs-Referenz), `guid` (GlobalId der
    Öffnung), `host_express_id` (voll qualifizierte Referenz des Bauteils)
  - `geometry_key`: Geometrie-Cache-Schlüssel der ermittelten Deckelflächen
  - `area`: Öffnungsfläche in der Ebene der Bauteiloberfläche (die größere
    Deckelfläche; bei geraden Durchbrüchen sind beide Deckelflächen kongruent)
  - `width` / `height`: Ausdehnungen der Öffnungsflächen innerhalb der
    Bauteilebene (horizontal / vertikal bei Wandöffnungen)
  - `depth`: Abstand der beiden Deckelflächen entlang der Flächennormale;
    `None`, wenn der Leerraum nur eine dominante ebene Fläche aufweist
  - `error`: Grund, wenn die Flächen nicht ermittelt werden konnten (z. B.
    „no cached geometry")

## Generierte Geometrie

Jede ermittelte Öffnungsfläche wird als generierte Geometrie unter
`gen:opening_surface_<slug>_<express_id>` gespeichert, wobei `<express_id>`
die Express-ID des Öffnungselements ist. Dies sind benutzerreferenzierbare
`gen:`-Schlüssel — gültige Geometrie-Cache-Keys für die measurement- und
collision-Nodes.

## Hinweise und Einschränkungen

- Nur Öffnungen mit zwischengespeichertem Body-Netz werden verarbeitet;
  Öffnungen ohne tessellierte Geometrie erhalten stattdessen einen
  Fehler-Eintrag.
- Jede Öffnung erscheint genau einmal, auch wenn ihr Bauteil mehrfach
  übergeben wird. Referenzen ohne auflösbare Entität tragen keine Öffnungen bei.
- Die Heuristik der zwei größten, entgegengesetzten Flächen passt für
  Öffnungen, deren Deckelflächen den Leerraum dominieren. Stark konische
  Leerräume melden die größere (äußere) Deckelfläche als `area`; Nischen,
  deren Rückfläche der Deckelfläche nahekommt (z. B. tiefe rechteckige
  Taschen), können die Rückfläche als zweite Deckelfläche aufnehmen.
- Öffnungen sind überdimensionierte Schneidekörper; die ermittelte
  Öffnungsfläche wird daher immer auf die durchstoßene Oberflächenplatte des
  Bauteils beschnitten und liegt in deren Ebene. Das dominante Oberflächenpaar
  (die zwei größten entgegengesetzten Flächen) liefert die Platte für den
  Normalfall (Wanddicke, Decken-/Dachdicke); bei einem vielflächigen Bauteil wie
  einem mehrschrägigen Dach wird das vom Öffnungskörper tatsächlich durchstoßene
  Flächenpaar verwendet. Die außerhalb des Bauteils liegenden vergrößerten
  Flächen werden verworfen, sodass `area` das physische Loch und `depth` die
  Dicke der Bauteiloberfläche an der Öffnung ist. Der Zuschnitt ist für
  Öffnungen, die bereits in die Bauteilplatte passen (Nischen, flache Fenster),
  wirkungslos. Bei fehlendem Bauteilnetz oder wenn der Zuschnitt keinen Durchbruch
  schneidet (Nische, einzelne Deckelfläche), wird auf die
  Zwei-größten-Heuristik zurückgegriffen.
- Gekrümmte Deckelflächen (z. B. Sturzöffnungen) werden mit einer festen
  Normalen-Toleranz von ~1° gruppiert; ermittelt wird der größte ebenen Teil
  der Krümmung.
- Öffnungen werden nur von den Eingabe-Elementen selbst gesammelt, nicht von
  Teilen zerlegter Elemente.
