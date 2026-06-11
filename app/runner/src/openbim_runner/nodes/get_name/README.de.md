---
title: Objektnamen auflösen
description: Löst IFC-Objektnamen für Express-IDs aus dem Workflow-Eingang auf.
categories: IFC
---

Der `get_name` Knoten liest IFC-Entitäten nach Express-ID aus dem Eingang und gibt deren `Name`-Werte in der gleichen Reihenfolge zurück.

Verwenden Sie diesen Knoten für menschenlesbare Beschriftungen, typischerweise nach einem `element_filter` oder anderen Knoten, die Express-IDs bereitstellen.

## Anwendungsbeispiel

Verbinden Sie einen `element_filter`, um alle Wände zu erhalten, und nutzen Sie dann `get_name`, um deren Namen für die Anzeige oder Berichterstattung aufzulösen.

## Einstellungen

- **Fail on missing**: Wenn aktiviert, wird ein Fehler ausgelöst, wenn eine Express-ID nicht im Modell existiert. Entitäten ohne Name geben `null` zurück.
