from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from openbim_runner.main import main
from openbim_runner.nodes import get_registry, get_registry_schema
from openbim_runner.port_types import (
    PortArray,
    PortScalar,
    PortUnion,
    UnsupportedPortTypeError,
    annotation_to_port_type,
    is_assignable,
    model_port_types,
)
from openbim_runner.workflow import (
    ModelFile,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    execute_workflow,
    validate_workflow,
)


def _map(annotation: Any) -> Any:
    return annotation_to_port_type(annotation, node="node", field="field")


def test_scalar_annotations_map_to_scalar_types() -> None:
    assert _map(str) == PortScalar(type="string")
    assert _map(int) == PortScalar(type="integer")
    assert _map(float) == PortScalar(type="number")
    assert _map(bool) == PortScalar(type="boolean")
    assert _map(Any) == PortScalar(type="any")
    assert _map(dict[str, int]) == PortScalar(type="object")
    assert _map(ModelFile) == PortScalar(type="object")


def test_collection_annotations_map_to_arrays_and_objects() -> None:
    assert _map(list[str]) == PortArray(type="array", items=PortScalar(type="string"))
    assert _map(list[ModelFile]) == PortArray(
        type="array", items=PortScalar(type="object")
    )
    assert _map(list[Any]) == PortArray(type="array", items=PortScalar(type="any"))


def test_optional_members_are_dropped() -> None:
    assert _map(str | None) == PortScalar(type="string")
    assert _map(list[str] | None) == PortArray(
        type="array", items=PortScalar(type="string")
    )
    assert _map(list[str | None]) == PortArray(
        type="array", items=PortScalar(type="string")
    )


def test_literals_collapse_to_their_value_type() -> None:
    assert _map(Literal["a", "b"]) == PortScalar(type="string")
    assert _map(Literal[1, 2]) == PortScalar(type="integer")


def test_mixed_unions_become_union_members() -> None:
    assert _map(int | str) == PortUnion(
        type="union",
        members=[PortScalar(type="integer"), PortScalar(type="string")],
    )


def test_unsupported_annotation_names_the_node_and_field() -> None:
    with pytest.raises(UnsupportedPortTypeError) as error:
        annotation_to_port_type(set[str], node="bad_node", field="thing")

    message = str(error.value)
    assert "bad_node" in message
    assert "thing" in message
    assert "set[str]" in message


@pytest.mark.parametrize(
    ("output", "input", "expected"),
    [
        ({"type": "string"}, {"type": "string"}, True),
        ({"type": "integer"}, {"type": "number"}, True),
        ({"type": "number"}, {"type": "integer"}, False),
        ({"type": "string"}, {"type": "integer"}, False),
        ({"type": "any"}, {"type": "array", "items": {"type": "string"}}, True),
        (
            {"type": "array", "items": {"type": "string"}},
            {"type": "array", "items": {"type": "any"}},
            True,
        ),
        (
            {"type": "array", "items": {"type": "integer"}},
            {"type": "array", "items": {"type": "string"}},
            False,
        ),
        (
            {"type": "union", "members": [{"type": "integer"}, {"type": "number"}]},
            {"type": "number"},
            True,
        ),
        (
            {"type": "string"},
            {"type": "union", "members": [{"type": "integer"}, {"type": "string"}]},
            True,
        ),
    ],
)
def test_assignability_matches_the_exported_rules(
    output: dict[str, Any], input: dict[str, Any], expected: bool
) -> None:
    from pydantic import TypeAdapter

    from openbim_runner.port_types import PortType

    adapter = TypeAdapter(PortType)
    assert (
        is_assignable(adapter.validate_python(output), adapter.validate_python(input))
        is expected
    )


def test_every_registered_node_exports_typed_ports() -> None:
    schema = get_registry_schema()
    assert "x-ports" not in schema

    node_schemas = schema["properties"]
    assert set(node_schemas) == set(get_registry())

    valid_kinds = {
        "string",
        "integer",
        "number",
        "boolean",
        "object",
        "array",
        "union",
        "any",
    }

    for node_name, definition in get_registry().items():
        node_properties = node_schemas[node_name]["properties"]

        output_types = model_port_types(definition.result_model, node=node_name)
        assert output_types
        assert list(node_properties["result"]["properties"]) == list(output_types)
        for port_type in output_types.values():
            assert port_type.type in valid_kinds

        if definition.takes_inputs:
            assert definition.inputs_model is not None
            input_types = model_port_types(definition.inputs_model, node=node_name)
            assert input_types
            assert list(node_properties["inputs"]["properties"]) == list(input_types)
            for port_type in input_types.values():
                assert port_type.type in valid_kinds


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


def test_type_mismatch_names_both_ports_and_nodes() -> None:
    with pytest.raises(ValueError) as error:
        validate_workflow(_workflow("get_property", "source.mode"))

    message = str(error.value)
    assert "Type mismatch" in message
    assert "values" in message
    assert "source.mode" in str(error.value) or "mode" in message
    assert "array<string>" in message
    assert "string" in message


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


def test_bcf_output_requires_an_elements_binding() -> None:
    workflow = WorkflowDefinition(
        files=[ModelFile(path="model.ifc", slug="main")],
        nodes=[
            WorkflowNode(id="source", type="ifc_element_filter"),
            WorkflowNode(id="report", type="bcf_output"),
        ],
        edges=[WorkflowEdge(source="source", target="report")],
    )

    with pytest.raises(ValueError, match="elements"):
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


def test_validate_command_exits_zero_on_a_valid_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow_path = tmp_path / "workflow.json"
    _write_workflow(
        workflow_path, "source.express_ids", source_type="ifc_element_filter"
    )

    assert main(["validate", str(workflow_path)]) == 0
    assert "OK:" in capsys.readouterr().out
