from __future__ import annotations

import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from openbim_runner.nodes.bcf_output.harmonized import HarmonizedCheckResult

# Comparison condition -> compact operator symbol. Word/phrase conditions carry
# their own surrounding whitespace so direct concatenation like
# `{check_parameter}{condition_symbol}{expected}` reads cleanly.
_CONDITION_SYMBOLS = {
    "equals": "=",
    "not_equals": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "contains": " contains ",
    "one_of": " ∈ ",
    "is_true": " is true",
    "is_false": " is false",
    "between": " between ",
    "outside": " outside ",
}

# Placeholders that cannot be resolved at runtime because the upstream node's
# label / type / id are not transmitted on the result models. They always
# resolve to an empty string and raise a warning.
FILE_ONLY_PLACEHOLDERS = ("node_label", "check_type", "node_id")


@dataclass(frozen=True)
class RenderContext:
    """Everything needed to resolve one BCF topic's template placeholders."""

    element_id: int
    element_guid: str
    element_name: str
    class_name: str
    check: HarmonizedCheckResult
    name_a: str = ""
    name_b: str = ""


class Namespace:
    """Attribute-access namespace used to resolve template placeholders.

    Supports dotted placeholder paths such as
    ``Pset_WallCommon.ThermalTransmittance.actual`` via normal Python attribute
    traversal, so ``string.Formatter`` resolves them without custom formatting.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node: Any = self
        for part in parts[:-1]:
            child = node._values.get(part)
            if not isinstance(child, Namespace):
                child = Namespace()
                node._values[part] = child
            node = child
        node._values[parts[-1]] = value

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as error:
            raise AttributeError(name) from error


class ResolvingFormatter(string.Formatter):
    def get_field(
        self,
        field_name: str,
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
    ) -> tuple[Any, str]:
        if not args:
            raise ValueError(field_name)
        namespace = args[0]
        parts = field_name.split(".")
        target: Any = namespace
        try:
            for part in parts:
                target = getattr(target, part)
        except AttributeError as error:
            raise ValueError(field_name) from error
        return target, parts[0]


def _adaptive_values(check: HarmonizedCheckResult) -> dict[str, str]:
    expectation = _expectation_clause(check)
    actual_display = check.actual_value if check.actual_value else "missing"
    if check.missing:
        failure_reason = (
            f"value for {check.check_parameter} is missing (expected {expectation})"
        )
    else:
        failure_reason = (
            f"value for {check.check_parameter} is {check.actual_value} "
            f"(expected {expectation})"
        )
    return {
        "expectation": expectation,
        "actual_display": actual_display,
        "failure_reason": failure_reason,
    }


def _expectation_clause(check: HarmonizedCheckResult) -> str:
    condition = check.expected_value_condition
    if condition in ("between", "outside"):
        bounds = f"{check.expected_value_min} and {check.expected_value_max}"
        return (
            f"between {bounds}" if condition == "between" else f"not between {bounds}"
        )
    if condition == "contains":
        return f'contains "{check.expected_value}"'
    if condition == "one_of":
        return f"is one of: {check.expected_value}"
    if condition == "is_true":
        return "is true"
    if condition == "is_false":
        return "is false"
    symbol = _CONDITION_SYMBOLS.get(condition, str(condition))
    return f"{symbol} {check.expected_value}".strip()


def build_namespace(ctx: RenderContext) -> Namespace:
    ns = Namespace()
    ns.set("id", ctx.element_id)
    ns.set("guid", ctx.element_guid)
    ns.set("name", ctx.element_name)
    ns.set("class_name", ctx.class_name)
    for placeholder in FILE_ONLY_PLACEHOLDERS:
        ns.set(placeholder, "")

    check = ctx.check
    actual = check.actual_value
    field_values: dict[str, Any] = {
        "key": check.key,
        "check_parameter": check.check_parameter,
        "property_name": check.check_parameter,
        "value": actual,
        "actual": actual,
        "actual_value": actual,
        "expected": check.expected_value,
        "expected_value": check.expected_value,
        "condition": check.expected_value_condition,
        "expected_value_condition": check.expected_value_condition,
        "expected_min": check.expected_value_min,
        "expected_value_min": check.expected_value_min,
        "expected_max": check.expected_value_max,
        "expected_value_max": check.expected_value_max,
        "unit": check.unit,
        "missing": check.missing,
        "passed": check.passed,
        "condition_symbol": _CONDITION_SYMBOLS.get(
            check.expected_value_condition, str(check.expected_value_condition)
        ),
        "name_a": ctx.name_a,
        "name_b": ctx.name_b,
    }
    field_values.update(_adaptive_values(check))
    # Expose the check's values under its own key as `<key>.<field>` and,
    # identically, as generic top-level fields so both resolve the same way.
    for field, value in field_values.items():
        ns.set(f"{check.key}.{field}", value)
        ns.set(field, value)

    return ns


def resolve_template(
    template: str,
    ns: Namespace,
    formatter: ResolvingFormatter,
    *,
    element_id: int,
    check_key: str,
) -> str:
    if not template:
        return ""
    try:
        return formatter.format(template, ns)
    except (AttributeError, KeyError, ValueError, IndexError) as error:
        placeholder = str(error)
        raise ValueError(
            f"Unresolved template placeholder '{placeholder}' for element "
            f"{element_id} (check '{check_key}')."
        ) from error
