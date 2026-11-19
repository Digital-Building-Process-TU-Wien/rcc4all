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
)
from openbim_runner.workflow import (
    ModelFile,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
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
    ports = schema["x-ports"]

    assert set(ports) == set(get_registry())

    for node_name, definition in get_registry().items():
        assert ports[node_name]["outputs"]
        for port in ports[node_name]["outputs"] + ports[node_name]["inputs"]:
            assert port["type"]["type"] in {
                "string",
                "integer",
                "number",
                "boolean",
                "object",
                "array",
                "union",
                "any",
            }

        if definition.takes_inputs:
            assert ports[node_name]["inputs"]


def _workflow(source_type: str, binding: str) -> WorkflowDefinition:
    return WorkflowDefinition(
        files=[ModelFile(path="model.ifc", slug="main")],
        nodes=[
            WorkflowNode(id="source", type=source_type),
            WorkflowNode(
                id="sink",
                type="concat_string",
                input_bindings={"values": binding},
            ),
        ],
        edges=[WorkflowEdge(source="source", target="sink")],
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


def _write_workflow(path: Path, binding: str, *, source_type: str) -> None:
    path.write_text(
        json.dumps(
            {
                "files": [{"path": "model.ifc", "slug": "main", "hash": ""}],
                "nodes": [
                    {"id": "source", "type": source_type},
                    {
                        "id": "sink",
                        "type": "concat_string",
                        "input_bindings": {"values": binding},
                    },
                ],
                "edges": [{"source": "source", "target": "sink"}],
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
