from __future__ import annotations

import asyncio

from openbim_runner.nodes import dispatch
from openbim_runner.nodes.file_input.file_input import FileInputResult
from openbim_runner.workflow import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    build_execution_order,
)


def test_file_input_returns_configured_slug() -> None:
    result = asyncio.run(dispatch("file_input", {"slug": "arch"}))
    assert result == FileInputResult(model_slug="arch")


def test_file_input_defaults_to_main() -> None:
    result = asyncio.run(dispatch("file_input", {}))
    assert result == FileInputResult(model_slug="main")


def test_file_input_runs_before_bound_consumer() -> None:
    """file_input's model output feeds ifc_element_filter, the only model port left."""
    workflow = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="file-1", type="file_input", settings={"slug": "arch"}),
            WorkflowNode(
                id="filter-1",
                type="ifc_element_filter",
                input_bindings={"model_slug": "file-1.model_slug"},
            ),
        ],
        edges=[WorkflowEdge(source="file-1", target="filter-1")],
    )

    order = build_execution_order(workflow)

    assert order.index("file-1") < order.index("filter-1")
