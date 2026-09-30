---
title: BCF-Ausgabe
description: Setzt Prüfungs-Node-Fehler in eine BCF-3.0-Issue-Datei um.
categories: Output
---

`bcf_output` verwandelt die fehlgeschlagenen Prüfungen eines vorgelagerten
Prüfungs-Nodes (LOI-Check, Tilt of Components oder Comparison) in eine
**BCF-3.0**-Issue-Datei — ein **Topic pro Element**, das alle
fehlgeschlagenen Prüfungen des Elements zusammenfasst und das betroffene
Element referenziert, damit es in einem BCF-Viewer geprüft werden kann. Die
Datei wird mit dem `bcf-client`-Paket aus dem IfcOpenShell-Ökosystem
geschrieben und enthält einen **Viewpoint** für jedes auflösbare betroffene
Element.

Der Node ermittelt selbst keine Daten; er liest die **harmonisierte**
`elements`-Ausgabe, die LOI-Check, Tilt of Components und Comparison teilen,
und löst GlobalId, Name und IFC-Entität des Elements nur zur Referenzierung
auf — aus dem Modell, das in der Referenz (bzw. den Referenzen) des Elements
genannt ist.

## Anwendungsbeispiel

Führen Sie `loi_check`, `tilt_of_components` oder `comparison` aus, verbinden
Sie dessen `elements`-Ausgabe mit diesem Node, wählen Sie eine Titel- und
Beschreibungsschablone (siehe unten) und führen Sie den Workflow aus — im
Ausgabeverzeichnis des Workflows wird eine BCF-Datei gespeichert (Standard
`check-results.bcf`).

## Einstellungen

| Einstellung | Beschreibung |
|-------------|--------------|
| **Modus** | `auto` (Standard) wendet fertige, bedingungsbewusste Schablonen an; `manual` löst Ihre eigene Schablone exakt wie geschrieben auf. |
| **Titelschablone** | Der BCF-Topic-Titel, für jede fehlgeschlagene Prüfung ausgefüllt. |
| **Beschreibungsschablone** | Die BCF-Topic-Nachricht, für jede fehlgeschlagene Prüfung ausgefüllt. |
| **Projektname** | Name in den BCF-Projektinformationen (Standard `Default Project`). |
| **Erstellungsautor** | Autor der Erstellungsdaten jedes Topics (Standard `Default Author`). |
| **Topic-Typ** | BCF-`TopicType` (Standard `Model Check`). |
| **Topic-Status** | BCF-`TopicStatus` (Standard `Open`). |
| **Ausgabedatei** | Dateiname (relativ zum Ausgabeverzeichnis; Standard `check-results.bcf`). Ein `{timestamp}`-Platzhalter wird pro Lauf ersetzt. |
| **Enthaltene Elemente** | Welche Elemente die BCF enthält: `fehlgeschlagen` (Standard) nur Elemente mit fehlgeschlagener Prüfung; `bestanden` nur vollständig bestandene Elemente (je ein Info-Topic); `alle` jedes Element (jedes Element wird ein Topic). |

## Platzhalter

Auf Elementebene: `{id}`, `{guid}`, `{name}`, `{class_name}`. `{id}` rendert
die nackte IFC-Express-ID — BCF kennt keine qualifizierten Referenzen — und
`{guid}` die rohe IFC-GlobalId. BCF-Ausgaben enthalten nie qualifizierte
Referenzen.

Die Platzhalter `{node_label}`, `{check_type}` und `{node_id}` werden
akzeptiert, rendern aber immer leer (mit einer Warnung), da Label / Typ / ID
eines vorgelagerten Nodes nicht auf dessen Ergebnismodell übertragen werden.

Pro Prüfung (generisch verfügbar):

`{key}`, `{check_parameter}` (Alias `{property_name}`), `{value}`/`{actual}`/
`{actual_value}`, `{expected}`/`{expected_value}`, `{unit}`, `{missing}`,
`{passed}`, `{condition}`/`{expected_value_condition}`, `{expected_min}`/
`{expected_value_min}`, `{expected_max}`/`{expected_value_max}`.

`{name_a}` / `{name_b}` — die aufgelösten Elementnamen des Elements, für
Überschneidungs-/Abstands-Paarelemente, deren rohe Referenz zu zwei
IFC-Elementen erweitert wird (z. B. `The volume of the intersection between
{name_a} and {name_b}`). Bei Einzelelement-Prüfungen rendern beide als leere
Strings.

Über den Key der Prüfung (z. B. `Pset_WallCommon.ThermalTransmittance` oder
`surface_0`): derselbe Satz unter `<key>.<field>`, z. B. `{<key>.expected}`,
`{<key>.actual}`, `{<key>.condition}`.

`{condition_symbol}` — der Operator: kompakt (`=`, `!=`, `<`, `<=`, `>`, `>=`)
oder mit Leerraum für Wort-Bedingungen (` contains `, ` ∈ `, ` is true`,
` is false`, ` between `, ` outside `), sodass
`{check_parameter}{condition_symbol}{expected}` natürlich liest (z. B.
`Material contains concrete`, `LoadBearing is true`). `between` / `outside`
vergleichen gegen einen Bereich — verwenden Sie `{expected_min}` /
`{expected_max}`.

### Auto-Modus-Platzhalter (bedingungsbewusst)

Generisch und pro Prüfungs-Key verfügbar (z. B. `{<key>.expectation}`):

| Platzhalter | Rendert |
|-------------|---------|
| `{expectation}` | Wie die Erwartung für diese Bedingung lauten sollte (siehe Tabelle). |
| `{actual_display}` | Der gemessene Wert oder `missing`, wenn das Element keinen Wert hat. |
| `{failure_reason}` | Warum die Prüfung fehlschlug, z. B. `value for ThermalTransmittance is 0.5 (expected < 0.24)`. |

`{expectation}` pro Bedingung:

| Bedingung | Rendert | Bedingung | Rendert |
|-----------|---------|-----------|---------|
| `equals` | `= {expected}` | `contains` | `contains "{expected}"` |
| `not_equals` | `!= {expected}` | `one_of` | `is one of: {expected}` |
| `lt` / `le` | `<` / `<= {expected}` | `is_true` / `is_false` | `is true` / `is false` |
| `gt` / `ge` | `>` / `>= {expected}` | `between` | `between {expected_min} and {expected_max}` |
| | | `outside` | `not between {expected_min} and {expected_max}` |

### Beispielschablonen

Auto-Modus (empfohlen):

```
Title:        {class_name} {name} failed {check_parameter}
Description:  Element #{id} failed because {failure_reason}
```

Manueller Modus:

```
Title:        {class_name} {name} failed {check_parameter}
Description:  Element {guid} ({class_name} {name}) hat {check_parameter}={actual}; erwartet {check_parameter}{condition_symbol}{expected}.
```

## Eingaben

- **Elements** (erforderlich): die harmonisierte Elementliste aus `loi_check`
  (`LOI-Check.elements`), `tilt_of_components`
  (`Tilt-of-Components.elements`) oder `comparison`
  (`Comparison.elements`); der Node meldet einen Fehler, wenn sie fehlt.
- **Automatische Verbindung**: Wenn Sie keine Quelle wählen, verwendet der
  Node automatisch den einzelnen direkt vorgelagerten Node, der die
  erwarteten Daten liefert. Das geschieht anhand des Node-Typs (nicht seines
  Anzeigenamens), sodass eine Umbenennung Ihres Prüfungs-Nodes keine
  Auswirkung hat. Können mehrere direkt vorgelagerte Nodes sie liefern, stoppt
  der Lauf und fordert eine Auswahl — und Sie können die automatische Wahl
  jederzeit im Eingabebindungen-Panel überschreiben.

## Ausgaben

Der Node meldet `output_path` (wo die Datei gespeichert wurde), `topic_count`,
`viewpoint_count`, `processed_result_count` (verarbeitete Prüfungen),
`element_count`, `failure_count` (fehlgeschlagene Prüfungen), `skipped`
(fehlgeschlagene Prüfungen, deren Element nicht zu einem BCF-Viewpoint
aufgelöst werden konnte — entweder weil seine IFC-Entität/GlobalId nicht
aufgelöst werden konnte oder weil seine rohen Referenzen auf keine
IFC-Elemente erweitert werden können), `warnings` und `topics` — der
aufgelöste Titel und die Nachricht pro Topic zur Kontrolle.

## Verhalten & Randfälle

- **Ein Topic pro Element** — jedes Element mit einer fehlgeschlagenen Prüfung
  wird ein einzelnes Topic, das alle seine fehlgeschlagenen Prüfungen
  zusammenfasst; ein Viewpoint wird pro auflösbarem betroffenen Element
  hinzugefügt.
- **Enthaltene Elemente** filtert, welche Elemente ausgegeben werden:
  `fehlgeschlagen` (Standard), `bestanden` (nur vollständig bestandene Elemente
  → je ein Info-Topic) oder `alle`.
- Ein **Viewpoint** wird pro auflösbarem fehlgeschlagenem Element hinzugefügt.
- **Viewpoint-Einfärbung** — jeder Viewpoint hebt **jedes Mitglied des Topics**
  hervor, indem ein einzelner `Components.Coloring`-Eintrag (deckendes Rot
  `FF0000FF`) hinzugefügt wird, der alle aufgelösten IFC-GlobalIds auflistet.
  Mehrmitglied-Topics (Kollisionsüberschneidungen, Abstandspaare) zeigen daher
  in jedem Viewpoint alle ihre Elemente hervorgehoben, während die Kamera
  weiterhin nur eines fokussiert. Der Rest des Modells bleibt sichtbar und
  ungefärbt.
- **Nicht auflösbarer Platzhalter** → der Lauf schlägt fehl und nennt die
  betroffene Prüfung.
- **`{node_label}` / `{check_type}` / `{node_id}`** → werden akzeptiert,
  rendern leer, mit Warnung (Upstream-Metadaten werden nicht übertragen).
- **Nicht auflösbares Element** (fehlende Entität oder GlobalId) → seine
  fehlgeschlagene Prüfung wird übersprungen (in `skipped` gezählt) und eine
  Warnung protokolliert, wodurch der Lauf robust bleibt.
- **Hilfs-/generierte Referenzen** (rohe `inter:intersection_...` über
  `gen:`-Schlüssel, fehlerhafte Referenzen oder Paare mit Nicht-`expr`-Elementen)
  können nicht auf IFC-Elemente erweitert werden und haben daher keinen
  BCF-Viewpoint. Ihre Elemente werden beim Normalisieren verworfen: als je eine
  Warnung pro verworfener Referenz gemeldet und in den `skipped`-Zähler
  eingerechnet. Eine auf generierter Geometrie erkannte Kollision
  (`inter:intersection_gen:1_gen:2`) schreibt also weiterhin **kein** Topic
  (korrekt — es gibt keine zu referenzierende IFC-Entität), meldet nun aber
  `skipped=1` mit einer erklärenden Warnung, statt still zu verschwinden.
- **Kein Anzeigename** (`{name}`) → wird als leerer String gerendert.
- **Keine fehlgeschlagenen Prüfungen** → speichert dennoch eine leere,
  gültige Issue-Datei.
- **Dateiname** — `output_filename`, Standard `check-results.bcf`; verwenden
  Sie einen `{timestamp}`-Platzhalter, um vorherige Dateien nicht zu
  überschreiben.
