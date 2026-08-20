from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import trimesh
import trimesh.boolean
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import (
    cache_mesh,
    ensure_watertight,
    resolve_mesh,
    resolve_side,
)

VOLUME_TOLERANCE = 1e-9


class CollisionSettings(NodeModel):
    mode: Literal["boolean", "intersection_mesh"] = Field(
        default="boolean",
        title="Mode",
        description=(
            "'boolean' reports which pairs collide without storing intersection geometry. "
            "'intersection_mesh' additionally stores each collision's intersection mesh in the "
            "geometry cache under a deterministic key (documented in the README)."
        ),
    )


class CollisionInputs(NodeModel):
    list_a: list[int | str] = Field(
        default=[],
        title="List A",
        description=(
            "First list of references — mix of express IDs (int → `ifc:<id>`) and object IDs "
            "(str → `gen:<id>`), in the order to test. When empty, the whole model is used."
        ),
    )
    list_b: list[int | str] = Field(
        default=[],
        title="List B",
        description=(
            "Second (optional) list of references — mix of express IDs (int → `ifc:<id>`) and "
            "object IDs (str → `gen:<id>`). When empty, the whole model is used as the counterpart set."
        ),
    )


class CollisionError(NodeModel):
    key_a: str = Field(title="Key A", description="Cache key of the first geometry in the failed pair.")
    key_b: str = Field(title="Key B", description="Cache key of the second geometry in the failed pair.")
    error: str = Field(
        title="Error",
        description="Error reason, e.g. 'non-watertight' or 'boolean failed: ...'.",
    )


class CollisionResult(NodeModel):
    collisions: dict[str, list[str]] = Field(
        default={},
        title="Collisions",
        description="Grouped by side-A cache key; each value lists the side-B cache keys it collides with. Only colliding pairs are included.",
    )
    errors: list[CollisionError] = Field(
        default=[],
        title="Errors",
        description="Pairs whose collision could not be decided (e.g. non-watertight or boolean failure).",
    )
    intersection_meshes: dict[str, str | None] = Field(
        default={},
        title="Intersection Meshes",
        description=(
            "Only populated in 'intersection_mesh' mode. Maps a pair key "
            "'{key_a}__{key_b}' to the geometry-cache key "
            "'inter:intersection_{key_a}_{key_b}' under which the intersection mesh was stored. "
            "A null value signals an FCL-decided collision (mesh non-repairable or boolean "
            "failed) for which no intersection mesh could be generated. Empty in 'boolean' mode."
        ),
    )


def _aabb_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh) -> bool:
    a_min, a_max = a.bounds
    b_min, b_max = b.bounds
    return bool(np.all(a_min <= b_max) and np.all(b_min <= a_max))


def _fcl_collision(mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> bool | None:
    """Triangle-based collision test via FCL (no watertight requirement).

    Returns True if the meshes collide, False if not, or None when FCL is
    unavailable (graceful degradation: caller falls through to ``errors``).
    """
    try:
        from trimesh.collision import CollisionManager
    except Exception:
        return None
    try:
        manager = CollisionManager()
        manager.add_object("a", mesh_a)
        manager.add_object("b", mesh_b)
        return bool(manager.in_collision_internal())
    except Exception:
        return None


@node()
async def collision(
    settings: CollisionSettings,
    inputs: CollisionInputs,
    context: ExecutionContext,
) -> CollisionResult:
    keys_a = resolve_side(context, refs=inputs.list_a)
    keys_b = resolve_side(context, refs=inputs.list_b)

    collisions: dict[str, list[str]] = {}
    errors: list[CollisionError] = []
    intersection_meshes: dict[str, str | None] = {}

    for key_a in keys_a:
        for key_b in keys_b:
            if key_a == key_b:
                continue

            mesh_a = resolve_mesh(context, key_a)
            mesh_b = resolve_mesh(context, key_b)

            if not _aabb_overlap(mesh_a, mesh_b):
                continue

            repaired_a, _error_a = ensure_watertight(mesh_a)
            repaired_b, _error_b = ensure_watertight(mesh_b)

            boolean_error: str | None = None
            result: trimesh.Trimesh | None = None
            if repaired_a is None or repaired_b is None:
                boolean_error = "non-watertight"
            else:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        result = trimesh.boolean.intersection(
                            [repaired_a, repaired_b],
                            engine="manifold",
                            check_volume=False,
                        )
                except Exception as exc:
                    boolean_error = f"boolean failed: {exc}"

            if boolean_error is not None:
                fcl_result = _fcl_collision(mesh_a, mesh_b)
                if fcl_result is True:
                    collisions.setdefault(key_a, []).append(key_b)
                    if settings.mode == "intersection_mesh":
                        intersection_meshes[f"{key_a}__{key_b}"] = None
                elif fcl_result is None:
                    errors.append(CollisionError(key_a=key_a, key_b=key_b, error=boolean_error))
                continue

            if result is not None and len(result.faces) > 0 and result.volume > VOLUME_TOLERANCE:
                collisions.setdefault(key_a, []).append(key_b)
                if settings.mode == "intersection_mesh":
                    inter_key = f"inter:intersection_{key_a}_{key_b}"
                    cache_mesh(context, result, key=inter_key)
                    intersection_meshes[f"{key_a}__{key_b}"] = inter_key

    return CollisionResult(
        collisions=collisions,
        errors=errors,
        intersection_meshes=intersection_meshes,
    )
