"""Turn a workflow file into a prepared, runnable workflow.

Everything before the first IFC file is opened lives here: reading the JSON,
checking model slots, ports, edges and cycles, expanding subworkflows, and
sorting the nodes. ``prepare_workflow`` is the entry point the executor uses, so
a file is parsed once per run.

The name pairs with ``executor``: the loader prepares, the executor runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rcc4all_runner.nodes import NodeDefinition, get_registry
from rcc4all_runner.schemas import (
    describe_schema,
    is_schema_assignable,
    model_field_schemas,
)
from rcc4all_runner.workflow.graph import (
    build_execution_order,
    build_node_lookup,
    index_nodes,
    validate_edges,
)
from rcc4all_runner.workflow.model import (
    SUBWORKFLOW_INPUT_TYPE,
    SUBWORKFLOW_META_TYPES,
    SUBWORKFLOW_OUTPUT_TYPE,
    SUBWORKFLOW_TYPE,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    describe_node,
    parse_input_reference,
    parse_single_port,
    require_subworkflow_definition,
    validate_model_files,
)
from rcc4all_runner.workflow.subworkflow import (
    collect_subworkflow_ports,
    expand_workflow,
)


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


def prepare_definition(workflow: WorkflowDefinition) -> PreparedWorkflow:
    """Run all static checks, expand subworkflows, and compute execution order."""
    validate_model_files(workflow.files)
    _validate_scope(workflow.nodes, workflow.edges)
    expanded = expand_workflow(workflow)
    _validate_expanded_types(expanded.nodes)
    node_lookup = build_node_lookup(expanded)
    execution_order = build_execution_order(expanded, node_lookup=node_lookup)
    return PreparedWorkflow(
        workflow=expanded,
        node_lookup=node_lookup,
        execution_order=execution_order,
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
    pair against the assignability table, every required input having a
    binding, and execution-order cycles.
    """
    prepare_definition(workflow)


def require_definition(node: WorkflowNode) -> NodeDefinition:
    """Return the registered definition for a node, naming the node on failure."""
    definition = get_registry().get(node.type)
    if definition is None:
        raise ValueError(f"Node {describe_node(node)} has unknown type '{node.type}'.")
    return definition


def _node_port_names(node: WorkflowNode) -> tuple[set[str], set[str]]:
    """Return ``(input_names, output_names)`` for a node in its scope."""
    if node.type == SUBWORKFLOW_INPUT_TYPE:
        port = parse_single_port(node)
        return set(), {port.name}
    if node.type == SUBWORKFLOW_OUTPUT_TYPE:
        port = parse_single_port(node)
        return {port.name}, set()
    if node.type == SUBWORKFLOW_TYPE:
        ports = collect_subworkflow_ports(node, require_subworkflow_definition(node))
        inputs = {port.name for port in ports.input_ports_by_id.values()}
        outputs: set[str] = (
            set() if ports.output_port is None else {ports.output_port.name}
        )
        return inputs, outputs

    definition = require_definition(node)
    inputs_names: set[str] = (
        set(definition.inputs_model.model_fields)
        if definition.takes_inputs and definition.inputs_model is not None
        else set()
    )
    outputs_names = set(definition.result_model.model_fields)
    return inputs_names, outputs_names


def _validate_required_inputs(node: WorkflowNode) -> None:
    """Every input without a default must be bound explicitly.

    "Required" is taken from the input model: the field has no default. The
    runner does not infer bindings, so an unbound required input is a workflow
    error rather than a guess.
    """
    if node.type in SUBWORKFLOW_META_TYPES:
        return

    definition = require_definition(node)
    if not definition.takes_inputs or definition.inputs_model is None:
        return

    for input_name, field_info in definition.inputs_model.model_fields.items():
        if field_info.is_required() and input_name not in node.input_bindings:
            raise ValueError(
                f"Node {describe_node(node)} input '{input_name}' is required but "
                "has no binding. Connect an upstream output to it."
            )


def _validate_scope(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> None:
    """Validate one scope structurally: edge endpoints, required inputs, and port names."""
    node_by_id = index_nodes(nodes)

    for node in nodes:
        if node.type == SUBWORKFLOW_TYPE:
            definition = require_subworkflow_definition(node)
            _validate_scope(definition.nodes, definition.edges)
            continue
        _validate_required_inputs(node)

    validate_edges(edges, node_by_id)

    for node in nodes:
        if not node.input_bindings:
            continue
        input_ports, _ = _node_port_names(node)
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

            _, output_ports = _node_port_names(source)
            if field_name not in output_ports:
                raise ValueError(
                    f"Node {describe_node(source)} has no output port '{field_name}'."
                )


def _validate_expanded_types(nodes: list[WorkflowNode]) -> None:
    """Validate structural JSON Schema compatibility across every concrete binding.

    Runs after ``expand_workflow()`` so subworkflow pass-through ports are
    resolved directly to their concrete producer and consumer models.
    """
    node_by_id = {node.id: node for node in nodes}
    ports_cache: dict[
        str, tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]
    ] = {}

    def node_schemas(
        node: WorkflowNode,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        cached = ports_cache.get(node.type)
        if cached is not None:
            return cached
        definition = require_definition(node)
        inputs = (
            model_field_schemas(definition.inputs_model, node=node.type)
            if definition.takes_inputs and definition.inputs_model is not None
            else {}
        )
        outputs = model_field_schemas(definition.result_model, node=node.type)
        ports_cache[node.type] = (inputs, outputs)
        return inputs, outputs

    for node in nodes:
        if not node.input_bindings:
            continue
        input_schemas, _ = node_schemas(node)
        for input_name, reference in node.input_bindings.items():
            source_id, field_name = parse_input_reference(
                reference, node=node, input_name=input_name
            )
            source = node_by_id[source_id]
            _, output_schemas = node_schemas(source)

            output_schema = output_schemas[field_name]
            input_schema = input_schemas[input_name]
            if not is_schema_assignable(output_schema, input_schema):
                raise ValueError(
                    f"Type mismatch on node {describe_node(node)}: input "
                    f"'{input_name}' expects {describe_schema(input_schema)} "
                    f"but receives {describe_schema(output_schema)} from "
                    f"'{field_name}' of node {describe_node(source)}."
                )
