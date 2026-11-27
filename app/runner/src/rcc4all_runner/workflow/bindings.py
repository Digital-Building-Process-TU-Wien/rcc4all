"""Turn declared input bindings into runtime values.

A binding is authored in the workflow as ``"<node_id>.<field_name>"``. This
module reads those references and returns the values of nodes that already ran.
The runner never invents a binding: what the workflow declares is what runs.
"""

from __future__ import annotations

from typing import Any

from rcc4all_runner.nodes import NodeModel
from rcc4all_runner.workflow.model import (
    WorkflowNode,
    describe_node,
    parse_input_reference,
)


def resolve_input_bindings(
    workflow_node: WorkflowNode,
    node_outputs: dict[str, NodeModel],
) -> dict[str, Any]:
    """Resolve every declared binding of ``workflow_node`` to a value."""
    input_payload: dict[str, Any] = {}

    for input_name, reference in workflow_node.input_bindings.items():
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
