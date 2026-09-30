from __future__ import annotations

from typing import Literal

from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
)
from openbim_runner.util.ifc_properties import (
    build_property_key,
    entity_matches_type,
    get_property_value,
    is_any_entity_type,
    stringify_value,
)
from openbim_runner.util.references import iter_resolved_elements

ComparisonCondition = Literal[
    "equals",
    "not_equals",
    "lt",
    "le",
    "gt",
    "ge",
    "contains",
    "one_of",
    "is_true",
    "is_false",
    "between",
    "outside",
]

# Strings considered truthy/falsy for is_true / is_false comparisons (case-insensitive).
_TRUTHY = {"true", "1", "yes", "y", "t"}
_FALSY = {"false", "0", "no", "n", "f"}


class ComparisonRow(NodeModel):
    entity_type: str = Field(
        default="",
        title="Entity type",
        description="Optional IFC entity type (e.g., IFCWALL, IFCDOOR). Empty means any entity type. Used for UI preselection only.",
    )
    property_set: str = Field(
        default="",
        title="Property set",
        description="IFC PropertySet name (e.g., Pset_WallCommon) or custom property set name.",
    )
    property_name: str = Field(
        default="",
        title="Property name",
        description="Name of the property to compare within the PropertySet.",
    )
    condition: ComparisonCondition = Field(
        title="Condition",
        description="Comparison operator applied to the property value. 'between' / 'outside' use the numeric range barriers.",
    )
    expected_value: str = Field(
        default="",
        title="Expected value",
        description="Target value the property is compared against. Ignored for is_true / is_false and range checks.",
    )
    allowed_values: list[str] = Field(
        default=[],
        title="Allowed values",
        description="List of accepted values for the 'one_of' condition. Empty entries are ignored.",
    )
    range_min: str = Field(
        default="",
        title="Range min",
        description="Lower barrier for numeric range checks (condition = between / outside).",
    )
    range_max: str = Field(
        default="",
        title="Range max",
        description="Upper barrier for numeric range checks (condition = between / outside).",
    )
    inclusive_min: bool = Field(
        default=True,
        title="Inclusive min",
        description="If True the range includes values equal to the lower barrier (>=); otherwise it is strictly greater (>).",
    )
    inclusive_max: bool = Field(
        default=True,
        title="Inclusive max",
        description="If True the range includes values equal to the upper barrier (<=); otherwise it is strictly less (<).",
    )


class LoiCheckSettings(NodeModel):
    rows: list[ComparisonRow] = Field(
        default=[],
        title="Comparison rows",
        description="List of property comparison rules. Each row is checked against every input element.",
    )


class LoiCheckInputs(NodeModel):
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "Qualified element references (`<slug>:expr:<id>`) to run property "
            "comparisons against. Bind ifc_element_filter output here."
        ),
    )


# The result models are the harmonized check schema shared with other checking
# nodes (e.g. tilt_of_components). Keeping these aliases lets this node read the
# same data shape while exposing a single source of truth for downstream
# consumers like bcf_output.
PropertyCheckResult = HarmonizedCheckResult
ComparisonElement = HarmonizedElement


class LoiCheckResult(NodeModel):
    summary_element_count: int = Field(
        title="Element count",
        description="Number of elements processed.",
    )
    summary_passed_count: int = Field(
        title="Passed count",
        description="Number of checked elements whose checks all passed.",
    )
    summary_failed_count: int = Field(
        title="Failed count",
        description="Number of checked elements with at least one failed check.",
    )
    summary_check_count: int = Field(
        title="Check count",
        description="Total number of property checks across all elements.",
    )
    passed_express_ids: list[str] = Field(
        default=[],
        title="Passed express IDs",
        description="Qualified references of elements whose checks all passed. Only elements that were actually checked (had at least one applied check) are included.",
    )
    failed_express_ids: list[str] = Field(
        default=[],
        title="Failed express IDs",
        description="Qualified references of elements with at least one failed check. Only elements that were actually checked (had at least one applied check) are included.",
    )
    elements: list[ComparisonElement] = Field(
        default=[],
        title="Elements",
        description="Ordered list of elements with their property check results.",
    )


@node()
async def loi_check(
    settings: LoiCheckSettings,
    inputs: LoiCheckInputs,
    context: ExecutionContext,
) -> LoiCheckResult:
    from ifcopenshell.util.element import get_psets

    if not settings.rows:
        raise ValueError("At least one comparison row must be specified.")

    for i, row in enumerate(settings.rows):
        if not row.property_name:
            raise ValueError(f"Comparison row {i + 1} must have a property name.")
        _validate_range(row, i + 1)
        _validate_one_of(row, i + 1)
        _validate_contains(row, i + 1)

    elements: list[ComparisonElement] = []
    total_checks = 0

    # Explicitly specified component types act as an output filter: only elements
    # matching at least one are emitted. If ANY row uses an "Any Element" signal
    # (empty component or the literal "any" token), filtering is disabled and all
    # input elements are tested/emitted.
    if any(is_any_entity_type(row.entity_type) for row in settings.rows):
        specified_types: set[str] = set()
    else:
        specified_types = {
            row.entity_type.strip().upper()
            for row in settings.rows
            if row.entity_type.strip()
        }

    # Each qualified reference resolves against its own model slug; mixed-model
    # lists are allowed.
    for element, model in iter_resolved_elements(
        inputs.express_ids, context, node="loi_check"
    ):
        try:
            entity = model.by_id(element.express_id)
        except RuntimeError:
            if not specified_types:
                elements.append(
                    ComparisonElement(
                        express_ids=[element.reference],
                        class_name="unknown",
                        failed=False,
                        checks=[],
                    )
                )
            continue

        if specified_types and not any(
            entity_matches_type(entity, entity_type) for entity_type in specified_types
        ):
            continue

        psets = get_psets(entity)
        class_name = entity.is_a()

        checks: list[PropertyCheckResult] = []
        element_failed = False

        for row in settings.rows:
            if not entity_matches_type(entity, row.entity_type):
                continue

            actual_raw = get_property_value(
                entity, psets, row.property_set, row.property_name
            )
            actual = stringify_value(actual_raw)

            if row.condition in ("between", "outside"):
                range_min = row.range_min.strip()
                range_max = row.range_max.strip()
                passed = _check_range_passes(
                    range_min,
                    range_max,
                    row.inclusive_min,
                    row.inclusive_max,
                    row.condition,
                    actual,
                )
                condition = row.condition
                expected = ""
                expected_min = range_min
                expected_max = range_max
            elif row.condition == "one_of":
                accepted = [
                    value.strip() for value in row.allowed_values if value.strip()
                ]
                passed = _check_one_of(actual, accepted)
                condition = row.condition
                expected = ", ".join(accepted)
                expected_min = ""
                expected_max = ""
            else:
                passed = _check_passes(row.condition, actual, row.expected_value)
                condition = row.condition
                expected = row.expected_value
                expected_min = ""
                expected_max = ""

            prop_key = build_property_key(row.property_set, row.property_name)
            checks.append(
                PropertyCheckResult(
                    key=prop_key,
                    check_parameter=row.property_name,
                    expected_value=expected,
                    actual_value=actual if actual is not None else "",
                    unit="",
                    missing=actual is None,
                    passed=passed,
                    expected_value_condition=condition,
                    expected_value_min=expected_min,
                    expected_value_max=expected_max,
                )
            )
            if not passed:
                element_failed = True

        total_checks += len(checks)

        elements.append(
            ComparisonElement(
                express_ids=[element.reference],
                class_name=class_name,
                failed=element_failed,
                checks=checks,
            )
        )

    checked = [element for element in elements if element.checks]
    passed_express_ids = [
        ref for element in checked if not element.failed for ref in element.express_ids
    ]
    failed_express_ids = [
        ref for element in checked if element.failed for ref in element.express_ids
    ]

    return LoiCheckResult(
        summary_element_count=len(elements),
        summary_passed_count=len(passed_express_ids),
        summary_failed_count=len(failed_express_ids),
        summary_check_count=total_checks,
        passed_express_ids=passed_express_ids,
        failed_express_ids=failed_express_ids,
        elements=elements,
    )


def _check_passes(
    condition: ComparisonCondition, actual: str | None, expected: str
) -> bool:
    """Evaluate a single comparison against an (already stringified) property value."""
    if condition in ("is_true", "is_false"):
        return _check_truth(condition, actual)

    # All remaining conditions require an actual value.
    if actual is None:
        return False

    expected_str = str(expected)

    if condition in ("equals", "not_equals", "contains"):
        actual_norm = _normalize_for_compare(actual)
        expected_norm = _normalize_for_compare(expected_str)
        if condition == "equals":
            return actual_norm == expected_norm
        if condition == "not_equals":
            return actual_norm != expected_norm
        # contains: expected is a substring of actual (both whitespace/case-normalized)
        return expected_norm in actual_norm

    # Numeric comparisons: non-numeric values fail the check.
    if condition in ("lt", "le", "gt", "ge"):
        try:
            actual_num = float(actual)
            expected_num = float(expected_str)
        except ValueError:
            return False

        if condition == "lt":
            return actual_num < expected_num
        if condition == "le":
            return actual_num <= expected_num
        if condition == "gt":
            return actual_num > expected_num
        return actual_num >= expected_num

    return False


def _normalize_for_compare(value: str) -> str:
    """Trim leading/trailing whitespace and lowercase for comparison."""
    return value.strip().lower()


def _check_truth(condition: ComparisonCondition, actual: str | None) -> bool:
    normalized = (actual or "").strip().lower()
    if condition == "is_true":
        return normalized in _TRUTHY
    # is_false
    return normalized in _FALSY


def _validate_range(row: ComparisonRow, row_number: int) -> None:
    """Validate range rows (condition = between/outside): both barriers set and numeric."""
    if row.condition not in ("between", "outside"):
        return

    min_set = bool(row.range_min.strip())
    max_set = bool(row.range_max.strip())

    if not min_set or not max_set:
        raise ValueError(
            f"Comparison row {row_number}: both range_min and range_max must be set for a range check."
        )

    try:
        min_num = float(row.range_min)
        max_num = float(row.range_max)
    except ValueError:
        raise ValueError(
            f"Comparison row {row_number}: range_min and range_max must both be numeric values."
        ) from None

    if min_num > max_num:
        raise ValueError(
            f"Comparison row {row_number}: range_min must be less than or equal to range_max."
        )


def _validate_one_of(row: ComparisonRow, row_number: int) -> None:
    """Validate one_of rows: require at least one non-empty accepted value."""
    if row.condition != "one_of":
        return

    if not any(value.strip() for value in row.allowed_values):
        raise ValueError(
            f"Comparison row {row_number}: condition 'one_of' requires at least one allowed value."
        )


def _validate_contains(row: ComparisonRow, row_number: int) -> None:
    """Validate contains rows: require a non-empty target value."""
    if row.condition != "contains":
        return

    if not row.expected_value.strip():
        raise ValueError(
            f"Comparison row {row_number}: condition 'contains' requires a non-empty expected value."
        )


def _check_one_of(actual: str | None, allowed_values: list[str]) -> bool:
    """Evaluate a case- and whitespace-insensitive 'one of' check. Missing actual fails."""
    if actual is None:
        return False

    actual_normalized = _normalize_for_compare(actual)
    return any(
        _normalize_for_compare(value) == actual_normalized for value in allowed_values
    )


def _check_range_passes(
    range_min: str,
    range_max: str,
    inclusive_min: bool,
    inclusive_max: bool,
    condition: ComparisonCondition,
    actual: str | None,
) -> bool:
    """Evaluate a numeric range check. Non-numeric actual values fail the check."""
    if actual is None:
        return False

    try:
        actual_num = float(actual)
        min_num = float(range_min)
        max_num = float(range_max)
    except ValueError:
        return False

    min_ok = actual_num >= min_num if inclusive_min else actual_num > min_num
    max_ok = actual_num <= max_num if inclusive_max else actual_num < max_num
    inside = min_ok and max_ok

    return inside if condition == "between" else not inside
