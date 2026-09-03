from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.util.geometry import cache_mesh, resolve_mesh

ElementCategory = Literal["2d", "1d"]
ComparisonMethod = Literal[
    "greater_than_lower",
    "less_than_upper",
    "inside_interval",
    "outside_interval",
]

_NEG_UNIT_Z = np.array([0.0, 0.0, -1.0], dtype=np.float64)
_DEG = 180.0 / math.pi
_AXIS_RADIUS = 0.02  # metres — thickness of the 1D helper-axis representation


class TiltOfComponentsSettings(NodeModel):
    element_category: ElementCategory = Field(
        default="2d",
        title="Element category",
        description=(
            "'2d' measures the two largest flat surfaces (walls & slabs); "
            "'1d' measures the longitudinal axis of the element (columns & beams)."
        ),
    )
    comparison_method: ComparisonMethod = Field(
        default="greater_than_lower",
        title="Comparison method",
        description=(
            "How the measured tilt is checked against the limits. "
            "'greater_than_lower' / 'less_than_upper' use the single lower / upper "
            "limit; 'inside_interval' / 'outside_interval' use the interval barriers."
        ),
    )
    lower_limit: float = Field(
        default=0.0,
        title="Lower limit (°)",
        description="Tilt is flagged when it exceeds this value (comparison_method = greater_than_lower).",
    )
    upper_limit: float = Field(
        default=90.0,
        title="Upper limit (°)",
        description="Tilt is flagged when it is below this value (comparison_method = less_than_upper).",
    )
    interval_lower: float = Field(
        default=0.0,
        title="Interval lower (°)",
        description="Lower barrier used for inside_interval / outside_interval.",
    )
    interval_upper: float = Field(
        default=90.0,
        title="Interval upper (°)",
        description="Upper barrier used for inside_interval / outside_interval.",
    )
    horizontal_separation_angle: float = Field(
        default=5.0,
        title="Horizontal separation angle (°)",
        description=(
            "Maximum horizontal angle deviation between two triangles to still count "
            "as the same surface. Used to merge the facets of curved / round objects."
        ),
    )
    tolerance: float = Field(
        default=0.1,
        title="Tolerance (°)",
        description="Shared tolerance added/subtracted to the limits when flagging.",
    )


class TiltOfComponentsInputs(NodeModel):
    express_ids: list[int] = Field(
        default=[],
        title="Express IDs",
        description=(
            "Optional list of IFC express IDs to measure. When empty, all IFC elements "
            "in the model are checked."
        ),
    )


class TiltSurfaceCheck(NodeModel):
    expected: str = Field(
        title="Expected",
        description="Human-readable expectation combined from the comparison method and limits.",
    )
    tilt_angle: float = Field(
        title="Tilt angle (°)",
        description="Measured tilt of the surface or axis in degrees.",
    )
    passed: bool = Field(
        title="Passed",
        description="False when this surface/axis is flagged by the comparison method.",
    )
    geometry_key: str | None = Field(
        default=None,
        title="Geometry key",
        description="Geometry-cache key of the helper geometry for flagged surfaces/axes.",
    )


class TiltsElement(NodeModel):
    express_id: int = Field(
        title="Express ID",
        description="The express ID of the IFC entity.",
    )
    class_name: str = Field(
        title="Class name",
        description="IFC entity class (e.g. IFCWALL) or 'unknown' for missing entities.",
    )
    element_category: ElementCategory = Field(
        title="Element category",
        description="The element category ('2d' or '1d') used to measure this element.",
    )
    failed: bool = Field(
        title="Failed",
        description="True if at least one surface/axis check in this element was flagged.",
    )
    checks: list[TiltSurfaceCheck] = Field(
        default=[],
        title="Checks",
        description="Surface ('2d') or axis ('1d') tilt checks for this element.",
    )


class TiltOfComponentsResult(NodeModel):
    element_count: int = Field(
        title="Element count",
        description="Number of elements processed.",
    )
    check_count: int = Field(
        title="Check count",
        description="Number of elements with at least one surface/axis check.",
    )
    failed_count: int = Field(
        title="Failed count",
        description="Number of elements with at least one flagged surface/axis.",
    )
    model_name: str = Field(
        default="",
        title="Model name",
        description="Name of the checked IFC model.",
    )
    elements: list[TiltsElement] = Field(
        default=[],
        title="Elements",
        description="Ordered list of elements with their tilt checks.",
    )


@node()
async def tilt_of_components(
    settings: TiltOfComponentsSettings,
    inputs: TiltOfComponentsInputs,
    context: ExecutionContext,
) -> TiltOfComponentsResult:
    _validate_settings(settings)

    if settings.horizontal_separation_angle < 0:
        raise ValueError("horizontal_separation_angle must not be negative.")

    express_ids = list(inputs.express_ids)
    if not express_ids:
        try:
            express_ids = [
                entity.id() for entity in context.ifc_model.by_type("IfcElement")
            ]
        except RuntimeError:
            express_ids = []

    elements: list[TiltsElement] = []
    check_count = 0
    failed_count = 0

    for express_id in express_ids:
        class_name = _resolve_class_name(context, express_id)
        mesh = _resolve_composed_mesh(context, express_id)

        if mesh is None or len(mesh.faces) == 0:
            elements.append(
                TiltsElement(
                    express_id=express_id,
                    class_name=class_name,
                    element_category=settings.element_category,
                    failed=False,
                    checks=[],
                )
            )
            continue

        checks = _compute_checks(
            settings,
            mesh,
            context=context,
            express_id=express_id,
        )
        element_failed = any(not check.passed for check in checks)
        check_count += 1
        if element_failed:
            failed_count += 1

        elements.append(
            TiltsElement(
                express_id=express_id,
                class_name=class_name,
                element_category=settings.element_category,
                failed=element_failed,
                checks=checks,
            )
        )

    return TiltOfComponentsResult(
        element_count=len(elements),
        check_count=check_count,
        failed_count=failed_count,
        model_name=_resolve_model_name(context),
        elements=elements,
    )


def _resolve_model_name(context: ExecutionContext) -> str:
    """Node-local best-effort name of the checked IFC model.

    Uses the IFC header ``FILE_NAME`` and reduces it to the basename (stripping
    any directory portion and the file extension). Falls back to the
    ``IfcProject`` name, then to an empty string. Never raises.
    """

    def _basename_stem(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.replace("\\", "/").rstrip("/")
        if not normalized:
            return None
        base = normalized.rsplit("/", 1)[-1]
        if base.lower().endswith(".ifc"):
            base = base[: -len(".ifc")]
        return base or None

    try:
        header = getattr(context.ifc_model, "header", None)
        file_name = getattr(header, "file_name", None)
        stored_name = _basename_stem(getattr(file_name, "name", None))
        if stored_name is not None:
            return stored_name
    except (AttributeError, RuntimeError):
        pass

    try:
        for project in context.ifc_model.by_type("IfcProject"):
            name = getattr(project, "Name", None)
            if isinstance(name, str) and name:
                return name
    except (AttributeError, RuntimeError):
        return ""

    return ""


def _validate_settings(settings: TiltOfComponentsSettings) -> None:
    if (
        settings.comparison_method in ("inside_interval", "outside_interval")
        and settings.interval_lower > settings.interval_upper
    ):
        raise ValueError("interval_lower must be less than or equal to interval_upper.")
    if settings.comparison_method == "greater_than_lower" and settings.lower_limit < 0:
        raise ValueError("lower_limit must not be negative for this comparison method.")
    if settings.comparison_method == "less_than_upper" and settings.upper_limit < 0:
        raise ValueError("upper_limit must not be negative for this comparison method.")


def _resolve_class_name(context: ExecutionContext, express_id: int) -> str:
    try:
        entity = context.ifc_model.by_id(express_id)
        return entity.is_a()
    except RuntimeError:
        return "unknown"


def _resolve_composed_mesh(
    context: ExecutionContext, express_id: int
) -> trimesh.Trimesh | None:
    """Resolve the mesh used to measure an element.

    The element's own tessellated Body mesh is used when available. Otherwise the
    element is treated as an assembly: the Body meshes of all its aggregated
    component parts (recursively through ``IfcRelAggregates``) are merged into a
    single combined mesh. Returns ``None`` when nothing usable is found.
    """
    try:
        try:
            mesh = resolve_mesh(context, f"ifc:{express_id}")
            if len(mesh.faces) > 0:
                return mesh
        except ValueError:
            pass

        entity = context.ifc_model.by_id(express_id)
        parts = _collect_descendant_meshes(context, entity, set())
        if not parts:
            return None

        vertex_offsets = np.cumsum([0] + [len(part.vertices) for part in parts[:-1]])
        vertices = np.concatenate([part.vertices for part in parts])
        faces = np.concatenate(
            [
                part.faces + offset
                for part, offset in zip(parts, vertex_offsets, strict=True)
            ]
        )
        return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _collect_descendant_meshes(
    context: ExecutionContext,
    entity: Any,
    seen: set[int],
) -> list[trimesh.Trimesh]:
    """Collect Body meshes from an element's aggregated component sub-tree.

    Depth-first: for each ``IfcRelAggregates`` child, its own Body mesh is used
    when present; otherwise traversal continues into the child's own aggregation.
    ``seen`` guards against shared parts and decomposition cycles.
    """
    collected: list[trimesh.Trimesh] = []
    relationships = getattr(entity, "IsDecomposedBy", None) or []
    for relationship in relationships:
        try:
            if relationship.is_a() != "IfcRelAggregates":
                continue
            parts = relationship.RelatedObjects or []
        except (AttributeError, RuntimeError):
            continue
        for part in parts:
            try:
                part_id = part.id()
            except (AttributeError, RuntimeError):
                continue
            if part_id in seen:
                continue
            seen.add(part_id)
            try:
                mesh = resolve_mesh(context, f"ifc:{part_id}")
                if len(mesh.faces) > 0:
                    collected.append(mesh)
                    continue
            except ValueError:
                pass
            collected.extend(_collect_descendant_meshes(context, part, seen))
    return collected


def _compute_checks(
    settings: TiltOfComponentsSettings,
    mesh: trimesh.Trimesh,
    *,
    context: ExecutionContext,
    express_id: int,
) -> list[TiltSurfaceCheck]:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normals = _face_normals(vertices, faces)

    if settings.element_category == "2d":
        return _checks_2d(
            settings,
            vertices,
            faces,
            normals,
            context,
            express_id,
        )
    return _checks_1d(
        settings,
        vertices,
        faces,
        normals,
        context,
        express_id,
    )


def _checks_2d(
    settings: TiltOfComponentsSettings,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    context: ExecutionContext,
    express_id: int,
) -> list[TiltSurfaceCheck]:
    separation = settings.horizontal_separation_angle / _DEG
    groups = _group_surfaces(normals, separation)
    areas = [_surface_area(vertices, faces, group) for group in groups]

    ordered = sorted(
        zip(areas, groups, strict=True), key=lambda item: item[0], reverse=True
    )
    largest_two = [group for _, group in ordered[:2]]

    checks: list[TiltSurfaceCheck] = []
    for surface_index, group in enumerate(largest_two):
        angles_rad = np.arccos(np.clip(-normals[group, 2], -1.0, 1.0))
        tilt = float(angles_rad.mean() * _DEG)
        if tilt > 90.1:
            tilt = 180.0 - tilt
        tilt = round(tilt, 2)

        passed = not _is_flagged(settings, tilt)
        geometry_key: str | None = None
        if not passed:
            geometry_key = f"inter:tilt_surface_{express_id}_{surface_index}"
            cache_mesh(
                context=context,
                mesh=_build_submesh(vertices, faces, group),
                key=geometry_key,
            )

        checks.append(
            TiltSurfaceCheck(
                expected=_expected_text(settings),
                tilt_angle=tilt,
                passed=passed,
                geometry_key=geometry_key,
            )
        )
    return checks


def _checks_1d(
    settings: TiltOfComponentsSettings,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    context: ExecutionContext,
    express_id: int,
) -> list[TiltSurfaceCheck]:
    separation = settings.horizontal_separation_angle / _DEG
    groups = _group_surfaces(normals, separation)

    centroids = [_area_weighted_centroid(vertices, faces, group) for group in groups]

    centroid1 = centroids[0]
    centroid2 = centroids[0]
    max_sq = -1.0
    for i in range(len(centroids)):
        for j in range(len(centroids)):
            diff = centroids[i] - centroids[j]
            sq = float(np.dot(diff, diff))
            if sq > max_sq:
                max_sq = sq
                centroid1 = centroids[i]
                centroid2 = centroids[j]

    tilt_vector = centroid1 - centroid2
    tilt_rad = _angle_to_neg_z(tilt_vector) - math.pi / 2
    tilt = abs(tilt_rad) * _DEG
    tilt = round(tilt, 2)

    passed = not _is_flagged(settings, tilt)
    geometry_key: str | None = None
    if not passed:
        geometry_key = f"inter:tilt_axis_{express_id}"
        cache_mesh(
            context=context,
            mesh=_build_axis_line(centroid1, centroid2),
            key=geometry_key,
        )

    return [
        TiltSurfaceCheck(
            expected=_expected_text(settings),
            tilt_angle=tilt,
            passed=passed,
            geometry_key=geometry_key,
        )
    ]


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(cross, axis=1)
    normals = np.zeros_like(cross)
    np.divide(cross, lengths[:, None], out=normals, where=lengths[:, None] > 0)
    return normals


def _surface_area(vertices: np.ndarray, faces: np.ndarray, group: list[int]) -> float:
    return float(_triangle_areas(vertices, faces, group).sum())


def _triangle_areas(
    vertices: np.ndarray, faces: np.ndarray, group: list[int]
) -> np.ndarray:
    v0 = vertices[faces[group, 0]]
    v1 = vertices[faces[group, 1]]
    v2 = vertices[faces[group, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    return 0.5 * np.linalg.norm(cross, axis=1)


def _group_surfaces(normals: np.ndarray, separation_rad: float) -> list[list[int]]:
    count = normals.shape[0]
    used = np.zeros(count, dtype=bool)
    groups: list[list[int]] = []

    for start in range(count):
        if used[start]:
            continue
        used[start] = True
        group: list[int] = []
        stack = [start]
        while stack:
            current = stack.pop()
            group.append(current)
            cur_normal = normals[current]
            cur_z = abs(cur_normal[2])
            for candidate in range(count):
                if used[candidate]:
                    continue
                cand_normal = normals[candidate]
                same_vertical = abs(cur_normal[2] - cand_normal[2]) < 0.001
                if cur_z < 0.99 and same_vertical:
                    angle = _angle_2d(cur_normal, cand_normal)
                    if angle < separation_rad:
                        used[candidate] = True
                        stack.append(candidate)
                else:
                    if _angle_3d(cur_normal, cand_normal) < math.pi / 180.0:
                        used[candidate] = True
                        stack.append(candidate)
        groups.append(group)
    return groups


def _angle_2d(a: np.ndarray, b: np.ndarray) -> float:
    cross = a[0] * b[1] - a[1] * b[0]
    dot = a[0] * b[0] + a[1] * b[1]
    return abs(math.atan2(cross, dot))


def _angle_3d(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    return math.acos(dot)


def _area_weighted_centroid(
    vertices: np.ndarray, faces: np.ndarray, group: list[int]
) -> np.ndarray:
    areas = _triangle_areas(vertices, faces, group)
    centroids = vertices[faces[group]].mean(axis=1)
    total = areas.sum()
    if total <= 0:
        return centroids.mean(axis=0)
    return np.sum(centroids * areas[:, None], axis=0) / total


def _angle_to_neg_z(vector: np.ndarray) -> float:
    length = float(np.linalg.norm(vector))
    if length <= 0:
        return 0.0
    dot = float(np.dot(vector, _NEG_UNIT_Z) / length)
    return math.acos(np.clip(dot, -1.0, 1.0))


def _expected_text(settings: TiltOfComponentsSettings) -> str:
    def _format(value: float) -> str:
        return format(value, ".10g")

    if settings.comparison_method == "greater_than_lower":
        return f"less than or equal to {_format(settings.lower_limit)}"
    if settings.comparison_method == "less_than_upper":
        return f"greater than or equal to {_format(settings.upper_limit)}"
    if settings.comparison_method == "inside_interval":
        return (
            f"outside {_format(settings.interval_lower)} and "
            f"{_format(settings.interval_upper)}"
        )
    return f"inside {_format(settings.interval_lower)} and {_format(settings.interval_upper)}"


def _is_flagged(settings: TiltOfComponentsSettings, tilt: float) -> bool:
    tol = settings.tolerance
    if settings.comparison_method == "greater_than_lower":
        return tilt > settings.lower_limit + tol
    if settings.comparison_method == "less_than_upper":
        return tilt < settings.upper_limit - tol
    if settings.comparison_method == "inside_interval":
        return (tilt > settings.interval_lower - tol) and (
            tilt < settings.interval_upper + tol
        )
    # outside_interval
    return (tilt < settings.interval_lower - tol) or (
        tilt > settings.interval_upper + tol
    )


def _build_submesh(
    vertices: np.ndarray, faces: np.ndarray, group: list[int]
) -> trimesh.Trimesh:
    return trimesh.Trimesh(vertices=vertices, faces=faces[group], process=False)


def _build_axis_line(point_a: np.ndarray, point_b: np.ndarray) -> trimesh.Trimesh:
    direction = point_b - point_a
    height = float(np.linalg.norm(direction))
    if height <= 1e-12:
        direction = np.array([0.0, 0.0, 1.0])
        height = 1.0
    direction = direction / np.linalg.norm(direction)

    cylinder = trimesh.creation.cylinder(radius=_AXIS_RADIUS, height=height, sections=8)

    from trimesh.transformations import rotation_matrix

    z_axis = np.array([0.0, 0.0, 1.0])
    axis = np.cross(z_axis, direction)
    axis_norm = float(np.linalg.norm(axis))
    if axis_norm > 1e-12:
        axis = axis / axis_norm
        angle = math.acos(float(np.clip(np.dot(z_axis, direction), -1.0, 1.0)))
        cylinder.apply_transform(rotation_matrix(angle, axis))
    elif float(np.dot(z_axis, direction)) < 0:
        cylinder.apply_translation([0.0, 0.0, height])

    cylinder.apply_translation((point_a + point_b) / 2.0)
    return cylinder
