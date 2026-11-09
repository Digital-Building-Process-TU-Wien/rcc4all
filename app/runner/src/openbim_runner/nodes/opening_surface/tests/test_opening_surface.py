from __future__ import annotations

import asyncio
import math
from collections.abc import Iterator
from typing import Any, cast

import ifcopenshell
import numpy as np
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


def _add_host_mesh(
    context: ExecutionContext, host: _FakeHost, mesh: trimesh.Trimesh
) -> None:
    cache_mesh(context, mesh, express_id=host.id())


# --- host-parallelity helpers ----------------------------------------------------

_ALIGNED_COS = math.cos(math.pi / 180.0)
_PLANE_TOLERANCE = 0.01
_OPPOSING_COS = -math.cos(math.radians(10.0))


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _group_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(0.5 * np.linalg.norm(cross, axis=1).sum())


def _planar_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    first_points = vertices[faces[:, 0]]
    assigned = np.zeros(len(faces), dtype=bool)
    groups: list[list[int]] = []
    for seed in range(len(faces)):
        if assigned[seed]:
            continue
        normal = normals[seed]
        offsets = (first_points - first_points[seed]) @ normal
        same = (
            (normals @ normal >= _ALIGNED_COS)
            & (np.abs(offsets) <= _PLANE_TOLERANCE)
            & ~assigned
        )
        same[seed] = True
        assigned |= same
        groups.append(np.flatnonzero(same).tolist())
    return groups


def _significant_host_normals(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    """Normals of the host's largest planar faces (its actual surface planes)."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = _face_normals(vertices, faces)
    sized = [
        (group, _group_area(vertices, faces, group))
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [(group, area) for group, area in sized if area > 0.0]
    if not sized:
        return []
    max_area = max(area for _group, area in sized)
    return [normals[group[0]] for group, area in sized if area >= 0.2 * max_area]


def _opening_cap_normal(mesh: trimesh.Trimesh) -> np.ndarray:
    """Normal of the largest planar face of a retrieved opening surface mesh."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = _face_normals(vertices, faces)
    groups = _planar_groups(vertices, faces, normals)
    largest = max(groups, key=lambda group: _group_area(vertices, faces, group))
    return normals[largest[0]]


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


def test_oversized_opening_is_clipped_to_host_planes() -> None:
    context = _context()
    # Wall: the two dominant opposing faces are the ±Z faces (thickness 0.4).
    host = _FakeHost(20, [])
    _add_entity(context, host)
    _add_host_mesh(context, host, _box([2.0, 2.0, 0.4]))
    # Opening prism crosses the wall along Z but extends far beyond it, so its
    # largest faces (±X/±Y, 0.6 each) are perpendicular to the wall surface.
    opening = _FakeOpening(21)
    _add_entity(context, _FakeHost(20, [opening]))
    _add_opening(context, opening, _box([0.3, 0.3, 2.0]))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(20)]), context)

    assert result.opening_count == 1
    opening_result = result.openings[0]
    assert opening_result.error is None
    # The true hole is the ±Z cross-section, not the large perpendicular faces.
    assert opening_result.area == pytest.approx(0.09, rel=1e-2)
    assert opening_result.depth == pytest.approx(0.4, rel=1e-2)
    assert opening_result.geometry_key is not None
    cap_mesh = resolve_mesh(context, opening_result.geometry_key)
    assert cap_mesh.bounds[0][2] == pytest.approx(-0.2, abs=1e-3)
    assert cap_mesh.bounds[1][2] == pytest.approx(0.2, abs=1e-3)


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

    # Oversized cutter that extends beyond the wall: its surface must be the
    # host-parallel hole (0.30 x 0.30) within the wall thickness, not the large
    # perpendicular faces of the raw element.
    entries = {
        opening.express_id.split(":")[-1]: opening for opening in real_result.openings
    }
    oversized = entries["2555"]
    assert oversized.area == pytest.approx(0.09, rel=0.01)
    assert oversized.depth == pytest.approx(0.47, rel=0.01)
    assert oversized.width == pytest.approx(0.30, rel=0.01)
    assert oversized.height == pytest.approx(0.30, rel=0.01)


def test_wall_opening_models_produce_host_parallel_caps() -> None:
    expected: dict[str, dict[str, Any]] = {
        "Testmodel-WallOpenings.ifc": {
            "count": 10,
            "areas": {"4188": 1.35, "4196": 1.7952},
        },
        "Testmodel-WallOpenings-Complex.ifc": {
            "count": 22,
            "areas": {"6303": 1.9404, "8059": 1.8415},
        },
    }
    for model_file, meta in expected.items():
        model = ifcopenshell.open(str(MODELS_ROOT / "specific" / model_file))
        context = ExecutionContext(
            ifc_model=cast(Any, model),
            node_outputs={},
            geometry_cache=build_geometry_cache(model),
        )
        refs = [f"main:expr:{entity.id()}" for entity in model.by_type("IfcWall")]
        result = _run(OpeningSurfaceInputs(express_ids=refs), context)
        assert result.opening_count == meta["count"]

        entries = {
            opening.express_id.split(":")[-1]: opening for opening in result.openings
        }
        for opening in result.openings:
            assert opening.error is None
            assert opening.geometry_key is not None
            host_id = opening.host_express_id.split(":")[-1]
            host_mesh = resolve_mesh(context, f"main:expr:{host_id}")
            host_normals = _significant_host_normals(host_mesh)
            assert host_normals
            cap_normal = _opening_cap_normal(
                resolve_mesh(context, opening.geometry_key)
            )
            parallel = max(abs(float(cap_normal @ normal)) for normal in host_normals)
            assert parallel >= 0.98

        for opening_id, area in meta["areas"].items():
            assert entries[opening_id].area == pytest.approx(area, rel=0.02)


def test_roof_openings_are_host_parallel_and_clipped_to_roof_thickness(
    real_context: ExecutionContext, real_result: OpeningSurfaceResult
) -> None:
    """Roof openings lie in the plane of their pitch and are clipped to its slab.

    The sloped roof (express 655) is ~0.35 units thick but is voided by cutters
    that are ~0.52 deep. Every roof opening must therefore be clipped to the
    pitch slab: its cap faces are host-parallel to one of the roof's significant
    surface planes and its depth equals the roof thickness, not the raw cutter
    length.
    """
    roof_openings = [
        opening
        for opening in real_result.openings
        if opening.host_express_id.endswith(":655")
    ]
    assert len(roof_openings) == 5

    for opening in roof_openings:
        assert opening.error is None
        assert opening.geometry_key is not None
        assert opening.area is not None and opening.area > 0
        assert opening.depth == pytest.approx(0.35, rel=0.01)

        host_mesh = resolve_mesh(real_context, opening.host_express_id)
        host_normals = _significant_host_normals(host_mesh)
        assert host_normals
        cap_normal = _opening_cap_normal(
            resolve_mesh(real_context, opening.geometry_key)
        )
        parallel = max(abs(float(cap_normal @ normal)) for normal in host_normals)
        assert parallel >= 0.98

    entries = {opening.express_id.split(":")[-1]: opening for opening in roof_openings}
    # The oversized cutters are clipped, so their area no longer reports the large
    # unclipped cap of the raw cutting solid.
    assert entries["667"].area == pytest.approx(1.8455, rel=0.01)
    assert entries["679"].area == pytest.approx(7.9971, rel=0.01)
    assert entries["817"].area == pytest.approx(2.8209, rel=0.01)


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
