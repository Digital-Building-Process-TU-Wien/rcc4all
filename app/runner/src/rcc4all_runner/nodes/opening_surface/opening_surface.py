from __future__ import annotations

from typing import Any

import numpy as np
import trimesh
from pydantic import Field

from rcc4all_runner.nodes.base import ExecutionContext, NodeModel, node
from rcc4all_runner.nodes.opening_surface._caps import (
    _cap_depth,  # pyright: ignore[reportPrivateUsage]
    _cap_extents,  # pyright: ignore[reportPrivateUsage]
    _cap_groups,  # pyright: ignore[reportPrivateUsage]
    _cap_info,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._host_surface import (
    _reveal_host_mesh,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._loft import (
    _loft_open_ring,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._numeric import (
    _face_normals,  # pyright: ignore[reportPrivateUsage]
    _iter_openings,  # pyright: ignore[reportPrivateUsage]
    _resolve_entity,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.nodes.opening_surface._tube import (
    _close_tube_rings,  # pyright: ignore[reportPrivateUsage]
    _cut_surface_tube,  # pyright: ignore[reportPrivateUsage]
)
from rcc4all_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
    cache_mesh,
    resolve_mesh,
)
from rcc4all_runner.util.references import expr_key, iter_resolved_elements

# A cut-surface tube that closes into a shell enclosing (near-)zero volume is a
# degenerate "pillow" from a host that exposes only two opposite cut surfaces
# (the tube collapses to a zero-thickness band). It is not a real through-bore,
# so it must not be kept as closed_cut_surface; the opening falls through to the
# lofted-caps path, which uses the two true cap faces. Genuine closed tubes on
# the real-world model measure 0.35 m^3 and up; only the degenerate pillow is
# ~1e-16 m^3.
_MIN_CLOSED_TUBE_VOLUME = 1e-6


class OpeningSurface(NodeModel):
    express_id: str = Field(
        title="Express ID",
        description="The qualified opening reference (`<slug>:expr:<id>`).",
    )
    guid: str = Field(
        default="",
        title="GUID",
        description="GlobalId of the opening element, empty when missing.",
    )
    host_express_id: str = Field(
        title="Host express ID",
        description="Qualified reference of the host element the opening voids.",
    )
    geometry_key: str | None = Field(
        default=None,
        title="Geometry key",
        description=(
            "Geometry-cache key (`gen:`) of the retrieved opening closed surface, "
            "or None when it could not be retrieved."
        ),
    )
    method: str | None = Field(
        default=None,
        title="Method",
        description=(
            "How the closed surface was derived: 'closed_cut_surface' (a "
            "through-bore whose cut-surface tube closed watertight), 'lofted_caps' "
            "(the two cap faces were lofted/connected, possibly with a synthesized "
            "second cap), or 'caps_only' (no watertight closed surface; the "
            "cap/tube geometry is emitted unchanged)."
        ),
    )
    watertight: bool = Field(
        default=False,
        title="Watertight",
        description=(
            "Whether the emitted geometry is a closed, winding-consistent, "
            "positive-volume solid."
        ),
    )
    area: float | None = Field(
        default=None,
        title="Area",
        description=(
            "Opening area in the plane of the host surface (the larger cap face), "
            "or None when it could not be retrieved."
        ),
    )
    width: float | None = Field(
        default=None,
        title="Width",
        description=(
            "Horizontal extent of the opening in the host plane, or None when it "
            "could not be retrieved."
        ),
    )
    height: float | None = Field(
        default=None,
        title="Height",
        description=(
            "Vertical extent of the opening in the host plane, or None when it "
            "could not be retrieved."
        ),
    )
    depth: float | None = Field(
        default=None,
        title="Depth",
        description=(
            "Distance between the two cap faces along the host surface normal. "
            "None when only one cap face exists or it could not be retrieved."
        ),
    )
    error: str | None = Field(
        default=None,
        title="Error",
        description="Error reason when the opening closed surface could not be "
        "retrieved.",
    )


class OpeningSurfaceResult(NodeModel):
    opening_count: int = Field(
        title="Opening count",
        description="Number of openings found on the input elements.",
    )
    surface_count: int = Field(
        title="Surface count",
        description=(
            "Number of openings whose closed-surface geometry was retrieved into "
            "the geometry cache."
        ),
    )
    geometry_keys: list[str] = Field(
        default=[],
        title="Geometry keys",
        description=(
            "Geometry-cache keys (`gen:`) of the retrieved opening closed "
            "surfaces, in opening order. Bind to geometry consumers such as "
            "measurement or collision."
        ),
    )
    openings: list[OpeningSurface] = Field(
        default=[],
        title="Openings",
        description="Flat list of openings with their retrieved closed-surface data.",
    )


class OpeningSurfaceInputs(NodeModel):
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "Qualified element references (`<slug>:expr:<id>`) of host building "
            "elements (e.g. walls, slabs, roofs) whose openings are retrieved. "
            "Bind ifc_element_filter output here."
        ),
    )


@node()
async def opening_surface(
    inputs: OpeningSurfaceInputs,
    context: ExecutionContext,
) -> OpeningSurfaceResult:
    openings: list[OpeningSurface] = []
    seen: set[str] = set()

    for element, model in iter_resolved_elements(
        inputs.express_ids, context, node="opening_surface"
    ):
        host = _resolve_entity(model, element.express_id)
        if host is None:
            continue

        for opening_entity in _iter_openings(host):
            opening_ref = expr_key(element.slug, opening_entity.id())
            if opening_ref in seen:
                continue
            seen.add(opening_ref)
            openings.append(
                _opening_surface(
                    context,
                    slug=element.slug,
                    host_ref=element.reference,
                    opening_ref=opening_ref,
                    opening_entity=opening_entity,
                )
            )

    geometry_keys = [
        opening.geometry_key for opening in openings if opening.geometry_key
    ]
    return OpeningSurfaceResult(
        opening_count=len(openings),
        surface_count=len(geometry_keys),
        geometry_keys=geometry_keys,
        openings=openings,
    )


def _opening_surface(
    context: ExecutionContext,
    *,
    slug: str,
    host_ref: str,
    opening_ref: str,
    opening_entity: Any,
) -> OpeningSurface:
    """The watertight closed surface of one opening.

    A through-bore is emitted straight from its closed cut-surface tube. An open
    ring (a door / non-planar rim) is built from the two cap faces on the host's
    dominant surface planes, which are lofted (connected by new side faces) into
    one watertight closed surface. When only one cap face is found, a second cap is
    synthesized by copying the first cap across the wall by its thickness and
    clipping the copy against the tube reveal faces before lofting.
    """
    guid = str(getattr(opening_entity, "GlobalId", "") or "")
    try:
        cutter = resolve_mesh(context, opening_ref)
    except ValueError:
        return _failed(opening_ref, guid, host_ref, "no cached geometry")
    if len(cutter.faces) == 0:
        return _failed(opening_ref, guid, host_ref, "empty opening mesh")

    # The cut-surface tube already closes a through-bore (planar rims). An open
    # ring stays open (its door sill has no host face), so the tube is not
    # watertight and we fall through to the lofted-cap path.
    host_mesh = _reveal_host_mesh(context, host_ref)
    tube: trimesh.Trimesh | None = None
    volume: trimesh.Trimesh | None = None
    method: str | None = None
    cap_info = _cap_info(context, host_ref, cutter)
    if host_mesh is not None:
        tube = _cut_surface_tube(context, host_ref, host_mesh, cutter)
        if (
            tube is not None
            and _is_watertight(tube)
            and _safe_volume(tube) > _MIN_CLOSED_TUBE_VOLUME
        ):
            reclosed = _close_tube_rings(context, host_ref, host_mesh, cutter, cap_info)
            volume = reclosed if reclosed is not None else tube
            method = "closed_cut_surface"

    if volume is None and cap_info is not None:
        vertices, faces, caps, cap_normal, depth = cap_info
        volume = _loft_open_ring(
            vertices, faces, caps, cap_normal, depth, tube, cutter, host_mesh
        )
        if volume is not None:
            method = "lofted_caps"

    if volume is None:
        if cap_info is None:
            return _failed(opening_ref, guid, host_ref, "no planar surfaces")
        vertices, faces, caps = cap_info[0], cap_info[1], cap_info[2]
        # No watertight volume: emit the cap geometry unchanged (diagnostics only).
        cap_face_indices = [index for group in caps for index in group]
        if not cap_face_indices:
            return _failed(opening_ref, guid, host_ref, "no cap faces")
        # Subset the cutter's (n, 3) face array by the cap indices, not a flat
        # list of face ids: passing a 1-D array to trimesh stores a degenerate
        # `faces` that crashes downstream.
        volume = trimesh.Trimesh(
            vertices=vertices,
            faces=np.asarray(faces[cap_face_indices], int),
            process=False,
        )
        method = "caps_only"

    area, width, height, depth = _dims(cap_info, volume)

    geometry_key = cache_mesh(
        context,
        volume,
        object_id=f"opening_surface_{slug}_{opening_entity.id()}",
    )
    return OpeningSurface(
        express_id=opening_ref,
        guid=guid,
        host_express_id=host_ref,
        geometry_key=geometry_key,
        method=method,
        watertight=_is_watertight(volume),
        area=area,
        width=width,
        height=height,
        depth=depth,
    )


def _failed(opening_ref: str, guid: str, host_ref: str, reason: str) -> OpeningSurface:
    return OpeningSurface(
        express_id=opening_ref,
        guid=guid,
        host_express_id=host_ref,
        error=reason,
    )


def _dims(
    cap_info: tuple[np.ndarray, np.ndarray, list[list[int]], np.ndarray, float | None]
    | None,
    volume: trimesh.Trimesh,
) -> tuple[float | None, float | None, float | None, float | None]:
    """``(area, width, height, depth)`` from the cap analysis, or from the volume."""
    if cap_info is None:
        vertices = np.asarray(volume.vertices, dtype=np.float64)
        faces = np.asarray(volume.faces, dtype=np.int64)
        normals = _face_normals(vertices, faces)
        caps = _cap_groups(vertices, faces, normals)
        if not caps:
            return None, None, None, None
        cap_normal = normals[caps[0][0]]
        depth = _cap_depth(vertices, faces, cap_normal, caps)
        return (*_cap_extents(vertices, faces, caps, cap_normal), depth)
    vertices, faces, caps, cap_normal, depth = cap_info
    area, width, height = _cap_extents(vertices, faces, caps, cap_normal)
    return area, width, height, depth
