from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import ifcopenshell.geom
import numpy as np
import pymeshfix
import trimesh
from shapely.geometry import Polygon

from openbim_runner.nodes.base import ExecutionContext

GEOMETRY_LIBRARY: ifcopenshell.geom.GEOMETRY_LIBRARY = "hybrid-cgal-simple-opencascade"
ALIGNMENT_TUBE_RADIUS = 3.0e-4  # 0.30 mm; total error ≤0.40 mm @R=300m (<0.5 mm target)
ALIGNMENT_TUBE_SECTIONS = 8  # cross-section segments for sweep_polygon


def expr_key(slug: str, express_id: int) -> str:
    """Geometry-cache key for an IFC entity: ``<slug>:expr:<express_id>``."""
    return f"{slug}:expr:{express_id}"


def split_expr_key(key: str) -> tuple[str, int] | None:
    """Split an express-key ``<slug>:expr:<id>`` into ``(slug, express_id)``.

    Returns ``None`` for keys that are not IFC express keys (e.g. ``gen:`` or
    ``inter:`` keys).
    """
    marker = ":expr:"
    start = key.find(marker)
    if start <= 0:
        return None
    slug = key[:start]
    try:
        return slug, int(key[start + len(marker) :])
    except ValueError:
        return None


def build_geometry_cache(
    ifc_model: Any,
    *,
    slug: str = "main",
    settings_factory: Callable[..., Any] | None = None,
    shape_iterator: Callable[..., Any] | None = None,
    geometry_library: ifcopenshell.geom.GEOMETRY_LIBRARY = GEOMETRY_LIBRARY,
) -> dict[str, trimesh.Trimesh]:
    """Tessellate the whole IFC model into a geometry cache keyed by model slug.

    Dependency-injected for testability: pass fakes for ``settings_factory``
    and ``shape_iterator`` to avoid depending on ifcopenshell. Elements that
    cannot be tessellated are skipped (absent from the returned cache). Keys are
    ``<slug>:expr:<express_id>`` so caches from different models do not collide.
    """
    settings_factory = settings_factory or ifcopenshell.geom.settings
    shape_iterator = shape_iterator or ifcopenshell.geom.iterator

    settings = settings_factory()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("context_types", ["Body"])  # pyright: ignore[reportArgumentType]

    cache: dict[str, trimesh.Trimesh] = {}
    iterator = shape_iterator(settings, ifc_model, geometry_library=geometry_library)

    try:
        iterator.initialize()
    except Exception:
        return cache

    while True:
        shape = iterator.get()
        if shape is not None:
            # ifcopenshell stubs model iterator.get() as a union that lacks the
            # runtime shape_tuple attributes; both members expose them at runtime.
            geometry = shape.geometry  # pyright: ignore[reportAttributeAccessIssue]
            if len(geometry.verts) > 0 and len(geometry.faces) > 0:
                express_id = shape.id  # pyright: ignore[reportAttributeAccessIssue]
                cache[expr_key(slug, express_id)] = reshape_flat(
                    geometry.verts, geometry.faces
                )
        if not iterator.next():
            break

    _add_alignment_geometry(ifc_model, cache, settings=settings, slug=slug)

    return _merge_decomposed_parents(ifc_model, cache, slug=slug)


def _ensure_cache(context: ExecutionContext) -> dict[str, trimesh.Trimesh]:
    return context.geometry_cache


def cache_mesh(
    context: ExecutionContext,
    mesh: trimesh.Trimesh,
    *,
    express_id: int | None = None,
    object_id: str | None = None,
    intermediate: bool = False,
    key: str | None = None,
    slug: str | None = None,
) -> str:
    """Store a mesh in the cache and return its key.

    - ``express_id`` stores an IFC body under ``<slug>:expr:<express_id>``.
    - ``object_id`` stores an external/generated geometry under ``gen:<object_id>``.
    - ``intermediate`` stores an internal helper mesh under ``inter:<uuid>`` (excluded
      from the whole-model expansion).
    - ``key`` stores the mesh under an explicit, fully-specified key (e.g. a
      deterministic intermediate key like ``inter:intersection_1_expr:2``).

    Exactly one of these must be provided, and the key must not already exist.
    ``slug`` defaults to the execution context's main model.
    """
    if key is not None:
        if not key:
            raise ValueError("cache_mesh 'key' must be a non-empty string.")
    elif express_id is not None:
        key = expr_key(context.resolve_slug(slug), express_id)
    elif object_id is not None:
        key = f"gen:{object_id}"
    elif intermediate:
        key = f"inter:{uuid.uuid4()}"
    else:
        raise ValueError(
            "cache_mesh requires express_id, object_id, intermediate=True, or a key."
        )

    cache = _ensure_cache(context)
    if key in cache:
        raise ValueError(f"Geometry cache key '{key}' already exists.")
    cache[key] = mesh
    return key


def resolve_mesh(context: ExecutionContext, key: str) -> trimesh.Trimesh:
    cache = _ensure_cache(context)
    if key not in cache:
        raise ValueError(
            f"Geometry cache key '{key}' is not present in the workflow cache."
        )
    return cache[key]


def is_model_key(key: str) -> bool:
    """True for user-referencable cache keys (IFC or generated), excluding intermediates."""
    return split_expr_key(key) is not None or key.startswith("gen:")


def resolve_side(
    context: ExecutionContext,
    *,
    refs: list[int | str] | None = None,
    slug: str | None = None,
) -> list[str]:
    """Resolve a list of mixed references into ordered geometry-cache keys.

    An ``int`` reference is an express ID mapping to ``<slug>:expr:<id>``; a ``str``
    reference is an object ID mapping to ``gen:<object_id>``. Order is preserved.
    When the list is empty the whole referenced model is used: every IFC express key
    for ``slug`` plus any generated ``gen:`` keys, in cache insertion order. Raises
    ``ValueError`` for a reference that has no cached geometry. ``slug`` defaults to
    the execution context's main model.
    """
    cache = _ensure_cache(context)
    refs = refs or []
    resolved_slug = context.resolve_slug(slug)

    if not refs:
        prefix = f"{resolved_slug}:"
        return [
            key for key in cache if key.startswith(prefix) or key.startswith("gen:")
        ]

    keys: list[str] = []
    for ref in refs:
        if isinstance(ref, int):
            key = expr_key(resolved_slug, ref)
            if key not in cache:
                raise ValueError(
                    f"Express ID {ref} has no tessellated geometry in the cache."
                )
        else:
            key = f"gen:{ref}"
            if key not in cache:
                raise ValueError(f"Object ID '{ref}' has no geometry in the cache.")
        keys.append(key)
    return keys


def _is_watertight(mesh: trimesh.Trimesh) -> bool:
    return bool(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0)


def ensure_watertight(
    mesh: trimesh.Trimesh,
) -> tuple[trimesh.Trimesh | None, str | None]:
    if _is_watertight(mesh):
        return mesh, None

    repaired = mesh.copy()
    try:
        repaired.process(validate=True)
        repaired.merge_vertices()
        trimesh.repair.fill_holes(repaired)
        trimesh.repair.fix_normals(repaired)
        trimesh.repair.fix_winding(repaired)
    except Exception:
        pass

    if _is_watertight(repaired):
        return repaired, None

    try:
        vfx = pymeshfix.MeshFix(repaired.vertices, repaired.faces)
        vfx.repair()
        pymesh = trimesh.Trimesh(vertices=vfx.mesh[0], faces=vfx.mesh[1], process=False)
        if _is_watertight(pymesh):
            return pymesh, None
    except Exception:
        pass

    return None, "non-watertight"


def reshape_flat(verts: tuple[float, ...], faces: tuple[int, ...]) -> trimesh.Trimesh:
    vertices = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    face_array = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    return trimesh.Trimesh(vertices=vertices, faces=face_array, process=False)


def _add_alignment_geometry(
    ifc_model: Any,
    cache: dict[str, trimesh.Trimesh],
    settings: Any,
    *,
    slug: str = "main",
    shape_creator: Callable[[Any, Any], Any] | None = None,
) -> None:
    """Add alignment centerline tubes to the geometry cache.

    IfcAlignment entities have no Body representation, so they are skipped by the
    Body-only iterator. This function adds them via a dedicated pass using
    ifcopenshell.geom.create_shape, which tessellates the alignment curve into a
    polyline. The polyline is then converted to a thin tube mesh for compatibility,
    e.g. with generic mesh-mesh distance routines.

    Accuracy: total deviation ≤ tube_radius + tessellation_deviation.
    With ALIGNMENT_TUBE_RADIUS=0.30 mm and tessellation ≤0.10 mm @R=300 m
    (min Radius main track), worst-case error ≈ 0.40 mm (<0.5 mm target).

    Note: the sliver aspect ratio (~4200:1 with 0.5 m chords) is acceptable for
    distance checks; if robustness issues arise, reduce linear-deflection for
    denser chords or adjust the tube radius.

    Args:
        ifc_model: The IFC model.
        cache: The geometry cache dict (modified in place).
        settings: The ifcopenshell geom settings (reuse from build_geometry_cache).
        shape_creator: Callable(settings, element) -> shape with .geometry.verts.
            Defaults to ifcopenshell.geom.create_shape (DI for tests).
    """
    try:
        alignments = ifc_model.by_type("IfcAlignment")
    except Exception:
        return

    shape_creator = shape_creator or ifcopenshell.geom.create_shape

    angles = np.linspace(0, 2 * np.pi, ALIGNMENT_TUBE_SECTIONS, endpoint=False)
    circle_pts = np.column_stack(
        [
            ALIGNMENT_TUBE_RADIUS * np.cos(angles),
            ALIGNMENT_TUBE_RADIUS * np.sin(angles),
        ]
    )
    polygon = Polygon(circle_pts)

    for alignment in alignments:
        try:
            key = expr_key(slug, alignment.id())
            if key in cache:
                continue

            shape = shape_creator(settings, alignment)
            verts = shape.geometry.verts  # pyright: ignore[reportAttributeAccessIssue]
            if len(verts) < 6:
                continue

            verts_np = np.asarray(verts, dtype=np.float64).reshape(-1, 3)

            tube_mesh = trimesh.creation.sweep_polygon(polygon, verts_np)
            cache[key] = tube_mesh
        except Exception:
            continue


def _merge_part_meshes(part_meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Merge part meshes into a single solid, removing internal touching surfaces.

    Uses boolean union (manifold engine) to produce a watertight shell with correct
    surface area. Falls back to concatenate if union fails (volume correct but area
    inflated due to internal faces).
    """
    if len(part_meshes) == 1:
        return part_meshes[0]
    try:
        return trimesh.boolean.union(part_meshes, engine="manifold")
    except Exception:
        return trimesh.util.concatenate(part_meshes)


def _merge_decomposed_parents(
    ifc_model: Any,
    cache: dict[str, trimesh.Trimesh],
    *,
    slug: str = "main",
) -> dict[str, trimesh.Trimesh]:
    """Synthesize geometry for aggregation/nesting parents that have no own body.

    A parent whose immediate parts all have cached geometry (and which itself has
    none) gets an `<slug>:expr:<parent_id>` entry built by merging its parts' meshes
    via boolean union (removing internal touching surfaces). Parents with their own
    geometry are left untouched to avoid double-counting.

    This implementation is recursive and order-independent: nested parents without
    geometry are resolved from their sub-parts before being used by their own parents.
    """
    try:
        rel_types = ["IfcRelAggregates", "IfcRelNests"]
        rels = [rel for rt in rel_types for rel in ifc_model.by_type(rt)]
    except Exception:
        return cache

    decompositions: dict[int, list[Any]] = {}
    for rel in rels:
        parent = getattr(rel, "RelatingObject", None)
        parts = getattr(rel, "RelatedObjects", None) or []
        if parent is None or not parts:
            continue
        parent_id = getattr(parent, "id", None)
        if parent_id is None:
            continue
        decompositions.setdefault(parent_id(), []).extend(parts)

    resolving: set[int] = set()

    def resolve(entity_id: int) -> trimesh.Trimesh | None:
        key = expr_key(slug, entity_id)
        if key in cache:
            return cache[key]
        parts = decompositions.get(entity_id)
        if not parts or entity_id in resolving:
            return None
        resolving.add(entity_id)
        try:
            part_meshes: list[trimesh.Trimesh] = []
            for part in parts:
                part_id = getattr(part, "id", None)
                if part_id is None:
                    return None
                part_mesh = resolve(part_id())
                if part_mesh is None:
                    return None
                part_meshes.append(part_mesh)
            mesh = _merge_part_meshes(part_meshes)
            cache[key] = mesh
            return mesh
        finally:
            resolving.discard(entity_id)

    for parent_id in decompositions:
        resolve(parent_id)

    return cache
