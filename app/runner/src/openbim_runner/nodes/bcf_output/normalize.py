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
    info_topics: list[list[FailedCheck]] = field(default_factory=list)


def _element_identities(
    element: HarmonizedElement,
) -> list[tuple[str, str, int]]:
    """Return one (reference, slug, express_id) identity per express_id in the element."""
    identities = []
    for reference in element.express_ids:
        if reference:
            parsed = parse_element_ref(reference, node="bcf_output")
            identities.append((reference, parsed.slug, parsed.express_id))
    return identities


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
    failed_groups: dict[tuple[str, ...], list[FailedCheck]] = {}
    info_groups: list[list[FailedCheck]] = []
    check_keys: list[str] = []
    seen_keys: set[str] = set()

    for element in elements:
        if not _is_included(element.failed, included):
            continue

        identities = _element_identities(element)
        if not identities:
            continue

        # Group key = tuple of all express_ids (preserves order for consistency)
        group_key = tuple(element.express_ids)

        for check in element.checks:
            processed += 1
            if check.key and check.key not in seen_keys:
                seen_keys.add(check.key)
                check_keys.append(check.key)

        failing = [check for check in element.checks if not check.passed]
        if failing:
            # One topic per element, merging all failing checks.
            # Emit one FailedCheck per express_id so each gets a viewpoint.
            group = failed_groups.setdefault(group_key, [])
            for ref, slug, express_id in identities:
                for check in failing:
                    group.append(
                        FailedCheck(
                            reference=ref,
                            slug=slug,
                            express_id=express_id,
                            class_name=element.class_name,
                            check=check,
                        )
                    )
        elif element.checks:
            # A selected element with no failing checks (all passed) emits one
            # informational topic, rendered from its first check.
            info_group: list[FailedCheck] = []
            for ref, slug, express_id in identities:
                info_group.append(
                    FailedCheck(
                        reference=ref,
                        slug=slug,
                        express_id=express_id,
                        class_name=element.class_name,
                        check=element.checks[0],
                    )
                )
            info_groups.append(info_group)

    failure_topics = list(failed_groups.values())
    # failure_count = number of failed checks (element-level, not expanded by id)
    failure_count = 0
    for element in elements:
        if not _is_included(element.failed, included):
            continue
        failing = [c for c in element.checks if not c.passed]
        failure_count += len(failing)

    return NormalizedOutput(
        element_count=len(elements),
        processed_result_count=processed,
        failure_count=failure_count,
        check_keys=check_keys,
        failure_topics=failure_topics,
        info_topics=info_groups,
    )
