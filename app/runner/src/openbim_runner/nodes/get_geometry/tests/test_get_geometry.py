from __future__ import annotations

import asyncio
from typing import Any, cast

import ifcopenshell.geom
import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_geometry.get_geometry import (
    GetGeometryInputs,
    GetGeometryResult,
    GetGeometrySettings,
    get_geometry,
)


class FakeGeometry:
    def __init__(self, verts: tuple[float, ...], faces: tuple[int, ...]) -> None:
        self.verts = verts
        self.faces = faces


class FakeShape:
    def __init__(self, verts: tuple[float, ...], faces: tuple[int, ...]) -> None:
        self.geometry = FakeGeometry(verts, faces)


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def get(self, key: str) -> Any:
        return self.values.get(key)


UNIT_CUBE_VERTS = (
    0.0, 0.0, 0.0,
    1.0, 0.0, 0.0,
    1.0, 1.0, 0.0,
    0.0, 1.0, 0.0,
    0.0, 0.0, 1.0,
    1.0, 0.0, 1.0,
    1.0, 1.0, 1.0,
    0.0, 1.0, 1.0,
)
UNIT_CUBE_FACES = (
    4, 5, 6, 4, 6, 7,
    0, 3, 2, 0, 2, 1,
    0, 4, 7, 0, 7, 3,
    1, 2, 6, 1, 6, 5,
    3, 7, 6, 3, 6, 2,
    0, 1, 5, 0, 5, 4,
)


class FakeElement:
    def __init__(self, test_id: int) -> None:
        self._test_id = test_id


class FakeIfcModel:
    def __init__(self, *, failing_ids: set[int] | None = None) -> None:
        self.failing_ids = set() if failing_ids is None else failing_ids

    def by_id(self, express_id: int) -> Any:
        if express_id in self.failing_ids:
            raise RuntimeError("Unknown express ID")
        return FakeElement(test_id=express_id)


class FakeGeom:
    def __init__(self, *, empty_ids: set[int] | None = None) -> None:
        self.empty_ids = set() if empty_ids is None else empty_ids
        self.captured_settings: FakeSettings | None = None

    def settings(self) -> FakeSettings:
        s = FakeSettings()
        self.captured_settings = s
        return s

    def create_shape(self, settings: Any, element: Any) -> FakeShape:
        express_id: int = getattr(element, "_test_id", 0)
        if express_id in self.empty_ids:
            return FakeShape(verts=(), faces=())
        return FakeShape(verts=UNIT_CUBE_VERTS, faces=UNIT_CUBE_FACES)


def _patch_geom(monkeypatch: pytest.MonkeyPatch, fake: FakeGeom) -> None:
    monkeypatch.setattr(ifcopenshell.geom, "settings", fake.settings)
    monkeypatch.setattr(ifcopenshell.geom, "create_shape", fake.create_shape)


def _context(failing_ids: set[int] | None = None) -> ExecutionContext:
    return ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel(failing_ids=failing_ids)),
        node_outputs={},
    )


def test_get_geometry_happy_path_emits_handles_and_caches_meshes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGeom()
    _patch_geom(monkeypatch, fake)
    context = _context()

    result = asyncio.run(
        get_geometry(
            GetGeometrySettings(),
            GetGeometryInputs(express_ids=[1, 2]),
            context,
        )
    )

    assert isinstance(result, GetGeometryResult)
    assert len(result.geometries) == 2
    assert context.geometry_cache is not None
    for handle, express_id in zip(result.geometries, [1, 2], strict=True):
        assert handle.express_id == express_id
        assert handle.key in context.geometry_cache
        mesh = context.geometry_cache[handle.key]
        assert mesh.vertices.shape == (8, 3)
        assert mesh.faces.shape == (12, 3)


def test_get_geometry_skips_missing_element_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_geom(monkeypatch, FakeGeom())
    context = _context(failing_ids={99})

    result = asyncio.run(
        get_geometry(
            GetGeometrySettings(fail_on_missing=False),
            GetGeometryInputs(express_ids=[1, 99]),
            context,
        )
    )

    assert len(result.geometries) == 1
    assert result.geometries[0].express_id == 1


def test_get_geometry_raises_on_missing_element_when_fail_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_geom(monkeypatch, FakeGeom())
    context = _context(failing_ids={99})

    with pytest.raises(ValueError, match="express ID 99"):
        asyncio.run(
            get_geometry(
                GetGeometrySettings(fail_on_missing=True),
                GetGeometryInputs(express_ids=[99]),
                context,
            )
        )


def test_get_geometry_skips_empty_body_representation_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_geom(monkeypatch, FakeGeom(empty_ids={2}))
    context = _context()

    result = asyncio.run(
        get_geometry(
            GetGeometrySettings(fail_on_missing=False),
            GetGeometryInputs(express_ids=[1, 2]),
            context,
        )
    )

    assert len(result.geometries) == 1
    assert result.geometries[0].express_id == 1


def test_get_geometry_raises_on_empty_body_representation_when_fail_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_geom(monkeypatch, FakeGeom(empty_ids={2}))
    context = _context()

    with pytest.raises(ValueError, match="no body geometry representation"):
        asyncio.run(
            get_geometry(
                GetGeometrySettings(fail_on_missing=True),
                GetGeometryInputs(express_ids=[2]),
                context,
            )
        )


def test_get_geometry_sets_expected_geom_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGeom()
    _patch_geom(monkeypatch, fake)
    context = _context()

    asyncio.run(
        get_geometry(
            GetGeometrySettings(),
            GetGeometryInputs(express_ids=[1]),
            context,
        )
    )

    assert fake.captured_settings is not None
    assert fake.captured_settings.get("mesher-linear-deflection") is None
    assert fake.captured_settings.get("use-world-coords") is True
    assert fake.captured_settings.get("weld-vertices") is True
