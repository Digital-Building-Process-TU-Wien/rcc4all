"""Run a validated workflow against IFC files.

Owns everything that touches the outside world at run time: loading IFC
models, building the geometry cache, dispatching nodes in execution order,
and serialising results.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import ifcopenshell

from openbim_runner.nodes import ExecutionContext, NodeModel, dispatch, get_registry
from openbim_runner.util.geometry import build_geometry_cache
from openbim_runner.workflow.bindings import resolve_input_bindings
from openbim_runner.workflow.io import parse_workflow, resolve_ifc_path
from openbim_runner.workflow.model import ModelFile, WorkflowNode, describe_node
from openbim_runner.workflow.validate import prepare_workflow


async def execute_workflow_async(
    workflow_path: Path,
) -> tuple[dict[str, NodeModel], dict[str, WorkflowNode]]:
    workflow = parse_workflow(workflow_path)
    prepared = prepare_workflow(workflow)
    workflow = prepared.workflow
    node_lookup = prepared.node_lookup
    execution_order = prepared.execution_order
    node_registry = get_registry()

    models: dict[str, Any] = {}
    for model_file in workflow.files:
        resolved_path = resolve_ifc_path(workflow_path, model_file.path)
        model = ifcopenshell.open(str(resolved_path))  # pyright: ignore[reportUnknownMemberType]
        models[model_file.slug] = model
        if model_file.hash:
            _warn_on_hash_mismatch(model_file, resolved_path)

    geometry_cache: dict[str, Any] = {}
    for slug, model in models.items():
        geometry_cache.update(build_geometry_cache(model, slug=slug))

    node_outputs: dict[str, NodeModel] = {}
    auto_bindings = prepared.auto_bindings

    for node_id in execution_order:
        workflow_node = node_lookup[node_id]
        definition = node_registry.get(workflow_node.type)
        if definition is None:
            raise ValueError(
                f"Node {describe_node(workflow_node)} has unknown type '{workflow_node.type}'."
            )

        if workflow_node.input_bindings and not definition.takes_inputs:
            raise ValueError(
                f"Node {describe_node(workflow_node)} does not accept input bindings."
            )

        settings_payload = workflow_node.settings
        input_payload = resolve_input_bindings(
            workflow_node,
            node_outputs,
            auto_bindings=auto_bindings.get(workflow_node.id, {}),
        )
        context = ExecutionContext(
            models=models,
            main_model_id="main",
            node_outputs=node_outputs,
            workflow_dir=workflow_path.parent,
            geometry_cache=geometry_cache,
            output_dir=workflow_path.parent,
        )
        node_outputs[node_id] = await dispatch(
            workflow_node.type,
            settings_payload,
            inputs_payload=input_payload,
            context=context,
        )

    return node_outputs, node_lookup


def _warn_on_hash_mismatch(model_file: ModelFile, resolved_path: Path) -> None:
    """Non-fatal warning when an IFC file's content differs from its recorded hash.

    The hash is recorded by the web when a file is assigned to a slot as a bare
    SHA-256 hex digest. A mismatch signals the file on disk changed since
    assignment; the workflow still runs against the current file contents.
    """
    import hashlib

    try:
        digest = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    except OSError:
        return
    if digest != model_file.hash:
        print(
            f"WARNING: IFC file '{model_file.slug}' hash does not match the "
            "workflow definition (file changed since it was assigned).",
            file=sys.stderr,
        )


def execute_workflow(
    workflow_path: Path,
) -> tuple[dict[str, NodeModel], dict[str, WorkflowNode]]:
    return asyncio.run(execute_workflow_async(workflow_path))


def dump_results(
    node_outputs: dict[str, NodeModel], node_lookup: dict[str, WorkflowNode]
) -> str:
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
