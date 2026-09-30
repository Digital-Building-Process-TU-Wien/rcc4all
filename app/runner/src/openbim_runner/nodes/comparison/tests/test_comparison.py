from __future__ import annotations

import asyncio

import pytest

from openbim_runner.nodes.comparison.comparison import (
    ComparisonInputs,
    ComparisonResult,
    ComparisonSettings,
    comparison,
)
from openbim_runner.nodes.measurement.measurement import MeasurementItem


def _run(settings: ComparisonSettings, inputs: ComparisonInputs) -> ComparisonResult:
    return asyncio.run(comparison(settings, inputs))


class TestRawReferencePassthrough:
    """Every MeasurementItem emits one element carrying its raw reference unchanged."""

    def test_direct_expr_ref_carried_raw(self) -> None:
        """Direct `<slug>:expr:<id>` → 1 element with the raw ref, empty class."""
        item = MeasurementItem(reference="main:expr:42", value=1.5, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["main:expr:42"]
        assert result.elements[0].class_name == ""

    def test_collision_intersection_carried_raw(self) -> None:
        """Collision `inter:intersection_...` → 1 element with the raw ref (not members)."""
        ref = "inter:intersection_main:expr:1_main:expr:2"
        item = MeasurementItem(reference=ref, value=0.5, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == [ref]
        assert result.elements[0].class_name == ""

    def test_distance_pair_carried_raw(self) -> None:
        """Distance pair `main:expr:17_main:expr:45` → 1 element with the raw pair ref."""
        ref = "main:expr:17_main:expr:45"
        item = MeasurementItem(reference=ref, value=2.5, error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="length_unit", check_parameter="distance"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == [ref]

    def test_mixed_inner_keys_still_emitted(self) -> None:
        """Mixed inner keys → element still emitted (bcf_output drops it)."""
        ref = "inter:intersection_gen:cube_main:expr:5"
        item = MeasurementItem(reference=ref, value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == [ref]

    def test_gen_direct_still_emitted(self) -> None:
        """`gen:...` direct → element still emitted (comparison is IFC-agnostic)."""
        item = MeasurementItem(reference="gen:mycube", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["gen:mycube"]

    def test_malformed_bare_string_still_emitted(self) -> None:
        """Malformed/bare string → element still emitted."""
        item = MeasurementItem(reference="not_a_valid_ref", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["not_a_valid_ref"]

    def test_cross_model_pair_carried_raw(self) -> None:
        """Cross-model pair → 1 element with the raw pair ref."""
        ref = "modelA:expr:1_modelB:expr:2"
        item = MeasurementItem(reference=ref, value=3.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == [ref]

    def test_slug_with_underscore_and_digits(self) -> None:
        """Slug containing `_` and/or digits → carried through unchanged."""
        item = MeasurementItem(reference="main:expr:99", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["main:expr:99"]

    def test_slug_starting_with_inter(self) -> None:
        """Model slug starting with 'inter' (e.g., 'interface') → unchanged."""
        item = MeasurementItem(reference="interface:expr:42", value=1.5, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["interface:expr:42"]

    def test_slug_starting_with_gen(self) -> None:
        """Model slug starting with 'gen' (e.g., 'generated') → unchanged."""
        item = MeasurementItem(reference="generated:expr:17", value=2.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["generated:expr:17"]

    def test_collision_reverse_pair_no_dedup(self) -> None:
        """Collision pairs in both orders → no dedup, 2 elements, one raw ref each."""
        ref1 = "inter:intersection_main:expr:170_main:expr:766"
        ref2 = "inter:intersection_main:expr:766_main:expr:170"
        item1 = MeasurementItem(reference=ref1, value=0.32, error=None)
        item2 = MeasurementItem(reference=ref2, value=0.32, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item1, item2], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 2
        assert result.elements[0].express_ids == [ref1]
        assert result.elements[1].express_ids == [ref2]
        assert result.summary_element_count == 2


class TestMissingAndNonFinite:
    """Test missing values and non-finite values (NaN, inf)."""

    def test_value_none_no_error_missing(self) -> None:
        """`value=None` (no `error`) → `missing=True`, `failed=True`, topic emitted."""
        item = MeasurementItem(reference="main:expr:1", value=None, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True
        assert result.summary_failed_count == 1

    def test_error_set_missing(self) -> None:
        """`error` set → `missing=True`, `failed=True`."""
        item = MeasurementItem(
            reference="main:expr:1", value=None, error="no cached geometry"
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_nan_missing(self) -> None:
        """`NaN` → `missing=True`, `failed=True`."""
        item = MeasurementItem(reference="main:expr:1", value=float("nan"), error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_plus_inf_missing(self) -> None:
        """`+inf` → `missing=True`, `failed=True`."""
        item = MeasurementItem(reference="main:expr:1", value=float("inf"), error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=100.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_minus_inf_missing(self) -> None:
        """`-inf` → `missing=True`, `failed=True`."""
        item = MeasurementItem(reference="main:expr:1", value=float("-inf"), error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_value_none_on_unresolvable_ref_emitted(self) -> None:
        """`value=None` on unresolvable ref → element still emitted, missing."""
        item = MeasurementItem(reference="gen:missing", value=None, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["gen:missing"]
        assert result.elements[0].checks[0].missing is True


class TestConditionsAndInclusivity:
    """Test all conditions and inclusive_min/max flags."""

    def test_equals_boundary(self) -> None:
        """`equals` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="equals", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True
        assert result.elements[0].failed is False

    def test_not_equals_boundary(self) -> None:
        """`not_equals` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="not_equals", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False
        assert result.elements[0].failed is True

    def test_lt_boundary(self) -> None:
        """`lt` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_le_boundary(self) -> None:
        """`le` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_gt_boundary(self) -> None:
        """`gt` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_ge_boundary(self) -> None:
        """`ge` at boundary value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="ge", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_between_inclusive_min_max(self) -> None:
        """`between` with `inclusive_min=True`, `inclusive_max=True`."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(
                condition="between",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=True,
                inclusive_max=True,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_between_exclusive_min(self) -> None:
        """`between` with `inclusive_min=False`."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(
                condition="between",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=False,
                inclusive_max=True,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_between_exclusive_max(self) -> None:
        """`between` with `inclusive_max=False`."""
        item = MeasurementItem(reference="main:expr:1", value=10.0, error=None)
        result = _run(
            ComparisonSettings(
                condition="between",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=True,
                inclusive_max=False,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_outside_inclusive(self) -> None:
        """`outside` with inclusive boundaries."""
        item = MeasurementItem(reference="main:expr:1", value=3.0, error=None)
        result = _run(
            ComparisonSettings(
                condition="outside",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=True,
                inclusive_max=True,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_float_noise_equals(self) -> None:
        """Float-noise `equals` (e.g., `0.30000000000000004`)."""
        item = MeasurementItem(
            reference="main:expr:1", value=0.30000000000000004, error=None
        )
        result = _run(
            ComparisonSettings(condition="equals", target_value=0.3),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_float_noise_equals_live_workflow(self) -> None:
        """Live workflow float noise: 0.3199999928 vs 0.32 should pass equals."""
        item = MeasurementItem(
            reference="main:expr:1", value=0.3199999928474426, error=None
        )
        result = _run(
            ComparisonSettings(condition="equals", target_value=0.32),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True


class TestStructureAndSummary:
    """Test result structure and summaries."""

    def test_empty_values(self) -> None:
        """Empty `values` → empty elements, all counts 0."""
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(values=[], unit="volume_unit", check_parameter="volume"),
        )
        assert result.elements == []
        assert result.summary_element_count == 0
        assert result.summary_passed_count == 0
        assert result.summary_failed_count == 0
        assert result.summary_check_count == 0

    def test_no_dedup_duplicates(self) -> None:
        """No dedup → every MeasurementItem becomes its own element."""
        item1 = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        item2 = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item1, item2], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert len(result.elements) == 2
        assert result.summary_element_count == 2

    def test_all_pass(self) -> None:
        """All-pass → `failed_express_ids` empty."""
        item = MeasurementItem(reference="main:expr:1", value=10.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.failed_express_ids == []
        assert result.summary_failed_count == 0

    def test_summaries_correct(self) -> None:
        """Summaries + passed/failed ids correct (one raw ref per element)."""
        item_pass = MeasurementItem(reference="main:expr:1", value=10.0, error=None)
        item_fail = MeasurementItem(reference="main:expr:2", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item_pass, item_fail],
                unit="volume_unit",
                check_parameter="volume",
            ),
        )
        assert result.summary_element_count == 2
        assert result.summary_passed_count == 1
        assert result.summary_failed_count == 1
        assert result.summary_check_count == 2
        assert result.passed_express_ids == ["main:expr:1"]
        assert result.failed_express_ids == ["main:expr:2"]


class TestValidations:
    """Test input validations."""

    def test_empty_check_parameter(self) -> None:
        """Empty `check_parameter` → `ValueError`."""
        item = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        with pytest.raises(ValueError, match="check_parameter must be non-empty"):
            _run(
                ComparisonSettings(condition="gt", target_value=0.0),
                ComparisonInputs(values=[item], unit="volume_unit", check_parameter=""),
            )

    def test_target_min_greater_than_target_max(self) -> None:
        """`target_min > target_max` for `between` → `ValueError`."""
        item = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        with pytest.raises(ValueError, match=r"target_min.*must be <= target_max"):
            _run(
                ComparisonSettings(
                    condition="between",
                    target_min=10.0,
                    target_max=5.0,
                ),
                ComparisonInputs(
                    values=[item], unit="volume_unit", check_parameter="volume"
                ),
            )

    def test_target_min_greater_than_target_max_outside(self) -> None:
        """`target_min > target_max` for `outside` → `ValueError`."""
        item = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        with pytest.raises(ValueError, match=r"target_min.*must be <= target_max"):
            _run(
                ComparisonSettings(
                    condition="outside",
                    target_min=10.0,
                    target_max=5.0,
                ),
                ComparisonInputs(
                    values=[item], unit="volume_unit", check_parameter="volume"
                ),
            )


class TestTolerance:
    """Test configurable absolute tolerance (abs_tol)."""

    def test_le_near_boundary_absorbed_by_tolerance(self) -> None:
        """`le` with value slightly above target (within tolerance) should pass."""
        item = MeasurementItem(reference="main:expr:1", value=5.0008, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_le_beyond_tolerance_fails(self) -> None:
        """`le` with value above target beyond tolerance should fail."""
        item = MeasurementItem(reference="main:expr:1", value=5.002, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_ge_near_boundary_absorbed_by_tolerance(self) -> None:
        """`ge` with value slightly below target (within tolerance) should pass."""
        item = MeasurementItem(reference="main:expr:1", value=4.9992, error=None)
        result = _run(
            ComparisonSettings(condition="ge", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_ge_beyond_tolerance_fails(self) -> None:
        """`ge` with value below target beyond tolerance should fail."""
        item = MeasurementItem(reference="main:expr:1", value=4.998, error=None)
        result = _run(
            ComparisonSettings(condition="ge", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_between_inclusive_absorbed_by_tolerance(self) -> None:
        """`between` with inclusive boundaries: values just outside are absorbed."""
        item = MeasurementItem(reference="main:expr:1", value=4.9992, error=None)
        result = _run(
            ComparisonSettings(
                condition="between",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=True,
                inclusive_max=True,
                abs_tol=0.001,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_between_exclusive_stays_exact(self) -> None:
        """`between` with exclusive boundaries: tolerance does not absorb."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(
                condition="between",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=False,
                inclusive_max=True,
                abs_tol=0.001,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_outside_inclusive_absorbed_by_tolerance(self) -> None:
        """`outside` with inclusive boundaries: tolerance expands the range."""
        item = MeasurementItem(reference="main:expr:1", value=5.0005, error=None)
        result = _run(
            ComparisonSettings(
                condition="outside",
                target_min=5.0,
                target_max=10.0,
                inclusive_min=True,
                inclusive_max=True,
                abs_tol=0.001,
            ),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_lt_unaffected_by_tolerance(self) -> None:
        """`lt` is strict: tolerance does not apply."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_gt_unaffected_by_tolerance(self) -> None:
        """`gt` is strict: tolerance does not apply."""
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is False

    def test_negative_abs_tol_normalized(self) -> None:
        """Negative abs_tol is normalized to absolute value."""
        item = MeasurementItem(reference="main:expr:1", value=5.0008, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0, abs_tol=-0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_custom_abs_tol(self) -> None:
        """Custom abs_tol value is respected."""
        item = MeasurementItem(reference="main:expr:1", value=5.005, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0, abs_tol=0.01),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result.elements[0].checks[0].passed is True

    def test_equals_with_custom_abs_tol(self) -> None:
        """equals uses math.isclose with custom abs_tol."""
        item = MeasurementItem(reference="main:expr:1", value=5.005, error=None)
        result_default = _run(
            ComparisonSettings(condition="equals", target_value=5.0, abs_tol=0.001),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result_default.elements[0].checks[0].passed is False

        result_custom = _run(
            ComparisonSettings(condition="equals", target_value=5.0, abs_tol=0.01),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
        )
        assert result_custom.elements[0].checks[0].passed is True
