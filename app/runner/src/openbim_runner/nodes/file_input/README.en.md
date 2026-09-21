---
title: File Input
description: Refers to an IFC model assigned in the editor and outputs its slug.
categories: Other
---

The `file_input` node selects one of the IFC models assigned to the workflow and outputs its slug. Connect its `model_slug` output to a consumer node's `model_slug` input to make other nodes operate on that model.

Without a `file_input`, consumer nodes default to the main model.

## Use case example

Add a `file_input` for a secondary model, then bind its `model_slug` output to an `ifc_element_filter` so the filter runs against that model instead of the main one.

## Settings

- **Model**: Slug of the IFC model this File Input refers to. Defaults to the main model.

## Outputs

- **Model slug**: Slug of the selected IFC model, for binding to a consumer's model input.
