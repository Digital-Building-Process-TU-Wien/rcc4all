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


def _aabb_overlap(a: trimesh.Trimesh, b: trimesh.Trimesh) -> bool:
    a_min, a_max = a.bounds
    b_min, b_max = b.bounds
    return bool(np.all(a_min <= b_max) and np.all(b_min <= a_max))


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

    for key_a in keys_a:
        for key_b in keys_b:
            if key_a == key_b:
                continue

            mesh_a = resolve_mesh(context, key_a)
            mesh_b = resolve_mesh(context, key_b)

            if not _aabb_overlap(mesh_a, mesh_b):
                continue

            repaired_a, error_a = ensure_watertight(mesh_a)
            repaired_b, error_b = ensure_watertight(mesh_b)
            if repaired_a is None or repaired_b is None:
                errors.append(CollisionError(key_a=key_a, key_b=key_b, error="non-watertight"))
                continue

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = trimesh.boolean.intersection(
                        [repaired_a, repaired_b],
                        engine="manifold",
                        check_volume=False,
                    )
            except Exception as exc:
                errors.append(CollisionError(key_a=key_a, key_b=key_b, error=f"boolean failed: {exc}"))
                continue

            if result is not None and len(result.faces) > 0 and result.volume > VOLUME_TOLERANCE:
                collisions.setdefault(key_a, []).append(key_b)
                if settings.mode == "intersection_mesh":
                    cache_mesh(context, result, key=f"inter:intersection_{key_a}_{key_b}")

    return CollisionResult(collisions=collisions, errors=errors)
