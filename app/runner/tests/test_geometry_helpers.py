from __future__ import annotations

import sys
from typing import Any

import fcl
import pytest
import trimesh

from rcc4all_runner.util.geometry import fcl_surface_distance


def _box(translation: list[float]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=[2.0, 2.0, 2.0])
    mesh.apply_translation(translation)
    return mesh


def test_fcl_surface_distance_import_failure_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing FCL backend degrades to None silently (no stderr noise)."""
    monkeypatch.setitem(sys.modules, "fcl", None)

    assert fcl_surface_distance(_box([0, 0, 0]), _box([5, 0, 0])) is None
    assert capsys.readouterr().err == ""


def test_fcl_surface_distance_query_exception_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A query-time exception is swallowed to None and logged to stderr."""

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("fcl query backend exploded")

    monkeypatch.setattr(fcl, "CollisionObject", _raise)

    assert fcl_surface_distance(_box([0, 0, 0]), _box([5, 0, 0])) is None
    captured = capsys.readouterr()
    assert "FCL surface distance failed" in captured.err
    assert "RuntimeError" in captured.err


def test_fcl_surface_distance_non_finite_distance_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-finite solver result is rejected instead of returned."""
    monkeypatch.setattr(fcl, "distance", lambda *_args: float("nan"))

    assert fcl_surface_distance(_box([0, 0, 0]), _box([5, 0, 0])) is None
    captured = capsys.readouterr()
    assert "non-finite" in captured.err
