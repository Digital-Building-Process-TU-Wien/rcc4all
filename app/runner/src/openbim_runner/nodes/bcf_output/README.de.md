---
title: BCF-Ausgabe
description: Wandelt LOI-Check-Fehler in eine BCF-3.0-Issue-Datei um.
categories: Output
---

`bcf_output` verwandelt die fehlgeschlagenen Prüfungen von `loi_check` in eine
**BCF-3.0**-Issue-Datei — ein **Topic pro fehlgeschlagener Prüfung**, die das
betroffene Element referenziert, damit es in einem BCF-Viewer geprüft werden
kann. Die Datei ist **rein Markup-basiert** (keine 3D-Viewpoint-Daten halten
sie klein und schnell zu öffnen). Der Node ermittelt selbst keine
Eigenschaften; er liest die strukturierte `elements`-Ausgabe von `loi_check`
und löst GUID / Name des Elements nur zur Referenzierung auf.

## Anwendungsbeispiel

Führen Sie `loi_check` aus, verbinden Sie dessen `elements`-Ausgabe mit diesem
Node, wählen Sie eine Titel- und Beschreibungsschablone (siehe unten) und
führen Sie den Workflow aus — neben der Workflow-Datei wird
`bcf_output-<Zeitstempel>.bcf` gespeichert.

## Einstellungen

Beide Schablonen sind `str.format`-Strings; der erwartete Wert der Prüfung
liefert automatisch das Limit (nichts muss von Hand eingegeben werden).

| Einstellung | Beschreibung |
|-------------|--------------|
| **Modus** | `auto` (Standard) wendet fertige, bedingungsbewusste Schablonen an; `manual` löst Ihre eigene Schablone exakt wie geschrieben auf. |
| **Titelschablone** | Der BCF-Topic-Titel, für jede fehlgeschlagene Prüfung ausgefüllt. |
| **Beschreibungsschablone** | Die BCF-Topic-Nachricht, für jede fehlgeschlagene Prüfung ausgefüllt. |

## Platzhalter

Auf Elementebene: `{id}`, `{guid}`, `{name}`, `{class_name}`.

Pro Eigenschaft (über den Property-Key der fehlgeschlagenen Prüfung, z. B.
`Pset_WallCommon.ThermalTransmittance` oder `ThermalTransmittance`):
`{<key>.actual}`, `{<key>.expected}`, `{<key>.condition}`,
`{<key>.property_name}`, `{<key>.expected_min}`, `{<key>.expected_max}`.

Generische Aliase: `{actual}`, `{expected}`, `{condition}`, `{property_name}`,
`{expected_min}`, `{expected_max}`.

`{condition_symbol}` — der Operator: kompakt (`=`, `!=`, `<`, `<=`, `>`, `>=`)
oder mit Leerraum für Wort-Bedingungen (` contains `, ` ∈ `, ` is true`,
` is false`, ` between `, ` outside `), sodass
`{property_name}{condition_symbol}{expected}` natürlich liest (z. B.
`Material contains concrete`, `LoadBearing is true`). `between` / `outside`
vergleichen gegen einen Bereich — verwenden Sie `{expected_min}` /
`{expected_max}`.

### Auto-Modus-Platzhalter (bedingungsbewusst)

Generisch und pro Property-Key verfügbar (z. B. `{<key>.expectation}`):

| Platzhalter | Rendert |
|-------------|---------|
| `{expectation}` | Wie die Erwartung für diese Bedingung lauten sollte (siehe Tabelle). |
| `{actual_display}` | Der gemessene Wert oder `missing`, wenn das Element keinen Wert hat. |
| `{failure_reason}` | Warum die Prüfung fehlschlug, z. B. `property ThermalTransmittance is 0.5 (expected < 0.24)`. |

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
Title:        {class_name} {name} failed {property_name}
Description:  Element #{id} failed because {failure_reason}
```

Manueller Modus:

```
Title:        {class_name} {name} failed {property_name}
Description:  Element {guid} ({class_name} {name}) hat {property_name}={actual}; erwartet {property_name}{condition_symbol}{expected}.
```

## Eingaben

- **Elements** (erforderlich): die Elementliste aus `loi_check`
  (`LOI-Check.elements`); der Node meldet einen Fehler, wenn sie fehlt.
- **Automatische Verbindung**: Wenn Sie keine Quelle wählen, verwendet der
  Node automatisch den einzelnen direkt vorgelagerten Node, der die
  erwarteten Daten liefert. Das geschieht anhand des Node-Typs (nicht seines
  Anzeigenamens), sodass eine Umbenennung Ihres LOI-Check-Nodes keine
  Auswirkung hat. Können mehrere direkt vorgelagerte Nodes sie liefern, stoppt
  der Lauf und fordert eine Auswahl — und Sie können die automatische Wahl
  jederzeit im Eingabebindungen-Panel überschreiben.

## Ausgaben

Der Node meldet `output_path` (wo die Datei gespeichert wurde),
`topic_count` (eines pro fehlgeschlagener Prüfung), `element_count`,
`failed_check_count` und `topics` — der aufgelöste Titel und die Nachricht pro
fehlgeschlagener Prüfung zur Kontrolle.

## Verhalten & Randfälle

- **Ein Topic pro fehlgeschlagener Prüfung** (3 fehlgeschlagene Regeln →
  3 Topics).
- **Nicht auflösbarer Platzhalter oder fehlende GUID** → der Lauf schlägt
  fehl und nennt die betroffene Prüfung (Element-ID + Property-Key).
- **Kein Anzeigename** (`{name}`) → wird als leerer String gerendert.
- **Keine fehlgeschlagenen Prüfungen** → speichert dennoch eine leere,
  gültige Issue-Datei.
- **Rein Markup-basierte Ausgabe** — jedes Topic hat Titel, Nachricht und
  Erstellungsdetails; es werden keine 3D-Viewpoint-Daten aufgenommen.
- **Dateiname mit Zeitstempel** (`bcf_output-<yyyyMMdd-HHmmss>.bcf`), sodass
  ein Lauf die vorherige Datei nie überschreibt.
