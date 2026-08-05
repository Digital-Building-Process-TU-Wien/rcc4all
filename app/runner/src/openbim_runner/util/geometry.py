from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import ifcopenshell.geom
import numpy as np
import pymeshfix
import trimesh

from openbim_runner.nodes.base import ExecutionContext

GEOMETRY_LIBRARY = "hybrid-cgal-simple-opencascade"


def build_geometry_cache(
    ifc_model: Any,
    *,
    settings_factory: Callable[..., Any] | None = None,
    shape_iterator: Callable[..., Any] | None = None,
    geometry_library: str = GEOMETRY_LIBRARY,
) -> dict[str, trimesh.Trimesh]:
    """Tessellate the whole IFC model into a geometry cache.

    Dependency-injected for testability: pass fakes for ``settings_factory``
    and ``shape_iterator`` to avoid depending on ifcopenshell. Elements that
    cannot be tessellated are skipped (absent from the returned cache).
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
            geometry = shape.geometry
            if len(geometry.verts) > 0 and len(geometry.faces) > 0:
                express_id = shape.id
                cache[f"ifc:{express_id}"] = reshape_flat(geometry.verts, geometry.faces)
        if not iterator.next():
            break

    return cache


def _ensure_cache(context: ExecutionContext) -> dict[str, trimesh.Trimesh]:
    if context.geometry_cache is None:
        context.geometry_cache = {}
    return context.geometry_cache


def cache_mesh(
    context: ExecutionContext,
    mesh: trimesh.Trimesh,
    *,
    express_id: int | None = None,
    object_id: str | None = None,
    intermediate: bool = False,
    key: str | None = None,
) -> str:
    """Store a mesh in the cache and return its key.

    - ``express_id`` stores an IFC body under ``ifc:<express_id>``.
    - ``object_id`` stores an external/generated geometry under ``gen:<object_id>``.
    - ``intermediate`` stores an internal helper mesh under ``inter:<uuid>`` (excluded
      from the whole-model expansion).
    - ``key`` stores the mesh under an explicit, fully-specified key (e.g. a
      deterministic intermediate key like ``inter:intersection_ifc:1_ifc:2``).

    Exactly one of these must be provided, and the key must not already exist.
    """
    if key is not None:
        if not key:
            raise ValueError("cache_mesh 'key' must be a non-empty string.")
    elif express_id is not None:
        key = f"ifc:{express_id}"
    elif object_id is not None:
        key = f"gen:{object_id}"
    elif intermediate:
        key = f"inter:{uuid.uuid4()}"
    else:
        raise ValueError("cache_mesh requires express_id, object_id, intermediate=True, or a key.")

    cache = _ensure_cache(context)
    if key in cache:
        raise ValueError(f"Geometry cache key '{key}' already exists.")
    cache[key] = mesh
    return key


def resolve_mesh(context: ExecutionContext, key: str) -> trimesh.Trimesh:
    cache = _ensure_cache(context)
    if key not in cache:
        raise ValueError(f"Geometry cache key '{key}' is not present in the workflow cache.")
    return cache[key]


def is_model_key(key: str) -> bool:
    """True for user-referencable cache keys (IFC or generated), excluding intermediates."""
    return key.startswith("ifc:") or key.startswith("gen:")


def resolve_side(context: ExecutionContext, *, refs: list[int | str] | None = None) -> list[str]:
    """Resolve a list of mixed references into ordered geometry-cache keys.

    An ``int`` reference is an express ID mapping to ``ifc:<id>``; a ``str`` reference
    is an object ID mapping to ``gen:<object_id>``. Order is preserved. When the list is
    empty the whole model is used: every user-referencable key in the cache, in cache
    insertion order. Raises ``ValueError`` for a reference that has no cached geometry.
    """
    cache = _ensure_cache(context)
    refs = refs or []

    if not refs:
        return [key for key in cache if is_model_key(key)]

    keys: list[str] = []
    for ref in refs:
        if isinstance(ref, int):
            key = f"ifc:{ref}"
            if key not in cache:
                raise ValueError(f"Express ID {ref} has no tessellated geometry in the cache.")
        else:
            key = f"gen:{ref}"
            if key not in cache:
                raise ValueError(f"Object ID '{ref}' has no geometry in the cache.")
        keys.append(key)
    return keys


def _is_watertight(mesh: trimesh.Trimesh) -> bool:
    return bool(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0)


def ensure_watertight(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh | None, str | None]:
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
        vfx.repair(verbose=False)
        pymesh = trimesh.Trimesh(vertices=vfx.mesh[0], faces=vfx.mesh[1], process=False)
        if _is_watertight(pymesh):
            return pymesh, None
    except Exception:
        pass

    return None, "non-watertight"


def reshape_flat(verts: tuple[float, ...], faces: tuple[int, ...]) -> trimesh.Trimesh:
    vertices = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    face_array = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    return trimesh.Trimesh(vertices=vertices, faces=face_array, process=True)
