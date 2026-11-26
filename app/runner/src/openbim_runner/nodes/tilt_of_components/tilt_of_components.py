from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import trimesh
from pydantic import Field

from openbim_runner.nodes.base import ExecutionContext, NodeModel, node
from openbim_runner.nodes.bcf_output.harmonized import (
    HarmonizedCheckResult,
    HarmonizedElement,
)
from openbim_runner.util.geometry import cache_mesh, expr_key, resolve_mesh
from openbim_runner.util.references import ElementRef, parse_element_refs

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
    express_ids: list[str] = Field(
        title="Express IDs",
        description=(
            "Qualified element references (`<slug>:expr:<id>`) to measure. Bind "
            "ifc_element_filter output here."
        ),
    )


# The result models are the harmonized check schema shared with other checking
# nodes (e.g. loi_check). Keeping these aliases lets this node read the same
# data shape while exposing a single source of truth for downstream consumers
# like bcf_output.
TiltCheck = HarmonizedCheckResult
TiltsElement = HarmonizedElement


class TiltOfComponentsResult(NodeModel):
    summary_element_count: int = Field(
        title="Element count",
        description="Number of elements processed.",
    )
    summary_passed_count: int = Field(
        title="Passed count",
        description="Number of checked elements with no flagged surface/axis.",
    )
    summary_failed_count: int = Field(
        title="Failed count",
        description="Number of checked elements with at least one flagged surface/axis.",
    )
    summary_check_count: int = Field(
        title="Check count",
        description="Total number of surface/axis checks across all elements.",
    )
    passed_express_ids: list[str] = Field(
        default=[],
        title="Passed express IDs",
        description="Qualified references of elements whose checks all passed. Only elements with at least one check are included.",
    )
    failed_express_ids: list[str] = Field(
        default=[],
        title="Failed express IDs",
        description="Qualified references of elements with at least one flagged check. Only elements with at least one check are included.",
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

    elements: list[TiltsElement] = []

    for element in parse_element_refs(inputs.express_ids, node="tilt_of_components"):
        reference = element.reference
        class_name = _resolve_class_name(context, element)
        mesh = _resolve_composed_mesh(context, element)

        if mesh is None or len(mesh.faces) == 0:
            elements.append(
                TiltsElement(
                    express_ids=[reference],
                    class_name=class_name,
                    failed=False,
                    checks=[],
                )
            )
            continue

        checks = _compute_checks(
            settings,
            mesh,
            context=context,
            reference=reference,
        )
        element_failed = any(not check.passed for check in checks)

        elements.append(
            TiltsElement(
                express_ids=[reference],
                class_name=class_name,
                failed=element_failed,
                checks=checks,
            )
        )

    checked = [element for element in elements if element.checks]
    passed_express_ids = [
        ref for element in checked if not element.failed for ref in element.express_ids
    ]
    failed_express_ids = [
        ref for element in checked if element.failed for ref in element.express_ids
    ]

    return TiltOfComponentsResult(
        summary_element_count=len(elements),
        summary_passed_count=len(passed_express_ids),
        summary_failed_count=len(failed_express_ids),
        summary_check_count=sum(len(element.checks) for element in elements),
        passed_express_ids=passed_express_ids,
        failed_express_ids=failed_express_ids,
        elements=elements,
    )


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


def _resolve_class_name(context: ExecutionContext, element: ElementRef) -> str:
    """Resolve the IFC class of a parsed element reference; 'unknown' if missing."""
    try:
        entity = context.resolve_model(element.slug).by_id(element.express_id)
        return entity.is_a()
    except RuntimeError:
        return "unknown"


def _resolve_composed_mesh(
    context: ExecutionContext, element: ElementRef
) -> trimesh.Trimesh | None:
    """Resolve the mesh used to measure a parsed element reference.

    The element's own tessellated Body mesh is used when available. Otherwise the
    element is treated as an assembly: the Body meshes of all its aggregated
    component parts (recursively through ``IfcRelAggregates``) are merged into a
    single combined mesh. Returns ``None`` when nothing usable is found.
    """
    try:
        try:
            mesh = resolve_mesh(context, element.reference)
            if len(mesh.faces) > 0:
                return mesh
        except ValueError:
            pass

        entity = context.resolve_model(element.slug).by_id(element.express_id)
        parts = _collect_descendant_meshes(context, entity, set(), element.slug)
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
    model_slug: str,
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
                mesh = resolve_mesh(context, expr_key(model_slug, part_id))
                if len(mesh.faces) > 0:
                    collected.append(mesh)
                    continue
            except ValueError:
                pass
            collected.extend(
                _collect_descendant_meshes(context, part, seen, model_slug)
            )
    return collected


def _compute_checks(
    settings: TiltOfComponentsSettings,
    mesh: trimesh.Trimesh,
    *,
    context: ExecutionContext,
    reference: str,
) -> list[TiltCheck]:
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
            reference,
        )
    return _checks_1d(
        settings,
        vertices,
        faces,
        normals,
        context,
        reference,
    )


def _checks_2d(
    settings: TiltOfComponentsSettings,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    context: ExecutionContext,
    reference: str,
) -> list[TiltCheck]:
    separation = settings.horizontal_separation_angle / _DEG
    groups = _group_surfaces(normals, separation)
    areas = [_surface_area(vertices, faces, group) for group in groups]

    ordered = sorted(
        zip(areas, groups, strict=True), key=lambda item: item[0], reverse=True
    )
    largest_two = [group for _, group in ordered[:2]]

    checks: list[TiltCheck] = []
    for surface_index, group in enumerate(largest_two):
        angles_rad = np.arccos(np.clip(-normals[group, 2], -1.0, 1.0))
        tilt = float(angles_rad.mean() * _DEG)
        if tilt > 90.1:
            tilt = 180.0 - tilt
        tilt = round(tilt, 2)

        passed = not _is_flagged(settings, tilt)
        if not passed:
            cache_mesh(
                context=context,
                mesh=_build_submesh(vertices, faces, group),
                key=f"inter:tilt_surface_{reference}_{surface_index}",
            )

        checks.append(
            TiltCheck(
                key=f"surface_{surface_index}",
                check_parameter="angle",
                expected_value=_expected_text(settings),
                actual_value=_format_tilt(tilt),
                unit="deg",
                passed=passed,
            )
        )
    return checks


def _checks_1d(
    settings: TiltOfComponentsSettings,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    context: ExecutionContext,
    reference: str,
) -> list[TiltCheck]:
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
    if not passed:
        cache_mesh(
            context=context,
            mesh=_build_axis_line(centroid1, centroid2),
            key=f"inter:tilt_axis_{reference}",
        )

    return [
        TiltCheck(
            key="axis",
            check_parameter="angle",
            expected_value=_expected_text(settings),
            actual_value=_format_tilt(tilt),
            unit="deg",
            passed=passed,
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


def _format_tilt(tilt: float) -> str:
    """Render a tilt angle (already rounded to 2 dp) as a string."""
    return str(tilt)


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
