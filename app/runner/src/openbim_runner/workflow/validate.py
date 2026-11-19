"""Static validation of a workflow graph.

Answers one question before any IFC file is opened: can this graph run? That
means model slots, subworkflow structure, edge endpoints, every bound port
pair against the assignability table, and execution-order cycles.

Port resolution here is written from the type checker's point of view: what
does a node accept in its own scope, and what does it produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openbim_runner.nodes import NodeModel, get_registry
from openbim_runner.port_types import (
    PortType,
    annotation_to_port_type,
    describe_port_type,
    is_assignable,
)
from openbim_runner.workflow.bindings import resolve_auto_bindings
from openbim_runner.workflow.graph import build_execution_order, build_node_lookup
from openbim_runner.workflow.model import (
    SUBWORKFLOW_INPUT_TYPE,
    SUBWORKFLOW_OUTPUT_TYPE,
    SUBWORKFLOW_TYPE,
    SubworkflowPort,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    describe_node,
    parse_reference,
    parse_single_port,
    validate_model_files,
)
from openbim_runner.workflow.subworkflow import expand_workflow


def _model_port_types(model: type[NodeModel], *, node_name: str) -> dict[str, PortType]:
    return {
        field_name: annotation_to_port_type(
            field_info.annotation, node=node_name, field=field_name
        )
        for field_name, field_info in model.model_fields.items()
    }


def _subworkflow_input_ports(node: WorkflowNode) -> dict[str, PortType]:
    definition = node.subworkflow
    if definition is None:
        return {}
    ports: dict[str, PortType] = {}
    for inner_node in definition.nodes:
        if inner_node.type == SUBWORKFLOW_INPUT_TYPE:
            port = parse_single_port(inner_node)
            ports[port.name] = port.type
    return ports


def _subworkflow_output_port(node: WorkflowNode) -> SubworkflowPort | None:
    definition = node.subworkflow
    if definition is None:
        return None
    for inner_node in definition.nodes:
        if inner_node.type == SUBWORKFLOW_OUTPUT_TYPE:
            return parse_single_port(inner_node)
    return None


def _node_input_ports(
    node: WorkflowNode, registry: dict[str, Any]
) -> dict[str, PortType]:
    """The ports a node accepts, as the type checker sees them in its scope."""
    if node.type == SUBWORKFLOW_INPUT_TYPE:
        return {}
    if node.type == SUBWORKFLOW_OUTPUT_TYPE:
        port = parse_single_port(node)
        return {port.name: port.type}
    if node.type == SUBWORKFLOW_TYPE:
        return _subworkflow_input_ports(node)

    definition = registry.get(node.type)
    if definition is None:
        raise ValueError(f"Node {describe_node(node)} has unknown type '{node.type}'.")
    if not definition.takes_inputs or definition.inputs_model is None:
        return {}
    return _model_port_types(definition.inputs_model, node_name=node.type)


def _node_output_ports(
    node: WorkflowNode, registry: dict[str, Any]
) -> dict[str, PortType]:
    """The ports a node produces, as the type checker sees them in its scope."""
    if node.type == SUBWORKFLOW_OUTPUT_TYPE:
        return {}
    if node.type == SUBWORKFLOW_INPUT_TYPE:
        port = parse_single_port(node)
        return {port.name: port.type}
    if node.type == SUBWORKFLOW_TYPE:
        port = _subworkflow_output_port(node)
        return {} if port is None else {port.name: port.type}

    definition = registry.get(node.type)
    if definition is None:
        raise ValueError(f"Node {describe_node(node)} has unknown type '{node.type}'.")
    return _model_port_types(definition.result_model, node_name=node.type)


def _validate_scope(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> None:
    """Validate one scope: edge endpoints and every bound port pair."""
    registry = get_registry()
    node_by_id = {node.id: node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("Workflow contains duplicate node IDs.")

    for node in nodes:
        if node.type == SUBWORKFLOW_TYPE:
            definition = node.subworkflow
            if definition is None:
                raise ValueError(
                    f"Subworkflow node {describe_node(node)} is missing its "
                    "embedded definition."
                )
            _validate_scope(definition.nodes, definition.edges)

    for edge in edges:
        if edge.source not in node_by_id:
            raise ValueError(f"Edge references unknown source node '{edge.source}'.")
        if edge.target not in node_by_id:
            raise ValueError(f"Edge references unknown target node '{edge.target}'.")

    for node in nodes:
        if not node.input_bindings:
            continue
        input_ports = _node_input_ports(node, registry)
        for input_name, reference in node.input_bindings.items():
            try:
                source_id, field_name = parse_reference(reference)
            except ValueError as error:
                raise ValueError(
                    f"Node {describe_node(node)} input '{input_name}' has an "
                    f"invalid reference: {error}"
                ) from error

            source = node_by_id.get(source_id)
            if source is None:
                raise ValueError(
                    f"Node {describe_node(node)} input '{input_name}' points at "
                    f"unknown node '{source_id}'."
                )
            if input_name not in input_ports:
                raise ValueError(
                    f"Node {describe_node(node)} has no input port '{input_name}'."
                )

            output_ports = _node_output_ports(source, registry)
            if field_name not in output_ports:
                raise ValueError(
                    f"Node {describe_node(source)} has no output port '{field_name}'."
                )

            output_type = output_ports[field_name]
            input_type = input_ports[input_name]
            if not is_assignable(output_type, input_type):
                raise ValueError(
                    f"Type mismatch on node {describe_node(node)}: input "
                    f"'{input_name}' expects {describe_port_type(input_type)} "
                    f"but receives {describe_port_type(output_type)} from "
                    f"'{field_name}' of node {describe_node(source)}."
                )


def validate_workflow(workflow: WorkflowDefinition) -> None:
    """Validate a workflow before any IFC file is opened.

    Checks model slots, subworkflow structure, edge endpoints, every bound port
    pair against the assignability table, auto-bind ambiguity, and
    execution-order cycles.
    """
    prepare_workflow(workflow)


@dataclass(frozen=True)
class PreparedWorkflow:
    """A validated workflow flattened once, ready to execute."""

    workflow: WorkflowDefinition
    node_lookup: dict[str, WorkflowNode]
    execution_order: list[str]
    auto_bindings: dict[str, dict[str, str]]


def prepare_workflow(workflow: WorkflowDefinition) -> PreparedWorkflow:
    """Run every static check and flatten subworkflows in a single pass.

    Validation used to expand and topologically sort, then execution repeated
    both steps. Both now build this value instead, so there is one path and the
    work happens once.
    """
    validate_model_files(workflow.files)
    _validate_scope(workflow.nodes, workflow.edges)
    expanded = expand_workflow(workflow)
    node_lookup = build_node_lookup(expanded)
    execution_order = build_execution_order(expanded)
    auto_bindings = resolve_auto_bindings(expanded, node_lookup)
    return PreparedWorkflow(
        workflow=expanded,
        node_lookup=node_lookup,
        execution_order=execution_order,
        auto_bindings=auto_bindings,
    )
