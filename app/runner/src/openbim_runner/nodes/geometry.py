from __future__ import annotations

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel


class Geometry(NodeModel):
    key: str = Field(
        title="Cache Key",
        description="Key into the workflow-scoped geometry cache holding the trimesh mesh.",
    )
    express_id: int | None = Field(
        default=None,
        title="Express ID",
        description="IFC express ID of the source element, or None for workflow-generated geometry.",
    )


def _ensure_cache(context: ExecutionContext) -> dict[str, trimesh.Trimesh]:
    if context.geometry_cache is None:
        context.geometry_cache = {}
    return context.geometry_cache


def cache_mesh(
    context: ExecutionContext,
    mesh: trimesh.Trimesh,
    express_id: int | None = None,
) -> Geometry:
    key = f"ifc:{express_id}" if express_id is not None else f"gen:{_uuid4()}"
    _ensure_cache(context)[key] = mesh
    return Geometry(key=key, express_id=express_id)


def resolve_mesh(context: ExecutionContext, geometry: Geometry) -> trimesh.Trimesh:
    cache = _ensure_cache(context)
    if geometry.key not in cache:
        raise ValueError(f"Geometry cache key '{geometry.key}' is not present in the workflow cache.")
    return cache[geometry.key]


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
        import pymeshfix

        vfx = pymeshfix.MeshFix(repaired.vertices, repaired.faces)
        vfx.repair(verbose=False)
        pymesh = trimesh.Trimesh(vertices=vfx.mesh[0], faces=vfx.mesh[1], process=False)
        if _is_watertight(pymesh):
            return pymesh, None
    except Exception:
        pass

    return None, "non-watertight"


def _uuid4() -> str:
    from uuid import uuid4

    return str(uuid4())


def reshape_flat(verts: tuple[float, ...], faces: tuple[int, ...]) -> trimesh.Trimesh:
    vertices = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    face_array = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    return trimesh.Trimesh(vertices=vertices, faces=face_array, process=True)
