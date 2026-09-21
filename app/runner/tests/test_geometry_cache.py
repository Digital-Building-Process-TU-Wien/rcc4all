from __future__ import annotations

from typing import Any, cast

import ifcopenshell
import pytest
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.util.geometry import (
    GEOMETRY_LIBRARY,
    build_geometry_cache,
    cache_mesh,
    is_model_key,
    resolve_mesh,
    resolve_side,
)

UNIT_CUBE_VERTS = (
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    1.0,
    1.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    1.0,
    0.0,
    1.0,
    1.0,
    1.0,
    1.0,
    0.0,
    1.0,
    1.0,
)
UNIT_CUBE_FACES = (
    0,
    1,
    2,
    0,
    2,
    3,
    4,
    6,
    5,
    4,
    7,
    6,
    0,
    4,
    5,
    0,
    5,
    1,
    1,
    5,
    6,
    1,
    6,
    2,
    2,
    6,
    7,
    2,
    7,
    3,
    3,
    7,
    4,
    3,
    4,
    0,
)


class FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        self.values[name] = value


class FakeGeometry:
    def __init__(self, verts: tuple[float, ...], faces: tuple[int, ...]) -> None:
        self.verts = verts
        self.faces = faces


class FakeShape:
    def __init__(
        self, express_id: int, verts: tuple[float, ...], faces: tuple[int, ...]
    ) -> None:
        self.id = express_id
        self.geometry = FakeGeometry(verts, faces)


class FakeIterator:
    def __init__(
        self, shapes: list[FakeShape], *, initialize_raises: bool = False
    ) -> None:
        self.shapes = list(shapes)
        self._initialize_raises = initialize_raises
        self._pos = -1
        self.settings: Any = None
        self.ifc_model: Any = None
        self.geometry_library: str = ""

    def initialize(self) -> None:
        if self._initialize_raises:
            raise RuntimeError("init failed")
        self._pos = 0

    def get(self) -> FakeShape | None:
        if 0 <= self._pos < len(self.shapes):
            return self.shapes[self._pos]
        return None

    def next(self) -> bool:
        self._pos += 1
        return self._pos < len(self.shapes)


class FakeGeom:
    def __init__(
        self, shapes: list[FakeShape], *, initialize_raises: bool = False
    ) -> None:
        self.shapes = shapes
        self.captured_settings: FakeSettings | None = None
        self.captured_iterator: FakeIterator | None = None
        self._initialize_raises = initialize_raises

    def settings(self) -> FakeSettings:
        self.captured_settings = FakeSettings()
        return self.captured_settings

    def iterator(
        self, settings: Any, ifc_model: Any, geometry_library: str = "opencascade"
    ) -> FakeIterator:
        it = FakeIterator(self.shapes, initialize_raises=self._initialize_raises)
        it.settings = settings
        it.ifc_model = ifc_model
        it.geometry_library = geometry_library
        self.captured_iterator = it
        return it


def _make_shapes() -> list[FakeShape]:
    return [
        FakeShape(1, UNIT_CUBE_VERTS, UNIT_CUBE_FACES),
        FakeShape(2, UNIT_CUBE_VERTS, UNIT_CUBE_FACES),
    ]


def test_build_geometry_cache_caches_every_element() -> None:
    fake = FakeGeom(_make_shapes())
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    assert set(cache.keys()) == {"main:expr:1", "main:expr:2"}
    assert cache["main:expr:1"].vertices.shape == (8, 3)
    assert cache["main:expr:1"].faces.shape == (12, 3)


def test_build_geometry_cache_uses_hybrid_library_and_settings() -> None:
    fake = FakeGeom(_make_shapes())
    build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    assert fake.captured_settings is not None
    assert fake.captured_settings.values["use-world-coords"] is True
    assert fake.captured_settings.values["weld-vertices"] is True
    assert fake.captured_settings.values["context_types"] == ["Body"]

    assert fake.captured_iterator is not None
    assert fake.captured_iterator.geometry_library == GEOMETRY_LIBRARY


def test_build_geometry_cache_skips_empty_geometry() -> None:
    shapes = [
        FakeShape(1, UNIT_CUBE_VERTS, UNIT_CUBE_FACES),
        FakeShape(2, (), ()),
        FakeShape(3, UNIT_CUBE_VERTS, UNIT_CUBE_FACES),
    ]
    fake = FakeGeom(shapes)

    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    assert set(cache.keys()) == {"main:expr:1", "main:expr:3"}


def test_build_geometry_cache_returns_empty_when_initialize_fails() -> None:
    fake = FakeGeom(_make_shapes(), initialize_raises=True)
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    assert cache == {}


def test_build_geometry_cache_empty_model_yields_empty_cache() -> None:
    fake = FakeGeom([])
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    assert cache == {}


def _context() -> ExecutionContext:
    return ExecutionContext(ifc_model=cast(Any, object()), node_outputs={})


def test_cache_mesh_keras_and_resolve() -> None:
    context = _context()
    mesh = trimesh.creation.box()

    express_key = cache_mesh(context, mesh, express_id=5)
    object_key = cache_mesh(context, mesh.copy(), object_id="probe")
    inter_key = cache_mesh(context, mesh.copy(), intermediate=True)

    assert express_key == "main:expr:5"
    assert object_key == "gen:probe"
    assert inter_key.startswith("inter:")
    assert resolve_mesh(context, "main:expr:5") is mesh

    assert is_model_key(express_key) is True
    assert is_model_key(object_key) is True
    assert is_model_key(inter_key) is False
    assert is_model_key("other") is False


def test_cache_mesh_requires_an_id_kind() -> None:
    context = _context()
    with pytest.raises(
        ValueError, match="requires express_id, object_id, intermediate=True, or a key"
    ):
        cache_mesh(context, trimesh.creation.box())


def test_cache_mesh_accepts_explicit_key() -> None:
    context = _context()
    mesh = trimesh.creation.box()
    key = cache_mesh(context, mesh, key="inter:intersection_main:expr:1_main:expr:2")

    assert key == "inter:intersection_main:expr:1_main:expr:2"
    assert resolve_mesh(context, key) is mesh
    assert is_model_key(key) is False


def test_cache_mesh_explicit_key_duplicate_raises() -> None:
    context = _context()
    cache_mesh(
        context,
        trimesh.creation.box(),
        key="inter:intersection_main:expr:1_main:expr:2",
    )

    with pytest.raises(
        ValueError, match="'inter:intersection_main:expr:1_main:expr:2' already exists"
    ):
        cache_mesh(
            context,
            trimesh.creation.box(),
            key="inter:intersection_main:expr:1_main:expr:2",
        )


def test_cache_mesh_duplicate_key_raises() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), object_id="dup")

    with pytest.raises(ValueError, match="'gen:dup' already exists"):
        cache_mesh(context, trimesh.creation.box(), object_id="dup")


def test_resolve_side_maps_express_and_object_ids() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), express_id=2)
    cache_mesh(context, trimesh.creation.box(), object_id="a")
    cache_mesh(context, trimesh.creation.box(), intermediate=True)

    assert resolve_side(context, refs=[2, "a"]) == ["main:expr:2", "gen:a"]


def test_resolve_side_mixed_list_preserves_order() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), object_id="a")
    cache_mesh(context, trimesh.creation.box(), express_id=2)

    assert resolve_side(context, refs=["a", 1, 2]) == [
        "gen:a",
        "main:expr:1",
        "main:expr:2",
    ]


def test_resolve_side_empty_list_returns_whole_model() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), object_id="a")
    cache_mesh(context, trimesh.creation.box(), intermediate=True)

    keys = resolve_side(context, refs=[])
    assert keys == ["main:expr:1", "gen:a"]
    assert all(is_model_key(key) for key in keys)


def test_resolve_side_missing_reference_raises() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)

    with pytest.raises(ValueError, match="Express ID 9 has no tessellated geometry"):
        resolve_side(context, refs=[9])
    with pytest.raises(ValueError, match="Object ID 'ghost' has no geometry"):
        resolve_side(context, refs=["ghost"])


class FakePart:
    def __init__(self, pid: int) -> None:
        self._pid = pid

    def id(self) -> int:
        return self._pid


class FakeRel:
    RelatingObject: Any = None
    RelatedObjects: list[Any] = None  # type: ignore[assignment]

    def __init__(self) -> None:
        self.RelatedObjects = []


class FakeAggregateModel:
    def __init__(self, rels: list[FakeRel], include_nests: bool = False) -> None:
        self._rels = rels
        self._include_nests = include_nests

    def by_type(self, name: str) -> list[FakeRel]:
        if name == "IfcRelAggregates":
            return self._rels
        if name == "IfcRelNests" and self._include_nests:
            return self._rels
        return []


def _make_cube_shape() -> tuple[tuple[float, ...], tuple[int, ...]]:
    return UNIT_CUBE_VERTS, UNIT_CUBE_FACES


def _offset_cube_vertices(
    verts: tuple[float, ...], dx: float, dy: float, dz: float
) -> tuple[float, ...]:
    """Translate cube vertices by (dx, dy, dz)."""
    result: list[float] = []
    for i, v in enumerate(verts):
        if i % 3 == 0:
            result.append(v + dx)
        elif i % 3 == 1:
            result.append(v + dy)
        else:
            result.append(v + dz)
    return tuple(result)


def test_composite_parent_with_all_parts_cached_is_synthesized() -> None:
    """Two offset cubes merged via union → single watertight solid with correct volume."""
    fake = FakeGeom(
        [
            FakeShape(165, *_make_cube_shape()),
            FakeShape(
                180,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 2.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
        ]
    )
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    rel = FakeRel()
    rel.RelatingObject = FakePart(359)
    rel.RelatedObjects = [FakePart(165), FakePart(180)]
    fake_model = FakeAggregateModel([rel])

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(fake_model, cache)

    assert "main:expr:359" in cache
    mesh = cache["main:expr:359"]
    assert mesh.is_watertight
    assert abs(abs(mesh.volume) - 2.0) < 1e-6


def test_composite_parent_with_missing_part_is_not_synthesized() -> None:
    fake = FakeGeom([FakeShape(165, *_make_cube_shape())])
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    rel = FakeRel()
    rel.RelatingObject = FakePart(359)
    rel.RelatedObjects = [FakePart(165), FakePart(999)]
    fake_model = FakeAggregateModel([rel])

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(fake_model, cache)

    assert "main:expr:359" not in cache


def test_composite_parent_with_own_geometry_is_not_overwritten() -> None:
    fake = FakeGeom(
        [
            FakeShape(359, *_make_cube_shape()),
            FakeShape(165, *_make_cube_shape()),
            FakeShape(180, *_make_cube_shape()),
        ]
    )
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    original_volume = cache["main:expr:359"].volume

    rel = FakeRel()
    rel.RelatingObject = FakePart(359)
    rel.RelatedObjects = [FakePart(165), FakePart(180)]
    fake_model = FakeAggregateModel([rel])

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(fake_model, cache)

    assert "main:expr:359" in cache
    assert abs(cache["main:expr:359"].volume - original_volume) < 1e-6


def test_non_ifc_model_returns_cache_unchanged() -> None:
    fake = FakeGeom([FakeShape(1, *_make_cube_shape())])
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(object(), cache)

    assert set(cache.keys()) == {"main:expr:1"}


def test_build_geometry_cache_synthesizes_composite_wall_model() -> None:
    """End-to-end test: composite wall parent gets synthesized geometry from parts."""
    import pathlib

    ifc_path = (
        pathlib.Path(__file__).parent
        / "testdata"
        / "models"
        / "multilayered"
        / "Multilayered_Wall.ifc"
    )
    if not ifc_path.exists():
        pytest.skip("Multilayered_Wall.ifc fixture not found")

    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    wall_id = 123
    part_ids = [96, 111]

    for pid in part_ids:
        assert f"main:expr:{pid}" in cache, f"Part {pid} should be cached"

    assert f"main:expr:{wall_id}" in cache, (
        f"Composite wall {wall_id} should be synthesized"
    )

    wall_mesh = cache[f"main:expr:{wall_id}"]
    assert wall_mesh.is_watertight, "Synthesized wall should be watertight"
    assert abs(wall_mesh.volume) > 0, "Synthesized wall should have positive volume"


def test_print_wall_volumes_on_test_volumen() -> None:
    """Print volumes for all wall instances in Test-Volumen.ifc for manual verification."""
    import pathlib

    ifc_path = (
        pathlib.Path(__file__).parent
        / "testdata"
        / "models"
        / "multilayered"
        / "Test-Volumen.ifc"
    )
    if not ifc_path.exists():
        pytest.skip("Test-Volumen.ifc fixture not found")

    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    walls = model.by_type("IfcWall")
    for wall in walls:
        wall_id = wall.id()
        key = f"main:expr:{wall_id}"
        assert key in cache, f"Wall {wall_id} should be in cache"
        mesh = cache[key]
        vol = abs(mesh.volume)
        assert vol > 0, f"Wall {wall_id} should have positive volume"
        print(f"{key}: {vol:.4f} m3")


def test_nested_layer_without_geometry_adversarial_order() -> None:
    """Prove recursive synthesis works even with adversarial relation order.

    Structure:
    - Wall (170) -> Layer-1 (186), Layer-2 (204), Layer-3 (212)
    - Layer-3 (212) -> Sub-layer-3a (228), Sub-layer-3b (246)
    - Layer-3 has NO own geometry; only sub-layers do.

    Relations given in adversarial order (Wall before Layer-3) would fail
    with the old single-pass implementation.

    Parts are offset to test boolean union (not concatenate) — volumes must be
    correct after merging, and internal touching surfaces removed.
    """
    fake = FakeGeom(
        [
            FakeShape(
                186,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 0.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
            FakeShape(
                204,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 2.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
            FakeShape(
                228,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 4.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
            FakeShape(
                246,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 6.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
        ]
    )
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    rel_l3 = FakeRel()
    rel_l3.RelatingObject = FakePart(212)
    rel_l3.RelatedObjects = [FakePart(228), FakePart(246)]

    rel_wall = FakeRel()
    rel_wall.RelatingObject = FakePart(170)
    rel_wall.RelatedObjects = [FakePart(186), FakePart(204), FakePart(212)]

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(FakeAggregateModel([rel_wall, rel_l3]), cache)

    assert "main:expr:212" in cache, (
        "Nested Layer-3 should be synthesized from sub-layers"
    )
    assert "main:expr:170" in cache, (
        "Wall should be synthesized even with adversarial order"
    )

    layer3_mesh = cache["main:expr:212"]
    wall_mesh = cache["main:expr:170"]

    assert abs(abs(layer3_mesh.volume) - 2.0) < 1e-6
    assert abs(abs(wall_mesh.volume) - 4.0) < 1e-6
    assert layer3_mesh.is_watertight
    assert wall_mesh.is_watertight


def test_multilayered_testmodel_wall4_nested_layers() -> None:
    """End-to-end: Wall-4 (170) with nested Layer-3 (212) in real IFC model.

    Multilayered_Testmodel.ifc contains:
    - Wall-4 (id=170) decomposed into Layer-1 (186), Layer-2 (204), Layer-3 (212)
    - Layer-3 (212) has no body representation, but has sub-layers 228 and 246
    - All walls and nested layers should have synthesized geometry.
    """
    import pathlib

    ifc_path = (
        pathlib.Path(__file__).parent
        / "testdata"
        / "models"
        / "multilayered"
        / "Multilayered_Testmodel.ifc"
    )
    if not ifc_path.exists():
        pytest.skip("Multilayered_Testmodel.ifc fixture not found")

    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    wall4_id = 170
    layer3_id = 212
    sublayer_ids = [228, 246]

    for sub_id in sublayer_ids:
        key = f"main:expr:{sub_id}"
        assert key in cache, f"Sub-layer {sub_id} should be cached"
        mesh = cache[key]
        assert mesh.is_watertight, f"Sub-layer {sub_id} should be watertight"
        assert abs(mesh.volume) > 0, f"Sub-layer {sub_id} should have positive volume"

    assert f"main:expr:{layer3_id}" in cache, (
        f"Layer-3 ({layer3_id}) should be synthesized"
    )
    layer3_mesh = cache[f"main:expr:{layer3_id}"]
    assert layer3_mesh.is_watertight, "Layer-3 should be watertight"
    assert abs(layer3_mesh.volume) > 0, "Layer-3 should have positive volume"

    assert f"main:expr:{wall4_id}" in cache, (
        f"Wall-4 ({wall4_id}) should be synthesized"
    )
    wall4_mesh = cache[f"main:expr:{wall4_id}"]
    assert wall4_mesh.is_watertight, "Wall-4 should be watertight"
    assert abs(wall4_mesh.volume) > 0, "Wall-4 should have positive volume"


def test_ifc_member_without_geometry_nested_sublayers() -> None:
    """An IfcMember without a body, decomposed into body-bearing sub-parts,
    should be synthesized — and its aggregating wall too.

    Structure:
    - Wall (261) -> Member (347, NO body), Plate (277, body)
    - Member (347) -> Batten-a (900, body), Batten-b (901, body)

    This mirrors real-world cases where an IfcMember (e.g., battens, studs)
    has no own body representation but is decomposed into sub-parts that do.

    Parts are offset to test boolean union (not concatenate) — volumes must be
    correct after merging, and internal touching surfaces removed.
    """
    fake = FakeGeom(
        [
            FakeShape(
                277,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 0.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
            FakeShape(
                900,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 2.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
            FakeShape(
                901,
                _offset_cube_vertices(UNIT_CUBE_VERTS, 4.0, 0.0, 0.0),
                UNIT_CUBE_FACES,
            ),
        ]
    )
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    rel_member = FakeRel()
    rel_member.RelatingObject = FakePart(347)
    rel_member.RelatedObjects = [FakePart(900), FakePart(901)]

    rel_wall = FakeRel()
    rel_wall.RelatingObject = FakePart(261)
    rel_wall.RelatedObjects = [FakePart(277), FakePart(347)]

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(FakeAggregateModel([rel_member, rel_wall]), cache)

    assert "main:expr:347" in cache, (
        "IfcMember without body should be synthesized from sub-parts"
    )
    assert "main:expr:900" in cache, "Batten-a should be cached"
    assert "main:expr:901" in cache, "Batten-b should be cached"
    assert "main:expr:261" in cache, "Wall should be synthesized from Plate + Member"

    member_mesh = cache["main:expr:347"]
    wall_mesh = cache["main:expr:261"]

    assert abs(abs(member_mesh.volume) - 2.0) < 1e-6, "Member volume = 2 unit cubes"
    assert abs(abs(wall_mesh.volume) - 3.0) < 1e-6, "Wall volume = Plate + Member"
    assert member_mesh.is_watertight
    assert wall_mesh.is_watertight


def test_merged_multilayer_surface_area_correct() -> None:
    """Verify boolean union removes internal touching surfaces.

    Two touching cubes merged should have surface area equal to the external
    boundary only, not the sum of individual surface areas (which would
    include internal faces).
    """
    from openbim_runner.util.geometry import _merge_part_meshes

    cube1 = trimesh.creation.box()
    cube2 = trimesh.creation.box().apply_translation([1.0, 0.0, 0.0])

    individual_area = cube1.area + cube2.area
    merged = _merge_part_meshes([cube1, cube2])

    assert merged.is_watertight
    assert abs(abs(merged.volume) - 2.0) < 1e-6
    assert merged.area < individual_area, (
        f"Merged area {merged.area} should be less than sum {individual_area} "
        "(internal faces removed)"
    )


def test_union_fallback_to_concatenate() -> None:
    """If boolean union fails, fallback to concatenate ensures caching still works.

    This tests the degradation mode: volume correct but surface area inflated.
    """
    from unittest.mock import patch

    from openbim_runner.util.geometry import _merge_part_meshes

    cube1 = trimesh.creation.box()
    cube2 = trimesh.creation.box().apply_translation([2.0, 0.0, 0.0])

    with patch("trimesh.boolean.union", side_effect=RuntimeError("union failed")):
        merged = _merge_part_meshes([cube1, cube2])

    assert merged is not None
    assert abs(abs(merged.volume) - 2.0) < 1e-6, "Volume still correct with fallback"


class FakeAlignmentModel:
    def __init__(self, alignments: list[Any]) -> None:
        self._alignments = alignments

    def by_type(self, name: str) -> list[Any]:
        if name == "IfcAlignment":
            return self._alignments
        return []


class FakeAlignmentShape:
    def __init__(self, verts: tuple[float, ...]) -> None:
        self.geometry = FakeGeometry(verts, ())


def test_add_alignment_geometry_di_unit() -> None:
    """DI unit test: fake model with IfcAlignment + fake shape_creator."""
    from openbim_runner.util.geometry import _add_alignment_geometry

    align_id = 166
    verts = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    fake_alignment = FakePart(align_id)
    fake_model = FakeAlignmentModel([fake_alignment])

    def fake_shape_creator(settings: Any, element: Any) -> FakeAlignmentShape:
        return FakeAlignmentShape(verts)

    cache: dict[str, trimesh.Trimesh] = {}
    fake_settings = FakeSettings()

    _add_alignment_geometry(
        fake_model, cache, fake_settings, shape_creator=fake_shape_creator
    )

    key = f"main:expr:{align_id}"
    assert key in cache
    mesh = cache[key]
    assert isinstance(mesh, trimesh.Trimesh)
    assert mesh.is_watertight
    assert len(mesh.faces) > 0


def test_add_alignment_geometry_non_ifc_noop() -> None:
    """Non-IFC model or by_type failure should be a no-op."""
    from openbim_runner.util.geometry import _add_alignment_geometry

    cache: dict[str, trimesh.Trimesh] = {}
    fake_settings = FakeSettings()

    _add_alignment_geometry(object(), cache, fake_settings)

    assert cache == {}


def test_add_alignment_geometry_real_models() -> None:
    """Real-model test: both rail fixtures have alignment tubes cached."""
    import pathlib

    from openbim_runner.util.geometry import build_geometry_cache

    base = pathlib.Path(__file__).parent / "testdata" / "models" / "rail"
    fixtures = ["simple_railway.ifc", "Simple_Railway-Civil_3D.ifc"]

    for fname in fixtures:
        ifc_path = base / fname
        if not ifc_path.exists():
            pytest.skip(f"{fname} fixture not found")

        model = ifcopenshell.open(str(ifc_path))
        cache = build_geometry_cache(model)

        alignments = model.by_type("IfcAlignment")
        for align in alignments:
            key = f"main:expr:{align.id()}"
            assert key in cache, f"Alignment {align.id()} should be cached in {fname}"
            mesh = cache[key]
            assert mesh.is_watertight, f"Alignment tube should be watertight in {fname}"
            assert len(mesh.faces) > 0, f"Alignment tube should have faces in {fname}"
