"""Resolve node input bindings to runtime values.

Explicit bindings are authored in the workflow. Auto-bindings are inferred for
inputs marked with ``AutoBind`` by finding the single compatible upstream
output. Both are applied here, at the moment a node is about to run.
"""

from __future__ import annotations

from typing import Any

from openbim_runner.nodes import NodeModel, get_registry
from openbim_runner.nodes.base import AutoBind
from openbim_runner.port_types import (
    annotation_to_port_type_or_none,
    is_assignable,
)
from openbim_runner.workflow.model import (
    WorkflowDefinition,
    WorkflowNode,
    describe_node,
    parse_input_reference,
)


def resolve_input_bindings(
    workflow_node: WorkflowNode,
    node_outputs: dict[str, NodeModel],
    *,
    auto_bindings: dict[str, str] | None = None,
) -> dict[str, Any]:
    explicit = workflow_node.input_bindings
    effective = {**(auto_bindings or {}), **explicit}

    input_payload: dict[str, Any] = {}

    for input_name, reference in effective.items():
        source_node_id, field_name = parse_input_reference(
            reference, node=workflow_node, input_name=input_name
        )
        source_output = node_outputs.get(source_node_id)
        if source_output is None:
            raise ValueError(
                f"Node {describe_node(workflow_node)} input '{input_name}' points "
                f"to '{source_node_id}', which has not run yet."
            )
        if not hasattr(source_output, field_name):
            raise ValueError(
                f"Node {describe_node(workflow_node)} input '{input_name}' points "
                f"to missing field '{field_name}' on '{source_node_id}'."
            )

        input_payload[input_name] = getattr(source_output, field_name)

    return input_payload


def resolve_auto_bindings(
    workflow: WorkflowDefinition,
    node_lookup: dict[str, WorkflowNode],
) -> dict[str, dict[str, str]]:
    """Resolve runtime-implicit bindings for inputs flagged with ``AutoBind``.

    For each node, every declared input that carries the ``AutoBind`` marker and
    is not explicitly bound resolves to the single directly-upstream neighbor
    (via ``workflow.edges``) whose result model exposes a field whose type
    matches the input's. Returns ``{node_id: {input_name: "<source>.<field>"}}``.

    Explicit bindings (``WorkflowNode.input_bindings``) always take precedence
    and are never returned here. An input with no compatible upstream stays
    unbound; one with several is rejected with a clear error.
    """
    registry = get_registry()
    predecessors: dict[str, set[str]] = {node_id: set() for node_id in node_lookup}
    for edge in workflow.edges:
        predecessors.setdefault(edge.target, set()).add(edge.source)

    auto_bindings: dict[str, dict[str, str]] = {}
    for node_id, workflow_node in node_lookup.items():
        definition = registry.get(workflow_node.type)
        if (
            definition is None
            or not definition.takes_inputs
            or definition.inputs_model is None
        ):
            continue

        for input_name, field_info in definition.inputs_model.model_fields.items():
            if input_name in workflow_node.input_bindings:
                continue
            if not any(isinstance(marker, AutoBind) for marker in field_info.metadata):
                continue

            source = _resolve_auto_source(
                node_id=node_id,
                input_name=input_name,
                input_annotation=field_info.annotation,
                predecessors=predecessors.get(node_id, set()),
                node_lookup=node_lookup,
                registry=registry,
            )
            if source is not None:
                auto_bindings.setdefault(node_id, {})[input_name] = source

    return auto_bindings


def _resolve_auto_source(
    *,
    node_id: str,
    input_name: str,
    input_annotation: Any,
    predecessors: set[str],
    node_lookup: dict[str, WorkflowNode],
    registry: dict[str, Any],
) -> str | None:
    """Return the ``"<source_id>.<field>"`` reference for ``input_name`` or ``None``.

    ``None`` means no upstream source is compatible, in which case the input
    simply stays unbound (the node keeps its own default/error behavior).
    Raises ``ValueError`` when the resolution is ambiguous.
    """
    input_type = annotation_to_port_type_or_none(input_annotation)
    if input_type is None:
        return None

    candidates: list[tuple[str, str | None]] = []
    for source_id in sorted(predecessors):
        source_definition = registry.get(node_lookup[source_id].type)
        if source_definition is None or source_definition.result_model is None:
            continue
        match_fields = [
            field
            for field, field_info in source_definition.result_model.model_fields.items()
            if (
                (output_type := annotation_to_port_type_or_none(field_info.annotation))
                is not None
                and is_assignable(output_type, input_type)
            )
        ]
        if not match_fields:
            continue
        candidates.append(
            (source_id, match_fields[0] if len(match_fields) == 1 else None)
        )

    if not candidates:
        return None
    if len(candidates) == 1:
        source_id, field_name = candidates[0]
        if field_name is None:
            raise ValueError(
                f"Node '{node_lookup[node_id].get_label()}' (id '{node_id}') input "
                f"'{input_name}' auto-bind is ambiguous: upstream node '{source_id}' "
                "has several matching outputs."
            )
        return f"{source_id}.{field_name}"

    raise ValueError(
        f"Node '{node_lookup[node_id].get_label()}' (id '{node_id}') input "
        f"'{input_name}' auto-bind is ambiguous: {len(candidates)} upstream nodes "
        "provide a matching output. Connect one or set the binding explicitly."
    )
