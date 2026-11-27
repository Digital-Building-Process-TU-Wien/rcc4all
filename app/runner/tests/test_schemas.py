from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rcc4all_runner.main import main
from rcc4all_runner.nodes import get_registry
from rcc4all_runner.schemas import (
    UnsupportedPortTypeError,
    build_all_node_schemas,
    is_schema_assignable,
    model_field_schemas,
    validate_port_annotation,
)
from rcc4all_runner.workflow import (
    ModelFile,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    execute_workflow,
    validate_workflow,
)


def test_unsupported_annotation_names_the_node_and_field() -> None:
    with pytest.raises(UnsupportedPortTypeError) as error:
        validate_port_annotation(set[str], node="bad_node", field="thing")

    message = str(error.value)
    assert "bad_node" in message
    assert "thing" in message


@pytest.mark.parametrize(
    ("output", "input_schema", "expected"),
    [
        ({"type": "string"}, {"type": "string"}, True),
        ({"type": "integer"}, {"type": "number"}, True),
        ({"type": "number"}, {"type": "integer"}, False),
        ({"type": "string"}, {"type": "integer"}, False),
        ({}, {"type": "array", "items": {"type": "string"}}, True),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {}},
            True,
        ),
        (
            {"type": "array", "items": {"type": "integer"}},
            {"type": "array", "items": {"type": "string"}},
            False,
        ),
        (
            {"anyOf": [{"type": "integer"}, {"type": "number"}]},
            {"type": "number"},
            True,
        ),
        (
            {"type": "string"},
            {"anyOf": [{"type": "integer"}, {"type": "string"}]},
            True,
        ),
        (
            {"anyOf": [{"type": "string"}, {"type": "null"}]},
            {"type": "string"},
            True,
        ),
        ({"enum": ["volume", "area"]}, {"type": "string"}, True),
        ({"enum": ["volume"]}, {"enum": ["volume", "area"]}, True),
        ({"type": "string"}, {"enum": ["volume", "area"]}, False),
        ({"enum": [1, 2]}, {"type": "number"}, True),
        ({"const": True}, {"type": "integer"}, False),
        (
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, "value": {"type": "integer"}},
                "required": ["id", "value"],
            },
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, "value": {"type": "number"}},
                "required": ["id"],
            },
            True,
        ),
        (
            {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, "value": {"type": "number"}},
                "required": ["id", "value"],
            },
            False,
        ),
        (
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, "value": {"type": "string"}},
                "required": ["id", "value"],
            },
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, "value": {"type": "number"}},
                "required": ["id", "value"],
            },
            False,
        ),
        (
            {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [{"type": "string"}, {"type": "null"}]
                },
            },
            {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {
                        "type": "object",
                        "additionalProperties": {
                            "anyOf": [{"type": "string"}, {"type": "null"}]
                        },
                    },
                ]
            },
            True,
        ),
    ],
)
def test_json_schema_assignability_rules(
    output: dict[str, Any], input_schema: dict[str, Any], expected: bool
) -> None:
    assert is_schema_assignable(output, input_schema) is expected


def test_every_registered_node_exports_valid_port_schemas() -> None:
    node_schemas = build_all_node_schemas()
    assert set(node_schemas) == set(get_registry())

    for node_name, definition in get_registry().items():
        node_properties = node_schemas[node_name]["properties"]

        output_schemas = model_field_schemas(definition.result_model, node=node_name)
        assert output_schemas
        assert list(node_properties["result"]["properties"]) == list(output_schemas)

        if definition.takes_inputs:
            assert definition.inputs_model is not None
            input_schemas = model_field_schemas(definition.inputs_model, node=node_name)
            assert input_schemas
            assert list(node_properties["inputs"]["properties"]) == list(input_schemas)


def _workflow(source_type: str, binding: str) -> WorkflowDefinition:
    return WorkflowDefinition(
        files=[ModelFile(path="model.ifc", slug="main")],
        nodes=[
            WorkflowNode(id="provider", type="ifc_element_filter"),
            WorkflowNode(
                id="source",
                type=source_type,
                input_bindings={"express_ids": "provider.express_ids"},
            ),
            WorkflowNode(
                id="sink",
                type="concat_string",
                input_bindings={"values": binding},
            ),
        ],
        edges=[
            WorkflowEdge(source="provider", target="source"),
            WorkflowEdge(source="source", target="sink"),
        ],
    )


def test_type_mismatch_rejects_incompatible_binding() -> None:
    with pytest.raises(ValueError) as error:
        validate_workflow(_workflow("get_property", "source.mode"))

    message = str(error.value)
    assert "Type mismatch" in message
    assert "values" in message
    assert "mode" in message


def test_compatible_binding_passes() -> None:
    validate_workflow(_workflow("ifc_element_filter", "source.express_ids"))


def test_required_input_without_binding_is_rejected() -> None:
    workflow = WorkflowDefinition(
        files=[ModelFile(path="model.ifc", slug="main")],
        nodes=[
            WorkflowNode(id="source", type="ifc_element_filter"),
            WorkflowNode(id="check", type="loi_check"),
        ],
        edges=[WorkflowEdge(source="source", target="check")],
    )

    with pytest.raises(ValueError, match="has no binding"):
        validate_workflow(workflow)


def test_optional_input_without_binding_is_allowed() -> None:
    workflow = WorkflowDefinition(
        files=[ModelFile(path="model.ifc", slug="main")],
        nodes=[
            WorkflowNode(id="source", type="ifc_element_filter"),
            WorkflowNode(id="sink", type="concat_string"),
        ],
        edges=[WorkflowEdge(source="source", target="sink")],
    )

    validate_workflow(workflow)


def test_execute_workflow_rejects_unbound_required_input_before_opening_ifc(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "unbound.json"
    workflow_path.write_text(
        json.dumps(
            {
                "files": [{"path": "does-not-exist.ifc", "slug": "main", "hash": ""}],
                "nodes": [
                    {"id": "filter", "type": "ifc_element_filter"},
                    {
                        "id": "check",
                        "type": "loi_check",
                        "input_bindings": {"express_ids": "filter.express_ids"},
                    },
                    {"id": "report", "type": "bcf_output"},
                ],
                "edges": [
                    {"source": "filter", "target": "check"},
                    {"source": "check", "target": "report"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"elements.*has no binding"):
        execute_workflow(workflow_path)


def _write_workflow(path: Path, binding: str, *, source_type: str) -> None:
    path.write_text(
        json.dumps(
            {
                "files": [{"path": "model.ifc", "slug": "main", "hash": ""}],
                "nodes": [
                    {"id": "provider", "type": "ifc_element_filter"},
                    {
                        "id": "source",
                        "type": source_type,
                        "input_bindings": {"express_ids": "provider.express_ids"},
                    },
                    {
                        "id": "sink",
                        "type": "concat_string",
                        "input_bindings": {"values": binding},
                    },
                ],
                "edges": [
                    {"source": "provider", "target": "source"},
                    {"source": "source", "target": "sink"},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_validate_command_exits_non_zero_on_a_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow_path = tmp_path / "workflow.json"
    _write_workflow(workflow_path, "source.mode", source_type="get_property")

    assert main(["validate", str(workflow_path)]) == 1
    assert "Type mismatch" in capsys.readouterr().out


def test_validate_command_exits_zero_on_a_valid_file(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    _write_workflow(
        workflow_path, "source.express_ids", source_type="ifc_element_filter"
    )

    assert main(["validate", str(workflow_path)]) == 0
