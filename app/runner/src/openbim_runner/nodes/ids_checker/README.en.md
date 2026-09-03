---
title: IDS Checker
description: Validates the IFC model against one or more IDS specifications.
categories: validation
---

The `ids_checker` node validates the loaded IFC model against an IDS (Information Delivery Specification) file. Each specification defines entity types, properties, and classifications to check. The node supports multiple specifications within a single IDS file and aggregates results across all of them.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| `express_ids` | `list[int]` | Optional list of IFC entity express IDs to validate. When provided, only these entities are checked. When empty, the whole model is validated. |

## Settings

| Name | Type | Description |
|------|------|-------------|
| `ids_file` | `str` | Path to the IDS specification file (required). |
| `generate_detailed_report` | `bool` (default: `false`) | When enabled, results are additionally grouped by specification (for report generation). Combined lists are always created. |
| `report_format` | `"json" \| "html" \| null` (default: `null`) | Format for the generated report file. Only effective when `generate_detailed_report` is enabled. Report is saved as `ids_report-{timestamp}.{format}` in the output directory. |

## Output Behavior

The combined lists (`failed_express_ids`, `passed_express_ids`) are always created. When `generate_detailed_report` is enabled, results are additionally grouped by specification for detailed reporting.

## Result

`IdsCheckerResult` contains three fields:

- `failed_express_ids: list[int]` — Express IDs that failed at least one IDS requirement. Always populated.
- `passed_express_ids: list[int]` — Express IDs that passed all applicable IDS requirements. Always populated.
- `specifications: list[SpecificationResult] | null` — Per-specification breakdown. Only included when `generate_detailed_report` is enabled. Omitted from output when disabled.

An entity not applicable to any specification is silently excluded from both lists.

## Notes

- An empty `ids_file` raises a `ValueError`.
- The IDS file must be valid XML.
- Multiple specifications within one IDS are all checked; an entity fails if it violates **any** specification.
