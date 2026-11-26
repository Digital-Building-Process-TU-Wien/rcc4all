from __future__ import annotations

import math
import warnings
import weakref
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import trimesh
from pydantic import Field
from shapely.geometry import MultiPoint

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import (
    _is_watertight,  # pyright: ignore[reportPrivateUsage]
    _safe_fix_normals,  # pyright: ignore[reportPrivateUsage]
    _safe_volume,  # pyright: ignore[reportPrivateUsage]
    cache_mesh,
    ensure_watertight,
    reshape_flat,
    resolve_mesh,
)
from openbim_runner.util.references import (
    expr_key,
    iter_resolved_elements,
    split_expr_key,
)

# A tube face roughly perpendicular to the cap normal is a reveal face; it bounds
# the hole laterally. Faces closer to parallel are the caps themselves and must
# not clip the offset far ring.
_REVEAL_PARALLEL_COS = 0.8

# A ring edge is a mid-wall jog (a step through a layer interface) when it is
# essentially parallel to the cap normal. Such edges never lie flat in a single
# plane, so they are capping with the dedicated jogged-ring closure; a folded-
# roof skylight's rim edges are not parallel to the caps and fall through to the
# plane decomposition.
_AXIAL_EDGE_COS = 0.99

# Wall thickness below which lofting two cap faces collapses into a flat sliver;
# those thin openings keep their closed cut-surface tube instead.
_MIN_LOFT_DEPTH = 0.05

# A cut-surface tube that closes into a shell enclosing (near-)zero volume is a
# degenerate "pillow" from a host that exposes only two opposite cut surfaces
# (the tube collapses to a zero-thickness band). It is not a real through-bore,
# so it must not be kept as closed_cut_surface; the opening falls through to the
# lofted-caps path, which uses the two true cap faces. Genuine closed tubes on
# the real-world model measure 0.35 m^3 and up; only the degenerate pillow is
# ~1e-16 m^3.
_MIN_CLOSED_TUBE_VOLUME = 1e-6

# --- Cut-surface tube / bore-closure helpers ---------------------------------
_PLANE_COS = math.cos(math.radians(1.0))
_PLANE_TOLERANCE = 0.02
_CONTAINMENT_EPS = 0.02
_REVEAL_GEOMETRY_LIBRARY: ifcopenshell.geom.GEOMETRY_LIBRARY = "cgal"
_REVEAL_HOST_MEMO: weakref.WeakKeyDictionary[
    ExecutionContext, dict[str, trimesh.Trimesh | None]
] = weakref.WeakKeyDictionary()
_MIN_CAP_LOOP = 3
_COINCIDENT_VERTS_EPS = 1e-3
_CAP_PLANAR_TOLERANCE = 0.03
_CAP_PLANE_TOLERANCE = 0.03
# A cap-ring vertex is a redundant sliver when the two edges meeting at it run
# in nearly the same direction (the path is almost straight through it) and one
# of those edges is only a short stub; collapsing it recovers the true polygon
# without changing the shape. Used when the two rims do not pair up cleanly —
# unequal vertex counts, or equal counts whose rings are not congruent (see
# ``_loft_caps_watertight``).
_COLLINEAR_COS = math.cos(math.radians(8.0))
_SLIVER_EDGE_LEN = 0.05

# Two equal-length cap rims bridge directly (the detected cap faces preserved
# verbatim) only when they are congruent: every vertex then maps to its
# counterpart at a pure offset along the cap normal, leaving no displacement
# inside the cap plane. Degenerate mirror-image rims (bevel slivers on different
# corners) leave some pairs displaced in-plane after any cyclic shift; when that
# displacement exceeds this fraction of the rims' in-plane extent a direct
# bridge would twist, so the rims are cleaned and — when that recovers
# congruent rings — re-lofted instead. Genuine congruent rims on the real-world
# model measure ~0.02 of extent; the degenerate ones measure 0.4 and up.
_TWIST_INPLANE_RATIO = 0.15

# --- Opening cap-face / host-surface helpers ---------------------------------
_ALIGNED_COS = math.cos(math.pi / 180.0)
_SURFACE_PLANE_TOLERANCE = 0.01
_OPPOSING_COS = -math.cos(math.radians(10.0))
_PARALLEL_COS = math.cos(math.radians(10.0))
_MIN_SLAB_THICKNESS = 0.01
_CLIP_EPSILON = 0.02
_HORIZONTAL_COS = 0.999
_SURFACE_REGION_COS = math.cos(math.radians(3.0))
_CURVED_REGION_COS = math.cos(math.radians(2.0))
_CAP_VERTICAL_COS = math.cos(math.radians(45.0))
_OPENING_PERPENDICULAR_COS = math.cos(math.radians(60.0))
_CURVED_HOST_MIN_SHARE = 0.25
# A curved (faceted) host wall can sit the hole cap plane noticeably proud of the
# outer facet centroids, so the outer->inner facet span under-reads the wall and
# the generated void is left too shallow. When the cap plane is this far beyond
# the facet span, re-measure the depth from the cap plane out to the innermost
# host surface instead; a near-flush cap leaves the facet-span depth unchanged.
_CAP_PROUD_TOL = 0.08


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


def _select_cut_faces(
    host_mesh: trimesh.Trimesh, cutter: trimesh.Trimesh
) -> trimesh.Trimesh | None:
    """The open cut-surface tube: the host faces that bound the bore.

    This is the selection half of the cut-surface tube closure, kept locally so
    the volume path can cap the bore's own rings instead of the centroid fans
    ``_close_bore`` adds. A host face is a cut face when a cutter
    face is coplanar with it (normal and plane position within tolerance) and the
    host face's footprint lies inside a cutter surface's footprint on that plane.
    Returns the raw open tube (unclosed), or ``None`` when no face is selected.
    """
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    cutter_vertices = np.asarray(cutter.vertices, dtype=np.float64)
    cutter_faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(host_faces) == 0 or len(cutter_faces) == 0:
        return None

    host_normals = _face_normals(host_vertices, host_faces)
    cutter_normals = _face_normals(cutter_vertices, cutter_faces)

    cutter_surfaces: list[
        tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any]
    ] = []
    for group in _planar_groups(cutter_vertices, cutter_faces, cutter_normals):
        surface = _planar_surface(cutter_vertices, cutter_faces, cutter_normals, group)
        if surface is not None:
            cutter_surfaces.append(surface)

    host_first_points = host_vertices[host_faces[:, 0]]
    selected = np.zeros(len(host_faces), dtype=bool)
    for cutter_normal, cutter_offset, cutter_axes, cutter_footprint in cutter_surfaces:
        coplanar = (np.abs(host_normals @ cutter_normal) >= _PLANE_COS) & (
            np.abs(host_first_points @ cutter_normal - cutter_offset)
            <= _PLANE_TOLERANCE
        )
        if not coplanar.any():
            continue
        for index in np.flatnonzero(coplanar):
            if _footprint_contained(
                host_vertices, host_faces[index], cutter_axes, cutter_footprint
            ):
                selected[index] = True
    if not selected.any():
        return None
    return trimesh.Trimesh(
        vertices=host_vertices, faces=host_faces[selected], process=False
    )


def _close_tube_rings(
    context: ExecutionContext,
    host_ref: str,
    host_mesh: trimesh.Trimesh,
    cutter: trimesh.Trimesh,
    cap_info: tuple[Any, ...] | None,
) -> trimesh.Trimesh | None:
    """Re-close the bore's rim rings, or return None.

    A decomposed multi-layer host (Zementputz / Stahlbeton / EPS) exposes a
    layer-interface plate between the caps, so the bore's rim is jogged: its
    edges span several planes (the caps, the layer interface, and the
    perpendicular reveal step). ``_close_bore`` caps such a rim with a centroid
    fan, which closes the wrong bore. This rebuilds the open tube from the host
    faces (`_select_cut_faces`) and caps each rim ring from the planes its own
    edges lie in: every run of consecutive in-plane edges becomes a flat cap in
    its plane closed by a new chord, and the perpendicular step bands become
    faces in the plane of the axial edges, with new edges created at the vertices
    where edges of different planes coincide. A ring with no axial step is a
    plain rim (a planar cross-section, or a folded-roof skylight rim spanning two
    host planes); it is capped by the ``_loop_cap_groups`` plane decomposition.

    Returns ``None`` when re-capping is not watertight, so the caller keeps the
    original (fan-)closed tube.
    """
    if cap_info is None:
        return None
    open_tube = _select_cut_faces(host_mesh, cutter)
    if open_tube is None or len(open_tube.faces) == 0:
        return None
    welded = _weld_rim(open_tube)
    if welded is None:
        return None
    welded = _prune_flaps(welded)
    if welded is None:
        return None
    loops = _boundary_loops(welded)
    if not loops:
        return None
    cap_normal = np.asarray(cap_info[3], dtype=np.float64)
    length = float(np.linalg.norm(cap_normal))
    if length <= 0.0:
        return None
    ncap = cap_normal / length

    vertices = np.asarray(welded.vertices, dtype=np.float64)
    faces = np.asarray(welded.faces, dtype=np.int64)
    return _build_ring_closed(
        vertices, faces, loops, ncap, context=context, host_ref=host_ref
    )


def _build_ring_closed(
    vertices: np.ndarray,
    faces: np.ndarray,
    loops: list[list[int]],
    ncap: np.ndarray,
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> trimesh.Trimesh | None:
    """Build the closed mesh by capping every loop from its plane groups; None when not watertight."""
    edge_traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_traversal.setdefault(_edge_key((u, v)), (u, v))
    cap_vertices = [vertices[i] for i in range(len(vertices))]
    cap_faces = [list(f) for f in faces]
    for ring in loops:
        groups = _ring_cap_groups(vertices, faces, ring, ncap, context, host_ref)
        if not groups:
            return None
        for group in groups:
            group_ids = np.asarray(group, dtype=int)
            if len(group_ids) < 3:
                return None
            apex_index = len(cap_vertices)
            cap_vertices.append(vertices[group_ids].mean(axis=0))
            _add_cap_fan(cap_faces, edge_traversal, group_ids, apex_index)
    closed = trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )
    if not _safe_fix_normals(closed):
        return None
    if closed.is_winding_consistent and _safe_volume(closed) < 0:
        closed.faces = closed.faces[:, ::-1]
    return closed if _is_watertight(closed) else None


def _ring_cap_groups(
    vertices: np.ndarray,
    faces: np.ndarray,
    ring: list[int],
    ncap: np.ndarray,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> list[np.ndarray]:
    """The planar cap polygons of one rim ring.

    A ring with an axial-step edge (a mid-wall jog) is decomposed into one flat
    cap plane group per run of consecutive in-plane edges plus one band group for
    the axial steps. A ring with no axial step is a plain rim and is decomposed
    by ``_loop_cap_groups`` (a planar ring yields a single group, a folded-roof
    skylight rim one group per host surface plane).
    """
    if not _ring_has_axial_edge(vertices, ring, ncap):
        groups = _loop_cap_groups(
            vertices, faces, np.asarray(ring, int), context=context, host_ref=host_ref
        )
        return groups if groups else []
    return _jogged_ring_groups(vertices, ring, ncap)


def _ring_has_axial_edge(
    vertices: np.ndarray, ring: list[int], ncap: np.ndarray
) -> bool:
    """Whether any edge of the ring runs parallel to the cap normal."""
    n = len(ring)
    for k in range(n):
        d = vertices[ring[(k + 1) % n]] - vertices[ring[k]]
        length = float(np.linalg.norm(d))
        if length > 0.0 and abs(float(d @ ncap)) / length > _AXIAL_EDGE_COS:
            return True
    return False


def _jogged_ring_groups(
    vertices: np.ndarray, ring: list[int], ncap: np.ndarray
) -> list[np.ndarray]:
    """The planar cap polygons of a jogged ring.

    The ring is rotated onto an axial edge, then split into maximal runs of
    consecutive non-axial (in-plane) edges and maximal axial chains. Every in-
    plane run of two or more edges becomes one flat cap polygon (its run closed by
    a new chord in that plane); the axial chains collapse into the band polygon:
    walking the ring keeps the chain vertices and replaces each in-plane run by a
    jump to its far endpoint, so the band is one planar polygon closed by the new
    chords at the vertices where the planes of adjacent edges coincide.
    """
    n = len(ring)
    axial = [
        (
            float(np.linalg.norm(vertices[ring[(k + 1) % n]] - vertices[ring[k]])) > 0.0
            and abs(float((vertices[ring[(k + 1) % n]] - vertices[ring[k]]) @ ncap))
            / float(np.linalg.norm(vertices[ring[(k + 1) % n]] - vertices[ring[k]]))
            > _AXIAL_EDGE_COS
        )
        for k in range(n)
    ]
    start = axial.index(True)
    ring = ring[start:] + ring[:start]
    axial = axial[start:] + axial[:start]

    groups: list[tuple[str, int, int]] = []
    k = 0
    while k < n:
        j = k
        while j < n and axial[j]:
            j += 1
        if j > k:
            groups.append(("chain", k, j - k))
            k = j
        while j < n and not axial[j]:
            j += 1
        if j > k:
            groups.append(("run", k, j - k))
            k = j

    polys: list[np.ndarray] = []
    for kind, st, ln in groups:
        if kind == "run" and ln >= 2:
            polys.append(np.asarray([ring[(st + i) % n] for i in range(ln + 1)], int))

    band: list[int] = []
    for kind, st, ln in groups:
        if kind == "chain":
            band.extend(ring[(st + i) % n] for i in range(ln + 1))
        else:
            band.append(ring[(st + ln) % n])
    deduplicated: list[int] = [band[0]]
    for v in band[1:]:
        if v != deduplicated[-1]:
            deduplicated.append(v)
    if len(deduplicated) > 2 and deduplicated[-1] == deduplicated[0]:
        deduplicated.pop()
    if len(deduplicated) >= 3:
        polys.append(np.asarray(deduplicated, int))
    return polys


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


def _cap_info(
    context: ExecutionContext, host_ref: str, cutter: trimesh.Trimesh
) -> tuple[np.ndarray, np.ndarray, list[list[int]], np.ndarray, float | None] | None:
    """The opening's cap faces ``(vertices, faces, caps, cap_normal, depth)``.

    The cutter is clipped to the host surface slab (or analysed via the
    curved-host path) and its host-parallel cap faces are returned, together
    with the shared cap normal and the host thickness.
    Returns ``None`` when the cutter exposes no planar cap surface.
    """
    vertices = np.asarray(cutter.vertices, dtype=np.float64)
    faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(faces) == 0:
        return None
    normals = _face_normals(vertices, faces)

    caps = _cap_groups(vertices, faces, normals)
    depth: float | None = None
    if caps:
        curved = _curved_host_caps(context, host_ref, vertices, faces, normals)
        if curved is not None:
            caps, depth = curved
        else:
            clipped = _clip_parallel_caps(
                context, host_ref, cutter, vertices, faces, normals, caps
            )
            if clipped is not None:
                vertices, faces, normals, caps = clipped

    if not caps:
        return None
    cap_normal = normals[caps[0][0]]
    if depth is None:
        depth = _cap_depth(vertices, faces, cap_normal, caps)
    return vertices, faces, caps, cap_normal, depth


def _cap_extents(
    vertices: np.ndarray,
    faces: np.ndarray,
    caps: list[list[int]],
    cap_normal: np.ndarray,
) -> tuple[float | None, float | None, float | None]:
    """``(area, width, height)`` of the cap faces in the host plane."""
    cap_indices = [index for group in caps for index in group]
    cap_points = vertices[np.unique(faces[cap_indices])]
    axis_u, axis_v = _in_plane_axes(cap_normal)
    area = max(_group_area(vertices, faces, group) for group in caps)
    width = float(np.ptp(cap_points @ axis_u))
    height = float(np.ptp(cap_points @ axis_v))
    return area, width, height


def _loft_open_ring(
    vertices: np.ndarray,
    faces: np.ndarray,
    caps: list[list[int]],
    cap_normal: np.ndarray,
    depth: float | None,
    tube: trimesh.Trimesh | None,
    cutter: trimesh.Trimesh | None = None,
    host: trimesh.Trimesh | None = None,
) -> trimesh.Trimesh | None:
    """The watertight volume lofted between the opening's two cap faces.

    The cap faces are split into a front and a back cluster by their offset along
    the cap normal. When both sides of the opening have cap faces, the two caps
    are kept exactly as they were detected (only new side faces bridge their
    boundary rings, connected in 3D). When the cap faces occupy only one side of
    the opening, a second ring is synthesized by copying the found ring across
    the wall by ``depth`` and clipping the copy against the tube reveal faces,
    and both caps are rebuilt from the derived rings. Returns ``None`` when no
    watertight closed surface can be built.
    """
    cap_face_indices = [index for group in caps for index in group]
    if not cap_face_indices:
        return None
    cap_faces = faces[cap_face_indices]
    offsets = vertices[cap_faces[:, 0]] @ cap_normal
    front: list[int] = []
    back: list[int] = []
    if float(offsets.max() - offsets.min()) <= 1e-9:
        front = list(cap_face_indices)
    else:
        mid = 0.5 * (float(offsets.min()) + float(offsets.max()))
        for index, offset in zip(cap_face_indices, offsets, strict=True):
            (back if float(offset) > mid else front).append(index)

    if front and back:
        front_ring = _outer_ring(vertices, faces, front)
        back_ring = _outer_ring(vertices, faces, back)
        if front_ring is None or back_ring is None:
            return None
        return _loft_caps_watertight(
            vertices, faces, front, back, front_ring, back_ring
        )

    # Only one cap side: synthesize the opposing cap across the wall thickness.
    side = front or back
    ring = _outer_ring(vertices, faces, side)
    if ring is None or depth is None or depth <= 0.0:
        return None
    near_ring = vertices[np.asarray(ring, int)]

    # A degenerate wedge (a coarse single-cap opening, e.g. an extruded opening
    # solid that tapers across the wall) exposes only one host-parallel cap whose
    # source solid does not represent the true void. Clipping that wedge against
    # the curved host wall produced a faceted shell (the malformed 20+ surface
    # "tent"), so the cap is instead rebuilt as a clean prism spanning the two
    # host wall faces: each ring vertex is projected along its adjacent reveal
    # planes to the near and far wall face, which preserves the wedge's per-side
    # taper (the angle+distance construction) and orients the void INTO the wall.
    # Genuine through-openings (clean prisms with two opposing caps) never reach
    # this branch, and openings on an already-voided host keep their behaviour.
    if cutter is not None and host is not None and _is_degenerate_wedge(cutter):
        faces_off = _wall_faces_along(cap_normal, near_ring.mean(axis=0), host)
        if faces_off is not None:
            near_off, far_off = faces_off
        elif depth > 0.0:
            # The ray from a proud cap can miss the host (an angled or thin wall).
            # Fall back to the host thickness already measured by ``_cap_info``:
            # the near cap sits at the source cap plane and the far cap crosses the
            # wall by ``depth`` into the host.
            ncap = np.asarray(cap_normal, dtype=np.float64)
            ncap = ncap / np.linalg.norm(ncap)
            near_off = float(np.mean(near_ring @ ncap))
            far_off = near_off - depth
        else:
            near_off = far_off = None
        if near_off is not None and far_off is not None:
            prism = _tapered_prism(
                vertices, faces, ring, caps, cap_normal, near_off, far_off
            )
            if prism is not None and _is_watertight(prism):
                return prism
        # The ray (or side-plane construction) cannot recover the void. Extrude the
        # host-parallel cap flat across the wall INTO the host -- away from the
        # outward ``cap_normal`` that the old ``+depth`` extrusion used to point
        # outside the wall -- so the wedge still closes into a sound prism instead
        # of a centroid fan.
        return _extrude_ring(near_ring, -depth * cap_normal)

    # Genuine open ring (a floor-reaching door / non-planar rim): keep the tube
    # reveal-band clip, which bounds the synthesized far cap to the wall opening.
    far_ring = near_ring + depth * cap_normal
    if tube is not None:
        far_ring = _cut_ring_by_tube(near_ring, far_ring, tube, cap_normal)
    return _loft_polygons(near_ring, far_ring)


def _is_degenerate_wedge(cutter: trimesh.Trimesh) -> bool:
    """Whether ``cutter`` is a coarse single-cap wedge rather than a fit opening.

    A class-B opening is authored as a low-poly degenerate solid (6 vertices): a
    door/window cross-section that tapers to a point or collapses towards a thin
    sliver instead of the clean prism a proper through-opening would expose. It
    reaches the single-cap loft path because its cut-surface tube never closes to
    a watertight bore. A genuine (clean) opening solid orders many more vertices,
    so a low vertex count is the reliable signature of the malformed wedge.
    """
    vertices = np.asarray(cutter.vertices)
    return len(vertices) >= 3 and len(vertices) <= 8


def _wall_faces_along(
    cap_normal: np.ndarray, cap_centroid: np.ndarray, host: trimesh.Trimesh
) -> tuple[float, float] | None:
    """The two host wall-face offsets bounding the opening along ``cap_normal``.

    Casts a ray from ``cap_centroid`` into the wall (along ``-cap_normal``, the
    direction away from the outward-facing cap) and returns the cap-normal offsets
    of the nearest and farthest *distinct* host surface crossed -- the two sides of
    the host wall the void spans. Coincident faces (a doubly-tessellated host
    surface) are de-duplicated, so a curved wall's outermost and innermost surfaces
    are used rather than its doubled facets. Returns ``None`` when the host is not
    crossed twice (an already-voided or oblique host).
    """
    ncap = np.asarray(cap_normal, dtype=np.float64)
    ncap = ncap / np.linalg.norm(ncap)
    hv = np.asarray(host.vertices, dtype=np.float64)
    hf = np.asarray(host.faces, dtype=np.int64)
    if len(hf) == 0:
        return None
    hmesh = trimesh.Trimesh(vertices=hv, faces=hf, process=False, validate=False)
    try:
        loc, _ridx, _tri = hmesh.ray.intersects_location(
            np.array([cap_centroid], dtype=np.float64),
            np.array([-ncap]),
            multiple_hits=True,
        )
    except Exception:
        return None
    if len(loc) == 0:
        return None
    cap_off = float(np.asarray(cap_centroid) @ ncap)
    offs = np.asarray(loc, dtype=np.float64) @ ncap
    distinct: dict[float, float] = {}
    for key, val in zip(np.round(offs, 4), offs, strict=True):
        distinct.setdefault(float(key), float(val))
    into = sorted(val for val in distinct.values() if val < cap_off)
    if len(into) < 2:
        return None
    near_off, far_off = float(max(into)), float(min(into))
    if abs(near_off - far_off) < _MIN_LOFT_DEPTH:
        return None
    return near_off, far_off


def _tapered_prism(
    vertices: np.ndarray,
    faces: np.ndarray,
    ring: list[int],
    caps: list[list[int]],
    cap_normal: np.ndarray,
    near_off: float,
    far_off: float,
) -> trimesh.Trimesh | None:
    """A watertight prism for a degenerate wedge between two host-parallel planes.

    Each ring vertex is projected along its two adjacent wedge side faces to the
    near and far wall-face planes, so the two caps keep the wedge's per-side taper
    (the angle+distance construction) and the void spans the wall *into* the host
    instead of out the far side. A side face is the non-cap cutter face sharing the
    ring edge, and its plane carries the reveal taper; a ring vertex is moved
    along the intersection line of its two adjacent side planes to each wall-plane
    offset. Returns ``None`` when no watertight prism can be built.
    """
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    ncap = np.asarray(cap_normal, dtype=np.float64)
    ncap = ncap / np.linalg.norm(ncap)
    n = len(ring)
    if n < 3 or near_off <= far_off:
        return None
    face_normals = _face_normals(v, f)
    cap_faces = {int(index) for group in caps for index in group}
    side_normals: list[np.ndarray] = []
    for i in range(n):
        a, b = int(ring[i]), int(ring[(i + 1) % n])
        adj = [
            j for j in range(len(f)) if j not in cap_faces and a in f[j] and b in f[j]
        ]
        if not adj:
            return None
        nn = face_normals[np.asarray(adj)].mean(axis=0)
        norm = float(np.linalg.norm(nn))
        if norm <= 0.0:
            return None
        side_normals.append(nn / norm)
    side_normal_array = np.asarray(side_normals, dtype=np.float64)

    near_pts: list[np.ndarray] = []
    far_pts: list[np.ndarray] = []
    for i in range(n):
        direction = np.cross(side_normal_array[(i - 1) % n], side_normal_array[i])
        norm = float(np.linalg.norm(direction))
        if norm < 1e-9:
            return None
        direction = direction / norm
        p0 = v[int(ring[i])]
        for offset, acc in ((near_off, near_pts), (far_off, far_pts)):
            dn = float(direction @ ncap)
            if abs(dn) < 1e-12:
                return None
            t = (offset - float(p0 @ ncap)) / dn
            acc.append(p0 + t * direction)

    verts = np.vstack(
        [np.asarray(near_pts, dtype=np.float64), np.asarray(far_pts, dtype=np.float64)]
    )
    new_faces: list[list[int]] = []
    for i in range(1, n - 1):
        new_faces.append([0, i, i + 1])  # near cap, kept flat
        new_faces.append([n, n + i + 1, n + i])  # far cap, kept flat
    for i in range(n):
        j = (i + 1) % n
        new_faces.append([i, j, n + j])
        new_faces.append([i, n + j, n + i])
    mesh = trimesh.Trimesh(
        vertices=verts, faces=np.asarray(new_faces, int), process=False
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _extrude_ring(ring_pts: np.ndarray, vec: np.ndarray) -> trimesh.Trimesh | None:
    """A watertight prism extruding a planar ring by ``vec``.

    The single host-parallel cap of a degenerate wedge is extruded along the cap
    normal by the wall thickness. Unlike ``_loft_polygons`` — which fans each cap
    to its own centroid and collapses the solid into a pyramid — both caps are
    triangulated as a fan from the first ring vertex so they stay flat and the
    solid is a true prism. The ring must be a simple, convex-ish polygon (the
    door / skylight cross-sections are quadrilaterals or triangles); a ring that
    cannot close watertight yields ``None`` and the caller degrades to ``caps_only``.
    """
    ring_pts = np.asarray(ring_pts, dtype=np.float64)
    vec = np.asarray(vec, dtype=np.float64)
    n = len(ring_pts)
    if n < 3:
        return None
    verts = np.vstack([ring_pts, ring_pts + vec])
    faces: list[list[int]] = []
    for i in range(1, n - 1):
        faces.append([0, i, i + 1])  # near cap, kept flat
        faces.append([n, n + i + 1, n + i])  # far cap, kept flat
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces, int), process=False)
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _outer_ring(
    vertices: np.ndarray, faces: np.ndarray, face_indices: list[int]
) -> list[int] | None:
    """The longest boundary loop of a cap face cluster, as global vertex ids."""
    subset = trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(faces[face_indices], int),
        process=False,
    )
    loops = _boundary_loops(subset)
    if not loops:
        return None
    return list(max(loops, key=len))


def _polygon_normal(points: np.ndarray) -> np.ndarray:
    """The polygon (Newell) normal of a closed 3D polyline."""
    points = np.asarray(points, dtype=np.float64)
    normal = np.zeros(3, dtype=np.float64)
    count = len(points)
    for i in range(count):
        normal += np.cross(points[i], points[(i + 1) % count])
    return normal


def _orient_ring(
    vertices: np.ndarray, ring: np.ndarray, cap_normal: np.ndarray
) -> np.ndarray:
    """Reverse ``ring`` (global vertex ids) so its polygon normal points along ``cap_normal``.

    ``_boundary_loops`` walks each cap's boundary without a shared orientation, so
    the front and back rims of a through-void can wind in opposite directions.
    Flipping the ring whose polygon normal opposes the cap normal brings the two
    rims into a consistent winding, which is what the side band needs to avoid
    self-intersecting when index i is matched to index i.
    """
    ring = np.asarray(ring, int)
    if float(_polygon_normal(vertices[ring]) @ cap_normal) < 0.0:
        return ring[::-1]
    return ring


def _clean_degenerate_ring(vertices: np.ndarray, ring: np.ndarray) -> np.ndarray | None:
    """Collapse redundant near-collinear sliver vertices from a cap ring.

    A cap rim authored as a degenerate polygon (a door/window frame with a tiny
    bevel corner) carries an extra near-coincident vertex: the two edges meeting
    at it run in almost the same direction, so the path is nearly straight through
    it and the point lies on a short stub. Dropping such a vertex merges the two
    edges and recovers the true polygon without changing its shape.

    A vertex is removed only when BOTH hold: its two incident edges are
    near-collinear (same direction, ``cos >= _COLLINEAR_COS``) AND one of them is
    a short stub (``<= _SLIVER_EDGE_LEN``), so a genuine corner with an angle is
    never simplified. This keeps at least three vertices; returns ``None`` when a
    valid ring cannot be produced (the caller then keeps the resampling loft).
    """
    ring = np.asarray(ring, int)
    pts = np.asarray(vertices[ring], dtype=np.float64)
    n = len(pts)
    if n < 4:
        return ring
    kept = list(range(n))
    changed = True
    while changed and len(kept) >= 3:
        changed = False
        next_kept: list[int] = []
        count = len(kept)
        for k in range(count):
            index = kept[k]
            previous = kept[(k - 1) % count]
            following = kept[(k + 1) % count]
            forward = pts[index] - pts[previous]
            backward = pts[following] - pts[index]
            forward_len = float(np.linalg.norm(forward))
            backward_len = float(np.linalg.norm(backward))
            if (
                forward_len <= _COINCIDENT_VERTS_EPS
                or backward_len <= _COINCIDENT_VERTS_EPS
            ):
                changed = True
                continue
            collinear = float((forward / forward_len) @ (backward / backward_len))
            if (
                collinear >= _COLLINEAR_COS
                and min(forward_len, backward_len) <= _SLIVER_EDGE_LEN
            ):
                changed = True
                continue
            next_kept.append(index)
        kept = next_kept
    if len(kept) < 3:
        return None
    return ring[kept]


def _loft_caps_watertight(
    vertices: np.ndarray,
    faces: np.ndarray,
    front: list[int],
    back: list[int],
    front_ring: list[int],
    back_ring: list[int],
) -> trimesh.Trimesh | None:
    """A watertight solid that keeps the two detected cap faces unchanged.

    The front/back cap triangles are emitted as-is, so the caps are exactly the
    faces found by the cap analysis; only new side
    faces are added between the two cap boundary rings, connected in 3D. The two
    rims are first brought into a consistent winding (a cyclic shift alone cannot
    fix opposite winding) so the side band does not self-intersect. Equal-length
    rims that no cyclic shift can pair are cleaned and re-lofted when cleanup
    recovers congruent rings (degenerate mirror-image slivers, whose direct
    bridge would twist); when the rims genuinely differ after cleanup the direct
    bridge keeps the detected cap faces verbatim. Returns ``None`` when no
    watertight closed surface can be built (the caller degrades to
    ``caps_only``).
    """
    front_arr = np.asarray(front_ring, int)
    back_arr = np.asarray(back_ring, int)
    n = len(front_arr)
    m = len(back_arr)
    if n < 3 or m < 3:
        return None

    # The cap-plane normal is the mean of the front cap cluster's face normals.
    # Orienting both rims to it makes them wind the same way; without this the two
    # boundary loops (walked without a shared orientation) can wind oppositely and
    # the side band self-intersects, collapsing the signed volume. Do this before
    # the equal/different-rim split so both paths (direct bridging and the
    # resampling loft) see consistently-wound rings.
    cap_normal = _face_normals(vertices, faces)[front]
    cap_normal = np.asarray(cap_normal, dtype=np.float64).mean(axis=0)
    norm = float(np.linalg.norm(cap_normal))
    if norm > 0.0:
        cap_normal = cap_normal / norm
        front_arr = _orient_ring(vertices, front_arr, cap_normal)
        back_arr = _orient_ring(vertices, back_arr, cap_normal)

    if n != m:
        # The two caps of a through-void are congruent; an unequal rim length only
        # means the two caps are tessellated differently. But an unequal rim can
        # also hide a degenerate ring: a door/window frame with a sliver bevel
        # corner carries one or two extra near-coincident, near-collinear vertices
        # (e.g. a rectangle authored as a 6-ring). Collapse such redundant vertices
        # first. Only a near-collinear sliver is removed, so a genuine (unequal)
        # rim with real corners is untouched and keeps the resampling loft below.
        cleaned_f = _clean_degenerate_ring(vertices, front_arr)
        cleaned_b = _clean_degenerate_ring(vertices, back_arr)
        if cleaned_f is not None and cleaned_b is not None:
            front_arr, back_arr = cleaned_f, cleaned_b
        # Rebuild a watertight volume from the (cleaned) derived rings rather than
        # hand-bridging. When cleanup collapsed the rims to a congruent polygon this
        # re-fans the caps (which were degenerate anyway) so the sliver vertices do
        # not survive as unshared boundary edges; when the rims stay unequal it keeps
        # the pre-existing resampling loft.
        return _loft_polygons(vertices[front_arr], vertices[back_arr])

    if _rings_twisted(vertices[front_arr], vertices[back_arr], cap_normal):
        # Equal counts do not imply congruent rims. When the collinear bevel
        # slivers sit on different corners in the two rims (mirror images) no
        # cyclic shift pairs the vertices and a direct bridge twists into long
        # diagonal side triangles. Such rims hide the same degenerate rings as
        # above — but reroute only when cleanup recovers congruent rings, the
        # signature of the mirror-image case. Rims that stay non-congruent after
        # cleanup genuinely differ: slivers at different spots along the same
        # edge mispair vertices that all lie on one line, a benign planar
        # re-triangulation whose direct bridge (and its detected cap faces) is
        # exact, while a resampling loft would push corners off the true
        # rectangle and distort the volume.
        cleaned_f = _clean_degenerate_ring(vertices, front_arr)
        cleaned_b = _clean_degenerate_ring(vertices, back_arr)
        if cleaned_f is not None and cleaned_b is not None:
            a = vertices[cleaned_f]
            b = vertices[cleaned_b]
            if len(a) == len(b) and not _rings_twisted(a, b, cap_normal):
                return _loft_polygons(a, b)
        # No congruent recovery: fall through and bridge the original rims.

    shift = _ring_shift(vertices[front_arr], vertices[back_arr])
    back_arr = np.roll(back_arr, shift)
    side: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        side.append([int(front_arr[i]), int(front_arr[j]), int(back_arr[j])])
        side.append([int(front_arr[i]), int(back_arr[j]), int(back_arr[i])])

    all_faces = (
        [list(tri) for tri in np.asarray(faces[front], int)]
        + [list(tri) for tri in np.asarray(faces[back], int)]
        + side
    )
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(all_faces, dtype=np.int64),
        process=False,
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _ring_shift(a: np.ndarray, b: np.ndarray) -> int:
    """Cyclic row shift of ``b`` that best aligns it to ``a``."""
    n = len(a)
    best_shift = 0
    best_distance = float("inf")
    for shift in range(n):
        distance = float(np.sum(np.linalg.norm(a - np.roll(b, shift, axis=0), axis=1)))
        if distance < best_distance:
            best_distance = distance
            best_shift = shift
    return best_shift


def _rings_twisted(a: np.ndarray, b: np.ndarray, cap_normal: np.ndarray) -> bool:
    """Whether two equal-length cap rims cannot be paired by a cyclic shift.

    Equal vertex counts do not imply congruent rims: a rectangle authored with
    collinear bevel slivers can carry them on *different corners* in the two rims
    (mirror images), so no cyclic shift pairs corresponding vertices and a direct
    bridge collapses into long diagonal side triangles — a watertight but twisted
    solid. Congruent rims pair every vertex with its counterpart at a pure offset
    along the cap normal, so the in-plane part of each pair offset is ~0; a
    mismatched pair sits displaced inside the cap plane. That displacement is
    compared to the rims' in-plane extent, so the test is scale-free. Used only
    when the two rims already agree on vertex count (see
    ``_loft_caps_watertight``).
    """
    n = len(a)
    if n < 3 or n != len(b):
        return False
    normal = np.asarray(cap_normal, dtype=np.float64)
    norm = float(np.linalg.norm(normal))
    if norm <= 0.0:
        return False
    normal = normal / norm
    shift = _ring_shift(a, b)
    offsets = np.asarray(a, dtype=np.float64) - np.roll(
        np.asarray(b, dtype=np.float64), shift, axis=0
    )
    along = offsets @ normal
    in_plane = np.linalg.norm(offsets - np.outer(along, normal), axis=1)
    points = np.vstack(
        [np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)]
    )
    flat = points - np.outer(points @ normal, normal)
    extent = float(np.linalg.norm(flat[:, None, :] - flat[None, :, :], axis=2).max())
    if extent <= 1e-9:
        return False
    return bool(float(in_plane.max()) > _TWIST_INPLANE_RATIO * extent)


def _loft_polygons(
    a_pts: np.ndarray, b_pts: np.ndarray, n: int | None = None
) -> trimesh.Trimesh | None:
    """Loft the closed polygons ``a_pts`` and ``b_pts`` into one watertight solid.

    When ``n`` is given, both polygons are resampled to ``n`` points (uniform arc
    length). When ``n`` is omitted and the two rings already agree on vertex
    count, the original ring vertices are kept so the caps are exact
    (resampling by uniform arc length would push non-regular polygon corners onto
    edge midpoints); otherwise both rings are resampled to the larger count. The
    b ring is rotated to best align with the a ring, and the volume is built from
    the two re-triangulated caps plus the side quads between corresponding
    samples.
    """
    a_pts = np.asarray(a_pts, dtype=np.float64)
    b_pts = np.asarray(b_pts, dtype=np.float64)
    if len(a_pts) < 3 or len(b_pts) < 3:
        return None
    count = n if n is not None else max(len(a_pts), len(b_pts))
    if n is None and len(a_pts) == len(b_pts):
        # The two caps already agree on vertex count. Resampling by uniform arc
        # length would move the corner vertices to edge midpoints whenever the cap
        # is a non-regular polygon (e.g. a non-square rectangle), distorting the
        # emitted cap. Keep the original ring vertices so the cap is exact.
        a, b = a_pts, b_pts
    else:
        a = _resample_closed(a_pts, count)
        b = _resample_closed(b_pts, count)
        if a is None or b is None:
            return None
    a, b = _align_rings(a, b)

    all_vertices: list[np.ndarray] = [a[i] for i in range(count)]
    all_vertices.extend([b[i] for i in range(count)])
    apex_a = 2 * count
    apex_b = 2 * count + 1
    all_vertices.append(a.mean(axis=0))
    all_vertices.append(b.mean(axis=0))
    faces: list[list[int]] = []
    for i in range(count):
        j = (i + 1) % count
        # cap A: traverse A[j]->A[i] (opposite the side-quad A[i]->A[j])
        faces.append([apex_a, j, i])
        # cap B: traverse B[i]->B[j] (opposite the side-quad B[j]->B[i])
        faces.append([apex_b, count + i, count + j])
        # side quad A[i], A[j], B[j], B[i] -> two triangles
        faces.append([i, j, count + j])
        faces.append([i, count + j, count + i])
    mesh = trimesh.Trimesh(
        vertices=np.asarray(all_vertices, dtype=np.float64),
        faces=np.asarray(faces, int),
        process=False,
    )
    if mesh.is_watertight and mesh.is_winding_consistent and _safe_volume(mesh) < 0:
        mesh.faces = mesh.faces[:, ::-1]
    if not _safe_fix_normals(mesh):
        return None
    return mesh if _is_watertight(mesh) else None


def _resample_closed(pts: np.ndarray, n: int) -> np.ndarray | None:
    """Resample the closed polygon ``pts`` to ``n`` points by uniform arc length."""
    pts = np.asarray(pts, dtype=np.float64)
    m = len(pts)
    if m == 0 or n <= 0:
        return None
    if m == 1:
        return np.repeat(pts[:1], n, axis=0)
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total <= 1e-12:
        return np.repeat(pts[:1], n, axis=0)
    targets = np.linspace(0.0, total, n, endpoint=False)
    out = np.empty((n, 3), dtype=np.float64)
    for k, target in enumerate(targets):
        index = int(np.searchsorted(s, target, side="right"))
        index = min(max(index, 1), m)
        t0, t1 = float(s[index - 1]), float(s[index])
        fraction = 0.0 if t1 <= t0 else (target - t0) / (t1 - t0)
        out[k] = pts[(index - 1) % m] * (1.0 - fraction) + pts[index % m] * fraction
    return out


def _align_rings(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rotate ``b`` (cyclic) so its samples best line up with ``a``."""
    n = len(a)
    if n == 0:
        return a, b
    best_shift = 0
    best_distance = float("inf")
    for shift in range(n):
        distance = float(np.sum(np.linalg.norm(a - np.roll(b, shift, axis=0), axis=1)))
        if distance < best_distance:
            best_distance = distance
            best_shift = shift
    return a, np.roll(b, best_shift, axis=0)


def _cut_ring_by_tube(
    near_ring: np.ndarray,
    far_ring: np.ndarray,
    tube: trimesh.Trimesh,
    cap_normal: np.ndarray,
) -> np.ndarray:
    """Clip ``far_ring`` so it stays inside the tube reveal band, or return it.

    The tube reveal faces bound the bore laterally. Each is a half-space; the far
    ring is clipped against every half-space (keeping the side that holds the near
    ring's centre) so the copied far cap matches the actual opening. When no tube
    face is a reveal, ``far_ring`` is returned unchanged (a pure thickness offset).
    """
    center = np.mean(near_ring, axis=0)
    points = np.asarray(far_ring, dtype=np.float64)
    for face in np.asarray(tube.faces, int):
        triangle = np.asarray(tube.vertices, dtype=np.float64)[face]
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        length = float(np.linalg.norm(normal))
        if length <= 1e-12:
            continue
        normal = normal / length
        if abs(float(normal @ cap_normal)) > _REVEAL_PARALLEL_COS:
            continue
        origin = triangle[0]
        keep_sign = 1.0 if float((center - origin) @ normal) >= 0.0 else -1.0
        clipped = _clip_polygon_halfspace(points, origin, normal, keep_sign)
        if clipped is None or len(clipped) < 3:
            return np.asarray(far_ring, dtype=np.float64)
        points = clipped
    return points


def _clip_polygon_halfspace(
    points: np.ndarray, origin: np.ndarray, normal: np.ndarray, keep_sign: float
) -> np.ndarray | None:
    """Sutherland-Hodgman clip of ``points`` to the half-space of ``normal``."""
    points = np.asarray(points, dtype=np.float64)
    n = len(points)
    if n < 3:
        return None
    signed = (points - origin) @ normal * keep_sign
    output: list[np.ndarray] = []
    for i in range(n):
        cur = points[i]
        nxt = points[(i + 1) % n]
        cur_inside = signed[i] >= 0
        nxt_inside = signed[(i + 1) % n] >= 0
        if cur_inside:
            output.append(cur)
        if cur_inside != nxt_inside:
            denominator = signed[i] - signed[(i + 1) % n]
            if abs(denominator) <= 1e-12:
                continue
            t = signed[i] / denominator
            output.append(cur + t * (nxt - cur))
    if len(output) < 3:
        return None
    return np.asarray(output, dtype=np.float64)


# ---------------------------------------------------------------------------
# Cut-surface tube / bore-closure helpers (self-contained).
# ---------------------------------------------------------------------------


def _reveal_host_mesh(
    context: ExecutionContext, host_ref: str
) -> trimesh.Trimesh | None:
    """The host mesh re-tessellated so the bore reveal stays planar.

    The default geometry cache library fans a curved wall's opening bore to a
    centroid vertex, collapsing the vertical reveal faces into slivers that are
    no longer coplanar with the cutter. Re-tessellating just the host with the
    ``cgal`` library keeps them as clean planar strips. Falls back to the cached
    host mesh when the host cannot be re-tessellated (e.g. a decomposed parent
    with no own body). Re-tessellated meshes are memoized per context so a host
    with several openings is tessellated once.
    """
    memo: dict[str, trimesh.Trimesh | None] = _REVEAL_HOST_MEMO.setdefault(context, {})
    if host_ref in memo:
        return memo[host_ref]
    parsed = split_expr_key(host_ref)
    if parsed is not None:
        slug, express_id = parsed
        mesh: trimesh.Trimesh | None = None
        try:
            settings = ifcopenshell.geom.settings()
            settings.set("use-world-coords", True)
            settings.set("weld-vertices", True)
            settings.set("context_types", ["Body"])  # pyright: ignore[reportArgumentType]
            entity = context.resolve_model(slug).by_id(express_id)
            shape = ifcopenshell.geom.create_shape(
                settings, entity, geometry_library=_REVEAL_GEOMETRY_LIBRARY
            )
            geometry = shape.geometry  # pyright: ignore[reportAttributeAccessIssue]
            mesh = reshape_flat(geometry.verts, geometry.faces)  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            mesh = None
        memo[host_ref] = mesh if mesh is not None else _host_mesh(context, host_ref)
        return memo[host_ref]
    memo[host_ref] = _host_mesh(context, host_ref)
    return memo[host_ref]


def _cut_surface_tube(
    context: ExecutionContext,
    host_ref: str,
    host_mesh: trimesh.Trimesh,
    cutter: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    """The cut-surface tube of an opening: the host faces that bound the bore.

    A host face is a cut face when a cutter face is coplanar with it (normal and
    plane position within tolerance) AND the host face's footprint lies inside a
    cutter surface's footprint that lies on that plane. The cutter faces are
    merged into planar surfaces first (``_planar_groups``) so the containment
    test is run against each whole surface rather than against a single
    triangle. This is the exact substitute for the former bounding-box filter:
    faces that share the cutter's plane but sit elsewhere (e.g. the wall's own
    large front face, coplanar with a cutter end cap) are excluded because their
    footprint is not contained in the cutter's. Keeping the coplanarity check at
    the individual-face level ensures the fine facets of a curved reveal band are
    matched to their cutter face, while the containment test prunes coplanar
    faces that lie outside the opening. The selected faces form the tube; the
    tube is closed when the faces can be made watertight, otherwise it is
    returned open.
    """
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    cutter_vertices = np.asarray(cutter.vertices, dtype=np.float64)
    cutter_faces = np.asarray(cutter.faces, dtype=np.int64)
    if len(host_faces) == 0 or len(cutter_faces) == 0:
        return None

    host_normals = _face_normals(host_vertices, host_faces)
    cutter_normals = _face_normals(cutter_vertices, cutter_faces)

    # Cutter planar surfaces pre-computed once: their shared plane (mean normal,
    # offset along it, in-plane axes) and the 2D footprint polygon in that plane.
    cutter_surfaces: list[
        tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any]
    ] = []
    for group in _planar_groups(cutter_vertices, cutter_faces, cutter_normals):
        surface = _planar_surface(cutter_vertices, cutter_faces, cutter_normals, group)
        if surface is not None:
            cutter_surfaces.append(surface)

    host_first_points = host_vertices[host_faces[:, 0]]
    selected = np.zeros(len(host_faces), dtype=bool)
    for cutter_normal, cutter_offset, cutter_axes, cutter_footprint in cutter_surfaces:
        coplanar = (np.abs(host_normals @ cutter_normal) >= _PLANE_COS) & (
            np.abs(host_first_points @ cutter_normal - cutter_offset)
            <= _PLANE_TOLERANCE
        )
        if not coplanar.any():
            continue
        coplanar_indices = np.flatnonzero(coplanar)
        for index in coplanar_indices:
            if _footprint_contained(
                host_vertices, host_faces[index], cutter_axes, cutter_footprint
            ):
                selected[index] = True
    if not selected.any():
        return None

    tube = trimesh.Trimesh(
        vertices=host_vertices, faces=host_faces[selected], process=False
    )
    closed = _close_bore(context, host_ref, tube)
    if closed is not None:
        return closed
    return tube


def _mean_normal(normals: np.ndarray, group: list[int]) -> np.ndarray:
    """The normalised mean of a planar face group's normals."""
    mean_normal = normals[group].mean(axis=0)
    length = float(np.linalg.norm(mean_normal))
    if length <= 1e-10:
        return mean_normal
    return mean_normal / length


def _planar_surface(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    group: list[int],
) -> tuple[np.ndarray, float, tuple[np.ndarray, np.ndarray], Any] | None:
    """The plane of a planar face group as ``(normal, offset, axes, footprint)``.

    ``normal`` is the group's mean normal and ``offset`` its plane position along
    it. ``axes`` are the in-plane ``(u, v)`` directions and ``footprint`` the 2D
    convex hull of the group projected onto the plane. Returns ``None`` for a
    degenerate group (no area, so no footprint).
    """
    points = vertices[np.unique(faces[group])]
    normal = _mean_normal(normals, group)
    if float(np.linalg.norm(normal)) <= 1e-10:
        return None
    axes = _in_plane_axes(normal)
    footprint = _project_footprint(points, axes)
    if footprint is None:
        return None
    offset = float(np.mean(points @ normal))
    return normal, offset, axes, footprint


def _project_footprint(
    points: np.ndarray, axes: tuple[np.ndarray, np.ndarray]
) -> Any | None:
    """The convex hull of ``points`` projected onto the in-plane axes, or None."""
    axis_u, axis_v = axes
    data = np.column_stack([points @ axis_u, points @ axis_v])
    footprint = MultiPoint(data).convex_hull
    if footprint.area <= 0.0:
        return None
    return footprint


def _footprint_contained(
    vertices: np.ndarray,
    face: np.ndarray,
    axes: tuple[np.ndarray, np.ndarray],
    cutter_footprint: Any,
) -> bool:
    """Whether a host face's footprint lies inside the cutter surface footprint.

    The host face is projected onto the cutter surface's in-plane axes so the
    test runs in a single shared 2D frame; a small buffer on the cutter absorbs
    tessellation jitter on shared edges. Returns False for a degenerate face.
    """
    face_points = vertices[face]
    data = np.column_stack([face_points @ axes[0], face_points @ axes[1]])
    footprint = MultiPoint(data).convex_hull
    if footprint.area <= 0.0:
        return False
    return bool(cutter_footprint.buffer(_CONTAINMENT_EPS).covers(footprint))


def _close_bore(
    context: ExecutionContext,
    host_ref: str,
    tube: trimesh.Trimesh,
) -> trimesh.Trimesh | None:
    """Close the cut-surface tube, or return None to keep the open tube.

    The tube's boundary consists of open rims. A through-bore (window) has two
    planar rims; an opening reaching a free face of the host (a floor-reaching
    door) has a non-planar rim, an open ring. The tube is first welded
    (coincident tessellation corners collapse to a single point), then each
    remaining boundary loop is capped. An open ring is deliberately NOT made
    watertight (``_close_open_ring``): only its cap faces are added — the ring's
    free edges are compared with the host's surface planes, and every run of
    ring vertices in one of those planes is closed with the new edge the open
    ring needs and filled with one flat cap face — while the rim the host's own
    surface model has no face for (e.g. the door sill) stays open. Any other rim
    (a window cross-section) is capped by the generic loop capping: one planar
    fan per plane it spans, with a single centroid fan as the watertight
    fallback.

    Returns ``None`` when the tube cannot be processed: a degenerate loop, or a
    through-bore rim that cannot be capped watertight. The caller then keeps the
    open tube.
    """
    if len(tube.faces) == 0:
        return None
    try:
        welded = _weld_rim(tube)
        if welded is None:
            return None
        welded = _prune_flaps(welded)
        if welded is None:
            return None
        loops = _boundary_loops(welded)
        if len(loops) == 0:
            return welded if _is_watertight(welded) else None
        if any(len(loop) < _MIN_CAP_LOOP for loop in loops):
            return None
        # A single non-planar boundary loop is an open ring: an opening that
        # reaches a free face of the host (e.g. a floor-reaching door), whose rim
        # (e.g. the door sill) the host's surface model leaves open. Only the
        # cap faces in the host's surface planes are added and the ring is not
        # forced watertight. A bent through-bore (e.g. a skylight whose rim spans
        # two host planes) also has a non-planar loop but keeps more than one
        # boundary loop, so it is not an open ring; it falls through to the
        # generic per-plane capping in _cap_loops below, which decomposes the
        # non-planar rim into one flat cap per host surface plane and closes it
        # watertight.
        if len(loops) == 1 and not _loop_is_planar(
            welded.vertices[np.asarray(loops[0], int)]
        ):
            return _close_open_ring(context, host_ref, welded, loops)
        if len(loops) not in (1, 2):
            return None
        return _cap_loops(welded, loops, context=context, host_ref=host_ref)
    except Exception:
        return None


def _weld_rim(tube: trimesh.Trimesh | None) -> trimesh.Trimesh | None:
    """Weld the tube's coincident corner vertices into distinct corners.

    A curved-wall bore has several tessellation vertices at one 3D corner (e.g. a
    corner where the reveal meets the curved facade, or a floor-reaching seam).
    Those within a small tolerance are collapsed so the rim becomes its geometric
    outline and a cap can close it without zero-length edges.
    """
    if tube is None or len(tube.faces) == 0:
        return None
    vertices = np.asarray(tube.vertices, float)
    faces = np.asarray(tube.faces, int)
    # Restrict to the referenced vertices so the weld never touches unrelated
    # model vertices, then collapse those within a small tolerance: a curved-wall
    # bore has several tessellation vertices at one 3D corner, and snapping them
    # makes the rim its geometric outline so the cap fan closes without
    # zero-length edges.
    referenced = np.unique(faces)
    representative, remap, welded_vertices = _weld_positions(vertices, referenced)
    welded_faces: list[list[int]] = []
    for face in faces:
        mapped = [remap[representative[int(v)]] for v in face]
        if len(set(mapped)) < 3:
            continue
        welded_faces.append(mapped)
    return trimesh.Trimesh(
        vertices=welded_vertices,
        faces=np.asarray(welded_faces, int),
        process=False,
    )


def _weld_positions(
    vertices: np.ndarray, referenced: np.ndarray
) -> tuple[dict[int, int], dict[int, int], np.ndarray]:
    """Collapse near-coincident referenced vertices; return (rep map, remap, verts).

    Vertices within ``_COINCIDENT_VERTS_EPS`` are grouped by a spatial grid (with
    a 27-cell neighbourhood scan so tolerance-cell boundaries never split a
    corner). Returns the mapping from reference-array index to representative
    index, the representative->new index mapping, and the deduplicated vertex
    array.
    """
    tol = _COINCIDENT_VERTS_EPS
    cell = tol
    grid: dict[tuple[int, int, int], int] = {}
    representative: dict[int, int] = {}
    for v in referenced:
        iv = int(v)
        x, y, z = vertices[iv]
        key = (
            int(np.floor(x / cell)),
            int(np.floor(y / cell)),
            int(np.floor(z / cell)),
        )
        rep = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    found = grid.get((key[0] + dx, key[1] + dy, key[2] + dz))
                    if (
                        found is not None
                        and np.linalg.norm(vertices[found] - vertices[iv]) < tol
                    ):
                        rep = found
                        break
                if rep is not None:
                    break
            if rep is not None:
                break
        if rep is None:
            rep = iv
            grid[key] = rep
        representative[iv] = rep
    order = np.sort(np.unique([representative[v] for v in referenced]))
    remap = {rep: new for new, rep in enumerate(order)}
    welded = vertices[order]
    return representative, remap, welded


def _prune_flaps(welded: trimesh.Trimesh) -> trimesh.Trimesh | None:
    """Drop non-manifold tessellation flaps from a welded tube, or return None.

    A curved-host bore's tessellation can leave a flap behind: a sliver triangle
    sharing an edge with two larger faces, so that edge is used three times and
    the tube is non-manifold -- no capping can ever close it (a boundary walk
    sees a fake loop through the flap). The smallest face on each over-used
    edge is dropped until every edge is used at most twice, which removes the
    flap and exposes the true rim. A manifold tube (every edge already used at
    most twice) is returned unchanged. Returns ``None`` when no face remains.
    """
    faces = np.asarray(welded.faces, int)
    face_edges = [
        (
            _edge_key((int(face[0]), int(face[1]))),
            _edge_key((int(face[1]), int(face[2]))),
            _edge_key((int(face[2]), int(face[0]))),
        )
        for face in faces
    ]
    # Fast path: a manifold tube is returned unchanged.
    use = _edge_use_counts([edge for edges in face_edges for edge in edges])
    if all(count <= 2 for count in use.values()):
        return welded
    vertices = np.asarray(welded.vertices, float)
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    keep = [True] * len(faces)
    while True:
        use = _edge_use_counts(
            [edge for i, edges in enumerate(face_edges) if keep[i] for edge in edges]
        )
        over = {key for key, count in use.items() if count > 2}
        if not over:
            break
        drop = min(
            (
                i
                for i in range(len(faces))
                if keep[i] and any(edge in over for edge in face_edges[i])
            ),
            key=lambda i: float(areas[i]),
        )
        keep[drop] = False
    if not any(keep):
        return None
    return trimesh.Trimesh(
        vertices=vertices,
        faces=faces[np.asarray(keep, bool)],
        process=False,
    )


def _edge_use_counts(edges: list[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """How often each (undirected) edge in ``edges`` appears."""
    use: dict[tuple[int, int], int] = {}
    for edge in edges:
        use[edge] = use.get(edge, 0) + 1
    return use


def _boundary_loops(mesh: trimesh.Trimesh) -> list[list[int]]:
    """Cyclic, corner-distinct vertex loops of the mesh's boundary.

    Boundary edges (used exactly once) are walked into ordered cycles. The walk
    follows real boundary edges (never a diagonal jump between two corners), so
    the cap fan for each loop always coincides with the tube's boundary.
    """
    edge_use: dict[tuple[int, int], int] = {}
    faces = np.asarray(mesh.faces, int)
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_use[key] = edge_use.get(key, 0) + 1
    adjacency: dict[int, list[int]] = {}
    for (u, v), use in edge_use.items():
        if use == 1:
            adjacency.setdefault(u, []).append(v)
            adjacency.setdefault(v, []).append(u)
    visited: set[int] = set()
    loops: list[list[int]] = []
    for start in sorted(adjacency):
        if start in visited:
            continue
        loop = [start]
        visited.add(start)
        cur = start
        prev = -1
        while True:
            candidates = [
                n for n in adjacency.get(cur, ()) if n != prev and n not in visited
            ]
            if not candidates:
                break
            nxt = candidates[0]
            loop.append(nxt)
            visited.add(nxt)
            prev, cur = cur, nxt
            if nxt == start:
                break
        loops.append(loop)
    return loops


def _cap_loops(
    mesh: trimesh.Trimesh,
    loops: list[list[int]],
    *,
    context: ExecutionContext | None = None,
    host_ref: str | None = None,
) -> trimesh.Trimesh | None:
    """Append a cap for each boundary ``loop``; return the closed mesh.

    Each loop is split by ``_loop_cap_groups`` into one planar cap group per
    plane it spans, then each group is capped from its own centroid so every cap
    face lies flat in that plane. A planar loop yields a single group and is
    capped with one fan (the classic through-bore closure). When a non-planar rim
    cannot be decomposed into a cleanly watertight set of flat caps (e.g. a
    heavily faceted curved-wall bore whose loop jitters across many facets), the
    loop is re-capped with a single centroid fan so the result stays watertight.
    Each cap triangle is wound opposite to the tube face that uses its boundary
    edge so the combined surface keeps one consistent winding. The mesh is then
    re-oriented to a positive volume. Returns ``None`` when the result is not
    watertight.
    """
    vertices = np.asarray(mesh.vertices, float)
    faces = np.asarray(mesh.faces, int)
    # Boundary edge -> the direction the adjacent tube face traverses it. A cap
    # triangle sharing that edge must traverse it in the opposite direction.
    edge_traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_traversal.setdefault(key, (u, v))
    closed = _build_closed(
        vertices,
        faces,
        edge_traversal,
        loops,
        context=context,
        host_ref=host_ref,
        decompose=True,
    )
    if closed is not None:
        return closed
    return _build_closed(
        vertices,
        faces,
        edge_traversal,
        loops,
        context=context,
        host_ref=host_ref,
        decompose=False,
    )


def _build_closed(
    vertices: np.ndarray,
    faces: np.ndarray,
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    loops: list[list[int]],
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
    decompose: bool,
) -> trimesh.Trimesh | None:
    """Build the closed mesh with one cap strategy; None when not watertight.

    With ``decompose`` a non-planar loop is capped per host-surface plane (flat
    caps); without it every loop is capped with one centroid fan (the classic
    closure, watertight even across a non-planar rim).
    """
    cap_vertices = list(vertices)
    cap_faces = [list(f) for f in faces]
    for loop in loops:
        loop_ids = np.asarray(loop, int)
        if len(loop_ids) < _MIN_CAP_LOOP:
            return None
        if decompose:
            cap_groups = _loop_cap_groups(
                vertices,
                faces,
                loop_ids,
                context=context,
                host_ref=host_ref,
            )
            if not cap_groups:
                return None
        else:
            cap_groups = [loop_ids]
        for group in cap_groups:
            apex = vertices[group].mean(axis=0)
            apex_index = len(cap_vertices)
            cap_vertices.append(apex)
            _add_cap_fan(cap_faces, edge_traversal, group, apex_index)
    closed_mesh = trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )
    # The tube is winding-consistent; the caps follow it. Re-orient to positive
    # volume (the interior-facing orientation is equally "watertight"). Only a
    # genuinely closed, consistently-wound mesh is re-oriented: reading volume on
    # a degenerate/self-intersecting one divides by nothing and reverses faces of
    # a mesh that is going to be rejected anyway.
    if (
        closed_mesh.is_watertight
        and closed_mesh.is_winding_consistent
        and _safe_volume(closed_mesh) < 0
    ):
        closed_mesh.faces = closed_mesh.faces[:, ::-1]
    if not _safe_fix_normals(closed_mesh):
        return None
    return closed_mesh if _is_watertight(closed_mesh) else None


def _add_cap_fan(
    cap_faces: list[list[int]],
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    group: np.ndarray,
    apex_index: int,
) -> None:
    """Append the centroid-fan triangles of one planar cap ``group``.

    ``group`` is a cyclic list of the cap's corner vertices. Each triangle uses
    ``apex_index`` as its third vertex. The winding of the edge shared with a
    tube face opposes the tube's traversal; a virtual edge created by the cap
    itself (joining two planes, e.g. the door sill's front edge) has no tube
    traversal to oppose and defaults to the group's winding, which the final
    ``fix_normals`` re-orients consistently.
    """
    group_ids = np.asarray(group, int)
    for i in range(len(group_ids)):
        a = int(group_ids[i])
        b = int(group_ids[(i + 1) % len(group_ids)])
        key = (a, b) if a < b else (b, a)
        u, v = edge_traversal.get(key, (a, b))
        # tube traverses u->v; the cap must traverse v->u.
        first, second = (b, a) if (a, b) == (u, v) else (a, b)
        cap_faces.append([first, second, apex_index])


def _edge_key(edge: tuple[int, int]) -> tuple[int, int]:
    """The unordered ``(min, max)`` key of an edge so it matches regardless of order."""
    u, v = edge
    return (u, v) if u < v else (v, u)


def _close_open_ring(
    context: ExecutionContext,
    host_ref: str,
    welded: trimesh.Trimesh,
    loops: list[list[int]],
) -> trimesh.Trimesh | None:
    """Add the cap faces of an open ring, or return None when none is known.

    An open ring is the non-planar boundary loop of an opening that reaches a
    free face of the host (a floor-reaching door): its free edges do not close
    into the flat cross-section rims of a through-bore. Each non-planar loop's
    free edges are compared with the host's surface planes (the dominant
    opposing plane pair first), and every run of
    loop vertices that lies in one of those planes is the outline of the cap
    face in that plane. A run is open (the ring is not closed there), so capping
    it creates the new edge between its two end vertices; the closed outline is
    filled with one flat cap face. The ring is deliberately NOT made watertight:
    the rim the host's own surface model has no face for (e.g. the door sill)
    stays open. Returns ``None`` when no host surface plane carries a cap
    outline; the caller then keeps the open tube.
    """
    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return None
    vertices = np.asarray(welded.vertices, float)
    faces = np.asarray(welded.faces, int)
    face_normals = _face_normals(vertices, faces)
    face_first = vertices[faces[:, 0]]
    open_loops = [
        loop for loop in loops if not _loop_is_planar(vertices[np.asarray(loop, int)])
    ]
    if not open_loops:
        return None
    for normal, t_min, t_max, _area in planes:
        chains: list[np.ndarray] = []
        for loop in open_loops:
            chains.extend(
                _ring_cap_chains(
                    vertices,
                    faces,
                    face_normals,
                    face_first,
                    loop,
                    normal,
                    t_min,
                    t_max,
                )
            )
        if chains:
            return _add_ring_caps(vertices, faces, chains)
    return None


def _ring_cap_chains(
    vertices: np.ndarray,
    faces: np.ndarray,
    face_normals: np.ndarray,
    face_first: np.ndarray,
    loop: list[int],
    normal: np.ndarray,
    t_min: float,
    t_max: float,
) -> list[np.ndarray]:
    """The cap outlines of an open ring in one host surface plane pair.

    The ring's vertices that lie on one of the two host surface planes (within
    ``_CAP_PLANE_TOLERANCE``) form runs; each run of consecutive ring vertices,
    kept in ring order, is the outline of the cap face in that plane. A plane
    the tube already closes with its own faces (a reveal, e.g. a jamb coplanar
    with the host's side face) carries no cap and is skipped. Runs shorter than
    ``_MIN_CAP_LOOP`` are degenerate fragments and are dropped. Returns an empty
    list when the pair carries no cap outline.
    """
    ring = np.asarray(loop, int)
    offsets = vertices[ring] @ normal
    chains: list[np.ndarray] = []
    for plane_offset in (t_min, t_max):
        if _plane_is_reveal(faces, face_normals, face_first, normal, plane_offset):
            continue
        on_plane = np.abs(offsets - plane_offset) <= _CAP_PLANE_TOLERANCE
        chains.extend(_plane_runs(ring, on_plane))
    return chains


def _plane_runs(ring: np.ndarray, on_plane: np.ndarray) -> list[np.ndarray]:
    """The maximal runs of consecutive ring vertices whose ``on_plane`` is True.

    The cyclic ring order is rotated to start on an off-plane vertex, so every
    run is a contiguous, non-wrapping run of vertex ids in ring order. A run is
    open (the ring leaves the plane at both of its ends), so the cap built from
    it creates the new edge between its two end vertices. Runs shorter than
    ``_MIN_CAP_LOOP`` are degenerate fragments and are dropped.
    """
    if not on_plane.any():
        return []
    n = len(ring)
    if on_plane.all():
        return [np.asarray(ring, int)]
    start = int(np.argmin(on_plane))  # the first off-plane vertex
    runs: list[np.ndarray] = []
    run: list[int] = []
    for step in range(n):
        index = (start + step) % n
        if on_plane[index]:
            run.append(int(ring[index]))
            continue
        if len(run) >= _MIN_CAP_LOOP:
            runs.append(np.asarray(run, int))
        run = []
    if len(run) >= _MIN_CAP_LOOP:  # defensive: start is off-plane
        runs.append(np.asarray(run, int))
    return runs


def _add_ring_caps(
    vertices: np.ndarray,
    faces: np.ndarray,
    chains: list[np.ndarray],
) -> trimesh.Trimesh:
    """Fill one flat cap per chain outline, leaving the remaining rim open.

    Each chain is capped from its own centroid (a flat face in its host surface
    plane): the fan is wound uniformly in the direction opposing the tube's
    traversal of the chain, and the closing edge between the chain's two end
    vertices is the new edge the open ring needs. The result is deliberately not
    made watertight: the rim between the caps (e.g. the door sill) stays open,
    because the host's own surface model has no face there.
    """
    cap_vertices: list[np.ndarray] = [vertices[i] for i in range(len(vertices))]
    cap_faces: list[list[int]] = [list(f) for f in faces]
    # Boundary edge -> the direction the adjacent tube face traverses it. A cap
    # triangle sharing that edge must traverse it in the opposite direction.
    edge_traversal: dict[tuple[int, int], tuple[int, int]] = {}
    for face in faces:
        a, b, c = (int(face[0]), int(face[1]), int(face[2]))
        for u, v in ((a, b), (b, c), (c, a)):
            edge_traversal.setdefault(_edge_key((u, v)), (u, v))
    for chain in chains:
        apex_index = len(cap_vertices)
        cap_vertices.append(vertices[chain].mean(axis=0))
        _add_chain_fan(cap_faces, edge_traversal, chain, apex_index)
    return trimesh.Trimesh(
        vertices=np.asarray(cap_vertices, float),
        faces=np.asarray(cap_faces, int),
        process=False,
    )


def _add_chain_fan(
    cap_faces: list[list[int]],
    edge_traversal: dict[tuple[int, int], tuple[int, int]],
    chain: np.ndarray,
    apex_index: int,
) -> None:
    """Append the centroid-fan triangles of one open chain cap.

    ``chain`` is an open run of ring vertices: each of its edges is a tube
    boundary edge shared with exactly one tube face, except the closing edge
    (chain[-1] -> chain[0]), which the cap itself creates. The fan is wound
    uniformly — in the direction opposing the tube's traversal of the chain's
    first edge — so every fan triangle opposes the tube on its shared edge AND
    the closing triangle's winding is consistent with its fan neighbours (there
    is no tube face on the closing edge to oppose; opposing a made-up direction
    would flip it against them).
    """
    chain_ids = np.asarray(chain, int)
    n = len(chain_ids)
    if n < 2:
        return
    a0, a1 = int(chain_ids[0]), int(chain_ids[1])
    u, v = edge_traversal.get(_edge_key((a0, a1)), (a0, a1))
    # The tube traverses u -> v; the fan runs the chain in the opposite
    # direction so every triangle opposes the tube across its shared edge.
    with_ring_order = (u, v) == (a1, a0)
    for i in range(n):
        first = int(chain_ids[i if with_ring_order else (i + 1) % n])
        second = int(chain_ids[(i + 1) % n if with_ring_order else i])
        cap_faces.append([first, second, apex_index])


def _loop_cap_groups(
    vertices: np.ndarray,
    faces: np.ndarray,
    loop_ids: np.ndarray,
    *,
    context: ExecutionContext | None,
    host_ref: str | None,
) -> list[np.ndarray]:
    """The planar cap groups of one boundary loop, one per plane it spans.

    A planar rim (a through-bore cross-section) is a single group. A rim that
    spans several planes (a floor-reaching door, a non-planar skylight rim) is
    split into one group per host surface plane a run of its corner vertices lies
    on, so every cap is a flat face in a host surface plane. A host plane that
    the tube already closes (a reveal face, e.g. a jamb or header coplanar with
    the host's own side face) is not a cap and is skipped. Returns an empty list
    when the loop is non-planar but lies on no cap plane.
    """
    points = vertices[loop_ids]
    if _loop_is_planar(points):
        return [loop_ids]
    if context is None or host_ref is None:
        return []
    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return []
    face_normals = _face_normals(vertices, faces)
    face_first = vertices[faces[:, 0]]
    groups: list[np.ndarray] = []
    seen: set[frozenset[int]] = set()
    for normal, t_min, t_max, _area in planes:
        offsets = points @ normal
        for t in (t_min, t_max):
            onplane = np.abs(offsets - t) <= _CAP_PLANE_TOLERANCE
            group = loop_ids[onplane]
            if len(group) < _MIN_CAP_LOOP:
                continue
            key = frozenset(int(v) for v in group)
            if key in seen:
                continue
            seen.add(key)
            if _plane_is_reveal(faces, face_normals, face_first, normal, t):
                continue
            ordered = _order_loop_group(vertices, group, normal)
            if ordered is None:
                continue
            groups.append(ordered)
    return groups


def _plane_is_reveal(
    faces: np.ndarray,
    face_normals: np.ndarray,
    face_first: np.ndarray,
    normal: np.ndarray,
    t: float,
) -> bool:
    """Whether the tube already closes the plane ``(normal, t)`` with a reveal.

    The tube's faces are the reveal band; a host surface plane that already has a
    coplanar tube face is a reveal (a jamb/header that happens to coincide with a
    host side face), not an open cap to fill. Returning True keeps that plane out
    of the caps so a cap never overlaps a reveal.
    """
    coplanar = (np.abs(face_normals @ normal) >= _PLANE_COS) & (
        np.abs(face_first @ normal - t) <= _CAP_PLANE_TOLERANCE
    )
    return bool(coplanar.any())


def _loop_is_planar(points: np.ndarray) -> bool:
    """Whether ``points`` lie within a small residual of their best-fit plane."""
    centered = points - points.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    if vt.shape[0] < 3:
        return True
    residue = float(np.abs(centered @ vt[-1]).max())
    return residue <= _CAP_PLANAR_TOLERANCE


def _order_loop_group(
    vertices: np.ndarray, group: np.ndarray, normal: np.ndarray
) -> np.ndarray | None:
    """Order the cap corner vertices of ``group`` as a simple polygon.

    The group's corners (a run of a non-planar rim that lies in one plane) are
    sorted by angle around their centroid projected onto the plane, so the
    polygon does not self-intersect and the centroid fan stays inside it. Returns
    ``None`` for a degenerate group that collapses to a line.
    """
    group = np.asarray(group, int)
    points = vertices[group]
    center = points.mean(axis=0)
    axis_u, axis_v = _in_plane_axes(normal)
    pu = (points - center) @ axis_u
    pv = (points - center) @ axis_v
    order = np.argsort(np.arctan2(pv, pu))
    ordered = group[order]
    if _polygon_area(pu[order], pv[order]) <= 1e-12:
        return None
    return ordered


def _polygon_area(u: np.ndarray, v: np.ndarray) -> float:
    """The unsigned area of the polygon with successive 2D points ``(u, v)``."""
    return float(
        0.5 * abs(float(np.dot(u, np.roll(v, -1)) - np.dot(v, np.roll(u, -1))))
    )


# ---------------------------------------------------------------------------
# Opening cap-face / host-surface helpers (self-contained).
# ---------------------------------------------------------------------------


def _resolve_entity(model: Any, express_id: int) -> Any | None:
    """The entity for ``express_id``, or None when the model has none."""
    try:
        return model.by_id(express_id)
    except RuntimeError:
        return None


def _iter_openings(host: Any) -> list[Any]:
    """The openings that void ``host``, via its ``IfcRelVoidsElement`` links."""
    openings: list[Any] = []
    for relationship in getattr(host, "HasOpenings", None) or []:
        opening = getattr(relationship, "RelatedOpeningElement", None)
        if opening is not None:
            openings.append(opening)
    return openings


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _group_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return float(0.5 * np.linalg.norm(cross, axis=1).sum())


def _planar_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """Group face indices into planar surfaces.

    A face joins the group of its seed face when its normal deviates by less
    than ~1° and its first vertex lies on the seed's plane. Every face joins
    exactly one group; degenerate faces end up in singleton groups.
    """
    first_points = vertices[faces[:, 0]]
    assigned = np.zeros(len(faces), dtype=bool)
    groups: list[list[int]] = []

    for seed in range(len(faces)):
        if assigned[seed]:
            continue
        normal = normals[seed]
        offsets = (first_points - first_points[seed]) @ normal
        same = (
            (normals @ normal >= _ALIGNED_COS)
            & (np.abs(offsets) <= _SURFACE_PLANE_TOLERANCE)
            & ~assigned
        )
        same[seed] = True
        assigned |= same
        groups.append(np.flatnonzero(same).tolist())

    return groups


def _cap_groups(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """The cap-face groups of an opening mesh.

    The caps are the void faces in the plane of the host surface: the two
    largest planar groups whose normals oppose each other. The remaining groups
    (the reveal band cut into the host) are dropped. A void exposing only one
    dominant flat face yields a single group.
    """
    sized = [
        (group, _group_area(vertices, faces, group))
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [(group, area) for group, area in sized if area > 0.0]
    sized.sort(key=lambda item: item[1], reverse=True)
    if not sized:
        return []

    caps = [sized[0][0]]
    first_normal = normals[caps[0][0]]
    for group, _area in sized[1:]:
        if float(normals[group[0]] @ first_normal) <= _OPPOSING_COS:
            caps.append(group)
            break
    return caps


def _host_surface_planes(
    context: ExecutionContext, host_ref: str
) -> list[tuple[np.ndarray, float, float, float]]:
    """The host's significant opposing surface-plane pairs, dominant first.

    Every entry is ``(normal, t_min, t_max, area)``: ``normal`` is the shared
    pierce direction of two opposing planar host face groups and ``t_min``/``t_max``
    bound the host slab along it. The largest pair comes first; the remaining
    significant pairs (e.g. the secondary pitch of a multi-slope roof) follow, so
    an opening that sits outside the dominant slab can be clipped to its own
    surface. Returns an empty list when the host cannot be analysed (no cached
    mesh, no planar surfaces, no opposing pair).
    """
    parsed = split_expr_key(host_ref)
    if parsed is None:
        return []
    host_slug, host_id = parsed
    host_mesh = context.geometry_cache.get(expr_key(host_slug, host_id))
    if host_mesh is None:
        return []
    try:
        vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
        faces = np.asarray(host_mesh.faces, dtype=np.int64)
    except Exception:
        return []
    if len(faces) == 0:
        return []

    normals = _face_normals(vertices, faces)
    sized = [
        (group, _group_area(vertices, faces, group), normals[group[0]])
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [(group, area, normal) for group, area, normal in sized if area > 0.0]
    sized.sort(key=lambda item: item[1], reverse=True)
    if not sized:
        return []

    # Opposing-plane pairs, deduplicated by their (sign-aware) pierce normal so
    # mirrored pitches are kept as separate candidates.
    pairs: list[tuple[np.ndarray, float, float, float]] = []
    seen: set[tuple[float, ...]] = set()
    for group, area, normal in sized:
        key = tuple(np.round(normal, 2))
        if key in seen:
            continue
        for other, other_area, other_normal in sized:
            if float(other_normal @ normal) > _OPPOSING_COS:
                continue
            first_off = float(np.mean(vertices[np.unique(faces[group])] @ normal))
            second_off = float(np.mean(vertices[np.unique(faces[other])] @ normal))
            thickness = abs(second_off - first_off)
            if thickness < _MIN_SLAB_THICKNESS:
                continue
            pairs.append(
                (
                    normal,
                    min(first_off, second_off),
                    max(first_off, second_off),
                    area + other_area,
                )
            )
            seen.add(key)
            break

    pairs.sort(key=lambda item: item[3], reverse=True)
    return pairs


def _surface_regions(
    vertices: np.ndarray, faces: np.ndarray, normals: np.ndarray
) -> list[list[int]]:
    """Group faces into smooth surface regions.

    A face joins the region of an edge-adjacent face when its normal deviates by
    less than ~3° — the facet step of a tessellated curve. The result groups a
    curved/faceted surface (e.g. a round wall) into one contiguous region, while
    sharper junction edges split distinct surfaces apart.
    """
    face_count = len(faces)
    if face_count == 0:
        return []
    edges: dict[tuple[int, int], list[int]] = {}
    for face_index in range(face_count):
        for offset in (0, 1, 2):
            a = int(faces[face_index, offset])
            b = int(faces[face_index, (offset + 1) % 3])
            key = (a, b) if a < b else (b, a)
            edges.setdefault(key, []).append(face_index)

    assigned = np.zeros(face_count, dtype=bool)
    regions: list[list[int]] = []
    for seed in range(face_count):
        if assigned[seed]:
            continue
        region = [seed]
        assigned[seed] = True
        stack = [seed]
        while stack:
            current = stack.pop()
            for offset in (0, 1, 2):
                a = int(faces[current, offset])
                b = int(faces[current, (offset + 1) % 3])
                key = (a, b) if a < b else (b, a)
                for neighbor in edges.get(key, ()):
                    if assigned[neighbor]:
                        continue
                    if (
                        float(normals[neighbor] @ normals[current])
                        < _SURFACE_REGION_COS
                    ):
                        continue
                    assigned[neighbor] = True
                    region.append(neighbor)
                    stack.append(neighbor)
        regions.append(region)
    return regions


def _host_mesh(context: ExecutionContext, host_ref: str) -> Any | None:
    """The cached host mesh for ``host_ref``, or None when it is unavailable."""
    parsed = split_expr_key(host_ref)
    if parsed is None:
        return None
    host_slug, host_id = parsed
    return context.geometry_cache.get(expr_key(host_slug, host_id))


def _curved_host_caps(
    context: ExecutionContext,
    host_ref: str,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
) -> tuple[list[list[int]], float | None] | None:
    """The hole caps of an oversized cutter on a curved host surface.

    A curved host (round wall) is faceted into thin strips, so it has no single
    dominant opposing plane pair to clip an oversized cutter to. The cutter's
    largest vertical faces are then its reveal wings — large faces lying along
    the wall — while the true hole caps are the vertical faces perpendicular to
    those wings (the through-window / through-door cross-section). The hole caps
    are selected from the cutter itself, and the depth is the host wall band
    along the hole normal.

    Returns ``(caps, depth)`` for a cutter that sits on a curved host surface
    region, or ``None`` for a flat host (which keeps the clip heuristic).
    """
    if len(faces) == 0:
        return None
    host_mesh = _host_mesh(context, host_ref)
    if host_mesh is None:
        return None
    host_vertices = np.asarray(host_mesh.vertices, dtype=np.float64)
    host_faces = np.asarray(host_mesh.faces, dtype=np.int64)
    if len(host_faces) == 0:
        return None
    host_normals = _face_normals(host_vertices, host_faces)

    cutter_min = vertices.min(axis=0)
    cutter_max = vertices.max(axis=0)
    curved: list[list[int]] = []
    curved_area = 0.0
    total_faces = list(range(len(host_faces)))
    total_area = _group_area(host_vertices, host_faces, total_faces)
    for region in _surface_regions(host_vertices, host_faces, host_normals):
        if not _region_is_curved(host_normals, region):
            continue
        curved_area += _group_area(host_vertices, host_faces, region)
        region_vertices = host_vertices[np.unique(host_faces[region])]
        if _bbox_overlap(
            cutter_min,
            cutter_max,
            region_vertices.min(axis=0),
            region_vertices.max(axis=0),
        ):
            curved.append(region)
    # Only a genuinely curved host (its curved regions dominate its surface) gets
    # the hole-cap rewrite; a flat wall with a tiny rounded corner stays on the
    # clip-to-slab path, which clips the opening to the real wall slab.
    if not curved or total_area <= 0.0:
        return None
    if curved_area / total_area < _CURVED_HOST_MIN_SHARE:
        return None

    vertical = [
        (group, _group_area(vertices, faces, group), normals[group[0]])
        for group in _planar_groups(vertices, faces, normals)
    ]
    vertical = [
        (group, area, normal)
        for group, area, normal in vertical
        if area > 0.0 and abs(float(normal[2])) < _CAP_VERTICAL_COS
    ]
    if len(vertical) < 2:
        return None
    vertical.sort(key=lambda item: item[1], reverse=True)

    # The largest vertical face is a reveal wing; the hole caps are the vertical
    # faces perpendicular to it. Wing faces themselves and the horizontal
    # top/bottom faces are dropped.
    wing_normal = vertical[0][2]
    hole_faces = [
        group
        for group, _area, normal in vertical
        if abs(float(normal @ wing_normal)) < _OPENING_PERPENDICULAR_COS
    ]
    if not hole_faces:
        return None

    depth = _host_band_depth(
        host_vertices,
        host_faces,
        host_normals,
        hole_faces[0],
        normals[hole_faces[0][0]],
        vertices,
        faces,
    )
    return (hole_faces, depth)


def _host_band_depth(
    host_vertices: np.ndarray,
    host_faces: np.ndarray,
    host_normals: np.ndarray,
    cap_group: list[int],
    cap_normal: np.ndarray,
    cutter_vertices: np.ndarray,
    cutter_faces: np.ndarray,
) -> float | None:
    """The host wall thickness along ``cap_normal`` under the hole cap face.

    The in-plane footprint of the hole cap selects the host wall facets that lie
    behind the opening. Their offsets along the cap normal span the inner and the
    outer wall surface; the full outer-to-inner span is the wall thickness the
    opening must reach. Returns ``None`` when the host contributes too few facets.
    """
    hole_points = cutter_vertices[np.unique(cutter_faces[cap_group])]
    center = hole_points.mean(axis=0)
    axis_u, axis_v = _in_plane_axes(cap_normal)
    pu = (hole_points - center) @ axis_u
    pv = (hole_points - center) @ axis_v
    u_min, u_max = float(pu.min()), float(pu.max())
    v_min, v_max = float(pv.min()), float(pv.max())

    centroids = host_vertices[host_faces].mean(axis=1)
    cu = (centroids - center) @ axis_u
    cv = (centroids - center) @ axis_v
    lateral = np.abs(host_normals[:, 2]) < _CAP_VERTICAL_COS
    in_region = lateral & (cu >= u_min) & (cu <= u_max) & (cv >= v_min) & (cv <= v_max)
    offsets = np.sort(centroids[in_region] @ cap_normal)
    if len(offsets) < 2:
        return None

    # A curved wall is faceted into many thin strips, so the host facets behind a
    # hole span several offset bands rather than two clean surfaces; the "largest
    # gap" split can land mid-wall between two intermediate strips and under-measure
    # the wall. The opening must span the full wall, so return the full outer-to-
    # inner span -- the distance between the outermost and innermost host surface
    # facets behind the hole. For a genuine two-band flat wall the outer and inner
    # facet clusters are each tight, so this equals the old single-gap split and
    # flat/2-band hosts did not regress.
    span = abs(float(offsets[-1]) - float(offsets[0]))

    # The single-cap prism is extruded from the hole CAP plane, which on a faced
    # round wall can sit noticeably proud of the curved outer facet centroids. When
    # it does, the outer->inner facet span stops short of the far wall surface by
    # that proud offset and the void under this cap is left too shallow. Re-measure
    # from the cap plane out to the innermost host surface and use it; keep the
    # plain facet span when the cap is near-flush so correctly-filled hosts are
    # untouched.
    cap_off = float(center @ cap_normal)
    cap_to_far = max(
        abs(cap_off - float(offsets[0])),
        abs(cap_off - float(offsets[-1])),
    )
    if cap_to_far - span > _CAP_PROUD_TOL:
        return cap_to_far
    return span


def _region_is_curved(normals: np.ndarray, region: list[int]) -> bool:
    """Whether a smooth surface region is curved (normals span more than ~2°)."""
    region_normals = normals[region]
    mean_normal = region_normals.mean(axis=0)
    length = float(np.linalg.norm(mean_normal))
    if length <= 1e-10:
        return False
    mean_normal = mean_normal / length
    return bool((np.abs(region_normals @ mean_normal) < _CURVED_REGION_COS).any())


def _bbox_overlap(
    a_min: np.ndarray, a_max: np.ndarray, b_min: np.ndarray, b_max: np.ndarray
) -> bool:
    """Whether two axis-aligned boxes overlap."""
    return bool(np.all(a_min <= b_max) and np.all(a_max >= b_min))


def _clip_to_slab(
    mesh: trimesh.Trimesh,
    host_normal: np.ndarray,
    t_min: float,
    t_max: float,
) -> trimesh.Trimesh | None:
    """The part of the opening solid that lies inside the host slab.

    Clips ``mesh`` between the two host surface planes by boolean intersection
    with a slab spanning the opening's in-plane footprint across ``[t_min, t_max]``
    along ``host_normal``. This cuts away the parts of the oversized opening that
    extend outside the element. Returns ``None`` when the intersection cannot be
    computed.
    """
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    axis_u, axis_v = _in_plane_axes(host_normal)
    u = float(np.ptp(vertices @ axis_u))
    v = float(np.ptp(vertices @ axis_v))
    dt = t_max - t_min
    if dt <= 0.0:
        return None
    origin = (
        float(np.mean(vertices @ axis_u)) * axis_u
        + float(np.mean(vertices @ axis_v)) * axis_v
        + (t_min + t_max) * 0.5 * host_normal
    )
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([axis_u, axis_v, host_normal])
    transform[:3, 3] = origin
    slab = trimesh.creation.box(
        extents=[u + 2.0 * _CLIP_EPSILON, v + 2.0 * _CLIP_EPSILON, dt],
        transform=transform,
    )

    solid, _error = ensure_watertight(mesh)
    if solid is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clipped = trimesh.boolean.intersection(
                [solid, slab], engine="manifold", check_volume=False
            )
    except Exception:
        return None
    if clipped is None or len(clipped.faces) == 0:
        return None
    return clipped


def _parallel_caps(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    host_normal: np.ndarray,
) -> list[list[int]]:
    """The cap-face groups parallel to the host surface.

    Only planar groups whose normal crosses ``host_normal`` by less than ~10°
    are candidates (the hole faces in the plane of the host surface). Among those
    the largest group and its largest opposing group are chosen, so the opening
    surface is always parallel to the wall it voids.
    """
    sized = [
        (
            group,
            _group_area(vertices, faces, group),
            float(normals[group[0]] @ host_normal),
        )
        for group in _planar_groups(vertices, faces, normals)
    ]
    sized = [
        (group, area)
        for group, area, parallel in sized
        if area > 0.0 and abs(parallel) >= _PARALLEL_COS
    ]
    sized.sort(key=lambda item: item[1], reverse=True)
    if not sized:
        return []

    caps = [sized[0][0]]
    first_normal = normals[caps[0][0]]
    for group, _area in sized[1:]:
        if float(normals[group[0]] @ first_normal) <= _OPPOSING_COS:
            caps.append(group)
            break
    return caps


def _clip_parallel_caps(
    context: ExecutionContext,
    host_ref: str,
    mesh: trimesh.Trimesh,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    caps: list[list[int]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[list[int]]] | None:
    """The host-parallel caps of ``mesh`` after clipping it to the host slab.

    Clips the opening solid to the host's dominant surface pair and returns its
    host-parallel cap faces (the hole in the host). When that slab does not cut a
    proper through-void (e.g. an opening in a secondary pitch of a multi-slope
    roof, where the dominant pair belongs to a different pitch), the remaining
    significant host surface pairs are tried in order of alignment with the
    opening's dominant face; the first to cut a two-cap, host-parallel through-void
    wins. Returns the clipped ``(vertices, faces, normals)`` and the new caps, or
    ``None`` when nothing cuts a through-void (the caller keeps the largest
    opposing heuristic, e.g. for recesses or single-cap voids).
    """
    cap_normal = normals[caps[0][0]]

    def clip_pair(
        normal: np.ndarray, t_min: float, t_max: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[list[int]]] | None:
        clipped = _clip_to_slab(mesh, normal, t_min, t_max)
        if clipped is None or len(clipped.faces) == 0:
            return None
        clipped_vertices = np.asarray(clipped.vertices, dtype=np.float64)
        clipped_faces = np.asarray(clipped.faces, dtype=np.int64)
        clipped_normals = _face_normals(clipped_vertices, clipped_faces)
        parallel_caps = _parallel_caps(
            clipped_vertices, clipped_faces, clipped_normals, normal
        )
        if len(parallel_caps) < 2:
            return None
        return (
            clipped_vertices,
            clipped_faces,
            clipped_normals,
            parallel_caps,
        )

    planes = _host_surface_planes(context, host_ref)
    if not planes:
        return None
    result = clip_pair(planes[0][0], planes[0][1], planes[0][2])
    if result is None:
        for normal, t_min, t_max, _area in sorted(
            planes[1:], key=lambda pair: -abs(float(pair[0] @ cap_normal))
        ):
            result = clip_pair(normal, t_min, t_max)
            if result is not None:
                break
    return result


def _in_plane_axes(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right-handed in-plane axes ``(u, v)`` of a cap plane.

    ``v`` stays as close to the world Z axis as the plane allows, so ``height``
    is the vertical extent for wall openings; near-horizontal planes
    (skylights) use the world Y axis instead. The chosen reference is never
    parallel to ``normal``, so the projection is always non-degenerate.
    """
    world_z = np.array([0.0, 0.0, 1.0])
    if abs(float(normal[2])) < _HORIZONTAL_COS:
        reference = world_z
    else:
        reference = np.array([0.0, 1.0, 0.0])
    vertical = reference - float(reference @ normal) * normal
    axis_v = vertical / float(np.linalg.norm(vertical))
    axis_u = np.cross(axis_v, normal)
    return axis_u, axis_v


def _cap_depth(
    vertices: np.ndarray,
    faces: np.ndarray,
    normal: np.ndarray,
    caps: list[list[int]],
) -> float | None:
    """Distance between the two cap planes along ``normal``; None for one cap."""
    if len(caps) < 2:
        return None
    offsets = [
        float(np.mean(vertices[np.unique(faces[group])] @ normal))
        for group in (caps[0], caps[1])
    ]
    return abs(offsets[1] - offsets[0])
