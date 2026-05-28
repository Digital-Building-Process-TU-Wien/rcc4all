---
title: IFC-Elemente filtern
description: Löst alle IFC-Entitäten eines angeforderten Typs zu ihren Express-IDs auf.
categories: IFC, Filter
---

Der `element_filter` Knoten fragt das IFC-Modell nach allen Entitäten ab, die mit dem konfigurierten `entity_type` übereinstimmen.

Verwenden Sie diesen Knoten am Anfang eines Workflows, wenn Sie eine stabile Liste von Express-IDs für eine bestimmte IFC-Klasse benötigen, bevor Sie diese IDs an nachgelagerte Knoten weiterleiten.

## Anwendungsbeispiel

Sammeln Sie alle `IFCWALL`-Entitäten aus dem Modell und leiten Sie deren Express-IDs an andere Knoten weiter, die Namen, Eigenschaften oder benutzerdefinierte Validierungsregeln prüfen.
