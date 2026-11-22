"""Graph queries and basic invariants over a workflow scope."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection

from rcc4all_runner.workflow.model import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    describe_node,
    parse_input_reference,
)


def index_nodes(
    nodes: list[WorkflowNode], *, scope: str = "Workflow"
) -> dict[str, WorkflowNode]:
    """Index nodes by ID, failing when a scope contains duplicates."""
    node_lookup = {node.id: node for node in nodes}
    if len(node_lookup) != len(nodes):
        raise ValueError(f"{scope} contains duplicate node IDs.")

    return node_lookup


def validate_edges(
    edges: list[WorkflowEdge],
    node_ids: Collection[str],
    *,
    scope: str | None = None,
) -> None:
    """Ensure every edge in a scope connects existing nodes."""
    prefix = "Edge references" if scope is None else f"{scope} has an edge with"
    for edge in edges:
        if edge.source not in node_ids:
            raise ValueError(f"{prefix} unknown source node '{edge.source}'.")
        if edge.target not in node_ids:
            raise ValueError(f"{prefix} unknown target node '{edge.target}'.")


def build_node_lookup(workflow: WorkflowDefinition) -> dict[str, WorkflowNode]:
    return index_nodes(workflow.nodes)


def _add_dependency(
    adjacency: dict[str, set[str]],
    indegree: dict[str, int],
    *,
    source: str,
    target: str,
) -> None:
    if target not in adjacency[source]:
        adjacency[source].add(target)
        indegree[target] += 1


def build_execution_order(
    workflow: WorkflowDefinition,
    *,
    node_lookup: dict[str, WorkflowNode] | None = None,
) -> list[str]:
    if node_lookup is None:
        node_lookup = build_node_lookup(workflow)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_lookup}
    indegree: dict[str, int] = dict.fromkeys(node_lookup, 0)

    validate_edges(workflow.edges, node_lookup)
    for edge in workflow.edges:
        _add_dependency(adjacency, indegree, source=edge.source, target=edge.target)

    for workflow_node in workflow.nodes:
        for input_name, reference in workflow_node.input_bindings.items():
            source_node_id, _ = parse_input_reference(
                reference, node=workflow_node, input_name=input_name
            )
            if source_node_id not in node_lookup:
                raise ValueError(
                    f"Node {describe_node(workflow_node)} input '{input_name}' points "
                    f"to unknown node '{source_node_id}'."
                )

            _add_dependency(
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
