---
title: Kollisionserkennung
description: Clash-Detection zwischen zwei Geometrielisten über ein kartesisches Produkt von Booleschen Schnittmengen. Eine leere Liste fällt auf das gesamte Modell zurück.
categories: geometry,collision
---

Der `collision`-Knoten führt **Clash-Detection** zwischen zwei Listen zwischengespeicherter Geometrien durch. Jede Seite wird durch Referenzen beschrieben: **Express-IDs** für interne IFC-Elemente (`ifc:<id>`) und **Objekt-IDs** für externe/generierte Elemente (`gen:<object_id>`). Er testet **Liste A gegen Liste B** (das vollständige kartesische Produkt — jedes `A[i]` wird gegen jedes `B[j]` geprüft), sodass keine gleiche Listenlänge erforderlich ist. Jedes Paar wird mit einem AABB-Präfilter und anschließender Boolescher Schnittmengenberechnung geprüft. Eine Kollision liegt vor, wenn die Schnittmenge ein positives Volumen hat.

## Eingaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `list_a` | `list[number \| string]` | Erste Liste von Referenzen — Mischung aus Express-IDs (`int` → `ifc:<id>`) und Objekt-IDs (`str` → `gen:<id>`), in der Test-Reihenfolge |
| `list_b` | `list[number \| string]` | Zweite (optionale) Liste von Referenzen — gleiche Kodierung wie `list_a` |

Jedes Element ist eine Referenz auf eine zwischengespeicherte Geometrie: ein **int** ist eine IFC-Express-ID, ein **str** eine Objekt-ID (z. B. von einem Würfel-Knoten). Die Elemente behalten ihre Reihenfolge in der aufgelösten Liste. Eine Referenz ohne zwischengespeicherte Geometrie löst einen Fehler aus.

## Paarbildung

- **Kartesisches Produkt**: jedes Element von Seite A wird gegen jedes Element von Seite B getestet. Ungleiche Listengrößen sind erlaubt.
- **Fallback auf das gesamte Modell**: sind beide Listen einer Seite leer, wird diese Seite durch **alle zwischengespeicherten Geometrien** ersetzt (das gesamte Modell). Eine leere B-Seite prüft beispielsweise jedes A-Element gegen das gesamte Modell.
- **Selbstpaare** (eine Geometrie gegen sich selbst) werden immer übersprungen.
- Paare werden nicht dedupliziert: Sowohl `X↔Y` als auch `Y↔X` werden ausgegeben.

## Modus

- **`boolean`** (Standard): meldet, welche Paare kollidieren, ohne Schnittmengengeometrie zu speichern.
- **`intersection_mesh`**: speichert zusätzlich das Schnittmengennetz jedes kollidierenden Paares unter einem **deterministischen Schlüssel** (unten) im Geometrie-Cache, sodass kollidierende Geometrie von einer zukünftigen Workflow-Erweiterung zurückgeschrieben werden kann (z. B. als IFC).

## Ergebnis

`CollisionResult` enthält zwei Felder:

- `collisions: dict[key_a, list[key_b]]` — gruppiert nach Seiten-A-Cache-Schlüssel; es werden nur **kollidierende** Paare aufgenommen. `key_a` erscheint einmal, und sein Wert listet jeden Seiten-B-Cache-Schlüssel auf, mit dem es kollidiert.
- `errors: list[{key_a, key_b, error}]` — Paare, deren Kollision nicht entschieden werden konnte (z. B. `non-watertight` oder `boolean failed: ...`).

Nicht kollidierende Paare (disjunkt oder flächenberührend) fehlen im Ergebnis einfach. `key_a`/`key_b` sind die Cache-Schlüssel (`ifc:<express_id>` oder `gen:<object_id>`) und identifizieren jedes Element eindeutig.

## Schlüssel der Schnittmengennetze

Im Modus `intersection_mesh` wird jedes kollidierende Paar `(key_a, key_b)` zusätzlich unter dem deterministischen Schlüssel gespeichert:

```
inter:intersection_{key_a}_{key_b}
```

Kollidiert beispielsweise `ifc:1` mit `ifc:2`, wird der Eintrag `inter:intersection_ifc:1_ifc:2` in den Geometrie-Cache geschrieben. Der Schlüssel ist **nicht** Teil des Ergebnisses — bei Bedarf über `resolve_mesh` nachschlagen. Da es sich um einen `inter:`-Schlüssel handelt, ist er von Kollisionseingaben und vom Ganzmodell-Fallback ausgeschlossen. Da Paare nicht dedupliziert werden, erhalten das symmetrische Paar `X↔Y` und `Y↔X` jeweils einen eigenen Schlüssel in der jeweiligen Richtung.

## Hinweise

- Nicht wasserdichte Netze werden bestmöglich repariert (Knotenverschweißung, Lochfüllung, pymeshfix). Nicht reparierbare Netze werden in `errors` mit `error="non-watertight"` festgehalten.
- Sich berührende Paare erzeugen Schnittmengen mit null Volumen und gelten als nicht kollidierend.
