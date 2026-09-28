---
title: File Input
description: Refers to an IFC model assigned in the editor and outputs its slug.
categories: Other
---

The `file_input` node selects one of the IFC models assigned to the workflow and outputs its slug. Connect its `model_slug` output to an `ifc_element_filter`'s `model_slug` input to make the filter scan that model — this is the only model port in the graph.

All other nodes consume **fully qualified element references** (`<slug>:expr:<id>`); each reference names its own model, so consumers of element references have no model inputs.

Without a `file_input`, `ifc_element_filter` scans the main model.

## Use case example

Add a `file_input` for a secondary model, then bind its `model_slug` output to an `ifc_element_filter` so the filter scans that model instead of the main one. The filter's qualified references (`<secondary-slug>:expr:<id>`) carry the model with them, so downstream nodes resolve them against the right file automatically.

## Settings

- **Model**: Slug of the IFC model this File Input refers to. Defaults to the main model.

## Outputs

- **Model slug**: Slug of the selected IFC model, for binding to `ifc_element_filter`'s `model_slug` input.