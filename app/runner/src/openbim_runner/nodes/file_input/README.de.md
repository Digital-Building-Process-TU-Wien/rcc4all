---
title: Datei-Eingabe
description: Verweist auf ein im Editor zugewiesenes IFC-Modell und gibt dessen Slug aus.
categories: Other
---

Der `file_input` Node wählt eines der dem Workflow zugewiesenen IFC-Modelle aus und gibt dessen Slug aus. Sein `model_slug`-Ausgang speist den `model_slug`-Eingang des `ifc_element_filter` — der einzige Modell-Eingang im Graphen. Alle anderen Nodes konsumieren **voll qualifizierte Element-Referenzen** (`<slug>:expr:<id>`): jede Referenz wie `main:expr:63` nennt ihr eigenes Modell und wird von den Verbrauchern gegen genau dieses aufgelöst.

Ohne einen `file_input` durchsucht der `ifc_element_filter` standardmäßig das Hauptmodell.

## Anwendungsbeispiel

Fügen Sie einen `file_input` für ein sekundäres Modell hinzu und binden Sie dessen `model_slug`-Ausgang an den `model_slug`-Eingang eines `ifc_element_filter`, damit dessen Scan-Modus dieses Modell statt des Hauptmodells durchsucht. Der Filter gibt qualifizierte Referenzen des sekundären Modells aus, die sich in nachgelagerten Verbraucher-Nodes frei mit Referenzen anderer Modelle mischen lassen.

## Einstellungen

- **Modell**: Slug des IFC-Modells, auf das sich dieser Dateieingang bezieht. Standardmäßig das Hauptmodell.

## Ausgaben

- **Modell-Slug**: Slug des ausgewählten IFC-Modells zur Bindung an den `model_slug`-Eingang des `ifc_element_filter`.
