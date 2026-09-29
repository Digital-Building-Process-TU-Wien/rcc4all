from __future__ import annotations

import math
from typing import Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
)
from openbim_runner.nodes.measurement.measurement import MeasurementItem
from openbim_runner.util.references import ElementRef, split_expr_key

ComparisonCondition = Literal[
    "equals",
    "not_equals",
    "lt",
    "le",
    "gt",
    "ge",
    "between",
    "outside",
]


class ComparisonSettings(NodeModel):
    condition: ComparisonCondition = Field(
        default="lt",
        title="Condition",
        description="Comparison operator applied to the measured value.",
    )
    target_value: float = Field(
        default=0.0,
        title="Target value",
        description="Target value for single-value operators (equals, not_equals, lt, le, gt, ge).",
    )
    target_min: float = Field(
        default=0.0,
        title="Target min",
        description="Lower barrier for between / outside operators.",
    )
    target_max: float = Field(
        default=0.0,
        title="Target max",
        description="Upper barrier for between / outside operators.",
    )
    inclusive_min: bool = Field(
        default=True,
        title="Inclusive min",
        description="If True, the range includes values equal to the lower barrier (>=); otherwise strictly greater (>).",
    )
    inclusive_max: bool = Field(
        default=True,
        title="Inclusive max",
        description="If True, the range includes values equal to the upper barrier (<=); otherwise strictly less (<).",
    )


class ComparisonInputs(NodeModel):
    values: list[MeasurementItem] = Field(
        default=[],
        title="Values",
        description="List of measured values with references (bound from measurement.measurements).",
    )
    unit: str = Field(
        default="",
        title="Unit",
        description="Unit of measurement (bound from measurement.unit).",
    )
    check_parameter: str = Field(
        default="",
        title="Check parameter",
        description="Label for the check (bound from measurement.type); becomes the check key.",
    )


ComparisonCheckResult = HarmonizedCheckResult
ComparisonElement = HarmonizedElement


class ComparisonResult(NodeModel):
    summary_element_count: int = Field(
        title="Element count",
        description="Number of elements processed.",
    )
    summary_passed_count: int = Field(
        title="Passed count",
        description="Number of elements whose check passed.",
    )
    summary_failed_count: int = Field(
        title="Failed count",
        description="Number of elements with a failed check.",
    )
    summary_check_count: int = Field(
        title="Check count",
        description="Total number of checks (equals element count, one check per element).",
    )
    passed_express_ids: list[str] = Field(
        default=[],
        title="Passed express IDs",
        description="Qualified references of elements whose check passed.",
    )
    failed_express_ids: list[str] = Field(
        default=[],
        title="Failed express IDs",
        description="Qualified references of elements with a failed check.",
    )
    elements: list[ComparisonElement] = Field(
        default=[],
        title="Elements",
        description="Ordered list of elements with their comparison check results.",
    )


def _resolve_reference(ref: str) -> list[ElementRef]:
    """Resolve a measurement reference into IFC element refs.

    Handles:
    - Direct expr ref: `<slug>:expr:<id>` → single ElementRef
    - Collision intersection: `inter:intersection_<k1>_<k2>` → both keys parsed
    - Distance pair: `<k1>_<k2>` → both keys parsed
    - gen:/inter:/malformed → [] (skip)
    """
    # Case 1: Collision intersection prefix — strip and parse as pair
    remainder = ref
    if ref.startswith("inter:intersection_"):
        remainder = ref[len("inter:intersection_") :]
        # Fall through to pair parsing
    else:
        # Case 2: Direct expr ref (not inter: or gen: prefixes)
        parsed = split_expr_key(ref)
        if parsed is not None:
            slug, express_id = parsed
            return [ElementRef(ref, slug, express_id)]
        # Not a direct ref, try as distance pair
        # remainder is still ref (no prefix stripped)

    # Case 3: Pair ref (collision or distance) — split on last _ between two keys
    # Format: <key1>_<key2> where each key should be <slug>:expr:<id>
    # Use split_expr_key on each side for robustness
    underscore_pos = remainder.rfind("_")
    if underscore_pos > 0:
        k1 = remainder[:underscore_pos]
        k2 = remainder[underscore_pos + 1 :]
        parsed_k1 = split_expr_key(k1)
        parsed_k2 = split_expr_key(k2)
        if parsed_k1 is not None and parsed_k2 is not None:
            slug1, id1 = parsed_k1
            slug2, id2 = parsed_k2
            return [
                ElementRef(k1, slug1, id1),
                ElementRef(k2, slug2, id2),
            ]

    # Case 4: Unresolvable (gen:, inter: non-intersection, malformed)
    return []


def _resolve_class_name(context: ExecutionContext, element: ElementRef) -> str:
    """Resolve the IFC class of a parsed element reference; 'unknown' if missing."""
    try:
        model = context.resolve_model(element.slug)
        entity = model.by_id(element.express_id)
        return entity.is_a()
    except (RuntimeError, AttributeError, ValueError):
        return "unknown"


def _is_missing(value: float | None, error: str | None) -> bool:
    """Check if a measurement value is missing or non-finite."""
    if value is None:
        return True
    if error is not None:
        return True
    return not math.isfinite(value)


def _check_passes(
    condition: ComparisonCondition,
    value: float,
    target_value: float,
    target_min: float,
    target_max: float,
    inclusive_min: bool,
    inclusive_max: bool,
) -> bool:
    """Evaluate a numeric comparison."""
    if condition == "equals":
        return math.isclose(value, target_value)
    if condition == "not_equals":
        return not math.isclose(value, target_value)
    if condition == "lt":
        return value < target_value
    if condition == "le":
        return value <= target_value
    if condition == "gt":
        return value > target_value
    if condition == "ge":
        return value >= target_value
    if condition == "between":
        min_ok = value >= target_min if inclusive_min else value > target_min
        max_ok = value <= target_max if inclusive_max else value < target_max
        return min_ok and max_ok
    if condition == "outside":
        min_ok = value >= target_min if inclusive_min else value > target_min
        max_ok = value <= target_max if inclusive_max else value < target_max
        return not (min_ok and max_ok)
    return False


def _validate_settings(settings: ComparisonSettings) -> None:
    """Validate comparison settings."""
    if (
        settings.condition in ("between", "outside")
        and settings.target_min > settings.target_max
    ):
        raise ValueError(
            f"target_min ({settings.target_min}) must be <= target_max ({settings.target_max}) for '{settings.condition}' condition."
        )


@node()
async def comparison(
    settings: ComparisonSettings,
    inputs: ComparisonInputs,
    context: ExecutionContext,
) -> ComparisonResult:
    if not inputs.check_parameter:
        raise ValueError("check_parameter must be non-empty.")

    _validate_settings(settings)

    elements: list[ComparisonElement] = []
    emitted_keys: set[tuple[tuple[str, ...], str]] = set()

    for item in inputs.values:
        resolved_refs = _resolve_reference(item.reference)
        if not resolved_refs:
            continue

        is_missing = _is_missing(item.value, item.error)
        if is_missing:
            passed = False
        else:
            # At this point, item.value is guaranteed to be a finite float
            assert item.value is not None
            passed = _check_passes(
                settings.condition,
                item.value,
                settings.target_value,
                settings.target_min,
                settings.target_max,
                settings.inclusive_min,
                settings.inclusive_max,
            )

        check = ComparisonCheckResult(
            key=inputs.check_parameter,
            check_parameter=inputs.check_parameter,
            expected_value=str(settings.target_value)
            if settings.condition not in ("between", "outside")
            else "",
            actual_value=str(item.value) if item.value is not None else "",
            unit=inputs.unit,
            missing=is_missing,
            passed=passed,
            expected_value_condition=settings.condition,
            expected_value_min=str(settings.target_min)
            if settings.condition in ("between", "outside")
            else "",
            expected_value_max=str(settings.target_max)
            if settings.condition in ("between", "outside")
            else "",
        )

        # Build canonical dedup key: sorted tuple of all refs + check_parameter
        # This ensures 170↔766 and 766↔170 dedup to the same pair
        ref_tuple = tuple(sorted(ref.reference for ref in resolved_refs))
        dedup_key = (ref_tuple, inputs.check_parameter)
        if dedup_key in emitted_keys:
            continue
        emitted_keys.add(dedup_key)

        # One element per pair (or single ref), with all express_ids
        express_ids = [ref.reference for ref in resolved_refs]
        class_name = _resolve_class_name(context, resolved_refs[0])
        element_failed = not passed

        elements.append(
            ComparisonElement(
                express_ids=express_ids,
                class_name=class_name,
                failed=element_failed,
                checks=[check],
            )
        )

    passed_express_ids = [
        ref for element in elements if not element.failed for ref in element.express_ids
    ]
    failed_express_ids = [
        ref for element in elements if element.failed for ref in element.express_ids
    ]

    return ComparisonResult(
        summary_element_count=len(elements),
        summary_passed_count=len(passed_express_ids),
        summary_failed_count=len(failed_express_ids),
        summary_check_count=len(elements),
        passed_express_ids=passed_express_ids,
        failed_express_ids=failed_express_ids,
        elements=elements,
    )
