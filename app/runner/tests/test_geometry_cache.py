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

    assert set(cache.keys()) == {"ifc:1", "ifc:2"}
    assert cache["ifc:1"].vertices.shape == (8, 3)
    assert cache["ifc:1"].faces.shape == (12, 3)


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

    assert set(cache.keys()) == {"ifc:1", "ifc:3"}


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

    assert express_key == "ifc:5"
    assert object_key == "gen:probe"
    assert inter_key.startswith("inter:")
    assert resolve_mesh(context, "ifc:5") is mesh

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
    key = cache_mesh(context, mesh, key="inter:intersection_ifc:1_ifc:2")

    assert key == "inter:intersection_ifc:1_ifc:2"
    assert resolve_mesh(context, key) is mesh
    assert is_model_key(key) is False


def test_cache_mesh_explicit_key_duplicate_raises() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), key="inter:intersection_ifc:1_ifc:2")

    with pytest.raises(
        ValueError, match="'inter:intersection_ifc:1_ifc:2' already exists"
    ):
        cache_mesh(
            context, trimesh.creation.box(), key="inter:intersection_ifc:1_ifc:2"
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

    assert resolve_side(context, refs=[2, "a"]) == ["ifc:2", "gen:a"]


def test_resolve_side_mixed_list_preserves_order() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), object_id="a")
    cache_mesh(context, trimesh.creation.box(), express_id=2)

    assert resolve_side(context, refs=["a", 1, 2]) == ["gen:a", "ifc:1", "ifc:2"]


def test_resolve_side_empty_list_returns_whole_model() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), object_id="a")
    cache_mesh(context, trimesh.creation.box(), intermediate=True)

    keys = resolve_side(context, refs=[])
    assert keys == ["ifc:1", "gen:a"]
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


def test_composite_parent_with_all_parts_cached_is_synthesized() -> None:
    fake = FakeGeom(
        [
            FakeShape(165, *_make_cube_shape()),
            FakeShape(180, *_make_cube_shape()),
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

    assert "ifc:359" in cache
    assert cache["ifc:359"].vertices.shape == (16, 3)
    assert abs(abs(cache["ifc:359"].volume) - 2.0) < 1e-6


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

    assert "ifc:359" not in cache


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

    original_volume = cache["ifc:359"].volume

    rel = FakeRel()
    rel.RelatingObject = FakePart(359)
    rel.RelatedObjects = [FakePart(165), FakePart(180)]
    fake_model = FakeAggregateModel([rel])

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(fake_model, cache)

    assert "ifc:359" in cache
    assert abs(cache["ifc:359"].volume - original_volume) < 1e-6


def test_non_ifc_model_returns_cache_unchanged() -> None:
    fake = FakeGeom([FakeShape(1, *_make_cube_shape())])
    cache = build_geometry_cache(
        object(),
        settings_factory=fake.settings,
        shape_iterator=fake.iterator,
    )

    from openbim_runner.util.geometry import _merge_decomposed_parents

    cache = _merge_decomposed_parents(object(), cache)

    assert set(cache.keys()) == {"ifc:1"}


def test_build_geometry_cache_synthesizes_composite_wall_model() -> None:
    """End-to-end test: composite wall parent gets synthesized geometry from parts."""
    import pathlib

    ifc_path = pathlib.Path(__file__).parent / "testdata" / "models" / "multilayered" / "Multilayered_Wall.ifc"
    if not ifc_path.exists():
        pytest.skip("Multilayered_Wall.ifc fixture not found")

    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    wall_id = 123
    part_ids = [96, 111]

    for pid in part_ids:
        assert f"ifc:{pid}" in cache, f"Part {pid} should be cached"

    assert f"ifc:{wall_id}" in cache, f"Composite wall {wall_id} should be synthesized"

    wall_mesh = cache[f"ifc:{wall_id}"]
    assert wall_mesh.is_watertight, "Synthesized wall should be watertight"
    assert abs(wall_mesh.volume) > 0, "Synthesized wall should have positive volume"


def test_print_wall_volumes_on_test_volumen() -> None:
    """Print volumes for all wall instances in Test-Volumen.ifc for manual verification."""
    import pathlib

    ifc_path = pathlib.Path(__file__).parent / "testdata" / "models" / "multilayered" / "Test-Volumen.ifc"
    if not ifc_path.exists():
        pytest.skip("Test-Volumen.ifc fixture not found")

    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    walls = model.by_type("IfcWall")
    for wall in walls:
        wall_id = wall.id()
        key = f"ifc:{wall_id}"
        assert key in cache, f"Wall {wall_id} should be in cache"
        mesh = cache[key]
        vol = abs(mesh.volume)
        assert vol > 0, f"Wall {wall_id} should have positive volume"
        print(f"{key}: {vol:.4f} m3")
