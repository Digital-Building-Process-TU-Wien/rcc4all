from __future__ import annotations

from pathlib import Path

from rcc4all_runner.schemas import (
    export_schemas,
    load_schemas,
)


def test_export_and_load_schemas_round_trip_and_prune_stale(tmp_path: Path) -> None:
    stale = tmp_path / "nodes" / "removed_node.schema.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}\n", encoding="utf-8")

    written = export_schemas(tmp_path)
    assert not stale.exists()
    assert (tmp_path / "index.json") in written
    assert (tmp_path / "workflow.schema.json") in written

    loaded = load_schemas(tmp_path)
    assert loaded.manifest["workflow"] == "workflow.schema.json"
    assert list(loaded.nodes.keys()) == sorted(loaded.nodes.keys())
    assert loaded.nodes
    for node_schema in loaded.nodes.values():
        locales = list(node_schema["locales"].keys())
        assert locales == sorted(locales)

    assert "SubworkflowPort" in loaded.workflow["$defs"]
    assert list(loaded.workflow["$defs"]["SubworkflowPort"]["properties"]) == ["name"]
