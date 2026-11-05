from __future__ import annotations

import asyncio
import json
import re
from collections import deque
from pathlib import Path
from typing import Any

import ifcopenshell
from pydantic import Field, ValidationError

from openbim_runner.nodes import ExecutionContext, NodeModel, dispatch, get_registry
from openbim_runner.nodes.base import AutoBind
from openbim_runner.util.geometry import build_geometry_cache

SUBWORKFLOW_TYPE = "subworkflow"
SUBWORKFLOW_INPUT_TYPE = "subworkflow_input"
SUBWORKFLOW_OUTPUT_TYPE = "subworkflow_output"
SUBWORKFLOW_META_TYPES = frozenset(
    {SUBWORKFLOW_TYPE, SUBWORKFLOW_INPUT_TYPE, SUBWORKFLOW_OUTPUT_TYPE}
)
NAMESPACE_SEPARATOR = "::"
PORT_NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


class NodePosition(NodeModel):
    x: float = Field(default=0, title="X", description="Canvas X coordinate.")
    y: float = Field(default=0, title="Y", description="Canvas Y coordinate.")


class SubworkflowPort(NodeModel):
    name: str = Field(title="Port name", description="Port name used in bindings.")
    type: Any = Field(
        default_factory=dict,
        title="Port type",
        description="JSON-schema-like type descriptor. Informational only for the runner.",
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


def load_workflow(workflow_path: Path) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate_json(
        workflow_path.read_text(encoding="utf-8")
    )


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


def expand_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
    """Inline every embedded subworkflow into a flat node/edge graph.

    Nested subworkflows are expanded depth-first, so inner nodes end up named
    ``<outer_id>::<inner_id>``. The returned workflow contains no
    ``subworkflow``-family nodes.
    """
    nodes, edges = _expand_scope(
        [node.model_copy(deep=True) for node in workflow.nodes],
        [edge.model_copy(deep=True) for edge in workflow.edges],
    )

    for node in nodes:
        if node.type in SUBWORKFLOW_META_TYPES:
            raise ValueError(
                f"Node {describe_node(node)} is only valid inside a subworkflow "
                "definition."
            )

    return workflow.model_copy(update={"nodes": nodes, "edges": edges})


def _expand_scope(
    nodes: list[WorkflowNode], edges: list[WorkflowEdge]
) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    """Expand one scope: nested subworkflows first, then inline them here."""
    while True:
        subworkflow_node = next(
            (node for node in nodes if node.type == SUBWORKFLOW_TYPE), None
        )
        if subworkflow_node is None:
            return nodes, edges

        definition = subworkflow_node.subworkflow
        if definition is None:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} is missing its "
                "embedded definition."
            )

        inner_nodes, inner_edges = _expand_scope(definition.nodes, definition.edges)
        definition.nodes = inner_nodes
        definition.edges = inner_edges
        nodes, edges = _inline_subworkflow(subworkflow_node, nodes, edges)


def _parse_single_port(node: WorkflowNode) -> SubworkflowPort:
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


def _inline_subworkflow(
    subworkflow_node: WorkflowNode,
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
    definition = subworkflow_node.subworkflow
    if definition is None:
        raise ValueError(
            f"Subworkflow node {describe_node(subworkflow_node)} is missing its "
            "embedded definition."
        )

    inner_nodes = definition.nodes
    inner_edges = definition.edges
    inner_node_ids = {node.id for node in inner_nodes}
    if len(inner_node_ids) != len(inner_nodes):
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} contains duplicate node IDs."
        )

    for inner_node in inner_nodes:
        if inner_node.type == SUBWORKFLOW_TYPE:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} still contains nested "
                f"subworkflow node {describe_node(inner_node)}."
            )

    input_nodes = [node for node in inner_nodes if node.type == SUBWORKFLOW_INPUT_TYPE]
    output_nodes = [
        node for node in inner_nodes if node.type == SUBWORKFLOW_OUTPUT_TYPE
    ]
    if len(output_nodes) > 1:
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} allows at most one "
            f"'{SUBWORKFLOW_OUTPUT_TYPE}' node (found {len(output_nodes)})."
        )

    output_node = output_nodes[0] if output_nodes else None
    output_node_id = output_node.id if output_node is not None else None
    output_port = _parse_single_port(output_node) if output_node is not None else None

    input_ports_by_id: dict[str, SubworkflowPort] = {}
    input_nodes_by_id: dict[str, WorkflowNode] = {}
    for input_node in input_nodes:
        if input_node.input_bindings:
            raise ValueError(
                f"Node {describe_node(input_node)} is a subworkflow input and cannot "
                "define input bindings."
            )
        port = _parse_single_port(input_node)
        duplicate = next(
            (other for other in input_ports_by_id.values() if other.name == port.name),
            None,
        )
        if duplicate is not None:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} defines duplicate "
                f"input port '{port.name}'."
            )
        input_ports_by_id[input_node.id] = port
        input_nodes_by_id[input_node.id] = input_node
    input_port_names = {port.name for port in input_ports_by_id.values()}

    for port_name in sorted(input_port_names):
        if port_name not in subworkflow_node.input_bindings:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} input port "
                f"'{port_name}' is not bound by the parent."
            )

    for input_name, reference in subworkflow_node.input_bindings.items():
        if input_name not in input_port_names:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} has a binding "
                f"for '{input_name}' but no matching input port."
            )
        try:
            source_id, _ = parse_reference(reference)
        except ValueError as error:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} input "
                f"'{input_name}' has an invalid reference: {error}"
            ) from error
        if source_id == subworkflow_node.id:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} input "
                f"'{input_name}' cannot bind to one of its own outputs."
            )

    namespace = f"{subworkflow_node.id}{NAMESPACE_SEPARATOR}"
    output_producer_id: str | None = None
    output_producer_reference: str | None = None

    if output_node is not None and output_port is not None:
        output_bindings = output_node.input_bindings
        if output_port.name not in output_bindings:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' has no producer binding."
            )
        for binding_name in output_bindings:
            if binding_name != output_port.name:
                raise ValueError(
                    f"Node {describe_node(output_node)} has a binding for "
                    f"'{binding_name}' but no matching output port."
                )

        try:
            producer_id, producer_field = parse_reference(
                output_bindings[output_port.name]
            )
        except ValueError as error:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' has an invalid producer reference: {error}"
            ) from error
        if producer_id in input_ports_by_id or producer_id == output_node.id:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' must be produced by an inner node, not a "
                "subworkflow meta node."
            )
        if producer_id not in inner_node_ids:
            raise ValueError(
                f"Node {describe_node(output_node)} output port "
                f"'{output_port.name}' points at unknown inner node '{producer_id}'."
            )
        output_producer_id = f"{namespace}{producer_id}"
        output_producer_reference = f"{output_producer_id}.{producer_field}"

    for inner_node in inner_nodes:
        if inner_node.id in input_ports_by_id or inner_node.id == output_node_id:
            continue
        for input_name, reference in inner_node.input_bindings.items():
            try:
                source_id, field_name = parse_reference(reference)
            except ValueError as error:
                raise ValueError(
                    f"Node {describe_node(inner_node)} input '{input_name}' has an "
                    f"invalid reference: {error}"
                ) from error
            if source_id in input_ports_by_id:
                port = input_ports_by_id[source_id]
                if field_name != port.name:
                    raise ValueError(
                        f"Node {describe_node(inner_node)} input '{input_name}' "
                        f"references '{source_id}.{field_name}', but input node "
                        f"{describe_node(input_nodes_by_id[source_id])} only exposes "
                        f"port '{port.name}'."
                    )
            elif source_id == output_node_id:
                raise ValueError(
                    f"Node {describe_node(inner_node)} input '{input_name}' references "
                    "the subworkflow output node, which produces no outputs."
                )
            elif source_id not in inner_node_ids:
                raise ValueError(
                    f"Node {describe_node(inner_node)} input '{input_name}' points at "
                    f"'{source_id}', which is outside subworkflow "
                    f"{describe_node(subworkflow_node)}."
                )

    for edge in inner_edges:
        if edge.source not in inner_node_ids:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} has an edge with "
                f"unknown source node '{edge.source}'."
            )
        if edge.target not in inner_node_ids:
            raise ValueError(
                f"Subworkflow {describe_node(subworkflow_node)} has an edge with "
                f"unknown target node '{edge.target}'."
            )

    injected_nodes: list[WorkflowNode] = []
    consumers_by_port: dict[str, set[str]] = {}

    for inner_node in inner_nodes:
        if inner_node.id in input_ports_by_id or inner_node.id == output_node_id:
            continue

        renamed_node = inner_node.model_copy(deep=True)
        renamed_node.id = f"{namespace}{inner_node.id}"
        rewritten_bindings: dict[str, str] = {}

        for input_name, reference in inner_node.input_bindings.items():
            source_id, field_name = parse_reference(reference)
            if source_id in input_ports_by_id:
                port = input_ports_by_id[source_id]
                rewritten_bindings[input_name] = subworkflow_node.input_bindings[
                    port.name
                ]
                consumers_by_port.setdefault(port.name, set()).add(renamed_node.id)
            else:
                rewritten_bindings[input_name] = f"{namespace}{source_id}.{field_name}"

        renamed_node.input_bindings = rewritten_bindings
        injected_nodes.append(renamed_node)

    dropped_ids = set(input_ports_by_id)
    if output_node_id is not None:
        dropped_ids.add(output_node_id)
    inner_edges_flattened: list[tuple[str, str]] = []
    for edge in inner_edges:
        if edge.source in dropped_ids or edge.target in dropped_ids:
            continue
        inner_edges_flattened.append(
            (f"{namespace}{edge.source}", f"{namespace}{edge.target}")
        )

    final_nodes: list[WorkflowNode] = []
    output_consumers: set[str] = set()

    for other_node in nodes:
        if other_node.id == subworkflow_node.id:
            final_nodes.extend(injected_nodes)
            continue

        renamed_other = other_node.model_copy(deep=True)
        rewritten_bindings = {}
        for input_name, reference in other_node.input_bindings.items():
            try:
                source_id, field_name = parse_reference(reference)
            except ValueError as error:
                raise ValueError(
                    f"Node {describe_node(other_node)} input '{input_name}' has an "
                    f"invalid reference: {error}"
                ) from error
            if source_id == subworkflow_node.id:
                if output_port is None or output_producer_reference is None:
                    raise ValueError(
                        f"Node {describe_node(other_node)} input '{input_name}' "
                        f"references '{subworkflow_node.id}.{field_name}', but "
                        f"subworkflow {describe_node(subworkflow_node)} defines no "
                        "output port."
                    )
                if field_name != output_port.name:
                    raise ValueError(
                        f"Node {describe_node(other_node)} input '{input_name}' "
                        f"references '{subworkflow_node.id}.{field_name}', but "
                        f"subworkflow {describe_node(subworkflow_node)} has no output "
                        f"port '{field_name}' (its output port is "
                        f"'{output_port.name}')."
                    )
                rewritten_bindings[input_name] = output_producer_reference
                output_consumers.add(other_node.id)
            else:
                rewritten_bindings[input_name] = reference
        renamed_other.input_bindings = rewritten_bindings
        final_nodes.append(renamed_other)

    final_node_ids = {node.id for node in final_nodes}
    if len(final_node_ids) != len(final_nodes):
        raise ValueError(
            f"Subworkflow {describe_node(subworkflow_node)} would produce duplicate "
            "node IDs after expansion."
        )

    final_edges: list[WorkflowEdge] = []
    seen_edges: set[tuple[str, str]] = set()

    def add_edge(source: str, target: str) -> None:
        if (source, target) in seen_edges:
            return
        seen_edges.add((source, target))
        final_edges.append(WorkflowEdge(source=source, target=target))

    for edge in edges:
        if edge.source == subworkflow_node.id and edge.target == subworkflow_node.id:
            raise ValueError(
                f"Subworkflow node {describe_node(subworkflow_node)} has an edge to "
                "itself."
            )

        if edge.target == subworkflow_node.id:
            bound_ports = {
                port_name
                for port_name, reference in subworkflow_node.input_bindings.items()
                if parse_reference(reference)[0] == edge.source
            }
            consumers: set[str] = set()
            for port_name in bound_ports:
                consumers.update(consumers_by_port.get(port_name, set()))
            if consumers:
                for consumer_id in sorted(consumers):
                    add_edge(edge.source, consumer_id)
            else:
                print(
                    f"WARNING: dropping order-only edge '{edge.source}' -> "
                    f"'{edge.target}' across subworkflow "
                    f"{describe_node(subworkflow_node)}."
                )
            continue

        if edge.source == subworkflow_node.id:
            if edge.target not in final_node_ids:
                raise ValueError(
                    f"Edge references unknown target node '{edge.target}'."
                )
            if output_producer_id is not None and edge.target in output_consumers:
                add_edge(output_producer_id, edge.target)
            else:
                print(
                    f"WARNING: dropping order-only edge '{edge.source}' -> "
                    f"'{edge.target}' across subworkflow "
                    f"{describe_node(subworkflow_node)}."
                )
            continue

        add_edge(edge.source, edge.target)

    for source, target in inner_edges_flattened:
        add_edge(source, target)

    return final_nodes, final_edges


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
        try:
            source_node_id, field_name = parse_reference(reference)
        except ValueError as error:
            raise ValueError(
                f"Node {describe_node(workflow_node)} input '{input_name}' has "
                f"an invalid reference: {error}"
            ) from error
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
    candidates: list[tuple[str, str | None]] = []
    for source_id in sorted(predecessors):
        source_definition = registry.get(node_lookup[source_id].type)
        if source_definition is None or source_definition.result_model is None:
            continue
        match_fields = [
            field
            for field, field_info in source_definition.result_model.model_fields.items()
            if field_info.annotation == input_annotation
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


async def execute_workflow_async(
    workflow_path: Path,
) -> tuple[dict[str, NodeModel], dict[str, WorkflowNode]]:
    workflow = load_workflow(workflow_path)
    workflow = expand_workflow(workflow)
    node_lookup = build_node_lookup(workflow)
    execution_order = build_execution_order(workflow)
    node_registry = get_registry()

    validate_model_files(workflow.files)
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
    auto_bindings = resolve_auto_bindings(workflow, node_lookup)

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
            "workflow definition (file changed since it was assigned)."
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
