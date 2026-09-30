"""Shared check-result schema for the BCF output feature.

These types are the single source of truth for a checking node's slim,
structured output: ``HarmonizedCheckResult`` (one property/tilt check outcome)
and ``HarmonizedElement`` (one checked element with its list of checks).

Consuming checking nodes alias them so their result carries the exact same
shape, allowing ``bcf_output`` to turn failures from LOI-Check,
Tilt-of-Components or Comparison into BCF topics without caring which node
produced the data:

- ``loi_check``: ``PropertyCheckResult = HarmonizedCheckResult``,
  ``ComparisonElement = HarmonizedElement``.
- ``tilt_of_components``: ``TiltCheck = HarmonizedCheckResult``,
  ``TiltsElement = HarmonizedElement``.
- ``comparison``: ``ComparisonCheckResult = HarmonizedCheckResult``,
  ``ComparisonElement = HarmonizedElement``.

Owned by the BCF-output feature and therefore kept in this folder. It depends
only on ``base`` / ``pydantic`` (no ``bcf-client``), so the producer nodes that
import it stay free of the BCF dependency.
"""

from __future__ import annotations

from pydantic import Field

from openbim_runner.nodes.base import NodeModel


class HarmonizedCheckResult(NodeModel):
    key: str = Field(
        title="Key",
        description="Stable identifier for this check (e.g. a property key or 'surface_0').",
    )
    check_parameter: str = Field(
        title="Check parameter",
        description="The parameter being checked (e.g. the property name, or 'angle').",
    )
    expected_value: str = Field(
        default="",
        title="Expected value",
        description="Expected value as a string (empty for is_true / is_false and range checks).",
    )
    actual_value: str = Field(
        default="",
        title="Actual value",
        description="Measured/read value as a string, or empty if the value is missing.",
    )
    unit: str = Field(
        default="",
        title="Unit",
        description="Measurement unit of the compared value, or empty when unknown.",
    )
    missing: bool = Field(
        default=False,
        title="Missing",
        description="True when the value is not present / could not be measured.",
    )
    passed: bool = Field(
        title="Passed",
        description="Whether the check passed.",
    )
    expected_value_condition: str = Field(
        default="",
        title="Expected value condition",
        description="The comparison operator that was applied (empty for checks with none).",
    )
    expected_value_min: str = Field(
        default="",
        title="Expected value min",
        description="Lower barrier used for numeric range checks, or empty for single-value checks.",
    )
    expected_value_max: str = Field(
        default="",
        title="Expected value max",
        description="Upper barrier used for numeric range checks, or empty for single-value checks.",
    )


class HarmonizedElement(NodeModel):
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "The element reference(s) this element carries. Usually a single raw "
            "reference (`<slug>:expr:<id>`, an `inter:intersection_...` helper key, "
            "or a `_`-joined distance pair) that bcf_output expands into IFC member "
            "objects for viewpoints."
        ),
    )
    class_name: str = Field(
        title="Class name",
        description="IFC entity class (e.g. IFCWALL) or 'unknown' for missing entities.",
    )
    failed: bool = Field(
        title="Failed",
        description="True if at least one check on this element failed.",
    )
    checks: list[HarmonizedCheckResult] = Field(
        default=[],
        title="Checks",
        description="List of check results for this element.",
    )


__all__ = ["HarmonizedCheckResult", "HarmonizedElement"]
