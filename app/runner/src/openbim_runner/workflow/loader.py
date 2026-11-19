"""Turn a workflow file into a prepared, runnable workflow.

Everything before the first IFC file is opened lives here: reading the JSON,
checking model slots, ports, edges and cycles, expanding subworkflows, sorting
the nodes, and resolving auto-bindings. ``prepare_workflow`` is the entry point
the executor uses, so a file is parsed once per run.

The name pairs with ``executor``: the loader prepares, the executor runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openbim_runner.nodes import NodeDefinition, get_registry
from openbim_runner.port_types import (
    PortType,
    describe_port_type,
    is_assignable,
    model_port_types,
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
    parse_input_reference,
    parse_single_port,
    validate_model_files,
)
from openbim_runner.workflow.subworkflow import expand_workflow


def _read(workflow_path: Path) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate_json(
        workflow_path.read_text(encoding="utf-8")
    )


@dataclass(frozen=True)
class PreparedWorkflow:
    """A validated workflow flattened once, ready to execute."""

    workflow: WorkflowDefinition
    node_lookup: dict[str, WorkflowNode]
    execution_order: list[str]
    auto_bindings: dict[str, dict[str, str]]


def prepare_definition(workflow: WorkflowDefinition) -> PreparedWorkflow:
    """Run every static check and flatten a parsed workflow in one pass.

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


def prepare_workflow(workflow_path: Path) -> PreparedWorkflow:
    """Read a workflow file and prepare it for execution."""
    return prepare_definition(_read(workflow_path))


def load_workflow(workflow_path: Path) -> WorkflowDefinition:
    """Read a workflow file and validate it, without flattening it."""
    workflow = _read(workflow_path)
    validate_workflow(workflow)
    return workflow


def validate_workflow(workflow: WorkflowDefinition) -> None:
    """Validate a workflow before any IFC file is opened.

    Checks model slots, subworkflow structure, edge endpoints, every bound port
    pair against the assignability table, auto-bind ambiguity, and
    execution-order cycles.
    """
    prepare_definition(workflow)


def resolve_ifc_path(workflow_path: Path, ifc_path: str) -> Path:
    candidate_path = Path(ifc_path)
    if candidate_path.is_absolute():
        return candidate_path

    return workflow_path.parent / candidate_path


def require_definition(node: WorkflowNode) -> NodeDefinition:
    """Return the registered definition for a node, naming the node on failure."""
    definition = get_registry().get(node.type)
    if definition is None:
        raise ValueError(f"Node {describe_node(node)} has unknown type '{node.type}'.")
    return definition


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


def _node_input_ports(node: WorkflowNode) -> dict[str, PortType]:
    """The ports a node accepts, as the type checker sees them in its scope."""
    if node.type == SUBWORKFLOW_INPUT_TYPE:
        return {}
    if node.type == SUBWORKFLOW_OUTPUT_TYPE:
        port = parse_single_port(node)
        return {port.name: port.type}
    if node.type == SUBWORKFLOW_TYPE:
        return _subworkflow_input_ports(node)

    definition = require_definition(node)
    if not definition.takes_inputs or definition.inputs_model is None:
        return {}
    return model_port_types(definition.inputs_model, node=node.type)


def _node_output_ports(node: WorkflowNode) -> dict[str, PortType]:
    """The ports a node produces, as the type checker sees them in its scope."""
    if node.type == SUBWORKFLOW_OUTPUT_TYPE:
        return {}
    if node.type == SUBWORKFLOW_INPUT_TYPE:
        port = parse_single_port(node)
        return {port.name: port.type}
    if node.type == SUBWORKFLOW_TYPE:
        port = _subworkflow_output_port(node)
        return {} if port is None else {port.name: port.type}

    definition = require_definition(node)
    return model_port_types(definition.result_model, node=node.type)


def _validate_scope(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> None:
    """Validate one scope: edge endpoints and every bound port pair."""
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
        input_ports = _node_input_ports(node)
        for input_name, reference in node.input_bindings.items():
            source_id, field_name = parse_input_reference(
                reference, node=node, input_name=input_name
            )

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

            output_ports = _node_output_ports(source)
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
