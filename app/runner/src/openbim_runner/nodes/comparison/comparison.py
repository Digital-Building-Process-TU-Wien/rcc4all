from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from openbim_runner.nodes.base import NodeModel, node
from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
)

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
        description="Comparison operator applied to the value.",
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
    abs_tol: float = Field(
        default=0.001,
        title="Absolute tolerance",
        description="Absolute tolerance for float comparisons. Negative values are treated as their absolute value.",
    )

    @field_validator("abs_tol", mode="before")
    @classmethod
    def normalize_abs_tol(cls, v: float | None) -> float:
        return abs(v) if v is not None else 0.001


class ComparisonValueItem(NodeModel):
    reference: str = Field(
        title="Reference",
        description="Reference of the value's source element (e.g. `main:expr:1`, an `inter:intersection_...` helper key, or a `_`-joined distance pair).",
    )
    value: float | None = Field(
        default=None,
        title="Value",
        description="The numeric value to compare. Null if the value is missing or could not be computed.",
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason when the value could not be computed (e.g. 'no cached geometry').",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_model_instance(cls, data: object) -> object:
        """Coerce any pydantic model instance (e.g. ``measurement.MeasurementItem``)
        to a dict so it validates structurally without coupling this node to its
        producer's type."""
        return data.model_dump() if isinstance(data, BaseModel) else data


class ComparisonInputs(NodeModel):
    values: list[ComparisonValueItem] = Field(
        default=[],
        title="Values",
        description="List of values to compare. Each item has a `reference` to its source element and a `value`. Bind to a list output of an upstream node.",
    )
    unit: str = Field(
        default="",
        title="Unit",
        description="Unit of the compared values. Bind to a unit output of an upstream node, e.g. measurement.unit.",
    )
    check_parameter: str = Field(
        default="",
        title="Check parameter",
        description="Label naming the check (becomes the BCF check key). Bind to a type/check_parameter output of an upstream node, e.g. measurement.type.",
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


def _is_missing(value: float | None, error: str | None) -> bool:
    """Check if a value is missing or non-finite."""
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
    abs_tol: float,
) -> bool:
    """Evaluate a numeric comparison."""
    if condition == "equals":
        return math.isclose(value, target_value, abs_tol=abs_tol)
    if condition == "not_equals":
        return not math.isclose(value, target_value, abs_tol=abs_tol)
    if condition == "lt":
        return value < target_value
    if condition == "le":
        return value <= target_value + abs_tol
    if condition == "gt":
        return value > target_value
    if condition == "ge":
        return value >= target_value - abs_tol
    if condition == "between":
        min_ok = value >= target_min - abs_tol if inclusive_min else value > target_min
        max_ok = value <= target_max + abs_tol if inclusive_max else value < target_max
        return min_ok and max_ok
    if condition == "outside":
        min_ok = value >= target_min - abs_tol if inclusive_min else value > target_min
        max_ok = value <= target_max + abs_tol if inclusive_max else value < target_max
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
) -> ComparisonResult:
    if not inputs.check_parameter:
        raise ValueError("check_parameter must be non-empty.")

    _validate_settings(settings)

    elements: list[ComparisonElement] = []

    for item in inputs.values:
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
                settings.abs_tol,
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

        # One element per ComparisonValueItem (no dedup), carrying the raw reference
        # unchanged. The comparison node is IFC-agnostic: bcf_output expands the
        # raw ref (inter:intersection_... / distance pair / <slug>:expr:<id>)
        # into member objects and derives the class_name per member.
        elements.append(
            ComparisonElement(
                express_ids=[item.reference],
                class_name="",
                failed=not passed,
                checks=[check],
            )
        )

    passed_express_ids = [
        element.express_ids[0] for element in elements if not element.failed
    ]
    failed_express_ids = [
        element.express_ids[0] for element in elements if element.failed
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
