"""Normalize harmonized check elements into flat BCF topic groups.

The BCF node consumes the shared harmonized element shape (from loi_check or
tilt_of_components). Normalization flattens the nested elements/checks into the
topic groups that become BCF topics, and deduplicates check keys across
elements (their union, in first-appearance order) so downstream rendering /
reporting can enumerate every check type that was seen.

The `included` filter selects which elements the BCF contains ("failed",
"passed" or "all"). Each selected element with at least one failing check
yields one BCF topic that merges all of its failing checks; selected elements
with no failing checks yield one informational topic each.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
)
from openbim_runner.util.references import parse_element_ref

INCLUDE_FAILED = "failed"
INCLUDE_PASSED = "passed"
INCLUDE_ALL = "all"


@dataclass(frozen=True)
class FailedCheck:
    """One failed check with the element context it belongs to."""

    reference: str
    slug: str
    express_id: int
    class_name: str
    check: HarmonizedCheckResult


@dataclass
class NormalizedOutput:
    element_count: int
    processed_result_count: int
    failure_count: int
    check_keys: list[str]
    failure_topics: list[list[FailedCheck]] = field(default_factory=list)
    info_topics: list[FailedCheck] = field(default_factory=list)


def _element_identity(
    element: HarmonizedElement,
) -> tuple[str, str, int]:
    reference = element.express_ids[0] if element.express_ids else ""
    if reference:
        parsed = parse_element_ref(reference, node="bcf_output")
        return reference, parsed.slug, parsed.express_id
    return reference, "", 0


def _is_included(element_failed: bool, included: str) -> bool:
    if included == INCLUDE_ALL:
        return True
    if included == INCLUDE_PASSED:
        return not element_failed
    # INCLUDE_FAILED (default)
    return element_failed


def normalize(
    elements: list[HarmonizedElement],
    *,
    included: str = INCLUDE_FAILED,
) -> NormalizedOutput:
    processed = 0
    failed: list[FailedCheck] = []
    info: list[FailedCheck] = []
    check_keys: list[str] = []
    seen_keys: set[str] = set()

    for element in elements:
        reference, slug, express_id = _element_identity(element)
        if not _is_included(element.failed, included):
            continue

        for check in element.checks:
            processed += 1
            if check.key and check.key not in seen_keys:
                seen_keys.add(check.key)
                check_keys.append(check.key)

        failing = [check for check in element.checks if not check.passed]
        if failing:
            for check in failing:
                failed.append(
                    FailedCheck(
                        reference=reference,
                        slug=slug,
                        express_id=express_id,
                        class_name=element.class_name,
                        check=check,
                    )
                )
        elif element.checks:
            # A selected element with no failing checks (all passed) emits one
            # informational topic, rendered from its first check.
            info.append(
                FailedCheck(
                    reference=reference,
                    slug=slug,
                    express_id=express_id,
                    class_name=element.class_name,
                    check=element.checks[0],
                )
            )

    # One BCF topic per element, merging all of its failing checks.
    grouped: dict[str, list[FailedCheck]] = {}
    for failed_check in failed:
        grouped.setdefault(failed_check.reference, []).append(failed_check)
    failure_topics = list(grouped.values())

    return NormalizedOutput(
        element_count=len(elements),
        processed_result_count=processed,
        failure_count=len(failed),
        check_keys=check_keys,
        failure_topics=failure_topics,
        info_topics=info,
    )
