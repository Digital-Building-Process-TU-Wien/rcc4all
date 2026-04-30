---
title: Concatenate Strings
description: Join a list of resolved string values into one output string.
---

The `concat_string` node combines the incoming `values` list into a single string.

Use this node when a workflow needs to turn several upstream values into a readable label, summary, or message.

## Use case example

Combine object names from an earlier lookup step into a comma-separated sentence for display in the UI or for downstream reporting.