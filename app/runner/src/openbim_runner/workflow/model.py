"""The workflow document model.

Owns the Pydantic representation of a workflow JSON, the model slug rules,
reference parsing, and the workflow JSON schema used by ``export-schema``.

This is the bottom of the ``workflow`` package dependency chain: every other
module imports from here, and this module imports nothing from the package.
"""

from __future__ import annotations

import re
from typing import Any, cast

from pydantic import Field, TypeAdapter, ValidationError

from openbim_runner.nodes import NodeModel
from openbim_runner.port_types import PortType

SUBWORKFLOW_TYPE = "subworkflow"
SUBWORKFLOW_INPUT_TYPE = "subworkflow_input"
SUBWORKFLOW_OUTPUT_TYPE = "subworkflow_output"
SUBWORKFLOW_META_TYPES = frozenset(
    {SUBWORKFLOW_TYPE, SUBWORKFLOW_INPUT_TYPE, SUBWORKFLOW_OUTPUT_TYPE}
)
PORT_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class NodePosition(NodeModel):
    x: float = Field(default=0, title="X", description="Canvas X coordinate.")
    y: float = Field(default=0, title="Y", description="Canvas Y coordinate.")


class SubworkflowPort(NodeModel):
    name: str = Field(title="Port name", description="Port name used in bindings.")
    type: PortType = Field(
        title="Port type",
        description="Port type descriptor. Enforced by the runner and the editor.",
    )


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
    position: NodePosition | None = Field(
        default=None,
        title="Position",
        description="Canvas position. Persisted so the editor can restore layout; ignored by execution.",
    )
    subworkflow: SubworkflowDefinition | None = Field(
        default=None,
        title="Subworkflow",
        description="Embedded subworkflow definition when this node's type is 'subworkflow'.",
    )

    def get_label(self) -> str:
        return self.label if self.label else self.type


class WorkflowEdge(NodeModel):
    source: str = Field(title="Source node", description="Upstream node ID.")
    target: str = Field(title="Target node", description="Downstream node ID.")


class SubworkflowDefinition(NodeModel):
    name: str = Field(default="", title="Name", description="Display name.")
    nodes: list[WorkflowNode] = Field(
        default=[], title="Nodes", description="Nodes belonging to the subworkflow."
    )
    edges: list[WorkflowEdge] = Field(
        default=[], title="Edges", description="Edges belonging to the subworkflow."
    )


WorkflowNode.model_rebuild()


class ModelFile(NodeModel):
    """An IFC file assigned to a workflow slot, keyed by a user-chosen slug."""

    path: str = Field(
        title="Path",
        description="Path to the IFC file, relative to the workflow JSON when not absolute.",
    )
    slug: str = Field(
        title="Slug",
        description="User-chosen identifier for this model. The reserved slug 'main' is the main IFC file.",
    )
    hash: str = Field(
        default="",
        title="File hash",
        description="Optional SHA-256 content hash of the file, recorded when the file was assigned.",
    )


class WorkflowDefinition(NodeModel):
    files: list[ModelFile] = Field(
        default=[],
        title="IFC files",
        description=(
            "IFC files loaded for this workflow, each keyed by a model slug. "
            "Exactly one file must use the reserved slug 'main'."
        ),
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


# Keep in sync with the web validator below:
# app/web/app/components/nodes/NodeLibrarySidebar.vue (MODEL_SLUG_RE).
MODEL_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-_]*$"


def validate_model_files(files: list[ModelFile]) -> None:
    """Validate that the workflow's IFC file slots are well-formed.

    - Every slug is non-empty and matches ``MODEL_SLUG_PATTERN``.
    - Slugs are unique.
    - The reserved ``main`` slug is present exactly once.
    """
    if not files:
        raise ValueError(
            "Workflow must define at least one IFC file with the reserved slug 'main'."
        )

    slugs: dict[str, ModelFile] = {}
    for model_file in files:
        slug = model_file.slug
        if not slug:
            raise ValueError("Every IFC file slot must define a non-empty 'slug'.")
        if not re.fullmatch(MODEL_SLUG_PATTERN, slug):
            raise ValueError(
                f"Invalid model slug '{slug}'. Slugs must match "
                f"'{MODEL_SLUG_PATTERN}' (lowercase letters, digits, '-' or '_'; "
                "must start with a letter or digit)."
            )
        if slug in slugs:
            raise ValueError(f"Duplicate model slug '{slug}'.")
        slugs[slug] = model_file

    if "main" not in slugs:
        raise ValueError("Workflow must define a file with the reserved slug 'main'.")


def get_workflow_models_schema() -> dict[str, Any]:
    """JSON Schema for the workflow file itself, for ``export-schema``.

    ``SubworkflowPort`` is not reachable from ``WorkflowDefinition`` because
    meta-node ports live in a free-form ``settings`` object, so it is added
    explicitly. Its inline ``PortType`` union is named once and referenced, so
    the generated TypeScript has a single ``PortType`` type to reuse.
    """
    schema = WorkflowDefinition.model_json_schema()
    defs: dict[str, Any] = schema.setdefault("$defs", {})

    port_schema = SubworkflowPort.model_json_schema()
    defs.update(port_schema.pop("$defs", {}))

    port_type_schema = TypeAdapter(PortType).json_schema()
    defs.update(port_type_schema.pop("$defs", {}))
    defs["PortType"] = port_type_schema

    properties = cast(dict[str, Any], port_schema["properties"])
    properties["type"] = {"$ref": "#/$defs/PortType"}
    defs["SubworkflowPort"] = port_schema
    return schema


def describe_node(workflow_node: WorkflowNode) -> str:
    """Label and id of a node, for error messages."""
    return f"'{workflow_node.get_label()}' (id '{workflow_node.id}')"


def parse_reference(reference: str) -> tuple[str, str]:
    try:
        node_id, field_name = reference.split(".", maxsplit=1)
    except ValueError as error:
        raise ValueError(
            f"Invalid reference format '{reference}'. Expected '<node_id>.<field_name>'."
        ) from error

    if not node_id or not field_name:
        raise ValueError(
            f"Invalid reference format '{reference}'. Expected '<node_id>.<field_name>'."
        )

    return node_id, field_name


def parse_input_reference(
    reference: str,
    *,
    node: WorkflowNode,
    input_name: str,
) -> tuple[str, str]:
    """Parse a node input reference, adding the node and input to errors."""
    try:
        return parse_reference(reference)
    except ValueError as error:
        raise ValueError(
            f"Node {describe_node(node)} input '{input_name}' has an "
            f"invalid reference: {error}"
        ) from error


def parse_single_port(node: WorkflowNode) -> SubworkflowPort:
    """Read the one port a ``subworkflow_input``/``subworkflow_output`` node owns."""
    raw_port = node.settings.get("port")
    if raw_port is None:
        raise ValueError(
            f"Node {describe_node(node)} must define a single port in 'settings.port'."
        )

    try:
        port = SubworkflowPort.model_validate(raw_port)
    except ValidationError as error:
        raise ValueError(
            f"Node {describe_node(node)} has an invalid port definition: {error}"
        ) from error

    if not re.fullmatch(PORT_NAME_PATTERN, port.name):
        raise ValueError(
            f"Node {describe_node(node)} has invalid port name '{port.name}'. "
            f"Port names must match '{PORT_NAME_PATTERN}'."
        )

    return port
