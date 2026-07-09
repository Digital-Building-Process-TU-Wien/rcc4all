from __future__ import annotations

import warnings

import numpy as np
import trimesh
import trimesh.boolean
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.geometry import Geometry, cache_mesh, ensure_watertight, resolve_mesh

VOLUME_TOLERANCE = 1e-9


class CollisionSettings(NodeModel):
    include_intersection_mesh: bool = Field(
        default=False,
        title="Include intersection mesh",
        description=(
            "When enabled, colliding pairs store the intersection mesh in the geometry cache "
            "and carry an intersection_key handle. Enables a future workflow extension "
            "that writes intersection geometry back as IFC."
        ),
    )


class CollisionInputs(NodeModel):
    geometries_a: list[Geometry] = Field(
        default=[],
        title="Geometries A",
        description="First list of geometry handles.",
    )
    geometries_b: list[Geometry] = Field(
        default=[],
        title="Geometries B",
        description="Second list of geometry handles, paired pairwise with A.",
    )


class CollisionPair(NodeModel):
    index: int = Field(title="Index", description="Zero-based pair index within the result.")
    key_a: str = Field(title="Key A", description="Cache key of the first geometry in the pair.")
    key_b: str = Field(title="Key B", description="Cache key of the second geometry in the pair.")
    express_id_a: int | None = Field(default=None, title="Express ID A", description="IFC express ID of the first geometry, or None.")
    express_id_b: int | None = Field(default=None, title="Express ID B", description="IFC express ID of the second geometry, or None.")
    collides: bool | None = Field(
        default=None,
        title="Collides",
        description="True if the pair intersects with positive volume, False if disjoint. None if undecidable (see error).",
    )
    intersection_volume: float | None = Field(
        default=None,
        title="Intersection volume",
        description="Volume of the intersection mesh when colliding, otherwise None.",
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason when collides is None, e.g. 'non-watertight' or 'boolean failed: ...'.",
    )
    intersection_key: str | None = Field(
        default=None,
        title="Intersection key",
        description="Geometry-cache handle for the intersection mesh, only when include_intersection_mesh is enabled and the pair collides. Enables a future workflow extension that writes intersection geometry back as IFC.",
    )


class CollisionResult(NodeModel):
    pairs: list[CollisionPair] = Field(
        default=[],
        title="Pairs",
        description="One record per paired geometry pair (zip by index).",
    )


def _pair(geometries_a: list[Geometry], geometries_b: list[Geometry]) -> list[tuple[Geometry, Geometry]]:
    len_a = len(geometries_a)
    len_b = len(geometries_b)

    if len_a == len_b:
        return list(zip(geometries_a, geometries_b, strict=True))

    raise ValueError(
        f"Geometry list length mismatch: A has {len_a} elements, B has {len_b} elements. "
        "Equal lengths required."
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
    pairs_input = _pair(inputs.geometries_a, inputs.geometries_b)
    pairs: list[CollisionPair] = []

    for index, (geo_a, geo_b) in enumerate(pairs_input):
        mesh_a = resolve_mesh(context, geo_a)
        mesh_b = resolve_mesh(context, geo_b)

        pair = CollisionPair(
            index=index,
            key_a=geo_a.key,
            key_b=geo_b.key,
            express_id_a=geo_a.express_id,
            express_id_b=geo_b.express_id,
        )

        if not _aabb_overlap(mesh_a, mesh_b):
            pair.collides = False
            pairs.append(pair)
            continue

        repaired_a, error_a = ensure_watertight(mesh_a)
        repaired_b, error_b = ensure_watertight(mesh_b)
        if repaired_a is None or repaired_b is None:
            pair.collides = None
            pair.error = "non-watertight"
            pairs.append(pair)
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
            pair.collides = None
            pair.error = f"boolean failed: {exc}"
            pairs.append(pair)
            continue

        collides = bool(
            result is not None and len(result.faces) > 0 and result.volume > VOLUME_TOLERANCE
        )
        pair.collides = collides
        if collides and result is not None:
            pair.intersection_volume = float(result.volume)
            if settings.include_intersection_mesh:
                handle = cache_mesh(context, result)
                pair.intersection_key = handle.key

        pairs.append(pair)

    return CollisionResult(pairs=pairs)
