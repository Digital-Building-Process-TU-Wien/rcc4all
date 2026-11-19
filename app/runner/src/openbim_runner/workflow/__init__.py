"""Public wrapper for workflow loading, validation, and execution.

The implementation lives in focused modules. This module re-exports the names
that callers have always imported from ``openbim_runner.workflow`` so the
package split stays invisible to ``main.py`` and the tests.

Module map:

- ``model``: the workflow document, slug rules, references, JSON schema
- ``loader``: read the JSON, validate it, flatten and prepare it to run
- ``subworkflow``: inline embedded subworkflows into a flat graph
- ``graph``: node lookup and topological execution order
- ``bindings``: declared input references resolved to runtime values
- ``executor``: IFC loading, geometry cache, dispatch, results
"""

from __future__ import annotations

from openbim_runner.workflow.bindings import resolve_input_bindings
from openbim_runner.workflow.executor import (
    dump_results,
    execute_workflow,
    execute_workflow_async,
)
from openbim_runner.workflow.graph import (
    add_dependency,
    build_execution_order,
    build_node_lookup,
)
from openbim_runner.workflow.loader import (
    PreparedWorkflow,
    load_workflow,
    prepare_workflow,
    resolve_ifc_path,
    validate_workflow,
)
from openbim_runner.workflow.model import (
    MODEL_SLUG_PATTERN,
    PORT_NAME_PATTERN,
    SUBWORKFLOW_INPUT_TYPE,
    SUBWORKFLOW_META_TYPES,
    SUBWORKFLOW_OUTPUT_TYPE,
    SUBWORKFLOW_TYPE,
    ModelFile,
    NodePosition,
    SubworkflowDefinition,
    SubworkflowPort,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    describe_node,
    get_workflow_models_schema,
    parse_reference,
    validate_model_files,
)
from openbim_runner.workflow.subworkflow import (
    NAMESPACE_SEPARATOR,
    expand_workflow,
)

__all__ = [
    "MODEL_SLUG_PATTERN",
    "NAMESPACE_SEPARATOR",
    "PORT_NAME_PATTERN",
    "SUBWORKFLOW_INPUT_TYPE",
    "SUBWORKFLOW_META_TYPES",
    "SUBWORKFLOW_OUTPUT_TYPE",
    "SUBWORKFLOW_TYPE",
    "ModelFile",
    "NodePosition",
    "PreparedWorkflow",
    "SubworkflowDefinition",
    "SubworkflowPort",
    "WorkflowDefinition",
    "WorkflowEdge",
    "WorkflowNode",
    "add_dependency",
    "build_execution_order",
    "build_node_lookup",
    "describe_node",
    "dump_results",
    "execute_workflow",
    "execute_workflow_async",
    "expand_workflow",
    "get_workflow_models_schema",
    "load_workflow",
    "parse_reference",
    "prepare_workflow",
    "resolve_ifc_path",
    "resolve_input_bindings",
    "validate_model_files",
    "validate_workflow",
]
