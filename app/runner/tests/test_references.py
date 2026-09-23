from __future__ import annotations

import pytest

from openbim_runner.util.references import (
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
