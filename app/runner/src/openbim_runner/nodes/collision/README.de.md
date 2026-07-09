---
title: Kollisionserkennung
description: Paarweise Kollisionserkennung zwischen zwei Geometrielisten mittels Boolescher Schnittmengenberechnung.
categories: geometry,collision
---

Der `collision` Knoten führt paarweise (zip) Kollisionserkennung zwischen zwei Listen von Geometrie-Handles durch. Jedes Paar wird mit einem AABB-Präfilter und anschließender Boolescher Schnittmengenberechnung geprüft. Eine Kollision liegt vor, wenn die Schnittmenge ein positives Volumen hat.

## Paarbildung

- Gleich lange Listen: Elemente werden nach Index gepaart (`A[i]` mit `B[i]`).
- Ungleich lange Listen erzeugen einen Fehler.

## Ergebnis

Jedes Paar erzeugt einen `CollisionPair`-Datensatz mit `collides` (`true`/`false`/`null`), `intersection_volume` und einem `error`-Feld, wenn das Ergebnis unentscheidbar ist (z.B. nicht wasserdichte Netze oder Boolesche-Fehlschlag).

## Einstellungen

- **Include intersection mesh**: Wenn aktiviert, speichern kollidierende Paare das Schnittmengennetz im Geometrie-Cache und tragen einen `intersection_key`-Handle. Dies ermöglicht eine zukünftige Workflow-Erweiterung, die Schnittmengengeometrie als IFC zurückschreibt.

## Hinweise

- Nicht wasserdichte Netze werden bestmöglich repariert (Knotenverschweißung, Lochfüllung, pymeshfix). Nicht reparierbare Netze melden `collides=null` mit `error="non-watertight"`.
- Sich berührende Paare erzeugen Schnittmengen mit null Volumen und gelten als nicht kollidierend.
