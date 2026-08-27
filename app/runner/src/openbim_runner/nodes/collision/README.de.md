---
title: Kollisionserkennung
description: Clash-Detection zwischen zwei Geometrielisten über AABB-Präfilter, Boolesche Schnittmenge und FCL-Fallback für nicht reparierbare Netze.
categories: geometry,collision
---

Der `collision`-Node erkennt Kollisionen zwischen zwei Listen zwischengespeicherter Geometrien. Referenzen sind **Express-IDs** (`int` → `ifc:<id>`) für IFC-Elemente oder **Objekt-IDs** (`str` → `gen:<id>`) für generierte Geometrie. Jedes Element der Liste A wird gegen jedes Element der Liste B getestet (kartesisches Produkt). Jedes Paar durchläuft eine dreistufige Pipeline:

1. **AABB-Präfilter** — Paare ohne überlappende Bounding-Boxes überspringen.
2. **Boolesche Schnittmenge** — beide Netze zu wasserdichten Netzen reparieren, Schnittmenge berechnen. Eine Kollision liegt vor, wenn die Schnittmenge positives Volumen hat.
3. **FCL-Fallback** — wenn Reparatur oder Boolesche Operation fehlschlagen, FCL dreiecksbasierte Kollisionserkennung auf den rohen Netzen verwenden. Über FCL entschiedene Kollisionen werden gemeldet, erzeugen aber kein Schnittmengennetz.

## Eingaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `list_a` | `list[number \| string]` | Erste Liste von Referenzen — Express-IDs (`int`) und/oder Objekt-IDs (`str`) |
| `list_b` | `list[number \| string]` | Zweite Liste von Referenzen — gleiche Kodierung. Wenn leer, Fallback auf das gesamte Modell. |

Beide Listen sind standardmäßig leer und erweitern sich auf das gesamte Modell. Eine Referenz ohne zwischengespeicherte Geometrie löst einen Fehler aus.

## Paarbildung

- **Kartesisches Produkt**: jedes A-Element wird gegen jedes B-Element getestet. Ungleiche Listengrößen sind erlaubt.
- **Fallback auf das gesamte Modell**: wenn eine Liste leer ist, wird diese Seite auf alle zwischengespeicherten Geometrien erweitert.
- **Selbstpaare** werden übersprungen. Paare werden nicht dedupliziert: sowohl `X↔Y` als auch `Y↔X` werden ausgegeben.

## Modus

- **`boolean`** (Standard): meldet, welche Paare kollidieren, ohne Schnittmengengeometrie zu speichern.
- **`intersection_mesh`**: speichert zusätzlich das Schnittmengennetz jedes kollidierenden Paares unter einer deterministischen ID im Geometrie-Cache.

## Ergebnis

`CollisionResult` enthält drei Felder:

- `collisions: dict[key_a, list[key_b]]` — kollidierende Paare, gruppiert nach Seiten-A-ID.
- `errors: list[{key_a, key_b, error}]` — Paare, die nicht entschieden werden konnten (sowohl Boolesche Operation als auch FCL fehlgeschlagen, oder FCL nicht verfügbar).
- `intersection_meshes: dict[paar_id, cache_id | null]` — nur im Modus `intersection_mesh`. Ordnet `"{key_a}__{key_b}"` die Cache-ID `inter:intersection_{key_a}_{key_b}` zu. `null` für über FCL entschiedene Kollisionen (kein Netz erzeugt). Im Modus `boolean` leer.

Nicht kollidierende Paare fehlen im Ergebnis.

## IDs der Schnittmengennetze

Im Modus `intersection_mesh` wird jedes über die Boolesche Operation entschiedene kollidierende Paar unter folgender ID gespeichert:

```
inter:intersection_{key_a}_{key_b}
```

Da es sich um eine `inter:`-ID handelt, ist sie von Kollisionseingaben und vom Ganzmodell-Fallback ausgeschlossen. Da Paare nicht dedupliziert werden, erhalten `X↔Y` und `Y↔X` jeweils eine eigene ID. Über FCL entschiedene Kollisionen erscheinen mit einem `null`-Wert — es wird kein Netz gespeichert.

## Hinweise

- Nicht wasserdichte Netze werden bestmöglich repariert (vertex welding, hole filling, pymeshfix). Wenn Reparatur oder Boolesche Operation fehlschlagen, bietet FCL (Flexible Collision Library) dreiecksbasierte Kollisionserkennung auf rohen Dreiecksnetzen. Paare landen nur dann in `errors`, wenn sowohl Boolesche Operation als auch FCL fehlschlagen.
- Sich berührende Paare erzeugen Schnittmengen mit null Volumen und gelten als nicht kollidierend.
