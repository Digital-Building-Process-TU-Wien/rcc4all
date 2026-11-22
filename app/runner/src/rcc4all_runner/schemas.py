"""Single point of interaction with the shared JSON Schema folder on the Python side.

Owns everything related to node and workflow JSON Schemas:
- Building standalone Draft 2020-12 JSON Schemas per registered node and for
  ``WorkflowDefinition`` / ``SubworkflowPort``.
- Exporting the schema directory (``index.json``, ``workflow.schema.json``,
  ``nodes/<name>.schema.json``) and pruning stale node files.
- Loading the schema directory back into structured Python objects.
- Structural JSON Schema assignability (``is_schema_assignable``) and readable
  type labels (``describe_schema``) used by ``workflow.loader`` to validate
  concrete port bindings after subworkflow expansion.
"""

from __future__ import annotations

import copy
import json
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Union, cast, get_args, get_origin

from pydantic import BaseModel

from rcc4all_runner.nodes.base import (
    NodeDefinition,
    get_registry,
    load_node_documentation_all_locales,
)

JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
DEFAULT_SCHEMAS_DIR = Path(__file__).resolve().parents[4] / "shared" / "schemas"

_METADATA_ONLY_KEYS = frozenset(
    {"title", "description", "default", "examples", "$comment"}
)
_PRIMITIVE_TYPES = frozenset({"string", "integer", "number", "boolean", "null"})


class UnsupportedPortTypeError(ValueError):
    """Raised when a Pydantic field annotation cannot be represented as a port schema."""


@dataclass(frozen=True)
class LoadedSchemas:
    """In-memory view of an exported schema directory."""

    manifest: dict[str, Any]
    workflow: dict[str, Any]
    nodes: dict[str, dict[str, Any]]


def validate_port_annotation(annotation: Any, *, node: str, field: str) -> None:
    """Ensure a Pydantic field annotation uses only JSON-Schema-supported types.

    Fails fast during ``export-schema`` / workflow validation so unsupported
    Python annotations never silently degrade to an unconstrained wildcard.
    """
    try:
        _check_annotation(annotation, seen=set())
    except UnsupportedPortTypeError as error:
        raise UnsupportedPortTypeError(
            f"Unsupported port type '{annotation}' for node '{node}' field "
            f"'{field}': {error}"
        ) from error


def _check_annotation(annotation: Any, *, seen: set[type[BaseModel]]) -> None:
    if annotation in (Any, str, bool, int, float, type(None)):
        return

    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation in seen:
                return
            seen.add(annotation)
            annotation.model_rebuild()
            for field_info in annotation.model_fields.values():
                _check_annotation(field_info.annotation, seen=seen)
            return
        raise UnsupportedPortTypeError(
            "Only JSON scalars, lists, dicts, unions, literals and Pydantic "
            "models are supported."
        )

    args = get_args(annotation)
    if origin is list:
        item = args[0] if args else Any
        _check_annotation(item, seen=seen)
        return
    if origin is dict:
        if len(args) == 2:
            if args[0] is not str:
                raise UnsupportedPortTypeError(
                    f"Only string-keyed dicts are supported, got key type '{args[0]}'."
                )
            _check_annotation(args[1], seen=seen)
        return
    if origin is Literal:
        if not args or all(value is None for value in args):
            raise UnsupportedPortTypeError("Literal must contain at least one value.")
        for value in args:
            if value is not None and not isinstance(value, (bool, int, float, str)):
                raise UnsupportedPortTypeError(
                    f"Unsupported literal value '{value!r}'."
                )
        return
    if origin in (Union, types.UnionType):
        if not args or all(arg is type(None) for arg in args):
            raise UnsupportedPortTypeError("Union has no representable members.")
        for arg in args:
            _check_annotation(arg, seen=seen)
        return

    raise UnsupportedPortTypeError(f"Unsupported generic origin '{origin}'.")


def _inline_local_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively inline local ``#/$defs/...`` references and drop ``$defs``."""
    result = copy.deepcopy(schema)
    defs = cast(dict[str, object], result.get("$defs", {}))

    def inline(value: object, active_refs: frozenset[str]) -> object:
        if isinstance(value, dict):
            schema_node = cast(dict[str, object], value)
            ref = schema_node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                def_name = ref.removeprefix("#/$defs/")
                if def_name in defs and def_name not in active_refs:
                    resolved = inline(
                        copy.deepcopy(defs[def_name]), active_refs | {def_name}
                    )
                    if isinstance(resolved, dict):
                        siblings = {
                            key: inline(item, active_refs)
                            for key, item in schema_node.items()
                            if key not in {"$ref", "$defs"}
                        }
                        return {**cast(dict[str, object], resolved), **siblings}
                    return resolved

            return {
                key: inline(item, active_refs)
                for key, item in schema_node.items()
                if key != "$defs"
            }

        if isinstance(value, list):
            return [inline(item, active_refs) for item in cast(list[object], value)]

        return value

    return cast(dict[str, Any], inline(result, frozenset()))


def model_field_schemas(
    model: type[BaseModel], *, node: str
) -> dict[str, dict[str, Any]]:
    """Return inlined per-field JSON Schemas for ``model`` after validating annotations."""
    model.model_rebuild()
    for field_name, field_info in model.model_fields.items():
        validate_port_annotation(field_info.annotation, node=node, field=field_name)

    inlined = _inline_local_refs(model.model_json_schema())
    return cast(dict[str, dict[str, Any]], inlined.get("properties", {}))


def build_node_schema(name: str, definition: NodeDefinition) -> dict[str, Any]:
    """Build a standalone Draft 2020-12 JSON Schema for one registered node."""
    all_locales = load_node_documentation_all_locales(definition)
    required_fields = ["result"]
    node_properties: dict[str, Any] = {}

    if definition.takes_settings:
        if definition.settings_model is None:
            raise ValueError(
                f"Node '{name}' has takes_settings=True but no settings_model"
            )
        definition.settings_model.model_rebuild()
        node_properties["settings"] = _inline_local_refs(
            definition.settings_model.model_json_schema()
        )
        required_fields.append("settings")

    for field_name, field_info in definition.result_model.model_fields.items():
        validate_port_annotation(field_info.annotation, node=name, field=field_name)
    definition.result_model.model_rebuild()
    node_properties["result"] = _inline_local_refs(
        definition.result_model.model_json_schema()
    )

    if definition.takes_inputs and definition.inputs_model is not None:
        for field_name, field_info in definition.inputs_model.model_fields.items():
            validate_port_annotation(field_info.annotation, node=name, field=field_name)
        definition.inputs_model.model_rebuild()
        node_properties["inputs"] = _inline_local_refs(
            definition.inputs_model.model_json_schema()
        )
        required_fields.append("inputs")

    en_docs = all_locales.get("en")
    title = en_docs.title if en_docs else ""
    description = en_docs.description if en_docs else ""
    categories = en_docs.categories if en_docs else []
    markdown_description = en_docs.body if en_docs else ""

    locales_data = {
        locale: {
            "title": docs.title,
            "description": docs.description,
            "categories": docs.categories,
            "markdownDescription": docs.body,
        }
        for locale, docs in sorted(all_locales.items())
    }

    return {
        "$schema": JSON_SCHEMA_DRAFT,
        "$id": f"nodes/{name}.schema.json",
        "type": "object",
        "title": title,
        "description": description,
        "categories": categories,
        "markdownDescription": markdown_description,
        "locales": locales_data,
        "properties": node_properties,
        "required": required_fields,
        "additionalProperties": False,
    }


def build_all_node_schemas() -> dict[str, dict[str, Any]]:
    """Build standalone JSON Schemas for all registered nodes, sorted by node name."""
    return {
        name: build_node_schema(name, definition)
        for name, definition in sorted(get_registry().items())
    }


def build_workflow_schema() -> dict[str, Any]:
    """Build the standalone Draft 2020-12 JSON Schema for workflow files.

    ``SubworkflowPort`` is not reachable from ``WorkflowDefinition`` because
    meta-node ports live inside free-form ``settings``, so it is registered
    explicitly under ``$defs``.
    """
    from rcc4all_runner.workflow.model import SubworkflowPort, WorkflowDefinition

    schema = WorkflowDefinition.model_json_schema()
    defs: dict[str, Any] = schema.setdefault("$defs", {})

    port_schema = SubworkflowPort.model_json_schema()
    defs.update(port_schema.pop("$defs", {}))
    defs["SubworkflowPort"] = port_schema

    return {
        "$schema": JSON_SCHEMA_DRAFT,
        "$id": "workflow.schema.json",
        **schema,
    }


def build_manifest(node_names: list[str]) -> dict[str, Any]:
    """Build ``index.json`` listing the workflow schema and every per-node schema."""
    return {
        "workflow": "workflow.schema.json",
        "nodes": {name: f"nodes/{name}.schema.json" for name in sorted(node_names)},
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    text = f"{json.dumps(payload, indent=2)}\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def export_schemas(output_dir: Path = DEFAULT_SCHEMAS_DIR) -> list[Path]:
    """Export all per-node schemas, ``workflow.schema.json``, and ``index.json``.

    Removes stale ``nodes/*.schema.json`` files for nodes no longer registered.
    """
    target_dir = output_dir.resolve()
    nodes_dir = target_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    node_schemas = build_all_node_schemas()
    expected_node_files: set[str] = set()
    written: list[Path] = []

    for node_name, node_schema in node_schemas.items():
        filename = f"{node_name}.schema.json"
        expected_node_files.add(filename)
        node_path = nodes_dir / filename
        _write_json(node_path, node_schema)
        written.append(node_path)

    for existing in nodes_dir.glob("*.schema.json"):
        if existing.name not in expected_node_files:
            existing.unlink()

    workflow_path = target_dir / "workflow.schema.json"
    _write_json(workflow_path, build_workflow_schema())
    written.append(workflow_path)

    manifest_path = target_dir / "index.json"
    _write_json(manifest_path, build_manifest(list(node_schemas.keys())))
    written.append(manifest_path)

    return written


def load_schemas(schema_dir: Path = DEFAULT_SCHEMAS_DIR) -> LoadedSchemas:
    """Read an exported schema directory back into memory."""
    root = schema_dir.resolve()
    manifest = cast(
        dict[str, Any], json.loads((root / "index.json").read_text(encoding="utf-8"))
    )
    workflow = cast(
        dict[str, Any],
        json.loads((root / manifest["workflow"]).read_text(encoding="utf-8")),
    )
    nodes: dict[str, dict[str, Any]] = {}
    for node_name, rel_path in sorted(manifest["nodes"].items()):
        nodes[node_name] = cast(
            dict[str, Any], json.loads((root / rel_path).read_text(encoding="utf-8"))
        )
    return LoadedSchemas(manifest=manifest, workflow=workflow, nodes=nodes)


# ---------------------------------------------------------------------------
# Direct JSON Schema structural assignability & formatting
# Keep in sync with `app/web/app/schemas/index.ts`.
# ---------------------------------------------------------------------------


def _is_unconstrained(schema: dict[str, Any]) -> bool:
    """True when a schema carries no type/structural constraints (explicit ``Any``)."""
    return all(key in _METADATA_ONLY_KEYS for key in schema)


def _as_schema_list(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[Any], value)
    return [cast(dict[str, Any], item) for item in items if isinstance(item, dict)]


def _unwrap_all_of(schema: dict[str, Any]) -> dict[str, Any]:
    all_of = _as_schema_list(schema.get("allOf"))
    if all_of is not None and len(all_of) == 1:
        return all_of[0]
    return schema


def _normalize_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip ``null`` branches from ``anyOf``/``oneOf`` unions for compatibility checks."""
    unwrapped = _unwrap_all_of(schema)
    branches = _as_schema_list(unwrapped.get("anyOf") or unwrapped.get("oneOf"))
    if branches is not None:
        non_null = [branch for branch in branches if branch.get("type") != "null"]
        if not non_null:
            return {"type": "null"}
        if len(non_null) == 1:
            return _normalize_nullable(non_null[0])
        return {"anyOf": non_null}

    schema_type = unwrapped.get("type")
    if isinstance(schema_type, list):
        raw_types = cast(list[Any], schema_type)
        non_null_types = [t for t in raw_types if isinstance(t, str) and t != "null"]
        if not non_null_types:
            return {"type": "null"}
        if len(non_null_types) == 1:
            return {**unwrapped, "type": non_null_types[0]}
        return {"anyOf": [{**unwrapped, "type": t} for t in non_null_types]}

    return unwrapped


def _extract_literals(schema: dict[str, Any]) -> list[Any] | None:
    if "const" in schema:
        value = schema["const"]
        return [] if value is None else [value]
    if isinstance(schema.get("enum"), list):
        return [v for v in cast(list[Any], schema["enum"]) if v is not None]
    return None


def _literal_key(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, int):
        return ("number", float(value))
    if isinstance(value, float):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    return ("other", repr(value))


def _literal_primitive_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object"


def _primitive_assignable(output_type: str, input_type: str) -> bool:
    if output_type == input_type:
        return True
    return output_type == "integer" and input_type == "number"


def is_schema_assignable(raw_output: dict[str, Any], raw_input: dict[str, Any]) -> bool:
    """Whether a value matching ``raw_output`` JSON Schema may feed ``raw_input``."""
    output = _normalize_nullable(raw_output)
    input_schema = _normalize_nullable(raw_input)

    if _is_unconstrained(output) or _is_unconstrained(input_schema):
        return True

    output_branches = _as_schema_list(output.get("anyOf") or output.get("oneOf"))
    if output_branches is not None:
        return bool(output_branches) and all(
            is_schema_assignable(branch, input_schema) for branch in output_branches
        )

    input_branches = _as_schema_list(
        input_schema.get("anyOf") or input_schema.get("oneOf")
    )
    if input_branches is not None:
        return any(is_schema_assignable(output, branch) for branch in input_branches)

    output_literals = _extract_literals(output)
    input_literals = _extract_literals(input_schema)
    if output_literals is not None:
        if input_literals is not None:
            allowed = {_literal_key(v) for v in input_literals}
            return all(_literal_key(v) in allowed for v in output_literals)
        input_type = input_schema.get("type")
        if isinstance(input_type, str) and input_type in _PRIMITIVE_TYPES:
            return all(
                _primitive_assignable(_literal_primitive_type(v), input_type)
                for v in output_literals
            )
        return False

    if input_literals is not None:
        # A wide primitive (e.g. `string`) cannot satisfy a narrow literal/enum.
        return False

    output_type = output.get("type")
    input_type = input_schema.get("type")

    if (
        isinstance(output_type, str)
        and isinstance(input_type, str)
        and output_type in _PRIMITIVE_TYPES
        and input_type in _PRIMITIVE_TYPES
    ):
        return _primitive_assignable(output_type, input_type)

    if output_type == "array" and input_type == "array":
        output_items = cast(dict[str, Any], output.get("items") or {})
        input_items = cast(dict[str, Any], input_schema.get("items") or {})
        return is_schema_assignable(output_items, input_items)

    if output_type == "object" and input_type == "object":
        return _is_object_assignable(output, input_schema)

    return False


def _is_object_assignable(output: dict[str, Any], input_schema: dict[str, Any]) -> bool:
    input_props = input_schema.get("properties")
    if isinstance(input_props, dict):
        output_props = output.get("properties")
        if not isinstance(output_props, dict):
            return False

        output_props_typed = cast(dict[str, dict[str, Any]], output_props)
        input_props_typed = cast(dict[str, dict[str, Any]], input_props)
        output_required = set(cast(list[str], output.get("required", [])))
        input_required = set(cast(list[str], input_schema.get("required", [])))

        for field_name in input_required:
            if (
                field_name not in output_props_typed
                or field_name not in output_required
            ):
                return False

        for field_name, input_prop in input_props_typed.items():
            output_prop = output_props_typed.get(field_name)
            if output_prop is None:
                # Optional input field absent from output is allowed.
                continue
            if not is_schema_assignable(output_prop, input_prop):
                return False

        return True

    input_additional = input_schema.get("additionalProperties")
    if isinstance(input_additional, dict):
        input_val = cast(dict[str, Any], input_additional)
        output_additional = output.get("additionalProperties")
        if isinstance(output_additional, dict):
            return is_schema_assignable(
                cast(dict[str, Any], output_additional), input_val
            )
        output_props = output.get("properties")
        if output_additional is False and isinstance(output_props, dict):
            return all(
                is_schema_assignable(prop_schema, input_val)
                for prop_schema in cast(
                    dict[str, dict[str, Any]], output_props
                ).values()
            )
        return is_schema_assignable({}, input_val)

    # Unconstrained `object` (e.g. `dict[str, Any]`) accepts any object.
    return True


def _needs_array_parens(schema: dict[str, Any]) -> bool:
    unwrapped = _unwrap_all_of(schema)
    branches = _as_schema_list(unwrapped.get("anyOf") or unwrapped.get("oneOf"))
    if branches is not None and len(branches) > 1:
        return True
    enum_values = unwrapped.get("enum")
    return isinstance(enum_values, list) and len(cast(list[Any], enum_values)) > 1


def describe_schema(schema: dict[str, Any]) -> str:
    """Human-readable label for a JSON Schema, e.g. ``HarmonizedElement[]``."""
    unwrapped = _unwrap_all_of(schema)
    if _is_unconstrained(unwrapped):
        return "any"

    branches = _as_schema_list(unwrapped.get("anyOf") or unwrapped.get("oneOf"))
    if branches is not None:
        return " | ".join(describe_schema(branch) for branch in branches)

    if "const" in unwrapped:
        return json.dumps(unwrapped["const"])

    enum_values = unwrapped.get("enum")
    if isinstance(enum_values, list):
        return " | ".join(json.dumps(v) for v in cast(list[Any], enum_values))

    schema_type = unwrapped.get("type")
    if isinstance(schema_type, list):
        return " | ".join(str(t) for t in cast(list[Any], schema_type))

    if schema_type == "array":
        items = cast(dict[str, Any], unwrapped.get("items") or {})
        inner = describe_schema(items)
        return f"({inner})[]" if _needs_array_parens(items) else f"{inner}[]"

    if schema_type == "object":
        if isinstance(unwrapped.get("properties"), dict):
            title = unwrapped.get("title")
            return str(title) if isinstance(title, str) and title else "object"
        additional = unwrapped.get("additionalProperties")
        if isinstance(additional, dict):
            return (
                f"Record<string, {describe_schema(cast(dict[str, Any], additional))}>"
            )
        return "object"

    if isinstance(schema_type, str):
        return schema_type

    return "any"
