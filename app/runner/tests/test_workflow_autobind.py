from __future__ import annotations

from typing import Any, cast

import pytest

from openbim_runner.nodes.base import NodeModel
from openbim_runner.workflow import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    build_node_lookup,
    resolve_auto_bindings,
    resolve_input_bindings,
)


def _node(node_id: str, node_type: str, **extra: Any) -> WorkflowNode:
    return WorkflowNode(id=node_id, type=node_type, **extra)


def _loi_check(node_id: str = "loi") -> WorkflowNode:
    # A custom label exercises that auto-binding resolves by type, not name.
    return _node(node_id, "loi_check", label="My Renamed Checker")


def _bcf(node_id: str = "bcf", **extra: Any) -> WorkflowNode:
    return _node(node_id, "bcf_output", **extra)


def _bindings(
    nodes: list[WorkflowNode], edges: list[tuple[str, str]]
) -> tuple[dict[str, dict[str, str]], dict[str, WorkflowNode]]:
    workflow = WorkflowDefinition(
        ifc_path="model.ifc",
        nodes=nodes,
        edges=[WorkflowEdge(source=s, target=t) for s, t in edges],
    )
    node_lookup = build_node_lookup(workflow)
    return resolve_auto_bindings(workflow, node_lookup), node_lookup


def test_auto_binds_bcf_to_connected_upstream_loi_check() -> None:
    loi = _loi_check("loi-1")
    bcf = _bcf("bcf-1")
    auto, lookup = _bindings([loi, bcf], [("loi-1", "bcf-1")])

    binding = auto[bcf.id]["elements"]
    assert binding == "loi-1.elements"
    assert binding.split(".")[0] in lookup


def test_explicit_binding_takes_precedence() -> None:
    loi = _loi_check("loi-1")
    other = _loi_check("loi-2")
    bcf = _bcf("bcf-1", input_bindings={"elements": "loi-2.elements"})
    auto, _ = _bindings([loi, other, bcf], [("loi-1", "bcf-1"), ("loi-2", "bcf-1")])

    assert bcf.id not in auto


def test_explicit_binding_wins_in_payload_resolution() -> None:
    class _Output:
        def __init__(self, **kw: Any) -> None:
            self.__dict__.update(kw)

    node = WorkflowNode(
        id="bcf",
        type="bcf_output",
        input_bindings={"elements": "explicit.elements"},
    )
    outputs = cast(
        "dict[str, NodeModel]",
        {
            "auto": _Output(elements="AUTO"),
            "explicit": _Output(elements="EXPLICIT"),
        },
    )
    payload = resolve_input_bindings(
        node, outputs, auto_bindings={"elements": "auto.elements"}
    )
    assert payload == {"elements": "EXPLICIT"}


def test_no_compatible_upstream_stays_unbound() -> None:
    # get_name's result has no list[ComparisonElement] -> not compatible.
    source = _node("name-1", "get_name")
    bcf = _bcf("bcf-1")
    auto, _ = _bindings([source, bcf], [("name-1", "bcf-1")])

    assert bcf.id not in auto


def test_two_compatible_predecessors_raise() -> None:
    loi_a = _loi_check("loi-a")
    loi_b = _loi_check("loi-b")
    bcf = _bcf("bcf-1")
    workflow = WorkflowDefinition(
        ifc_path="model.ifc",
        nodes=[loi_a, loi_b, bcf],
        edges=[
            WorkflowEdge(source="loi-a", target="bcf-1"),
            WorkflowEdge(source="loi-b", target="bcf-1"),
        ],
    )
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_auto_bindings(workflow, build_node_lookup(workflow))


def test_non_immediate_ancestor_not_picked() -> None:
    # loi_check feeds get_name which feeds bcf; bcf's only direct predecessor
    # is get_name (incompatible), so elements stays unbound.
    loi = _loi_check("loi-1")
    mid = _node("mid-1", "get_name")
    bcf = _bcf("bcf-1")
    auto, _ = _bindings([loi, mid, bcf], [("loi-1", "mid-1"), ("mid-1", "bcf-1")])

    assert bcf.id not in auto


def test_unmarked_input_never_auto_bound() -> None:
    # loi_check.express_ids has no AutoBind marker; even with a compatible
    # upstream present, it must stay unbound (keeps whole-model semantics).
    loi = _loi_check("loi-1")
    provider = _node("provider-1", "ifc_element_filter")
    auto, _ = _bindings([provider, loi], [("provider-1", "loi-1")])

    assert loi.id not in auto
