"""Expand embedded subworkflows into one flat node and edge graph.

Inlining is the only job of this module: nested definitions are expanded
depth-first and their nodes renamed ``<outer_id>::<inner_id>``. Ports are
rewired so consumers point at the producer inside the subworkflow, and edges
that only expressed ordering across the boundary are kept or dropped as the
graph allows.
"""

from __future__ import annotations

import sys

from openbim_runner.workflow.model import (
    SUBWORKFLOW_INPUT_TYPE,
    SUBWORKFLOW_META_TYPES,
    SUBWORKFLOW_OUTPUT_TYPE,
    SUBWORKFLOW_TYPE,
    SubworkflowPort,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    describe_node,
    parse_input_reference,
    parse_reference,
    parse_single_port,
)

NAMESPACE_SEPARATOR = "::"


def expand_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
    """Inline every embedded subworkflow into a flat node/edge graph.

    Nested subworkflows are expanded depth-first, so inner nodes end up named
    ``<outer_id>::<inner_id>``. The returned workflow contains no
    ``subworkflow``-family nodes.
    """
    nodes, edges = _expand_scope(
        [node.model_copy(deep=True) for node in workflow.nodes],
        [edge.model_copy(deep=True) for edge in workflow.edges],
    )

    for node in nodes:
        if node.type in SUBWORKFLOW_META_TYPES:
            raise ValueError(
                f"Node {describe_node(node)} is only valid inside a subworkflow "
                "definition."
            )

    return workflow.model_copy(update={"nodes": nodes, "edges": edges})


def _expand_scope(
    nodes: list[WorkflowNode], edges: list[WorkflowEdge]
) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    """Expand one scope: nested subworkflows first, then inline them here."""
    while True:
        subworkflow_node = next(
            (node for node in nodes if node.type == SUBWORKFLOW_TYPE), None
        )
        if subworkflow_node is None:
            return nodes, edges

        definition = subworkflow_node.subworkflow
        if definition is None:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} is missing its "
                "embedded definition."
            )

        inner_nodes, inner_edges = _expand_scope(definition.nodes, definition.edges)
        definition.nodes = inner_nodes
        definition.edges = inner_edges
        nodes, edges = _inline_subworkflow(subworkflow_node, nodes, edges)


def _warn_order_only_edge(edge: WorkflowEdge, subworkflow_node: WorkflowNode) -> None:
    print(
        f"WARNING: dropping order-only edge '{edge.source}' -> '{edge.target}' "
        f"across subworkflow {describe_node(subworkflow_node)}.",
        file=sys.stderr,
    )


def _inline_subworkflow(
    subworkflow_node: WorkflowNode,
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    definition = subworkflow_node.subworkflow
    if definition is None:
        raise ValueError(
            f"Subworkflow node {describe_node(subworkflow_node)} is missing its "
            "embedded definition."
        )

    inner_nodes = definition.nodes
    inner_edges = definition.edges
    inner_node_ids = {node.id for node in inner_nodes}
    if len(inner_node_ids) != len(inner_nodes):
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} contains duplicate node IDs."
        )

    for inner_node in inner_nodes:
        if inner_node.type == SUBWORKFLOW_TYPE:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} still contains nested "
                f"subworkflow node {describe_node(inner_node)}."
            )

    input_nodes = [node for node in inner_nodes if node.type == SUBWORKFLOW_INPUT_TYPE]
    output_nodes = [
        node for node in inner_nodes if node.type == SUBWORKFLOW_OUTPUT_TYPE
    ]
    if len(output_nodes) > 1:
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} allows at most one "
            f"'{SUBWORKFLOW_OUTPUT_TYPE}' node (found {len(output_nodes)})."
        )

    output_node = output_nodes[0] if output_nodes else None
    output_node_id = output_node.id if output_node is not None else None
    output_port = parse_single_port(output_node) if output_node is not None else None

    input_ports_by_id: dict[str, SubworkflowPort] = {}
    input_nodes_by_id: dict[str, WorkflowNode] = {}
    for input_node in input_nodes:
        if input_node.input_bindings:
            raise ValueError(
                f"Node {describe_node(input_node)} is a subworkflow input and cannot "
                "define input bindings."
            )
        port = parse_single_port(input_node)
        duplicate = next(
            (other for other in input_ports_by_id.values() if other.name == port.name),
            None,
        )
        if duplicate is not None:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} defines duplicate "
                f"input port '{port.name}'."
            )
        input_ports_by_id[input_node.id] = port
        input_nodes_by_id[input_node.id] = input_node
    input_port_names = {port.name for port in input_ports_by_id.values()}

    for port_name in sorted(input_port_names):
        if port_name not in subworkflow_node.input_bindings:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} input port "
                f"'{port_name}' is not bound by the parent."
            )

    for input_name, reference in subworkflow_node.input_bindings.items():
        if input_name not in input_port_names:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} has a binding "
                f"for '{input_name}' but no matching input port."
            )
        source_id, _ = parse_input_reference(
            reference, node=subworkflow_node, input_name=input_name
        )
        if source_id == subworkflow_node.id:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} input "
                f"'{input_name}' cannot bind to one of its own outputs."
            )

    namespace = f"{subworkflow_node.id}{NAMESPACE_SEPARATOR}"
    output_producer_id: str | None = None
    output_producer_reference: str | None = None

    if output_node is not None and output_port is not None:
        output_bindings = output_node.input_bindings
        if output_port.name not in output_bindings:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' has no producer binding."
            )
        for binding_name in output_bindings:
            if binding_name != output_port.name:
                raise ValueError(
                    f"Node {describe_node(output_node)} has a binding for "
                    f"'{binding_name}' but no matching output port."
                )

        try:
            producer_id, producer_field = parse_reference(
                output_bindings[output_port.name]
            )
        except ValueError as error:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' has an invalid producer reference: {error}"
            ) from error
        if producer_id in input_ports_by_id or producer_id == output_node.id:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' must be produced by an inner node, not a "
                "subworkflow meta node."
            )
        if producer_id not in inner_node_ids:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' points at unknown inner node '{producer_id}'."
            )
        output_producer_id = f"{namespace}{producer_id}"
        output_producer_reference = f"{output_producer_id}.{producer_field}"

    for inner_node in inner_nodes:
        if inner_node.id in input_ports_by_id or inner_node.id == output_node_id:
            continue
        for input_name, reference in inner_node.input_bindings.items():
            source_id, field_name = parse_input_reference(
                reference, node=inner_node, input_name=input_name
            )
            if source_id in input_ports_by_id:
                port = input_ports_by_id[source_id]
                if field_name != port.name:
                    raise ValueError(
                        f"Node {describe_node(inner_node)} input '{input_name}' "
                        f"references '{source_id}.{field_name}', but input node "
                        f"{describe_node(input_nodes_by_id[source_id])} only exposes "
                        f"port '{port.name}'."
                    )
            elif source_id == output_node_id:
                raise ValueError(
                    f"Node {describe_node(inner_node)} input '{input_name}' references "
                    "the subworkflow output node, which produces no outputs."
                )
            elif source_id not in inner_node_ids:
                raise ValueError(
                    f"Node {describe_node(inner_node)} input '{input_name}' points at "
                    f"'{source_id}', which is outside subworkflow "
                    f"{describe_node(subworkflow_node)}."
                )

    for edge in inner_edges:
        if edge.source not in inner_node_ids:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} has an edge with "
                f"unknown source node '{edge.source}'."
            )
        if edge.target not in inner_node_ids:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} has an edge with "
                f"unknown target node '{edge.target}'."
            )

    injected_nodes: list[WorkflowNode] = []
    consumers_by_port: dict[str, set[str]] = {}

    for inner_node in inner_nodes:
        if inner_node.id in input_ports_by_id or inner_node.id == output_node_id:
            continue

        renamed_node = inner_node.model_copy(deep=True)
        renamed_node.id = f"{namespace}{inner_node.id}"
        rewritten_bindings: dict[str, str] = {}

        for input_name, reference in inner_node.input_bindings.items():
            source_id, field_name = parse_reference(reference)
            if source_id in input_ports_by_id:
                port = input_ports_by_id[source_id]
                rewritten_bindings[input_name] = subworkflow_node.input_bindings[
                    port.name
                ]
                consumers_by_port.setdefault(port.name, set()).add(renamed_node.id)
            else:
                rewritten_bindings[input_name] = f"{namespace}{source_id}.{field_name}"

        renamed_node.input_bindings = rewritten_bindings
        injected_nodes.append(renamed_node)

    dropped_ids = set(input_ports_by_id)
    if output_node_id is not None:
        dropped_ids.add(output_node_id)
    inner_edges_flattened: list[tuple[str, str]] = []
    for edge in inner_edges:
        if edge.source in dropped_ids or edge.target in dropped_ids:
            continue
        inner_edges_flattened.append(
            (f"{namespace}{edge.source}", f"{namespace}{edge.target}")
        )

    final_nodes: list[WorkflowNode] = []
    output_consumers: set[str] = set()

    for other_node in nodes:
        if other_node.id == subworkflow_node.id:
            final_nodes.extend(injected_nodes)
            continue

        renamed_other = other_node.model_copy(deep=True)
        rewritten_bindings = {}
        for input_name, reference in other_node.input_bindings.items():
            source_id, field_name = parse_input_reference(
                reference, node=other_node, input_name=input_name
            )
            if source_id == subworkflow_node.id:
                if output_port is None or output_producer_reference is None:
                    raise ValueError(
                        f"Node {describe_node(other_node)} input '{input_name}' "
                        f"references '{subworkflow_node.id}.{field_name}', but "
                        f"subworkflow {describe_node(subworkflow_node)} defines no "
                        "output port."
                    )
                if field_name != output_port.name:
                    raise ValueError(
                        f"Node {describe_node(other_node)} input '{input_name}' "
                        f"references '{subworkflow_node.id}.{field_name}', but "
                        f"subworkflow {describe_node(subworkflow_node)} has no output "
                        f"port '{field_name}' (its output port is "
                        f"'{output_port.name}')."
                    )
                rewritten_bindings[input_name] = output_producer_reference
                output_consumers.add(other_node.id)
            else:
                rewritten_bindings[input_name] = reference
        renamed_other.input_bindings = rewritten_bindings
        final_nodes.append(renamed_other)

    final_node_ids = {node.id for node in final_nodes}
    if len(final_node_ids) != len(final_nodes):
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} would produce duplicate "
            "node IDs after expansion."
        )

    final_edges: list[WorkflowEdge] = []
    seen_edges: set[tuple[str, str]] = set()

    def add_edge(source: str, target: str) -> None:
        if (source, target) in seen_edges:
            return
        seen_edges.add((source, target))
        final_edges.append(WorkflowEdge(source=source, target=target))

    for edge in edges:
        if edge.source == subworkflow_node.id and edge.target == subworkflow_node.id:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} has an edge to "
                "itself."
            )

        if edge.target == subworkflow_node.id:
            bound_ports = {
                port_name
                for port_name, reference in subworkflow_node.input_bindings.items()
                if parse_reference(reference)[0] == edge.source
            }
            consumers: set[str] = set()
            for port_name in bound_ports:
                consumers.update(consumers_by_port.get(port_name, set()))
            if consumers:
                for consumer_id in sorted(consumers):
                    add_edge(edge.source, consumer_id)
            else:
                _warn_order_only_edge(edge, subworkflow_node)
            continue

        if edge.source == subworkflow_node.id:
            if edge.target not in final_node_ids:
                raise ValueError(
                    f"Edge references unknown target node '{edge.target}'."
                )
            if output_producer_id is not None and edge.target in output_consumers:
                add_edge(output_producer_id, edge.target)
            else:
                _warn_order_only_edge(edge, subworkflow_node)
            continue

        add_edge(edge.source, edge.target)

    for source, target in inner_edges_flattened:
        add_edge(source, target)

    return final_nodes, final_edges
