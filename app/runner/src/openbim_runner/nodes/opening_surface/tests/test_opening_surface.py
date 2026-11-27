from __future__ import annotations

import asyncio
from typing import Any, cast

import ifcopenshell
import numpy as np
import pytest
import trimesh

from conftest import main_ref as _ref
from openbim_runner.inspect_models import MODELS_ROOT
from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.opening_surface._loft import (
    _loft_caps_watertight,  # pyright: ignore[reportPrivateUsage]
    _loft_open_ring,  # pyright: ignore[reportPrivateUsage]
    _loft_polygons,  # pyright: ignore[reportPrivateUsage]
    _rings_twisted,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.nodes.opening_surface._tube import (
    _build_ring_closed,  # pyright: ignore[reportPrivateUsage]
    _jogged_ring_groups,  # pyright: ignore[reportPrivateUsage]
    _ring_has_axial_edge,  # pyright: ignore[reportPrivateUsage]
)
from openbim_runner.nodes.opening_surface.opening_surface import (
    OpeningSurfaceInputs,
    OpeningSurfaceResult,
    opening_surface,
)
from openbim_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    build_geometry_cache,
    cache_mesh,
    resolve_mesh,
)

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


def _add_host_mesh(
    context: ExecutionContext, host: _FakeHost, mesh: trimesh.Trimesh
) -> None:
    cache_mesh(context, mesh, express_id=host.id())
    _add_entity(context, host)


def _box(extents: list[float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=extents)


def _host_with_bore(extents: list[float], bore: list[float]) -> trimesh.Trimesh:
    return trimesh.boolean.difference([_box(extents), _box(bore)])


def _run(
    inputs: OpeningSurfaceInputs, context: ExecutionContext
) -> OpeningSurfaceResult:
    return asyncio.run(opening_surface(inputs, context))


# --- pure loft helpers -----------------------------------------------------------


def test_loft_polygons_makes_a_watertight_solid() -> None:
    """Two offset rectangles loft into a closed, positive-volume prism."""
    a = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    b = a + 0.3

    mesh = _loft_polygons(a, b)

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(1.0 * 0.3, rel=1e-6)


def test_loft_polygons_resamples_different_vertex_counts() -> None:
    """Varying ring sizes (4 vs 5 points) still produce a watertight volume."""
    a = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    b = np.array(
        [
            [0.0, 0.0, 0.3],
            [1.1, 0.0, 0.3],
            [1.1, 0.9, 0.3],
            [0.4, 1.0, 0.3],
            [0.0, 1.0, 0.3],
        ],
        dtype=np.float64,
    )

    mesh = _loft_polygons(a, b)

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0


def test_loft_open_ring_from_single_cap_synthesizes_opposite_face() -> None:
    """A lone cap + a wall depth yields a watertight volume in the loft path."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    caps: list[list[int]] = [[0, 1]]
    cap_normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    mesh = _loft_open_ring(vertices, faces, caps, cap_normal, depth=0.3, tube=None)

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(1.0 * 0.3, rel=1e-6)


def _tri_set(
    vertices: np.ndarray, faces: np.ndarray
) -> set[tuple[tuple[float, float, float], ...]]:
    """The output mesh faces keyed by their (rounded) vertex coordinates."""
    result: set[tuple[tuple[float, float, float], ...]] = set()
    for tri in np.asarray(faces, int):
        rows = [[float(c) for c in row] for row in np.asarray(vertices[tri], float)]
        result.add(tuple(sorted((row[0], row[1], row[2]) for row in rows)))
    return result


def test_loft_two_caps_preserves_both_cap_faces() -> None:
    """Lofting two detected caps keeps their triangles; only side faces are new.

    Regression for the ``2_boiG``-style vertical opening: the previous loft
    rebuilt each cap by resampling its outer ring to a uniform arc length and
    re-triangulating it as a fan from the ring centroid, which moved the corner
    vertices and collapsed the cap outline. The two-cap branch must emit the
    detected cap triangles verbatim so the caps stay exactly as analysed.
    """
    # Two non-axis-aligned quad caps parallel to a plane with normal (0.767, 0.641, 0)
    # (the caps recovered from opening id 80997, host wall 80228 on the real model).
    front_corners = np.array(
        [
            [-7.669, 18.446, 2.36],
            [-7.669, 18.446, -0.22],
            [-6.386, 16.911, -0.22],
            [-6.386, 16.911, 2.36],
        ],
        dtype=np.float64,
    )
    back_corners = np.array(
        [
            [-7.957, 18.14, -0.22],
            [-7.957, 18.14, 2.31],
            [-6.738, 16.682, 2.31],
            [-6.738, 16.682, -0.22],
        ],
        dtype=np.float64,
    )
    vertices = np.concatenate([front_corners, back_corners], axis=0)
    # Each cap is a quad triangulated into two faces (vertices 0..3, 4..7).
    cap_faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]], dtype=np.int64)
    front = [0, 1]
    back = [2, 3]
    front_ring = [0, 1, 2, 3]
    back_ring = [4, 5, 6, 7]

    mesh = _loft_caps_watertight(
        vertices, cap_faces, front, back, front_ring, back_ring
    )

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0

    # The detected cap triangles must be present verbatim in the closed volume.
    expected_caps = _tri_set(vertices, cap_faces)
    actual = _tri_set(np.asarray(mesh.vertices, float), np.asarray(mesh.faces, int))
    assert expected_caps.issubset(actual)
    # And the caps are the only pre-existing faces: the volume adds side faces only,
    # so the cap triangles are preserved exactly (nothing resampled or re-fanned).
    assert len(mesh.faces) == len(cap_faces) + 2 * len(front_ring)

    # The solid is the prism between the two caps, so its volume must be the mean
    # cap area times the cap-plane separation. The two rings wind opposite ways
    # (the real ``2_boiG`` case); a cyclic shift alone cannot fix that and the side
    # band self-intersects, collapsing the signed volume — the orientation fix is
    # what restores this. Regression for the near-zero volumes on the real model.
    cap_normal = np.cross(
        front_corners[1] - front_corners[0], front_corners[2] - front_corners[0]
    )
    cap_normal = cap_normal / float(np.linalg.norm(cap_normal))

    def _tri_area(c0: np.ndarray, c1: np.ndarray, c2: np.ndarray) -> float:
        return float(0.5 * np.linalg.norm(np.cross(c1 - c0, c2 - c0)))

    def _quad_area(corners: np.ndarray) -> float:
        return _tri_area(corners[0], corners[1], corners[2]) + _tri_area(
            corners[0], corners[2], corners[3]
        )

    mean_cap_area = 0.5 * (_quad_area(front_corners) + _quad_area(back_corners))
    separation = float(
        (back_corners.mean(axis=0) - front_corners.mean(axis=0)) @ cap_normal
    )
    assert mesh.volume == pytest.approx(mean_cap_area * separation, rel=0.05)


def test_loft_unequal_rims_orients_before_resample() -> None:
    """Unequal-rim caps must still close into a solid with a real volume.

    Regression for the ``364362`` opening on the real model: the two caps are the
    same outline but tessellated to different boundary lengths (the front ring has
    4 corner vertices, the back ring has 6 with a mid-edge split). That makes
    ``_loft_caps_watertight`` fall into the resampling branch (``_loft_polygons``),
    which never re-oriented the rims. When the two boundary loops also wind
    opposite ways, the side band self-intersects and the signed volume cancels to
    ~0. The caps are re-triangulated here (they are not preserved verbatim), but
    the loft must still be a sound solid with a volume of mean-cap-area x depth.
    """
    front_corners = np.array(
        [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float64,
    )
    # Same outline, one midpoint per horizontal edge -> 6-point ring, opposite winding.
    back_corners = np.array(
        [
            [0.0, 0.0, 0.5],
            [1.0, 0.0, 0.5],
            [2.0, 0.0, 0.5],
            [2.0, 1.0, 0.5],
            [1.0, 1.0, 0.5],
            [0.0, 1.0, 0.5],
        ],
        dtype=np.float64,
    )
    vertices = np.concatenate([front_corners, back_corners], axis=0)
    cap_faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 5, 6],
            [4, 6, 7],
            [4, 7, 8],
            [4, 9, 8],
        ],
        dtype=np.int64,
    )
    front = [0, 1]
    back = [2, 3, 4, 5]
    front_ring = [0, 1, 2, 3]  # CCW
    back_ring = [4, 9, 8, 7, 6, 5]  # opposite winding

    mesh = _loft_caps_watertight(
        vertices, cap_faces, front, back, front_ring, back_ring
    )

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    # The two caps outline the same 2x1 rectangle, separated by 0.5 along the cap
    # normal, so the solid's volume is 2.0 * 0.5. The uncorrected loft returned ~0.
    assert mesh.volume == pytest.approx(1.0, rel=0.05)


def test_loft_equal_rims_mirror_slivers_loft_clean_prism() -> None:
    """Equal-length rims with mirrored bevel slivers loft into a clean prism.

    Regression for the real-world door ``3ndo_UUzohbPDx681yNH6S`` (``Tür-017``
    on wall ``Wand-003``): a rectangle authored as a 6-ring can carry its
    collinear bevel slivers on *different corners* in the two rims — mirror
    images no cyclic shift can pair. The direct bridge still closed watertight,
    but every side triangle was a long diagonal (a twisted band) and the volume
    was computed off that twisted solid. The in-plane mismatch is detected, the
    slivers collapsed, and the caps re-lofted as the true 4-corner rectangle.
    """
    # A 2x1 rectangle at z=0 whose two bevel slivers (0.03 stubs on the bottom
    # and top edge) sit by the bottom-right and top-left corners.
    front_corners = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.97, 0.0, 0.0],  # sliver, 0.03 before the right corner
            [2.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],
            [0.03, 1.0, 0.0],  # sliver, 0.03 after the left corner
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    # The same rectangle at z=0.5 with the slivers mirrored onto the other two
    # corners (bottom-left and top-right), as the real door's back rim has them.
    back_corners = np.array(
        [
            [0.0, 0.0, 0.5],
            [0.03, 0.0, 0.5],  # sliver, 0.03 after the left corner
            [2.0, 0.0, 0.5],
            [2.0, 1.0, 0.5],
            [1.97, 1.0, 0.5],  # sliver, 0.03 before the right corner
            [0.0, 1.0, 0.5],
        ],
        dtype=np.float64,
    )
    vertices = np.concatenate([front_corners, back_corners], axis=0)
    # Fans of the two 6-gon caps (the sliver fans carry one zero-area triangle,
    # as the authored degenerate caps do); the front faces give the cap normal.
    cap_faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 3, 4],
            [0, 4, 5],
            [6, 7, 8],
            [6, 8, 9],
            [6, 9, 10],
            [6, 10, 11],
        ],
        dtype=np.int64,
    )
    front = [0, 1, 2, 3]
    back = [4, 5, 6, 7]
    front_ring = list(range(6))
    back_ring = list(range(6, 12))
    cap_normal = np.array([0.0, 0.0, 1.0])

    # The detector itself: mirrored slivers cannot be paired, congruent rims can.
    assert _rings_twisted(front_corners, back_corners, cap_normal)
    clean_front = front_corners[[0, 2, 3, 5]]
    clean_back = back_corners[[0, 2, 3, 5]]
    assert not _rings_twisted(clean_front, clean_back, cap_normal)

    mesh = _loft_caps_watertight(
        vertices, cap_faces, front, back, front_ring, back_ring
    )

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    # The true void is the 4-corner rectangle prism: 2 x 1 area, 0.5 deep. The
    # twisted direct bridge (the previous behaviour) computes a different volume
    # off its diagonal side band.
    assert mesh.volume == pytest.approx(1.0, rel=0.05)
    # The clean path re-fans both caps from the collapsed 4-corner rings:
    # 2x4 cap triangles plus 2x4 side triangles. A direct bridge of the two
    # 6-rings would carry 20 faces.
    assert len(mesh.faces) == 16


def test_loft_equal_rims_benign_sliver_offset_keeps_direct_bridge() -> None:
    """Equal rims with a benign mispairing keep the direct bridge and cap faces.

    Regression for the real-world ``Tür-001`` doors (e.g.
    ``3texd0KTo1WTX$r2SeRJ02``): the two cap rims are the *same* rectangle,
    offset purely along the cap normal, but the collinear bevel slivers sit at
    different heights on the same edge. No cyclic shift pairs the vertices by
    height, so the twist detector fires — yet every mispaired vertex lies on the
    two parallel edge lines, so the direct bridge's side triangles stay in that
    plane and the solid is exact. Cleanup cannot recover congruent rings (one
    rim keeps an isolated collinear vertex with no short stub), so the rims must
    stay on the direct bridge with the detected cap faces verbatim; a resampling
    loft would push corners off the true rectangle and distort the volume
    (0.2240 -> 0.1709 on the real door).
    """
    # A 2x1 rectangle at z=0 with bevel slivers low on the left edge: the stub
    # pair (y=0.02/0.035) plus a single stub-below-the-corner vertex (y=0.97).
    front_ring_pts = np.array(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.97, 0.0],  # 0.03 stub below the corner
            [0.0, 0.035, 0.0],  # upper end of the stub pair
            [0.0, 0.02, 0.0],  # lower end of the stub pair
        ],
        dtype=np.float64,
    )
    # The same rectangle at z=0.5 with its slivers high on the left edge; the
    # isolated vertex at y=0.19 has no short stub (edges 0.71 and 0.19), so
    # cleanup keeps it and the ring stays a pentagon.
    back_ring_pts = np.array(
        [
            [0.0, 0.0, 0.5],
            [2.0, 0.0, 0.5],
            [2.0, 1.0, 0.5],
            [0.0, 1.0, 0.5],
            [0.0, 0.915, 0.5],  # upper end of the stub pair
            [0.0, 0.9, 0.5],  # 0.015 stub below the corner
            [0.0, 0.19, 0.5],  # isolated collinear vertex, no stub
        ],
        dtype=np.float64,
    )
    vertices = np.concatenate([front_ring_pts, back_ring_pts], axis=0)
    # Fans of the two 7-gon caps (the sliver fans carry zero-area triangles, as
    # the authored degenerate caps do); the front faces give the cap normal.
    cap_faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 3, 4],
            [0, 4, 5],
            [0, 5, 6],
            [7, 8, 9],
            [7, 9, 10],
            [7, 10, 11],
            [7, 11, 12],
            [7, 12, 13],
        ],
        dtype=np.int64,
    )
    front = [0, 1, 2, 3, 4]
    back = [5, 6, 7, 8, 9]
    front_ring = list(range(7))
    back_ring = list(range(7, 14))
    cap_normal = np.array([0.0, 0.0, 1.0])

    # The detector fires: the slivers sit at different heights, so the best
    # cyclic shift still mispairs vertices by up to ~0.87 in-plane.
    assert _rings_twisted(front_ring_pts, back_ring_pts, cap_normal)

    mesh = _loft_caps_watertight(
        vertices, cap_faces, front, back, front_ring, back_ring
    )

    assert mesh is not None
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    # The mispaired vertices all lie on the left-edge line, so the twisted-looking
    # side triangles stay inside the left face plane: the direct bridge is exact
    # and the volume is the true prism 2 x 1 x 0.5.
    assert mesh.volume == pytest.approx(1.0, rel=0.05)
    # The detected caps survive verbatim: 2x5 fan triangles plus 2x7 side
    # triangles. A clean+reloft of the 4/5 rings would carry a different count.
    assert len(mesh.faces) == 24


def _two_surface_host_mesh() -> trimesh.Trimesh:
    """A wall segment whose opening exposes only two opposite cut surfaces.

    Recovered from the real-world host ``main:expr:340868`` (``Wand-003``): the
    opening bore's reveal band is cut from just the two coplanar wall planks, so
    the cut-surface tube reads as two opposite surfaces only and ``_close_bore``
    caps it into a zero-thickness pillow.
    """
    vertices = np.array(
        [
            [0.364616, 25.972299, 8.660000],
            [0.211086, 25.844126, 8.660000],
            [0.335050, 26.007714, 8.660000],
            [0.181577, 25.879473, 8.660000],
            [0.211086, 25.844126, 11.150000],
            [0.364616, 25.972299, 11.150000],
            [0.335050, 26.007714, 11.150000],
            [0.181577, 25.879473, 11.150000],
            [1.488828, 24.625686, 8.660000],
            [1.335297, 24.497512, 8.660000],
            [1.108036, 25.081809, 8.660000],
            [0.954506, 24.953635, 8.660000],
            [1.488828, 24.625686, 11.150000],
            [1.335297, 24.497512, 11.150000],
            [1.108036, 25.081809, 11.150000],
            [0.954506, 24.953635, 11.150000],
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [2, 1, 3],
            [4, 1, 5],
            [5, 1, 0],
            [5, 0, 2],
            [6, 5, 2],
            [2, 3, 7],
            [6, 2, 7],
            [1, 4, 3],
            [3, 4, 7],
            [4, 5, 6],
            [7, 4, 6],
            [8, 9, 10],
            [10, 9, 11],
            [8, 12, 9],
            [9, 12, 13],
            [12, 8, 10],
            [14, 12, 10],
            [11, 15, 14],
            [10, 11, 14],
            [9, 13, 11],
            [11, 13, 15],
            [13, 12, 14],
            [15, 13, 14],
        ],
        dtype=np.int64,
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _two_surface_opening_mesh() -> trimesh.Trimesh:
    """The opening cutter for the wall segment (a through-door prism)."""
    vertices = np.array(
        [
            [0.117098, 24.254543, 11.230000],
            [-0.626310, 25.145018, 11.230000],
            [-0.626310, 25.145018, 8.660000],
            [1.202024, 26.671391, 11.230000],
            [1.202024, 26.671391, 8.660000],
            [1.945432, 25.780916, 8.660000],
            [0.117098, 24.254543, 8.660000],
            [1.945432, 25.780916, 11.230000],
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [1, 3, 4],
            [2, 4, 5],
            [6, 5, 7],
            [1, 0, 7],
            [7, 5, 4],
            [2, 6, 0],
            [4, 2, 1],
            [5, 6, 2],
            [7, 0, 6],
            [7, 3, 1],
            [4, 3, 7],
        ],
        dtype=np.int64,
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def test_two_opposite_cut_surfaces_loft_caps_not_zero_volume_tube() -> None:
    """A two-opposite-cut-surface tube must loft its caps, not emit a sliver.

    Regression for the real-world opening ``2hS$0Nz...`` (``main:expr:340917``
    voiding ``main:expr:340868``): its cut-surface tube is built solely from the
    host's two opposite cut surfaces, so ``_close_bore`` caps it into a shell
    trimesh deems watertight and winding-consistent but with ~1e-16 m^3 enclosed
    volume. The old ``volume > 0`` watertight test accepted that shell, emitting
    a zero-volume ``closed_cut_surface`` solid instead of lofting the two caps.
    """
    context = _context()
    opening = _FakeOpening(340917, guid="2hS$0Nzmdwc3olqPHoF593")
    host = _FakeHost(340868, [opening])
    _add_host_mesh(context, host, _two_surface_host_mesh())
    _add_opening(context, opening, _two_surface_opening_mesh())

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(340868)]), context)

    assert result.opening_count == 1
    assert result.surface_count == 1
    entry = result.openings[0]
    assert entry.error is None
    assert entry.guid == "2hS$0Nzmdwc3olqPHoF593"
    assert entry.method == "lofted_caps"
    assert entry.watertight is True
    volume = resolve_mesh(context, entry.geometry_key or "")
    assert volume.is_watertight
    assert volume.is_winding_consistent
    assert volume.volume == pytest.approx(0.596238, rel=1e-3)


# --- extraction edge cases ---------------------------------------------------------


def test_through_bore_closes_watertight() -> None:
    context = _context()
    opening = _FakeOpening(2, guid="0LhBByOR0VH8aBzIyEdt5G")
    host = _FakeHost(1, [opening])
    _add_host_mesh(context, host, _host_with_bore([2.0, 1.4, 0.3], [0.5, 0.5, 1.0]))
    _add_opening(context, opening, _box([0.5, 0.5, 1.0]))

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(1)]), context)

    assert result.opening_count == 1
    assert result.surface_count == 1
    assert result.geometry_keys == ["gen:opening_surface_main_2"]
    entry = result.openings[0]
    assert entry.express_id == "main:expr:2"
    assert entry.guid == "0LhBByOR0VH8aBzIyEdt5G"
    assert entry.host_express_id == "main:expr:1"
    assert entry.error is None
    assert entry.method == "closed_cut_surface"
    assert entry.watertight is True
    assert entry.area == pytest.approx(0.25)
    assert entry.depth == pytest.approx(0.3)

    volume = resolve_mesh(context, entry.geometry_key or "")
    assert volume.is_watertight
    assert volume.volume > 0


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
    _add_entity(context, opening)

    result = _run(OpeningSurfaceInputs(express_ids=[_ref(12)]), context)

    assert result.opening_count == 1
    assert result.surface_count == 0
    entry = result.openings[0]
    assert entry.error == "no cached geometry"
    assert entry.geometry_key is None
    assert entry.method is None


def test_repeated_host_emits_opening_once() -> None:
    context = _context()
    opening = _FakeOpening(13)
    host = _FakeHost(14, [opening])
    _add_host_mesh(context, host, _host_with_bore([2.0, 1.4, 0.3], [0.5, 0.5, 1.0]))
    _add_opening(context, opening, _box([0.5, 0.5, 1.0]))

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


def test_is_watertight_returns_false_for_degenerate_meshes() -> None:
    """A malformed (1-D faces) or empty mesh reports False instead of raising.

    Regression for the real-world model: the caps_only fallback once built a
    trimesh from a flat list of face ids, leaving a 1-D ``faces`` array, and
    ``_is_watertight`` crashed in trimesh's ``faces_to_edges``. It must be
    tolerant of degenerate geometry (diagnostics only, never watertight).
    """
    malformed = trimesh.Trimesh(
        vertices=np.zeros((3, 3), dtype=np.float64),
        faces=np.array([0, 1, 2], dtype=np.int64),
        process=False,
    )
    assert getattr(malformed.faces, "ndim", 0) == 1
    assert _is_watertight(malformed) is False

    empty = trimesh.Trimesh(
        vertices=np.zeros((3, 3), dtype=np.float64),
        faces=np.empty((0, 3), dtype=np.int64),
        process=False,
    )
    assert _is_watertight(empty) is False


def _jogged_ring_mesh() -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    """An open tube whose two rims are jogged rings.

    The bore steps from a cap-plane run, down a perpendicular reveal step into an
    internal layer plane, along it, and back up — the rim of a decomposed
    multi-layer wall's bore. Both rims are the same jogged profile translated
    along the cap normal (``z``), so the side faces are the planar vertical quads
    between matching rim vertices.
    """
    near = np.array(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],
            [2.0, 1.0, -0.2],
            [0.0, 1.0, -0.2],
            [0.0, 0.0, -0.2],
        ],
        dtype=np.float64,
    )
    far = near + np.array([0.0, 0.0, 1.0], dtype=np.float64)
    vertices = np.concatenate([near, far], axis=0)
    faces: list[list[int]] = []
    for i in range(6):
        a, b = i, (i + 1) % 6
        fa, fb = a + 6, b + 6
        faces.append([a, b, fb])
        faces.append([a, fb, fa])
    return (
        vertices,
        np.asarray(faces, dtype=np.int64),
        [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]],
    )


_CAP_NORMAL_Z = np.array([0.0, 0.0, 1.0], dtype=np.float64)


def test_jogged_ring_has_axial_edge() -> None:
    """A mid-wall jog edge runs parallel to the cap normal and is detected."""
    vertices, _, _ = _jogged_ring_mesh()
    assert _ring_has_axial_edge(vertices, [0, 1, 2, 3, 4, 5], _CAP_NORMAL_Z) is True


def test_planar_ring_has_no_axial_edge() -> None:
    """A flat cross-section rim (planar) has no axial step edge."""
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float64)
    assert _ring_has_axial_edge(vertices, [0, 1, 2, 3], _CAP_NORMAL_Z) is False


def test_jogged_ring_groups_decompose_into_level_and_band_caps() -> None:
    """The jogged rim becomes one level cap per in-plane run plus one band cap.

    The near rim has two in-plane runs (the cap plane ``z=0`` and the internal
    layer plane ``z=-0.2``) and two axial reveal steps, so it must decompose into
    exactly three disjoint cap polygons (two level faces and one band face), each
    with no repeated corner.
    """
    vertices, _, _ = _jogged_ring_mesh()
    groups = _jogged_ring_groups(vertices, [0, 1, 2, 3, 4, 5], _CAP_NORMAL_Z)
    assert len(groups) == 3
    for group in groups:
        assert len(group) >= 3
        assert len({int(v) for v in group}) == len(group)


def _planar_box_tube() -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    """An open box tube: four vertical quads with planar square rims."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )
    faces = np.asarray(
        [
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int64,
    )
    return vertices, faces, [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_build_ring_closed_planar_tube_is_a_prism() -> None:
    """A planar rim tube closes into a unit cube with an analytic volume."""
    vertices, faces, rings = _planar_box_tube()
    closed = _build_ring_closed(
        vertices, faces, rings, _CAP_NORMAL_Z, context=None, host_ref=None
    )
    assert closed is not None
    assert closed.is_watertight
    assert closed.is_winding_consistent
    assert closed.volume == pytest.approx(1.0, rel=1e-6)


def test_build_ring_closed_jogged_tube_is_watertight() -> None:
    """A jogged rim tube re-caps into a watertight, positive-volume solid."""
    vertices, faces, rings = _jogged_ring_mesh()
    closed = _build_ring_closed(
        vertices, faces, rings, _CAP_NORMAL_Z, context=None, host_ref=None
    )
    assert closed is not None
    assert closed.is_watertight
    assert closed.is_winding_consistent
    assert closed.volume > 0


def test_build_ring_closed_fails_open_when_a_loop_cannot_be_capped() -> None:
    """A rim that yields no valid cap polygon returns None so the caller falls back."""
    vertices, faces, _ = _planar_box_tube()
    # A two-vertex degenerate loop cannot form a cap: must fail (fallback).
    assert (
        _build_ring_closed(
            vertices, faces, [[0, 2]], _CAP_NORMAL_Z, context=None, host_ref=None
        )
        is None
    )


# --- real model -------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_context() -> ExecutionContext:
    model = ifcopenshell.open(str(_REAL_MODEL))
    return ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
    )


def _host_refs(model: Any) -> list[str]:
    return [
        f"main:expr:{entity.id()}"
        for entity_type in ("IfcWall", "IfcSlab", "IfcRoof")
        for entity in model.by_type(entity_type)
    ]


def test_real_model_produces_watertight_volumes(
    real_context: ExecutionContext,
) -> None:
    model = cast(Any, real_context.ifc_model)
    result = _run(OpeningSurfaceInputs(express_ids=_host_refs(model)), real_context)

    assert result.opening_count > 0
    assert result.surface_count == result.opening_count
    for entry in result.openings:
        assert entry.error is None
        assert entry.geometry_key is not None
        volume = resolve_mesh(real_context, entry.geometry_key or "")
        assert len(volume.faces) > 0
        if entry.watertight:
            assert volume.is_watertight
            assert volume.is_winding_consistent
            assert volume.volume > 0


def test_real_model_closed_cut_surface_is_watertight() -> None:
    """Every closed_cut_surface volume re-caps its bore's rims to a watertight solid.

    Regression for decomposed multi-layer hosts (Zementputz / Stahlbeton / EPS
    walls): the cut-surface tube's rim is jogged across a layer-interface plane,
    so the surface node must re-cap the bore from its own rim rings (a level cap
    per in-plane run plus a perpendicular band cap) rather than trust the
    centroid-fan ``_close_bore`` applies. Every ``closed_cut_surface`` volume must
    come out watertight and winding-consistent with a positive volume.

    A fresh context is used so the test is order-independent (the shared module
    fixture already caches the generated geometry keys).
    """
    model = ifcopenshell.open(str(_REAL_MODEL))
    context = ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
    )
    result = _run(OpeningSurfaceInputs(express_ids=_host_refs(model)), context)

    assert result.opening_count > 0
    closed = 0
    for entry in result.openings:
        if (entry.method or "") != "closed_cut_surface":
            continue
        closed += 1
        assert entry.watertight is True
        volume = resolve_mesh(context, entry.geometry_key or "")
        assert volume.is_watertight, f"{entry.express_id} not watertight"
        assert volume.is_winding_consistent
        assert volume.volume > 0

    assert closed > 0, "expected at least one through-bore to stay closed"


def test_real_model_volumes_are_always_created_for_every_opening() -> None:
    """Every opening on the small model closes to a watertight positive-volume solid.

    Regression guard: the surface node must always produce a closed, positive-volume
    solid for every opening on the model, with its method recorded. The upstream
    surface-extraction node is deprecated, so the surface node itself is the truth:
    no hard-coded volume numbers, only the structural invariants of the solid.

    A fresh context is used so the test is order-independent: the shared
    ``real_context`` module fixture already caches ``gen:opening_surface_main_*``
    keys, and ``cache_mesh`` rejects a repeated key.
    """
    model = ifcopenshell.open(str(_REAL_MODEL))
    context = ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
    )
    refs = _host_refs(model)

    volumes = _run(OpeningSurfaceInputs(express_ids=refs), context)

    # The closed-surface geometry is ALWAYS created for every opening.
    assert volumes.opening_count > 0
    assert volumes.surface_count == volumes.opening_count
    assert len(volumes.geometry_keys) == volumes.opening_count

    for volume in volumes.openings:
        assert volume.error is None
        assert volume.geometry_key is not None
        assert volume.method in {"closed_cut_surface", "lofted_caps"}

        mesh = resolve_mesh(context, volume.geometry_key or "")
        assert len(mesh.faces) > 0
        # The produced geometry stays a correct solid on this model.
        assert volume.watertight is True
        assert mesh.is_watertight
        assert mesh.is_winding_consistent
        assert mesh.volume > 0


def test_light_exposure_skylights_closed_with_correct_volumes() -> None:
    """The folded-roof skylights are closed cut surfaces, not lofted caps.

    Openings 679 and 703 are the roof skylights whose rims span two pitches.
    Because the cut-surface tube now closes watertight, the surface node must use
    ``closed_cut_surface`` and report the correct volumes, never the buggy
    ``lofted_caps`` path (which once reported 0.405 and 0.071).
    """
    model = ifcopenshell.open(str(_REAL_MODEL))
    context = ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
    )
    result = _run(OpeningSurfaceInputs(express_ids=_host_refs(model)), context)

    expected_volumes = {"679": 2.359805, "703": 0.539082}
    found = 0
    for entry in result.openings:
        opening_id = entry.express_id.rsplit(":", 1)[-1]
        if opening_id not in expected_volumes:
            continue
        found += 1
        assert entry.error is None
        assert entry.method == "closed_cut_surface"
        assert entry.watertight is True
        volume = resolve_mesh(context, entry.geometry_key or "")
        assert volume.is_watertight
        assert volume.is_winding_consistent
        assert abs(volume.volume - expected_volumes[opening_id]) < 1e-3
    assert found == 2
