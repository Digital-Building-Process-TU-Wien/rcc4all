---
title: IDS Checker
description: Validates the IFC model against one or more IDS specifications.
categories: validation
---

The `ids_checker` node validates IFC elements against an IDS (Information Delivery Specification) file. Each specification defines entity types, properties, and classifications to check. The node supports multiple specifications within a single IDS file and aggregates results across all of them.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[str]` | Required list of fully qualified element references (`<slug>:expr:<id>`) to validate, typically bound to `ifc_element_filter`. Mixed-model lists are allowed: references are grouped by slug and each model is validated once against the IDS file, with results filtered to the given references per group. An empty bound list validates zero elements. |

## Settings

| Name | Type | Description |
|------|------|-------------|
| `ids_file` | `str` | Path to the IDS specification file (required). |
| `generate_detailed_report` | `bool` (default: `false`) | Adds a per-specification breakdown to the result. Combined lists are always created. Generating a report file also requires `report_format` and references from a single model. |
| `report_format` | `"json" \| "html" \| null` (default: `null`) | Format for the generated report file. A report is written only when both `generate_detailed_report` and `report_format` are enabled. The file is saved as `ids_report-{timestamp}.{format}` in the output directory. |

## Output Behavior

The combined lists (`failed_express_ids`, `passed_express_ids`) are always created. When `generate_detailed_report` is enabled, results are also grouped by specification. A report file is written only when both `generate_detailed_report` and `report_format` are enabled.

## Result

`IdsCheckerResult` contains four fields:

- `failed_express_ids: list[str]` — Qualified references (`<slug>:expr:<id>`) of elements that failed at least one IDS requirement. Always populated.
- `passed_express_ids: list[str]` — Qualified references of elements that passed all applicable IDS requirements. Always populated.
- `specifications: list[SpecificationResult] | null` — Per-specification breakdown (its per-spec lists also hold qualified references). Populated when `generate_detailed_report` is enabled; otherwise `null`.
- `report_path: str | null` — Path to the generated report file. Populated only when both `generate_detailed_report` and `report_format` are enabled; otherwise `null`.

An entity not applicable to any specification is silently excluded from both lists.

## Notes

- An empty `ids_file` raises a `ValueError`.
- The IDS file must be valid XML.
- Multiple specifications within one IDS are all checked; an entity fails if it violates **any** specification.
