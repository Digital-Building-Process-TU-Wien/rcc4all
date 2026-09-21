---
title: Datei-Eingabe
description: Verweist auf ein im Editor zugewiesenes IFC-Modell und gibt dessen Slug aus.
categories: Other
---

Der `file_input` Node wählt eines der dem Workflow zugewiesenen IFC-Modelle aus und gibt dessen Slug aus. Verbinden Sie den `model_slug`-Ausgang mit dem `model_slug`-Eingang eines Verbraucher-Nodes, damit andere Nodes mit diesem Modell arbeiten.

Ohne einen `file_input` verwenden Verbraucher-Nodes standardmäßig das Hauptmodell.

## Anwendungsbeispiel

Fügen Sie einen `file_input` für ein sekundäres Modell hinzu und binden Sie dessen `model_slug`-Ausgang an einen `ifc_element_filter`, damit der Filter gegen dieses Modell statt gegen das Hauptmodell läuft.

## Einstellungen

- **Modell**: Slug des IFC-Modells, auf das sich dieser Dateieingang bezieht. Standardmäßig das Hauptmodell.

## Ausgaben

- **Modell-Slug**: Slug des ausgewählten IFC-Modells zur Bindung an den Modelleingang eines Verbraucher-Nodes.
