---
title: Resolve Object Names
description: Look up IFC object names by express ID from workflow input.
categories: IFC
---

The `get_name` node reads IFC entities by express ID from its input and returns their `Name` values in the same order.

Use this node to get human-readable labels for model elements, typically after an `ifc_element_filter` or other node that provides express IDs.

## Use case example

Connect an `ifc_element_filter` to get all walls, then use `get_name` to resolve their names for display or reporting.

## Settings

- **Fail on missing**: When enabled, raises an error if an express ID does not exist in the model. Entities without a name return `null` instead.