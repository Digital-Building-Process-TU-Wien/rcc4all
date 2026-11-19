"""Graph queries over a flat workflow: node lookup and execution order."""

from __future__ import annotations

from collections import deque

from openbim_runner.workflow.model import (
    WorkflowDefinition,
    WorkflowNode,
    describe_node,
    parse_reference,
)


def build_node_lookup(workflow: WorkflowDefinition) -> dict[str, WorkflowNode]:
    node_lookup = {node.id: node for node in workflow.nodes}
    if len(node_lookup) != len(workflow.nodes):
        raise ValueError("Workflow contains duplicate node IDs.")

    return node_lookup


def add_dependency(
    adjacency: dict[str, set[str]],
    indegree: dict[str, int],
    *,
    source: str,
    target: str,
) -> None:
    if target not in adjacency[source]:
        adjacency[source].add(target)
        indegree[target] += 1


def build_execution_order(workflow: WorkflowDefinition) -> list[str]:
    node_lookup = build_node_lookup(workflow)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_lookup}
    indegree: dict[str, int] = dict.fromkeys(node_lookup, 0)

    for edge in workflow.edges:
        if edge.source not in node_lookup:
            raise ValueError(f"Edge references unknown source node '{edge.source}'.")
        if edge.target not in node_lookup:
            raise ValueError(f"Edge references unknown target node '{edge.target}'.")

        add_dependency(adjacency, indegree, source=edge.source, target=edge.target)

    for workflow_node in workflow.nodes:
        for input_name, reference in workflow_node.input_bindings.items():
            try:
                source_node_id, _ = parse_reference(reference)
            except ValueError as error:
                raise ValueError(
                    f"Node {describe_node(workflow_node)} input '{input_name}' has "
                    f"an invalid reference: {error}"
                ) from error
            if source_node_id not in node_lookup:
                raise ValueError(
                    f"Node {describe_node(workflow_node)} input '{input_name}' points "
                    f"to unknown node '{source_node_id}'."
                )

            add_dependency(
                adjacency, indegree, source=source_node_id, target=workflow_node.id
            )

    queue: deque[str] = deque(
        node.id for node in workflow.nodes if indegree[node.id] == 0
    )
    execution_order: list[str] = []

    while queue:
        node_id = queue.popleft()
        execution_order.append(node_id)

        for downstream_node_id in adjacency[node_id]:
            indegree[downstream_node_id] -= 1
            if indegree[downstream_node_id] == 0:
                queue.append(downstream_node_id)

    if len(execution_order) != len(workflow.nodes):
        raise ValueError("Workflow contains a cycle and cannot be executed.")

    return execution_order
