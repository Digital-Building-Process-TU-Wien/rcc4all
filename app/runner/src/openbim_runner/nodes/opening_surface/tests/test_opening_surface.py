from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any, cast

import ifcopenshell
import pytest
import trimesh

from conftest import main_ref as _ref
from openbim_runner.inspect_models import MODELS_ROOT
from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.opening_surface.opening_surface import (
    OpeningSurfaceInputs,
    OpeningSurfaceResult,
    opening_surface,
)
from openbim_runner.util.geometry import build_geometry_cache, cache_mesh, resolve_mesh

_REAL_MODEL = MODELS_ROOT / "specific" / "Testmodell-LightExposureSmall.ifc"


# --- fakes ----------------------------------------------------------------------


class _FakeOpening:
    def __init__(self, express_id: int, guid: str = "") -> None:
        self._id = express_id
        self.GlobalId = guid

    def id(self) -> int:
        return self._id


class _FakeVoidsRelationship:
    def __init__(self, opening: _FakeOpening) -> None:
        self.RelatedOpeningElement = opening


class _FakeHost:
    def __init__(self, express_id: int, openings: list[_FakeOpening]) -> None:
        self._id = express_id
        self.HasOpenings = [_FakeVoidsRelationship(opening) for opening in openings]

    def id(self) -> int:
        return self._id


class _FakeModel:
    def __init__(self) -> None:
        self._entities: dict[int, Any] = {}

    def by_id(self, express_id: int) -> Any:
        entity = self._entities.get(express_id)
        if entity is None:
            raise RuntimeError(f"No entity for {express_id}")
        return entity


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, _FakeModel()), node_outputs={})


def _add_entity(context: ExecutionContext, entity: Any) -> None:
    cast(Any, context.ifc_model)._entities[entity.id()] = entity


def _add_opening(
    context: ExecutionContext, opening: _FakeOpening, mesh: trimesh.Trimesh
) -> None:
    cache_mesh(context, mesh, express_id=opening.id())
    _add_entity(context, opening)


def _box(extents: list[float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=extents)


def _run(
    inputs: OpeningSurfaceInputs, context: ExecutionContext
) -> OpeningSurfaceResult:
    return asyncio.run(opening_surface(inputs, context))


# --- cap-face retrieval ---------------------------------------------------------


def test_wall_opening_retrieves_both_cap_faces() -> None:
    context = _context()
    opening = _FakeOpening(2, guid="0LhBByOR0VH8aBzIyEdt5G")
    _add_entity(context, _FakeHost(1, [opening]))
    _add_opening(context, opening, _box([1.0, 0.3, 1.4]))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(1)]), context)

    assert result.opening_count == 1
    assert result.surface_count == 1
    assert result.geometry_keys == ["gen:opening_surface_main_2"]
    opening = result.openings[0]
    assert opening.express_id == "main:expr:2"
    assert opening.guid == "0LhBByOR0VH8aBzIyEdt5G"
    assert opening.host_express_id == "main:expr:1"
    assert opening.error is None
    assert opening.area == pytest.approx(1.4)
    assert opening.width == pytest.approx(1.0)
    assert opening.height == pytest.approx(1.4)
    assert opening.depth == pytest.approx(0.3)
    # both cap faces are cached: the mesh area is twice the single cap area
    assert resolve_mesh(context, "gen:opening_surface_main_2").area == pytest.approx(
        2.8
    )


def test_horizontal_opening_uses_horizontal_axes() -> None:
    context = _context()
    opening = _FakeOpening(3)
    _add_entity(context, _FakeHost(2, [opening]))
    # flat box: the largest opposing surfaces are the ±Z faces (a skylight)
    _add_opening(context, opening, _box([1.2, 0.8, 0.3]))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(2)]), context)

    opening_result = result.openings[0]
    assert opening_result.area == pytest.approx(0.96)
    assert opening_result.width == pytest.approx(1.2)
    assert opening_result.height == pytest.approx(0.8)
    assert opening_result.depth == pytest.approx(0.3)


def test_opening_with_single_cap_face_has_no_depth() -> None:
    context = _context()
    box = _box([1.0, 0.3, 1.4])
    # drop one cap face: the remaining void exposes only one dominant flat face
    keep = box.face_normals[:, 1] > -0.9
    single_cap = trimesh.Trimesh(
        vertices=box.vertices, faces=box.faces[keep], process=False
    )
    opening = _FakeOpening(4)
    _add_entity(context, _FakeHost(3, [opening]))
    _add_opening(context, opening, single_cap)

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(3)]), context)

    opening_result = result.openings[0]
    assert opening_result.area == pytest.approx(1.4)
    assert opening_result.depth is None


# --- edge cases -----------------------------------------------------------------


def test_host_without_openings_contributes_nothing() -> None:
    context = _context()
    _add_entity(context, _FakeHost(10, []))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(10)]), context)

    assert result.opening_count == 0
    assert result.openings == []


def test_opening_without_cached_mesh_reports_error() -> None:
    context = _context()
    opening = _FakeOpening(11)
    _add_entity(context, _FakeHost(12, [opening]))
    _add_entity(context, opening)  # entity exists, but its geometry is not cached

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(12)]), context)

    assert result.opening_count == 1
    assert result.surface_count == 0
    opening_result = result.openings[0]
    assert opening_result.error == "no cached geometry"
    assert opening_result.geometry_key is None
    assert opening_result.area is None
    assert opening_result.depth is None


def test_repeated_host_emits_opening_once() -> None:
    context = _context()
    opening = _FakeOpening(13)
    _add_entity(context, _FakeHost(14, [opening]))
    _add_opening(context, opening, _box([1.0, 0.3, 1.4]))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(14), _ref(14)]), context)

    assert result.opening_count == 1
    assert result.geometry_keys == ["gen:opening_surface_main_13"]


def test_missing_host_entity_is_skipped() -> None:
    context = _context()

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(999)]), context)

    assert result.opening_count == 0


def test_bound_but_empty_runs_vacuously() -> None:
    context = _context()

    result = _run(OpeningSurfaceInputs(express_ids=[]), context)

    assert result.opening_count == 0
    assert result.surface_count == 0
    assert result.openings == []


def test_non_element_reference_raises() -> None:
    context = _context()

    with pytest.raises(ValueError, match="opening_surface requires"):
        _run(OpeningSurfaceInputs(express_ids=["gen:cube"]), context)


def test_unbound_express_ids_fails_validation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="express_ids"):
        OpeningSurfaceInputs.model_validate({})


# --- real model -------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_context() -> ExecutionContext:
    model = ifcopenshell.open(str(_REAL_MODEL))
    return ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
    )


@pytest.fixture(scope="module")
def real_result(real_context: ExecutionContext) -> OpeningSurfaceResult:
    model = cast(Any, real_context.ifc_model)
    host_refs = [
        f"main:expr:{entity.id()}"
        for entity_type in ("IfcWall", "IfcSlab", "IfcRoof")
        for entity in model.by_type(entity_type)
    ]
    return _run(OpeningSurfaceInputs(express_ids=host_refs), real_context)


def test_all_model_openings_are_retrieved(
    real_context: ExecutionContext, real_result: OpeningSurfaceResult
) -> None:
    assert real_result.opening_count == 17
    assert real_result.surface_count == 17
    assert len(real_result.geometry_keys) == 17

    for opening in real_result.openings:
        assert opening.error is None
        assert opening.geometry_key is not None
        assert opening.geometry_key.startswith("gen:opening_surface_main_")
        assert opening.area is not None and opening.area > 0
        assert opening.width is not None and opening.width > 0
        assert opening.height is not None and opening.height > 0
        assert opening.depth is not None and opening.depth > 0
        mesh = resolve_mesh(real_context, opening.geometry_key)
        assert len(mesh.faces) > 0


def _filled_windows(real_context: ExecutionContext) -> Iterator[tuple[Any, Any]]:
    """Yield (window entity, its opening entity) for every filled opening."""
    model = cast(Any, real_context.ifc_model)
    for relationship in model.by_type("IfcRelFillsElement"):
        yield relationship.RelatedBuildingElement, relationship.RelatingOpeningElement


def test_wall_window_opening_matches_window_overall_dimensions(
    real_context: ExecutionContext, real_result: OpeningSurfaceResult
) -> None:
    """Wall windows sit tightly in their void, so the caps equal the window size."""
    entries = {opening.express_id: opening for opening in real_result.openings}

    checked = 0
    for window, opening_entity in _filled_windows(real_context):
        host = opening_entity.VoidsElements[0].RelatingBuildingElement
        if not host.is_a("IfcWall"):
            continue
        width = getattr(window, "OverallWidth", None)
        height = getattr(window, "OverallHeight", None)
        entry = entries.get(f"main:expr:{opening_entity.id()}")
        if entry is None or entry.area is None or width is None or height is None:
            continue
        checked += 1
        assert entry.area == pytest.approx(width * height, rel=0.01)
        assert entry.width == pytest.approx(width, rel=0.01)
        assert entry.height == pytest.approx(height, rel=0.01)

    assert checked > 0
