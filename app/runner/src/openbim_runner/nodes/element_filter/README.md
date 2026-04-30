---
title: Filter IFC Elements
description: Resolve all IFC entities of a requested type to their express IDs.
---

The `element_filter` node queries the IFC model for all entities matching the configured `entity_type`.

Use this node at the start of a workflow when you need a stable list of express IDs for a specific IFC class before passing those IDs to downstream nodes.

## Use case example

Collect all `IFCWALL` entities from the model, then forward their express IDs to other nodes that inspect names, properties, or custom validation rules.