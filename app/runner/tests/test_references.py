from __future__ import annotations

import pytest

from rcc4all_runner.util.references import (
    ElementRef,
    expand_reference,
    expr_key,
    guid_key,
    is_generated_key,
    is_geometry_key,
    split_guid_key,
    split_reference,
)


def test_round_trip_qualified_key() -> None:
    key = expr_key("main", 63)
    assert key == "main:expr:63"
    slug, kind, value = split_reference(key)
    assert (slug, kind, value) == ("main", "expr", 63)


def test_round_trip_generated_key() -> None:
    slug, kind, value = split_reference("gen:cube1")
    assert (slug, kind, value) == ("", "gen", "cube1")
    assert is_generated_key("gen:cube1") is True
    assert is_generated_key("main:expr:1") is False


def test_round_trip_guid_key() -> None:
    guid = "0xSWhGC9G5j9nhLzm6tcX$"
    key = guid_key("main", guid)
    assert key == f"main:guid:{guid}"
    assert split_guid_key(key) == ("main", guid)
    # split_reference never parses guid keys: they are identifiers, not geometry.
    with pytest.raises(ValueError, match="not a valid qualified reference"):
        split_reference(key)


def test_guid_key_rejects_colons() -> None:
    with pytest.raises(ValueError, match="cannot contain colons"):
        guid_key("main", "bad:guid")


def test_split_guid_key_rejects_non_guid_keys() -> None:
    assert split_guid_key("main:expr:5") is None
    assert split_guid_key("gen:abc") is None
    assert split_guid_key("main:guid:") is None


def test_malformed_references_raise() -> None:
    for bad in ("cube1", "265", "", ":expr:5", "inter:helper", "main:guid:Ab23"):
        with pytest.raises(ValueError, match="not a valid qualified reference"):
            split_reference(bad)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("main:expr:5", True),
        ("arch-1:expr:9", True),
        ("gen:cube1", True),
        ("inter:intersection_a_b", True),
        ("main:guid:Ab23x", False),
        ("cube1", False),
        ("", False),
    ],
)
def test_is_geometry_key(key: str, expected: bool) -> None:
    assert is_geometry_key(key) is expected


def test_expand_reference_direct_expr_key() -> None:
    refs = expand_reference("main:expr:63")
    assert refs == [ElementRef("main:expr:63", "main", 63)]


def test_expand_reference_direct_expr_key_with_underscore_slug() -> None:
    refs = expand_reference("second_model:expr:5")
    assert refs == [ElementRef("second_model:expr:5", "second_model", 5)]


def test_expand_reference_pair_with_underscore_slug() -> None:
    """Underscores are valid slug characters; the pair split must survive them.

    The former last-underscore split returned [] for this reference, so BCF
    normalization silently dropped the distance pair.
    """
    refs = expand_reference("main:expr:1_second_model:expr:2")
    assert refs == [
        ElementRef("main:expr:1", "main", 1),
        ElementRef("second_model:expr:2", "second_model", 2),
    ]


def test_expand_reference_pair_with_underscore_slug_first() -> None:
    refs = expand_reference("second_model:expr:1_main:expr:2")
    assert refs == [
        ElementRef("second_model:expr:1", "second_model", 1),
        ElementRef("main:expr:2", "main", 2),
    ]


def test_expand_reference_pair_with_underscore_slugs_on_both_sides() -> None:
    refs = expand_reference("model_a:expr:1_model_b:expr:2")
    assert refs == [
        ElementRef("model_a:expr:1", "model_a", 1),
        ElementRef("model_b:expr:2", "model_b", 2),
    ]


def test_expand_reference_intersection_pair_with_underscore_slug() -> None:
    refs = expand_reference("inter:intersection_main:expr:1_second_model:expr:2")
    assert refs == [
        ElementRef("main:expr:1", "main", 1),
        ElementRef("second_model:expr:2", "second_model", 2),
    ]


def test_expand_reference_pair_prefers_first_valid_split() -> None:
    """Digit-leading slugs stay ambiguous; the first valid split wins."""
    refs = expand_reference("a:expr:1_2_3:expr:4")
    assert refs == [
        ElementRef("a:expr:1", "a", 1),
        ElementRef("2_3:expr:4", "2_3", 4),
    ]


def test_expand_reference_drops_non_ifc_pairs() -> None:
    assert expand_reference("gen:cube1_gen:cube2") == []
    assert expand_reference("inter:helper") == []
    assert expand_reference("not-a-reference") == []
    assert expand_reference("") == []
