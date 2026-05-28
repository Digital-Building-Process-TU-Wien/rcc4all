---
title: Objektnamen auflösen
description: Schlägt IFC-Objektnamen für eine konfigurierte Liste von Express-IDs nach.
categories: IFC
---

Der `get_name` Knoten liest IFC-Entitäten nach Express-ID und gibt deren `Name`-Werte in der gleichen Reihenfolge wie die konfigurierte Eingabeliste zurück.

Verwenden Sie diesen Knoten, wenn ein Workflow menschenlesbare Beschriftungen für Modellemente benötigt, insbesondere nachdem ein Filterschritt die Kandidatenentitäten bereits eingegrenzt hat.

## Anwendungsbeispiel

Lösen Sie die Namen einer Wandauswahl auf und senden Sie diese geordnete Namenliste dann an einen formatierenden Knoten wie `concat_string`, um eine lesbare Zusammenfassung zu erstellen.
