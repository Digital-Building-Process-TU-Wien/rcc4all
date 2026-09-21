from __future__ import annotations

from typing import Any, cast

import pytest
import trimesh

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.util.geometry import cache_mesh, resolve_side, split_expr_key
from openbim_runner.workflow import (
    ModelFile,
    WorkflowDefinition,
    WorkflowNode,
    validate_model_files,
)


class _FakeModel:
    """Minimal stand-in for ifcopenshell.file (identity resolution only)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def by_id(self, express_id: int) -> Any:
        if express_id < 1:
            raise RuntimeError(f"no entity {express_id}")
        return _FakeEntity(self.name, express_id)


class _FakeEntity:
    def __init__(self, model: str, express_id: int) -> None:
        self._model = model
        self._id = express_id
        self.is_a_result = f"{model}-entity"

    def id(self) -> int:
        return self._id

    def is_a(self) -> str:
        return self.is_a_result


# --- WorkflowDefinition.files -----------------------------------------------


def _definition(files: list[ModelFile]) -> WorkflowDefinition:
    return WorkflowDefinition(
        files=files,
        nodes=[WorkflowNode(id="n1", type="concat_string", settings={})],
        edges=[],
    )


def test_main_slug_is_required() -> None:
    workflow = _definition([ModelFile(path="a.ifc", slug="arch")])
    with pytest.raises(ValueError, match="slug 'main'"):
        validate_model_files(workflow.files)


def test_empty_files_are_rejected() -> None:
    workflow = _definition([])
    with pytest.raises(ValueError, match="at least one IFC file"):
        validate_model_files(workflow.files)


def test_duplicate_slugs_are_rejected() -> None:
    workflow = _definition(
        [
            ModelFile(path="a.ifc", slug="main"),
            ModelFile(path="b.ifc", slug="arch"),
            ModelFile(path="c.ifc", slug="arch"),
        ]
    )
    with pytest.raises(ValueError, match="Duplicate model slug 'arch'"):
        validate_model_files(workflow.files)


@pytest.mark.parametrize("slug", ["Main", "Arch Plan", "ä", "arch.name", "arc h"])
def test_invalid_slug_pattern_is_rejected(slug: str) -> None:
    workflow = _definition(
        [ModelFile(path="a.ifc", slug="main"), ModelFile(path="b.ifc", slug=slug)]
    )
    with pytest.raises(ValueError, match="Invalid model slug"):
        validate_model_files(workflow.files)


def test_valid_slugs_pass() -> None:
    workflow = _definition(
        [
            ModelFile(path="a.ifc", slug="main"),
            ModelFile(path="b.ifc", slug="arch-1"),
            ModelFile(path="c.ifc", slug="arch_2"),
        ]
    )
    validate_model_files(workflow.files)


# --- ExecutionContext model resolution --------------------------------------


def _context() -> ExecutionContext:
    return ExecutionContext(
        models={
            "main": cast(Any, _FakeModel("main")),
            "arch": cast(Any, _FakeModel("arch")),
        },
        node_outputs={},
    )


def test_resolve_model_defaults_to_main() -> None:
    context = _context()
    assert context.resolve_model().name == "main"
    assert context.resolve_model(None).name == "main"
    assert context.ifc_model.name == "main"


def test_resolve_model_by_slug() -> None:
    context = _context()
    assert context.resolve_model("arch").name == "arch"


def test_resolve_model_unknown_slug_lists_known() -> None:
    context = _context()
    with pytest.raises(ValueError, match=r"Unknown model slug 'nope'.*Available slugs"):
        context.resolve_model("nope")


# --- Geometry cache keys are slug-scoped ------------------------------------


def test_split_expr_key() -> None:
    assert split_expr_key("main:expr:123") == ("main", 123)
    assert split_expr_key("arch-1:expr:9") == ("arch-1", 9)
    assert split_expr_key("gen:abc") is None
    assert split_expr_key("inter:x") is None


def test_cache_mesh_keys_by_slug() -> None:
    context = _context()
    key_main = cache_mesh(context, trimesh.creation.box(), express_id=1)
    key_arch = cache_mesh(context, trimesh.creation.box(), express_id=1, slug="arch")
    assert key_main == "main:expr:1"
    assert key_arch == "arch:expr:1"
    assert key_main in context.geometry_cache
    assert key_arch in context.geometry_cache


def test_resolve_side_uses_slug() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=7)
    cache_mesh(context, trimesh.creation.box(), express_id=7, slug="arch")
    assert resolve_side(context, refs=[7]) == ["main:expr:7"]
    assert resolve_side(context, refs=[7], slug="arch") == ["arch:expr:7"]


def test_resolve_side_empty_scopes_to_slug() -> None:
    context = _context()
    cache_mesh(context, trimesh.creation.box(), express_id=1)
    cache_mesh(context, trimesh.creation.box(), express_id=2, slug="arch")
    cache_mesh(context, trimesh.creation.box(), object_id="shared")
    assert resolve_side(context, slug="main") == ["main:expr:1", "gen:shared"]
    assert resolve_side(context, slug="arch") == ["arch:expr:2", "gen:shared"]
