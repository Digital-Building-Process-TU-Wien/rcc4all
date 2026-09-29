from __future__ import annotations

from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.comparison.comparison import (
    ComparisonInputs,
    ComparisonResult,
    ComparisonSettings,
    comparison,
)
from openbim_runner.nodes.measurement.measurement import MeasurementItem


class _MockEntity:
    """Mock IFC entity for testing."""

    def is_a(self) -> str:
        return "IFCWALL"


class _MockModel:
    """Mock IFC model for testing."""

    def by_id(self, express_id: int) -> _MockEntity:
        return _MockEntity()


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, _MockModel()), node_outputs={})


def _run(
    settings: ComparisonSettings, inputs: ComparisonInputs, context: ExecutionContext
) -> ComparisonResult:
    import asyncio

    return asyncio.run(comparison(settings, inputs, context))


class TestReferenceResolution:
    """Test reference resolution for direct expr refs, collision intersections, and distance pairs."""

    def test_direct_expr_ref_single_element(self) -> None:
        """Direct `<slug>:expr:<id>` → 1 element, unchanged reference."""
        context = _context()
        item = MeasurementItem(reference="main:expr:42", value=1.5, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["main:expr:42"]
        assert result.elements[0].class_name == "IFCWALL"

    def test_collision_intersection_two_elements(self) -> None:
        """Collision `inter:intersection_main:expr:1_main:expr:2` → 1 element with both ids."""
        context = _context()
        item = MeasurementItem(
            reference="inter:intersection_main:expr:1_main:expr:2",
            value=0.5,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert set(result.elements[0].express_ids) == {"main:expr:1", "main:expr:2"}

    def test_distance_pair_two_elements(self) -> None:
        """Distance pair `main:expr:17_main:expr:45` → 1 element with both ids."""
        context = _context()
        item = MeasurementItem(
            reference="main:expr:17_main:expr:45",
            value=2.5,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="lt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="length_unit", check_parameter="distance"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert set(result.elements[0].express_ids) == {"main:expr:17", "main:expr:45"}

    def test_mixed_inner_keys_skipped(self) -> None:
        """Mixed inner keys (`inter:intersection_gen:cube_main:expr:5`) → skipped."""
        context = _context()
        item = MeasurementItem(
            reference="inter:intersection_gen:cube_main:expr:5",
            value=1.0,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 0

    def test_gen_direct_skipped(self) -> None:
        """`gen:...` direct → skipped."""
        context = _context()
        item = MeasurementItem(reference="gen:mycube", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 0

    def test_malformed_bare_string_skipped(self) -> None:
        """Malformed/bare string → skipped."""
        context = _context()
        item = MeasurementItem(reference="not_a_valid_ref", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 0

    def test_cross_model_pair(self) -> None:
        """Cross-model pair (`modelA:expr:1_modelB:expr:2`) → 1 element with both ids."""
        context = _context()
        item = MeasurementItem(
            reference="main:expr:1_main:expr:2",
            value=3.0,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert set(result.elements[0].express_ids) == {"main:expr:1", "main:expr:2"}

    def test_slug_with_underscore_and_digits(self) -> None:
        """Slug containing `_` and/or digits → parser handles correctly."""
        context = _context()
        item = MeasurementItem(
            reference="main:expr:99",
            value=1.0,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["main:expr:99"]

    def test_slug_starting_with_inter(self) -> None:
        """Model slug starting with 'inter' (e.g., 'interface') → resolved correctly."""
        context = _context()
        item = MeasurementItem(
            reference="interface:expr:42",
            value=1.5,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["interface:expr:42"]

    def test_slug_starting_with_gen(self) -> None:
        """Model slug starting with 'gen' (e.g., 'generated') → resolved correctly."""
        context = _context()
        item = MeasurementItem(
            reference="generated:expr:17",
            value=2.0,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].express_ids == ["generated:expr:17"]

    def test_collision_reverse_pair_dedup(self) -> None:
        """Collision pairs in both orders (170↔766 and 766↔170) → dedup to 1 element."""
        context = _context()
        # Simulate collision output: both directions of the same pair
        item1 = MeasurementItem(
            reference="inter:intersection_main:expr:170_main:expr:766",
            value=0.32,
            error=None,
        )
        item2 = MeasurementItem(
            reference="inter:intersection_main:expr:766_main:expr:170",
            value=0.32,
            error=None,
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item1, item2], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        # Should dedup to a single element with both ids
        assert len(result.elements) == 1
        assert set(result.elements[0].express_ids) == {"main:expr:170", "main:expr:766"}
        assert result.summary_element_count == 1


class TestMissingAndNonFinite:
    """Test missing values and non-finite values (NaN, inf)."""

    def test_value_none_no_error_missing(self) -> None:
        """`value=None` (no `error`) → `missing=True`, `failed=True`, topic emitted."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=None, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True
        assert result.summary_failed_count == 1

    def test_error_set_missing(self) -> None:
        """`error` set → `missing=True`, `failed=True`."""
        context = _context()
        item = MeasurementItem(
            reference="main:expr:1",
            value=None,
            error="no cached geometry",
        )
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_nan_missing(self) -> None:
        """**`NaN`** → `missing=True`, `failed=True`."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=float("nan"), error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_plus_inf_missing(self) -> None:
        """**`+inf`** → `missing=True`, `failed=True`."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=float("inf"), error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=100.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_minus_inf_missing(self) -> None:
        """**`-inf`** → `missing=True`, `failed=True`."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=float("-inf"), error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.elements[0].checks[0].missing is True
        assert result.elements[0].failed is True

    def test_value_none_unresolvable_ref_dropped(self) -> None:
        """`value=None` on unresolvable ref → dropped (no element emitted)."""
        context = _context()
        item = MeasurementItem(reference="gen:missing", value=None, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 0


class TestConditionsAndInclusivity:
    """Test all conditions and inclusive_min/max flags."""

    def test_equals_boundary(self) -> None:
        """`equals` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="equals", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is True
        assert result.elements[0].failed is False

    def test_not_equals_boundary(self) -> None:
        """`not_equals` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="not_equals", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is False
        assert result.elements[0].failed is True

    def test_lt_boundary(self) -> None:
        """`lt` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="lt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is False

    def test_le_boundary(self) -> None:
        """`le` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="le", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is True

    def test_gt_boundary(self) -> None:
        """`gt` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is False

    def test_ge_boundary(self) -> None:
        """`ge` at boundary value."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=5.0, error=None)
        result = _run(
            ComparisonSettings(condition="ge", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is True

    def test_between_inclusive_min_max(self) -> None:
        """`between` with `inclusive_min=True`, `inclusive_max=True`."""
        context = _context()
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
            context,
        )
        assert result.elements[0].checks[0].passed is True

    def test_between_exclusive_min(self) -> None:
        """`between` with `inclusive_min=False`."""
        context = _context()
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
            context,
        )
        assert result.elements[0].checks[0].passed is False

    def test_between_exclusive_max(self) -> None:
        """`between` with `inclusive_max=False`."""
        context = _context()
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
            context,
        )
        assert result.elements[0].checks[0].passed is False

    def test_outside_inclusive(self) -> None:
        """`outside` with inclusive boundaries."""
        context = _context()
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
            context,
        )
        assert result.elements[0].checks[0].passed is True

    def test_float_noise_equals(self) -> None:
        """Float-noise `equals` (e.g., `0.30000000000000004`)."""
        context = _context()
        item = MeasurementItem(
            reference="main:expr:1", value=0.30000000000000004, error=None
        )
        result = _run(
            ComparisonSettings(condition="equals", target_value=0.3),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.elements[0].checks[0].passed is True


class TestStructureAndSummary:
    """Test result structure, summaries, and dedup."""

    def test_empty_values(self) -> None:
        """Empty `values` → empty elements, all counts 0."""
        context = _context()
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(values=[], unit="volume_unit", check_parameter="volume"),
            context,
        )
        assert result.elements == []
        assert result.summary_element_count == 0
        assert result.summary_passed_count == 0
        assert result.summary_failed_count == 0
        assert result.summary_check_count == 0

    def test_dedup_duplicates(self) -> None:
        """**Dedup duplicates** → single element per unique `(ref, check)`."""
        context = _context()
        # Same reference twice
        item1 = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        item2 = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=0.0),
            ComparisonInputs(
                values=[item1, item2], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert len(result.elements) == 1
        assert result.summary_element_count == 1

    def test_all_pass(self) -> None:
        """All-pass → `failed_express_ids` empty."""
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=10.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item], unit="volume_unit", check_parameter="volume"
            ),
            context,
        )
        assert result.failed_express_ids == []
        assert result.summary_failed_count == 0

    def test_summaries_correct(self) -> None:
        """Summaries + passed/failed ids correct."""
        context = _context()
        item_pass = MeasurementItem(reference="main:expr:1", value=10.0, error=None)
        item_fail = MeasurementItem(reference="main:expr:2", value=1.0, error=None)
        result = _run(
            ComparisonSettings(condition="gt", target_value=5.0),
            ComparisonInputs(
                values=[item_pass, item_fail],
                unit="volume_unit",
                check_parameter="volume",
            ),
            context,
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
        context = _context()
        item = MeasurementItem(reference="main:expr:1", value=1.0, error=None)
        with pytest.raises(ValueError, match="check_parameter must be non-empty"):
            _run(
                ComparisonSettings(condition="gt", target_value=0.0),
                ComparisonInputs(values=[item], unit="volume_unit", check_parameter=""),
                context,
            )

    def test_target_min_greater_than_target_max(self) -> None:
        """`target_min > target_max` for `between` → `ValueError`."""
        context = _context()
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
                context,
            )

    def test_target_min_greater_than_target_max_outside(self) -> None:
        """`target_min > target_max` for `outside` → `ValueError`."""
        context = _context()
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
                context,
            )
