---
title: Kollisionserkennung
description: Clash-Detection zwischen zwei Geometrielisten über AABB-Präfilter, Boolesche Schnittmenge und FCL-Fallback für nicht reparierbare Netze.
categories: geometry,collision
---

Der `collision`-Node erkennt Kollisionen zwischen zwei Listen zwischengespeicherter Geometrien. Referenzen sind **voll qualifizierte Geometrie-Cache-Keys**: `<slug>:expr:<id>` (z. B. `main:expr:63`) für IFC-Elemente, `gen:<object_id>` für generierte Geometrie oder `inter:<id>` für Hilfsgeometrie. IFC-Referenzen werden gegen das darin genannte Modell aufgelöst. `gen:`- und `inter:`-Keys werden direkt aus dem gemeinsamen Geometrie-Cache gelesen. Die beiden Listen dürfen daher aus unterschiedlichen IFC-Dateien stammen. Jedes Element der Liste A wird gegen jedes Element der Liste B getestet (kartesisches Produkt). Jedes Paar durchläuft eine dreistufige Pipeline:

1. **AABB-Präfilter** — Paare ohne überlappende Bounding-Boxes überspringen.
2. **Boolesche Schnittmenge** — beide Netze zu wasserdichten Netzen reparieren, Schnittmenge berechnen. Eine Kollision liegt vor, wenn die Schnittmenge positives Volumen hat.
3. **FCL-Fallback** — wenn Reparatur oder Boolesche Operation fehlschlagen, FCL dreiecksbasierte Kollisionserkennung auf den rohen Netzen verwenden. Über FCL entschiedene Kollisionen werden gemeldet, erzeugen aber kein Schnittmengennetz.

## Eingaben

| Name | Typ | Beschreibung |
|------|-----|--------------|
| `list_a` | `list[string]` | Erste Liste von Geometrie-Cache-Keys — `<slug>:expr:<id>`, `gen:<object_id>` oder `inter:<id>` (erforderlich) |
| `list_b` | `list[string]` | Zweite Liste von Geometrie-Cache-Keys — gleiche Kodierung (erforderlich) |

Beide Listen sind erforderlich. Eine leere Liste bedeutet null Elemente — es werden keine Paare getestet (kein Ganzmodell-Fallback). Eine missgebildete Referenz oder eine Referenz ohne zwischengespeicherte Geometrie löst einen Fehler aus.

## Paarbildung

- **Selbstpaare** sowie Vorfahr-/Nachfahr-Paare über `IfcRelAggregates`/`IfcRelNests` (nur innerhalb desselben Modells) werden übersprungen. Paare werden nicht dedupliziert: sowohl `X↔Y` als auch `Y↔X` werden ausgegeben.

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

Die `inter:`-ID ist ein gültiger Geometrie-Cache-Key und kann an Geometrieknoten wie den measurement-Node übergeben werden. Da Paare nicht dedupliziert werden, erhalten `X↔Y` und `Y↔X` jeweils eine eigene ID. Über FCL entschiedene Kollisionen erscheinen mit einem `null`-Wert; es wird kein Netz gespeichert.

## Hinweise

- Nicht wasserdichte Netze werden bestmöglich repariert (vertex welding, hole filling, pymeshfix). Wenn Reparatur oder Boolesche Operation fehlschlagen, bietet FCL (Flexible Collision Library) dreiecksbasierte Kollisionserkennung auf rohen Dreiecksnetzen. Paare landen nur dann in `errors`, wenn sowohl Boolesche Operation als auch FCL fehlschlagen.
- Sich berührende Paare erzeugen Schnittmengen mit null Volumen und gelten als nicht kollidierend.
