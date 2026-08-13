from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Sequence

import ifcopenshell
import trimesh

from openbim_runner.util.geometry import build_geometry_cache

# Dev tooling defaults: resolve the runner tree from the source layout.
RUNNER_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = RUNNER_ROOT / "tests" / "testdata" / "models"
ARTIFACTS_ROOT = RUNNER_ROOT / "tests" / "artifacts"


def discover_models(
    models_root: Path = MODELS_ROOT,
    *,
    category: str | None = None,
    pattern: str | None = None,
) -> list[tuple[str, Path]]:
    """Yield (category, path) for every IFC model under the models root.

    The category is the first path segment below the root (e.g. ``rail``,
    ``large_models``). Optional ``category`` and ``pattern`` filters restrict
    the result; ``pattern`` matches the file stem case-insensitively.
    """
    discovered: list[tuple[str, Path]] = []
    for ifc_path in sorted(models_root.rglob("*.ifc")):
        rel = ifc_path.relative_to(models_root)
        rel_category = rel.parts[0] if len(rel.parts) > 1 else ""
        if category and rel_category != category:
            continue
        if pattern and pattern.lower() not in ifc_path.stem.lower():
            continue
        discovered.append((rel_category, ifc_path))
    return discovered


def _mesh_report(mesh: trimesh.Trimesh) -> dict[str, Any]:
    return {
        "verts": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
    }


def process_model(
    ifc_path: Path,
    artifacts_root: Path,
    *,
    express_id: int | None = None,
) -> dict[str, Any]:
    """Tessellate one IFC model and write report (and OBJ) artifacts."""
    model = ifcopenshell.open(str(ifc_path))
    cache = build_geometry_cache(model)

    mesh_dir = artifacts_root / ifc_path.stem
    mesh_dir.mkdir(parents=True, exist_ok=True)

    elements: list[dict[str, Any]] = []
    combined: list[trimesh.Trimesh] = []
    for key in sorted(cache, key=lambda k: int(k.split(":")[1])):
        mesh = cache[key]
        combined.append(mesh)
        elements.append({"express_id": int(key.split(":")[1]), **_mesh_report(mesh)})

    combined_verts = 0
    if combined:
        merged = trimesh.util.concatenate(combined)
        merged.export(str(mesh_dir / f"{ifc_path.stem}_all.obj"))
        combined_verts = int(len(merged.vertices))

    report = {
        "model": ifc_path.stem,
        "ifc_path": str(ifc_path),
        "mesh_count": len(elements),
        "elements": elements,
        "combined_verts": combined_verts,
    }

    if express_id is not None:
        target_key = f"ifc:{express_id}"
        if target_key not in cache:
            raise ValueError(f"Express ID {express_id} not found in model '{ifc_path.stem}'.")
        cache[target_key].export(str(mesh_dir / f"ifc_{express_id}.obj"))
        report["exported_express_id"] = express_id

    (mesh_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def inspect_models(
    models_root: Path = MODELS_ROOT,
    artifacts_root: Path = ARTIFACTS_ROOT,
    *,
    category: str | None = None,
    pattern: str | None = None,
    express_id: int | None = None,
) -> int:
    models = discover_models(models_root, category=category, pattern=pattern)
    if not models:
        print(f"No IFC models found under {models_root}", file=sys.stderr)
        return 1

    failures = 0
    print(f"{'MODEL':40} {'CATEGORY':14} MESHES   STATUS")
    for rel_category, ifc_path in models:
        try:
            report = process_model(ifc_path, artifacts_root, express_id=express_id)
        except Exception as exc:  # noqa: BLE001 - report any unprocessable model
            failures += 1
            print(f"{ifc_path.stem:40} {rel_category:14} {'-':7} FAIL: {exc}")
            continue

        status = "OK"
        if express_id is not None and "exported_express_id" in report:
            status = f"OK (exported {report['exported_express_id']})"
        elif report["mesh_count"] == 0:
            status = "NO-GEOMETRY"
        print(f"{ifc_path.stem:40} {rel_category:14} {report['mesh_count']:<7} {status}")

    print(f"\nProcessed {len(models) - failures}/{len(models)} models -> {artifacts_root}")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="inspect-models")
    parser.add_argument("--models-root", type=Path, default=MODELS_ROOT)
    parser.add_argument("--artifacts-root", type=Path, default=ARTIFACTS_ROOT)
    parser.add_argument("--category", default=None, help="Only process this category (e.g. rail, large_models).")
    parser.add_argument("--pattern", default=None, help="Only process models whose stem matches (case-insensitive).")
    parser.add_argument("--express-id", type=int, default=None, help="Also export this single express ID as OBJ for each model.")
    args = parser.parse_args(argv)

    return inspect_models(
        args.models_root,
        args.artifacts_root,
        category=args.category,
        pattern=args.pattern,
        express_id=args.express_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
