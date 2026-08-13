from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Any

import ifcopenshell
from pydantic import Field

from openbim_runner.nodes import ExecutionContext, NodeModel, dispatch, get_registry
from openbim_runner.util.geometry import build_geometry_cache


class WorkflowNode(NodeModel):
    id: str = Field(title="Node ID", description="Unique workflow node identifier.")
    type: str = Field(title="Node type", description="Registered node type name.")
    label: str = Field(
        default="",
        title="Node label",
        description="Human-readable label for the node. Falls back to node type if empty.",
    )
    settings: dict[str, Any] = Field(
        default={},
        title="Node settings",
        description="User-authored settings passed directly to the node function.",
    )
    input_bindings: dict[str, str] = Field(
        default={},
        title="Input bindings",
        description="Mappings from node input names to previously produced '<node_id>.<field_name>' references.",
    )

    def get_label(self) -> str:
        return self.label if self.label else self.type


class WorkflowEdge(NodeModel):
    source: str = Field(title="Source node", description="Upstream node ID.")
    target: str = Field(title="Target node", description="Downstream node ID.")


class WorkflowDefinition(NodeModel):
    ifc_path: str = Field(
        title="IFC path",
        description="Path to the IFC file, relative to the workflow JSON when not absolute.",
    )
    nodes: list[WorkflowNode] = Field(
        default=[],
        title="Nodes",
        description="Workflow nodes to execute.",
    )
    edges: list[WorkflowEdge] = Field(
        default=[],
        title="Edges",
        description="Directed edges used to determine execution order.",
    )


def load_workflow(workflow_path: Path) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate_json(workflow_path.read_text(encoding="utf-8"))


def resolve_ifc_path(workflow_path: Path, ifc_path: str) -> Path:
    candidate_path = Path(ifc_path)
    if candidate_path.is_absolute():
        return candidate_path

    return workflow_path.parent / candidate_path


def build_node_lookup(workflow: WorkflowDefinition) -> dict[str, WorkflowNode]:
    node_lookup = {node.id: node for node in workflow.nodes}
    if len(node_lookup) != len(workflow.nodes):
        raise ValueError("Workflow contains duplicate node IDs.")

    return node_lookup


def parse_reference(reference: str) -> tuple[str, str]:
    try:
        node_id, field_name = reference.split(".", maxsplit=1)
    except ValueError as error:
        raise ValueError(f"Invalid reference format '{reference}'. Expected '<node_id>.<field_name>'.") from error

    if not node_id or not field_name:
        raise ValueError(f"Invalid reference format '{reference}'. Expected '<node_id>.<field_name>'.")

    return node_id, field_name


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
    indegree: dict[str, int] = {node_id: 0 for node_id in node_lookup}

    for edge in workflow.edges:
        if edge.source not in node_lookup:
            raise ValueError(f"Edge references unknown source node '{edge.source}'.")
        if edge.target not in node_lookup:
            raise ValueError(f"Edge references unknown target node '{edge.target}'.")

        add_dependency(adjacency, indegree, source=edge.source, target=edge.target)

    for workflow_node in workflow.nodes:
        for reference in workflow_node.input_bindings.values():
            source_node_id, _ = parse_reference(reference)
            if source_node_id not in node_lookup:
                raise ValueError(
                    f"Node '{workflow_node.id}' input binding references unknown node '{source_node_id}'."
                )

            add_dependency(adjacency, indegree, source=source_node_id, target=workflow_node.id)

    queue: deque[str] = deque(node.id for node in workflow.nodes if indegree[node.id] == 0)
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


def resolve_input_bindings(workflow_node: WorkflowNode, node_outputs: dict[str, NodeModel]) -> dict[str, Any]:
    input_payload: dict[str, Any] = {}

    for input_name, reference in workflow_node.input_bindings.items():
        source_node_id, field_name = parse_reference(reference)
        source_output = node_outputs.get(source_node_id)
        if source_output is None:
            raise ValueError(
                f"Node '{workflow_node.id}' input '{input_name}' references '{reference}' before '{source_node_id}' has run."
            )
        if not hasattr(source_output, field_name):
            raise ValueError(
                f"Node '{workflow_node.id}' input '{input_name}' references missing field '{field_name}' on '{source_node_id}'."
            )

        input_payload[input_name] = getattr(source_output, field_name)

    return input_payload


async def execute_workflow_async(workflow_path: Path) -> tuple[dict[str, NodeModel], dict[str, WorkflowNode]]:
    workflow = load_workflow(workflow_path)
    node_lookup = build_node_lookup(workflow)
    execution_order = build_execution_order(workflow)
    node_registry = get_registry()
    ifc_model = ifcopenshell.open(str(resolve_ifc_path(workflow_path, workflow.ifc_path)))  # pyright: ignore[reportUnknownMemberType]
    node_outputs: dict[str, NodeModel] = {}
    geometry_cache = build_geometry_cache(ifc_model)

    for node_id in execution_order:
        workflow_node = node_lookup[node_id]
        definition = node_registry.get(workflow_node.type)
        if definition is None:
            raise ValueError(f"Unknown node type '{workflow_node.type}'.")

        if workflow_node.input_bindings and not definition.takes_inputs:
            raise ValueError(f"Node '{workflow_node.id}' does not accept input bindings.")

        settings_payload = workflow_node.settings
        input_payload = resolve_input_bindings(workflow_node, node_outputs)
        context = ExecutionContext(
            ifc_model=ifc_model,
            node_outputs=node_outputs,
            workflow_dir=workflow_path.parent,
            geometry_cache=geometry_cache,
        )
        node_outputs[node_id] = await dispatch(
            workflow_node.type,
            settings_payload,
            inputs_payload=input_payload,
            context=context,
        )

    return node_outputs, node_lookup


def execute_workflow(workflow_path: Path) -> tuple[dict[str, NodeModel], dict[str, WorkflowNode]]:
    return asyncio.run(execute_workflow_async(workflow_path))


def dump_results(node_outputs: dict[str, NodeModel], node_lookup: dict[str, WorkflowNode]) -> str:
    return json.dumps(
        {
            node_id: {
                "label": workflow_node.get_label(),
                "type": workflow_node.type,
                "result": output.model_dump(mode="json"),
            }
            for node_id, output in node_outputs.items()
            if (workflow_node := node_lookup.get(node_id))
        },
        indent=2,
    )