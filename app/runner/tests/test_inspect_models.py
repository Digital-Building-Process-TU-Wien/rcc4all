from __future__ import annotations

import json
from pathlib import Path

import pytest

from openbim_runner.inspect_models import MODELS_ROOT, discover_models, process_model


def _railway() -> Path:
    return MODELS_ROOT / "rail" / "simple_railway.ifc"


def test_discover_models_finds_in_repo_models() -> None:
    models = discover_models()

    assert ("rail", _railway()) in models


def test_discover_models_respects_category_and_pattern(tmp_path: Path) -> None:
    models = discover_models(category="rail")
    assert all(category == "rail" for category, _ in models)

    assert discover_models(category="does-not-exist") == []
    assert discover_models(pattern="simple_railway") != []
    assert discover_models(pattern="does-not-exist") == []


def test_process_model_writes_obj_and_report(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    report = process_model(_railway(), artifacts)

    assert report["mesh_count"] >= 1
    assert report["combined_verts"] > 0

    mesh_dir = artifacts / "simple_railway"
    assert (mesh_dir / "simple_railway_all.obj").exists()
    assert (mesh_dir / "report.json").exists()

    written = json.loads((mesh_dir / "report.json").read_text(encoding="utf-8"))
    assert written["model"] == "simple_railway"


def test_process_model_writes_only_combined_obj_by_default(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    process_model(_railway(), artifacts)

    objs = sorted(p.name for p in (artifacts / "simple_railway").glob("*.obj"))
    assert objs == ["simple_railway_all.obj"]


def test_process_model_exports_singular_express_id(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    report = process_model(_railway(), artifacts, express_id=252)

    mesh_dir = artifacts / "simple_railway"
    assert (mesh_dir / "ifc_252.obj").exists()
    assert report["exported_express_id"] == 252
    assert sorted(p.name for p in (mesh_dir).glob("*.obj")) == [
        "ifc_252.obj",
        "simple_railway_all.obj",
    ]


def test_process_model_unknown_express_id_raises(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    with pytest.raises(ValueError, match="Express ID 999"):
        process_model(_railway(), artifacts, express_id=999)
