---
title: IDS Checker
description: Validiert das IFC-Modell gegen eine oder mehrere IDS-Spezifikationen.
categories: validation
---

Der `ids_checker` Node validiert IFC-Elemente gegen eine IDS-Datei (Information Delivery Specification). Jede Spezifikation definiert IFC-Entitätstypen, Eigenschaften und Klassifikationen zur Prüfung. Der Node unterstützt mehrere Spezifikationen in einer einzigen IDS-Datei und aggregiert die Ergebnisse über alle Spezifikationen hinweg.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[str]` | Erforderliche Liste voll qualifizierter Referenzen (`<slug>:expr:<id>`) der zu validierenden Elemente. Bei gemischten Listen aus mehreren Modellen werden die Referenzen nach Slug gruppiert: jedes Modell wird einmalig gegen die IDS-Datei validiert und die Ergebnisse auf die Referenzen der jeweiligen Gruppe gefiltert. Jede Referenz wird gegen das in ihr genannte Modell aufgelöst. |

## Settings

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `ids_file` | `str` | Pfad zur IDS-Spezifikationsdatei (erforderlich). |
| `generate_detailed_report` | `bool` (Standard: `false`) | Wenn aktiviert, werden die Ergebnisse zusätzlich nach Specification gruppiert (für Report-Generierung). Die kombinierten Listen werden immer erstellt. |
| `report_format` | `"json" \| "html" \| null` (Standard: `null`) | Format für den generierten Report. Nur wirksam wenn `generate_detailed_report` aktiviert ist. Report wird als `ids_report-{timestamp}.{format}` im Output-Verzeichnis gespeichert. |

## Ausgabe-Verhalten

Die kombinierten Listen (`failed_express_ids`, `passed_express_ids`) werden immer erstellt. Bei aktivierter Checkbox gibt es zusätzlich eine Gruppierung nach Specification für detaillierte Reports. Der detaillierte Report (`generate_detailed_report` + `report_format`) erfordert Referenzen aus einem einzigen Modell.

## Result

`IdsCheckerResult` enthält drei Felder:

- `failed_express_ids: list[str]` — voll qualifizierte Referenzen (`<slug>:expr:<id>`) der Elemente, die mindestens eine IDS-Anforderung nicht erfüllt haben. Wird immer erstellt.
- `passed_express_ids: list[str]` — voll qualifizierte Referenzen der Elemente, die alle anwendbaren IDS-Anforderungen erfüllt haben. Wird immer erstellt.
- `specifications: list[SpecificationResult] | null` — Pro-Spezifikation-Aufschlüsselung. Nur enthalten, wenn `generate_detailed_report` aktiviert ist. Wird bei Deaktivierung nicht im Output ausgegeben.

Eine Entität, die auf keine Spezifikation passt, wird stillschweigend aus beiden Listen ausgeschlossen.

## Notes

- Ein leerer `ids_file`-Wert löst einen `ValueError` aus.
- Die IDS-Datei muss gültiges XML sein.
- Mehrere Spezifikationen in einer IDS-Datei werden alle geprüft; eine Entität gilt als fehlgeschlagen, wenn sie **irgendeine** Spezifikation verletzt.
