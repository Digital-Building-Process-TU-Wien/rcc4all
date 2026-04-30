---
title: Resolve Object Names
description: Look up IFC object names for a configured list of express IDs.
---

The `get_name` node reads IFC entities by express ID and returns their `Name` values in the same order as the configured input list.

Use this node when a workflow needs human-readable labels for model elements, especially after a filtering step has already narrowed the candidate entities.

## Use case example

Resolve the names of a wall selection, then send that ordered name list into a formatting node such as `concat_string` to create a readable summary.