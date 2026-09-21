from __future__ import annotations

import asyncio
from typing import Any, cast

from openbim_runner.nodes import dispatch
from openbim_runner.nodes.base import ExecutionContext, NodeModel
from openbim_runner.nodes.file_input.file_input import FileInputResult
from openbim_runner.nodes.get_name.get_name import (
    GetNameInputs,
    GetNameResult,
    GetNameSettings,
    get_name,
)
from openbim_runner.workflow import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    build_execution_order,
    resolve_input_bindings,
)


def test_file_input_returns_configured_slug() -> None:
    result = asyncio.run(dispatch("file_input", {"slug": "arch"}))
    assert result == FileInputResult(model_slug="arch")


def test_file_input_defaults_to_main() -> None:
    result = asyncio.run(dispatch("file_input", {}))
    assert result == FileInputResult(model_slug="main")


def test_model_input_resolves_from_file_input_output() -> None:
    node = WorkflowNode(
        id="name-1",
        type="get_name",
        input_bindings={"model_slug": "file-1.model_slug"},
    )
    outputs = cast(
        "dict[str, NodeModel]",
        {"file-1": FileInputResult(model_slug="arch")},
    )

    payload = resolve_input_bindings(node, outputs)

    assert payload == {"model_slug": "arch"}


def test_file_input_runs_before_bound_consumer() -> None:
    workflow = WorkflowDefinition(
        nodes=[
            WorkflowNode(id="file-1", type="file_input", settings={"slug": "arch"}),
            WorkflowNode(
                id="name-1",
                type="get_name",
                input_bindings={"model_slug": "file-1.model_slug"},
            ),
        ],
        edges=[WorkflowEdge(source="file-1", target="name-1")],
    )

    order = build_execution_order(workflow)

    assert order.index("file-1") < order.index("name-1")


def test_get_name_result_reports_resolved_model_slug() -> None:
    class _FakeEntity:
        Name = "Wall"

    class _FakeModel:
        def by_id(self, express_id: int) -> _FakeEntity:
            return _FakeEntity()

    context = ExecutionContext(
        models={"main": cast(Any, _FakeModel()), "arch": cast(Any, _FakeModel())},
        node_outputs={},
    )

    result = asyncio.run(
        get_name(
            GetNameSettings(fail_on_missing=False),
            GetNameInputs(express_ids=[1], model_slug="arch"),
            context,
        )
    )

    assert result == GetNameResult(object_names=["Wall"], model_slug="arch")
