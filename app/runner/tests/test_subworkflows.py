from __future__ import annotations

from typing import Any

import pytest

from openbim_runner.workflow import (
    ModelFile,
    NodePosition,
    SubworkflowDefinition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    build_execution_order,
    expand_workflow,
)


def _files() -> list[ModelFile]:
    return [ModelFile(path="model.ifc", slug="main")]


def _port(name: str) -> dict[str, Any]:
    return {"name": name, "type": {"type": "array"}}


def _input(node_id: str = "in", port_name: str = "elements") -> WorkflowNode:
    """One input node owns exactly one port."""
    return WorkflowNode(
        id=node_id,
        type="subworkflow_input",
        settings={"port": _port(port_name)},
    )


def _output(
    node_id: str = "out",
    port_name: str = "passed",
    producer: str | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="subworkflow_output",
        settings={"port": _port(port_name)},
        input_bindings={} if producer is None else {port_name: producer},
    )


def _inner(
    nodes: list[WorkflowNode], edges: list[tuple[str, str]]
) -> SubworkflowDefinition:
    return SubworkflowDefinition(
        name="Inner",
        nodes=nodes,
        edges=[WorkflowEdge(source=source, target=target) for source, target in edges],
    )


def _workflow(
    nodes: list[WorkflowNode], edges: list[tuple[str, str]]
) -> WorkflowDefinition:
    return WorkflowDefinition(
        files=_files(),
        nodes=nodes,
        edges=[WorkflowEdge(source=source, target=target) for source, target in edges],
    )


def _simple_subworkflow(
    *,
    node_id: str = "sw",
    input_port: str = "elements",
    output_port: str = "passed",
    producer: str = "check",
    producer_field: str = "value",
    input_bindings: dict[str, str] | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="subworkflow",
        input_bindings=input_bindings
        if input_bindings is not None
        else {"elements": "filter.express_ids"},
        subworkflow=_inner(
            [
                _input(port_name=input_port),
                WorkflowNode(
                    id=producer,
                    type="get_property",
                    input_bindings={"elements": f"in.{input_port}"},
                ),
                _output(
                    port_name=output_port,
                    producer=f"{producer}.{producer_field}",
                ),
            ],
            [("in", producer), (producer, "out")],
        ),
    )


def _filter() -> WorkflowNode:
    return WorkflowNode(id="filter", type="ifc_element_filter")


def test_expands_single_subworkflow() -> None:
    consumer = WorkflowNode(
        id="consumer",
        type="get_property",
        input_bindings={"elements": "sw.passed"},
    )
    workflow = _workflow(
        [_filter(), _simple_subworkflow(), consumer],
        [("filter", "sw"), ("sw", "consumer")],
    )

    expanded = expand_workflow(workflow)
    nodes = {node.id: node for node in expanded.nodes}

    assert set(nodes) == {"filter", "sw::check", "consumer"}
    assert nodes["sw::check"].input_bindings == {"elements": "filter.express_ids"}
    assert nodes["consumer"].input_bindings == {"elements": "sw::check.value"}
    assert {(edge.source, edge.target) for edge in expanded.edges} == {
        ("filter", "sw::check"),
        ("sw::check", "consumer"),
    }


def test_expands_multiple_input_ports() -> None:
    subworkflow = WorkflowNode(
        id="sw",
        type="subworkflow",
        input_bindings={
            "elements": "filter.express_ids",
            "guids": "filter.guids",
        },
        subworkflow=_inner(
            [
                _input("in_elements", "elements"),
                _input("in_guids", "guids"),
                WorkflowNode(
                    id="first",
                    type="get_property",
                    input_bindings={"elements": "in_elements.elements"},
                ),
                WorkflowNode(
                    id="second",
                    type="get_property",
                    input_bindings={"elements": "in_guids.guids"},
                ),
                _output(producer="first.value"),
            ],
            [("in_elements", "first"), ("in_guids", "second"), ("first", "out")],
        ),
    )
    workflow = _workflow([_filter(), subworkflow], [("filter", "sw")])

    expanded = expand_workflow(workflow)
    nodes = {node.id: node for node in expanded.nodes}

    assert set(nodes) == {"filter", "sw::first", "sw::second"}
    assert nodes["sw::first"].input_bindings == {"elements": "filter.express_ids"}
    assert nodes["sw::second"].input_bindings == {"elements": "filter.guids"}
    assert {(edge.source, edge.target) for edge in expanded.edges} == {
        ("filter", "sw::first"),
        ("filter", "sw::second"),
    }


def test_expands_nested_subworkflows() -> None:
    inner_subworkflow = WorkflowNode(
        id="inner",
        type="subworkflow",
        input_bindings={"elements": "in.elements"},
        subworkflow=_inner(
            [
                _input(port_name="elements"),
                WorkflowNode(
                    id="check",
                    type="get_property",
                    input_bindings={"elements": "in.elements"},
                ),
                _output(producer="check.value"),
            ],
            [("in", "check"), ("check", "out")],
        ),
    )
    outer_subworkflow = WorkflowNode(
        id="outer",
        type="subworkflow",
        input_bindings={"elements": "filter.express_ids"},
        subworkflow=_inner(
            [
                _input(port_name="elements"),
                inner_subworkflow,
                _output(producer="inner.passed"),
            ],
            [("in", "inner"), ("inner", "out")],
        ),
    )
    consumer = WorkflowNode(
        id="consumer",
        type="get_property",
        input_bindings={"elements": "outer.passed"},
    )
    workflow = _workflow(
        [_filter(), outer_subworkflow, consumer],
        [("filter", "outer"), ("outer", "consumer")],
    )

    expanded = expand_workflow(workflow)
    nodes = {node.id: node for node in expanded.nodes}

    assert set(nodes) == {"filter", "outer::inner::check", "consumer"}
    assert nodes["outer::inner::check"].input_bindings == {
        "elements": "filter.express_ids"
    }
    assert nodes["consumer"].input_bindings == {"elements": "outer::inner::check.value"}
    assert {(edge.source, edge.target) for edge in expanded.edges} == {
        ("filter", "outer::inner::check"),
        ("outer::inner::check", "consumer"),
    }


def test_golden_expanded_matches_hand_flattened() -> None:
    expanded = expand_workflow(
        _workflow(
            [
                _filter(),
                _simple_subworkflow(),
                WorkflowNode(
                    id="consumer",
                    type="get_property",
                    input_bindings={"elements": "sw.passed"},
                ),
            ],
            [("filter", "sw"), ("sw", "consumer")],
        )
    )
    hand_flattened = _workflow(
        [
            _filter(),
            WorkflowNode(
                id="sw::check",
                type="get_property",
                input_bindings={"elements": "filter.express_ids"},
            ),
            WorkflowNode(
                id="consumer",
                type="get_property",
                input_bindings={"elements": "sw::check.value"},
            ),
        ],
        [("filter", "sw::check"), ("sw::check", "consumer")],
    )

    assert _normalized(expanded) == _normalized(hand_flattened)


def _normalized(workflow: WorkflowDefinition) -> dict[str, Any]:
    return {
        "nodes": sorted(
            (node.model_dump(mode="json") for node in workflow.nodes),
            key=lambda node: node["id"],
        ),
        "edges": sorted(
            (edge.model_dump(mode="json") for edge in workflow.edges),
            key=lambda edge: (edge["source"], edge["target"]),
        ),
    }


def test_execution_order_uses_namespaced_nodes() -> None:
    consumer = WorkflowNode(
        id="consumer",
        type="get_property",
        input_bindings={"elements": "sw.passed"},
    )
    expanded = expand_workflow(
        _workflow(
            [_filter(), _simple_subworkflow(), consumer],
            [("filter", "sw"), ("sw", "consumer")],
        )
    )

    order = build_execution_order(expanded)
    assert order.index("filter") < order.index("sw::check")
    assert order.index("sw::check") < order.index("consumer")


def test_positions_survive_expansion() -> None:
    subworkflow = _simple_subworkflow()
    subworkflow.position = NodePosition(x=10, y=20)
    assert subworkflow.subworkflow is not None
    subworkflow.subworkflow.nodes[1].position = NodePosition(x=30, y=40)

    expanded = expand_workflow(_workflow([subworkflow], []))
    nodes = {node.id: node for node in expanded.nodes}

    assert nodes["sw::check"].position == NodePosition(x=30, y=40)


def test_drops_order_only_edges_across_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    subworkflow = WorkflowNode(
        id="sw",
        type="subworkflow",
        input_bindings={"elements": "filter.express_ids"},
        subworkflow=_inner(
            [
                _input(port_name="elements"),
                _output(producer="check.value"),
                WorkflowNode(id="check", type="get_property"),
            ],
            [("check", "out")],
        ),
    )
    workflow = _workflow([_filter(), subworkflow], [("filter", "sw")])

    expanded = expand_workflow(workflow)

    # Nothing inside consumes the port, so the edge has no inner endpoint.
    assert expanded.edges == []
    assert "order-only edge" in capsys.readouterr().out


def test_bindings_without_edges_still_order() -> None:
    subworkflow = WorkflowNode(
        id="sw",
        type="subworkflow",
        input_bindings={"elements": "filter.express_ids"},
        subworkflow=_inner(
            [
                _input(port_name="elements"),
                WorkflowNode(
                    id="check",
                    type="get_property",
                    input_bindings={"elements": "in.elements"},
                ),
                _output(producer="check.value"),
            ],
            [],
        ),
    )
    consumer = WorkflowNode(
        id="consumer",
        type="get_property",
        input_bindings={"elements": "sw.passed"},
    )
    expanded = expand_workflow(_workflow([_filter(), subworkflow, consumer], []))

    assert expanded.edges == []
    order = build_execution_order(expanded)
    assert order.index("filter") < order.index("sw::check") < order.index("consumer")


def test_subworkflow_without_output_node_is_valid() -> None:
    subworkflow = WorkflowNode(
        id="sw",
        type="subworkflow",
        input_bindings={"elements": "filter.express_ids"},
        subworkflow=_inner(
            [
                _input(port_name="elements"),
                WorkflowNode(
                    id="check",
                    type="get_property",
                    input_bindings={"elements": "in.elements"},
                ),
            ],
            [("in", "check")],
        ),
    )
    expanded = expand_workflow(_workflow([_filter(), subworkflow], [("filter", "sw")]))
    nodes = {node.id: node for node in expanded.nodes}

    assert set(nodes) == {"filter", "sw::check"}
    assert nodes["sw::check"].input_bindings == {"elements": "filter.express_ids"}
    assert {(edge.source, edge.target) for edge in expanded.edges} == {
        ("filter", "sw::check")
    }


@pytest.mark.parametrize(
    ("nodes", "edges", "message"),
    [
        pytest.param(
            [
                _filter(),
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            WorkflowNode(
                                id="check",
                                type="get_property",
                                input_bindings={"elements": "in.elements"},
                            ),
                        ],
                        [],
                    ),
                ),
                WorkflowNode(
                    id="consumer",
                    type="get_property",
                    input_bindings={"elements": "sw.passed"},
                ),
            ],
            [],
            "defines no output port",
            id="missing-output-node-but-consumed",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    subworkflow=_inner(
                        [
                            _input(),
                            _output("out-1"),
                            _output("out-2"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "allows at most one 'subworkflow_output'",
            id="duplicate-output-node",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    subworkflow=_inner(
                        [
                            _input(),
                            WorkflowNode(
                                id="out",
                                type="subworkflow_output",
                                input_bindings={"passed": "check.value"},
                            ),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "must define a single port",
            id="output-node-without-port",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer=None),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "has no producer binding",
            id="output-port-unbound",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            WorkflowNode(
                                id="out",
                                type="subworkflow_output",
                                settings={"port": _port("passed")},
                                input_bindings={
                                    "passed": "check.value",
                                    "other": "check.value",
                                },
                            ),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "but no matching output port",
            id="output-binding-without-port",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input("in-1", "elements"),
                            _input("in-2", "elements"),
                            _output(producer="check.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "duplicate input port",
            id="duplicate-port-across-input-nodes",
        ),
        pytest.param(
            [
                _filter(),
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                ),
            ],
            [],
            "is not bound by the parent",
            id="input-port-unbound",
        ),
        pytest.param(
            [
                _filter(),
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={
                        "elements": "filter.express_ids",
                        "nope": "filter.guids",
                    },
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                ),
            ],
            [],
            "no matching input port",
            id="parent-binding-without-port",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input("in-1", "elements"),
                            _output(producer="check.value"),
                            WorkflowNode(
                                id="check",
                                type="get_property",
                                input_bindings={"elements": "in-1.wrong"},
                            ),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "only exposes port",
            id="inner-binding-wrong-field",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(
                                id="check",
                                type="get_property",
                                input_bindings={"elements": "outside.value"},
                            ),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "outside subworkflow",
            id="inner-binding-outside",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(
                                id="check",
                                type="get_property",
                                input_bindings={"value": "out.passed"},
                            ),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "produces no outputs",
            id="inner-binding-to-output-node",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            WorkflowNode(
                                id="in",
                                type="subworkflow_input",
                                settings={"port": _port("elements")},
                                input_bindings={"x": "y.z"},
                            ),
                            _output(producer="check.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "cannot define input bindings",
            id="input-node-with-bindings",
        ),
        pytest.param(
            [_input("in-1"), _output(producer="in-1.elements")],
            [],
            "only valid inside",
            id="leftover-meta-node",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(
                                id="check",
                                type="get_property",
                                input_bindings={"elements": "in.elements"},
                            ),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "duplicate node IDs",
            id="duplicate-inner-node-id",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="check.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [("in", "missing")],
                    ),
                )
            ],
            [],
            "unknown target node",
            id="inner-edge-unknown-node",
        ),
        pytest.param(
            [_simple_subworkflow()],
            [("sw", "sw")],
            "edge to itself",
            id="subworkflow-self-edge",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="in.elements"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "not a subworkflow meta node",
            id="output-producer-is-input-node",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [
                            _input(),
                            _output(producer="nope.value"),
                            WorkflowNode(id="check", type="get_property"),
                        ],
                        [],
                    ),
                )
            ],
            [],
            "unknown inner node",
            id="output-producer-unknown",
        ),
        pytest.param(
            [
                WorkflowNode(
                    id="sw",
                    type="subworkflow",
                    input_bindings={"elements": "filter.express_ids"},
                    subworkflow=_inner(
                        [_input("in-1", "bad-name"), _output(producer="check.value")],
                        [],
                    ),
                )
            ],
            [],
            "invalid port name",
            id="invalid-port-name",
        ),
        pytest.param(
            [WorkflowNode(id="sw", type="subworkflow")],
            [],
            "missing its embedded definition",
            id="missing-definition",
        ),
    ],
)
def test_rejects_invalid_subworkflows(
    nodes: list[WorkflowNode],
    edges: list[tuple[str, str]],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        expand_workflow(_workflow(nodes, edges))
