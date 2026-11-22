"""Public wrapper for workflow loading, validation, and execution.

The implementation lives in focused modules. This module re-exports only the
names imported by ``main.py`` and the test suite so the package split stays
invisible to callers.

Module map:

- ``model``: the workflow document, slug rules, references, JSON schema
- ``loader``: read the JSON, validate it, flatten and prepare it to run
- ``subworkflow``: inline embedded subworkflows into a flat graph
- ``graph``: node lookup, edge checks, topological execution order
- ``bindings``: declared input references resolved to runtime values
- ``executor``: IFC loading, geometry cache, dispatch, results
"""

from __future__ import annotations

from rcc4all_runner.workflow.executor import (
    dump_results,
    execute_workflow,
    execute_workflow_async,
)
from rcc4all_runner.workflow.graph import build_execution_order
from rcc4all_runner.workflow.loader import load_workflow, validate_workflow
from rcc4all_runner.workflow.model import (
    ModelFile,
    NodePosition,
    SubworkflowDefinition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    validate_model_files,
)
from rcc4all_runner.workflow.subworkflow import expand_workflow

__all__ = [
    "ModelFile",
    "NodePosition",
    "SubworkflowDefinition",
    "WorkflowDefinition",
    "WorkflowEdge",
    "WorkflowNode",
    "build_execution_order",
    "dump_results",
    "execute_workflow",
    "execute_workflow_async",
    "expand_workflow",
    "load_workflow",
    "validate_model_files",
    "validate_workflow",
]
