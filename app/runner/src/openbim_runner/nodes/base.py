from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from inspect import getfile, isawaitable, signature
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_type_hints

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import ifcopenshell
    import trimesh


class NodeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class AutoBind:
    """Opt-in marker for a node input field.

    When an input is marked with this and is left unbound in a workflow, the
    runner auto-resolves it at execution time to the single, directly-upstream
    node (via workflow edges) whose result exposes a field of a compatible
    type. Explicit ``input_bindings`` always take precedence. The marker is
    intended as ``pydantic`` field metadata and never appears in the exported
    JSON schema.
    """


class ExecutionContext:
    def __init__(
        self,
        ifc_model: ifcopenshell.file,
        node_outputs: dict[str, NodeModel],
        workflow_dir: Path | None = None,
        geometry_cache: dict[str, trimesh.Trimesh] | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.ifc_model = ifc_model
        self.node_outputs = node_outputs
        self.workflow_dir = workflow_dir
        self.geometry_cache: dict[str, trimesh.Trimesh] | None = (
            {} if geometry_cache is None else geometry_cache
        )
        self.output_dir = output_dir


@dataclass(frozen=True)
class NodeDefinition:
    name: str
    handler: Callable[..., Any]
    settings_model: type[NodeModel] | None
    inputs_model: type[NodeModel] | None
    result_model: type[NodeModel]
    takes_inputs: bool
    takes_context: bool
    takes_settings: bool


@dataclass(frozen=True)
class NodeDocumentation:
    title: str
    description: str
    categories: list[str]
    body: str


REGISTRY: dict[str, NodeDefinition] = {}


def parse_frontmatter_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    return value


def parse_node_documentation(readme_path: Path) -> NodeDocumentation:
    content = readme_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not content.startswith("---\n"):
        raise ValueError(f"{readme_path} must start with YAML-style frontmatter.")

    try:
        frontmatter_block, body = content[4:].split("\n---\n", maxsplit=1)
    except ValueError as error:
        raise ValueError(
            f"{readme_path} must contain a closing frontmatter delimiter."
        ) from error

    metadata: dict[str, str] = {}
    for raw_line in frontmatter_block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line '{raw_line}' in {readme_path}.")

        key, raw_value = line.split(":", maxsplit=1)
        metadata[key.strip()] = parse_frontmatter_value(raw_value)

    title = metadata.get("title", "").strip()
    description = metadata.get("description", "").strip()
    categories = [
        cat.strip() for cat in metadata.get("categories", "").split(",") if cat.strip()
    ]
    markdown_body = body.strip()

    if not title:
        raise ValueError(
            f"{readme_path} must define a non-empty 'title' frontmatter field."
        )
    if not description:
        raise ValueError(
            f"{readme_path} must define a non-empty 'description' frontmatter field."
        )
    if not markdown_body:
        raise ValueError(
            f"{readme_path} must include markdown body content after the frontmatter."
        )

    return NodeDocumentation(
        title=title, description=description, categories=categories, body=markdown_body
    )


def load_node_documentation_all_locales(
    definition: NodeDefinition,
) -> dict[str, NodeDocumentation]:
    """Load documentation for all available locales.

    Scans for README.{locale}.md files in the node's directory.
    Prints a warning if English or German translations are missing.
    """
    handler_path = Path(getfile(definition.handler)).resolve()
    node_dir = handler_path.parent

    import re

    readme_pattern = re.compile(r"^README\.([a-z]{2})\.md$")

    all_locales: dict[str, NodeDocumentation] = {}

    for readme_file in node_dir.iterdir():
        match = readme_pattern.match(readme_file.name)
        if match:
            locale = match.group(1)
            all_locales[locale] = parse_node_documentation(readme_file)

    required_locales = {"en", "de"}
    missing_locales = required_locales - set(all_locales.keys())

    if missing_locales:
        print(
            f"⚠️  WARNING: Node '{definition.name}' missing translations: {missing_locales}"
        )

    return all_locales


def node(
    name: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        hints = get_type_hints(func)
        param_names = set(signature(func).parameters)

        takes_settings = "settings" in param_names
        takes_inputs = "inputs" in param_names
        takes_context = "context" in param_names

        settings_model = hints.get("settings") if takes_settings else None
        inputs_model = hints.get("inputs") if takes_inputs else None
        result_model = hints.get("return")

        if takes_settings and (
            not isinstance(settings_model, type)
            or not issubclass(settings_model, BaseModel)
        ):
            raise TypeError(f"{func.__name__}.settings must be a BaseModel subclass")
        if takes_inputs and (
            not isinstance(inputs_model, type)
            or not issubclass(inputs_model, BaseModel)
        ):
            raise TypeError(f"{func.__name__}.inputs must be a BaseModel subclass")
        if not isinstance(result_model, type) or not issubclass(
            result_model, BaseModel
        ):
            raise TypeError(f"{func.__name__}.return must be a BaseModel subclass")

        key = name or func.__name__
        definition = NodeDefinition(
            name=key,
            handler=func,
            settings_model=cast(type[NodeModel] | None, settings_model),
            inputs_model=cast(type[NodeModel] | None, inputs_model),
            result_model=cast(type[NodeModel], result_model),
            takes_inputs=takes_inputs,
            takes_context=takes_context,
            takes_settings=takes_settings,
        )
        setattr(func, "meta", definition)  # noqa: B010 - dot-assign blocked by pyright strict (FunctionType has no "meta")
        REGISTRY[key] = definition
        return func

    return decorator


def get_registry() -> dict[str, NodeDefinition]:
    return REGISTRY.copy()


async def dispatch(
    name: str,
    settings_payload: dict[str, Any] | None = None,
    *,
    inputs_payload: dict[str, Any] | None = None,
    context: ExecutionContext | None = None,
) -> NodeModel:
    definition = REGISTRY.get(name)
    if definition is None:
        raise ValueError(f"Unknown node type '{name}'.")

    settings: NodeModel | None = None
    if definition.takes_settings:
        if definition.settings_model is None:
            raise ValueError(f"Node '{name}' is missing a settings model.")
        settings = definition.settings_model.model_validate(settings_payload or {})
    elif settings_payload:
        raise ValueError(f"Node '{name}' does not accept workflow settings.")

    inputs: NodeModel | None = None
    if definition.takes_inputs:
        if definition.inputs_model is None:
            raise ValueError(f"Node '{name}' is missing an inputs model.")
        inputs = definition.inputs_model.model_validate(inputs_payload or {})
    elif inputs_payload:
        raise ValueError(f"Node '{name}' does not accept workflow inputs.")

    if (
        definition.takes_settings
        and definition.takes_inputs
        and definition.takes_context
    ):
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(settings, inputs, context)
    elif definition.takes_settings and definition.takes_inputs:
        result = definition.handler(settings, inputs)
    elif definition.takes_inputs and definition.takes_context:
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(inputs, context)
    elif definition.takes_inputs:
        result = definition.handler(inputs)
    elif definition.takes_settings and definition.takes_context:
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(settings, context)
    elif definition.takes_settings:
        result = definition.handler(settings)
    elif definition.takes_context:
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(context)
    else:
        raise ValueError(f"Node '{name}' must define at least one parameter")

    resolved_result = await result if isawaitable(result) else result
    return definition.result_model.model_validate(resolved_result)


def _remove_titles_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove title fields from a JSON schema to prevent named type generation."""
    import copy

    result = copy.deepcopy(schema)
    defs = cast(dict[str, object], result.get("$defs", {}))

    def inline_local_refs(value: object) -> object:
        if isinstance(value, dict):
            schema_node = cast(dict[str, object], value)
            ref = schema_node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                def_name = ref.removeprefix("#/$defs/")
                if def_name in defs:
                    return inline_local_refs(copy.deepcopy(defs[def_name]))

            return {
                key: inline_local_refs(item)
                for key, item in schema_node.items()
                if key != "$defs"
            }

        if isinstance(value, list):
            return [inline_local_refs(item) for item in cast(list[object], value)]

        return value

    result = cast(dict[str, Any], inline_local_refs(result))
    result.pop("title", None)

    if "properties" in result:
        properties = cast(dict[str, object], result["properties"])
        result["properties"] = {
            key: _remove_titles_from_schema(cast(dict[str, Any], value))
            if isinstance(value, dict)
            else value
            for key, value in properties.items()
        }

    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _remove_titles_from_schema(
            cast(dict[str, object], result["items"])
        )

    if "additionalProperties" in result and isinstance(
        result["additionalProperties"], dict
    ):
        result["additionalProperties"] = _remove_titles_from_schema(
            cast(dict[str, object], result["additionalProperties"])
        )

    if "anyOf" in result:
        result["anyOf"] = [
            _remove_titles_from_schema(cast(dict[str, Any], item))
            if isinstance(item, dict)
            else item
            for item in cast(list[object], result["anyOf"])
        ]

    return result


def get_registry_schema() -> dict[str, Any]:
    nodes_schemas: dict[str, Any] = {}
    # Sorted so the exported schema (and the generated types derived from it)
    # are deterministic regardless of node import/registration order.
    for name, definition in sorted(REGISTRY.items()):
        all_locales = load_node_documentation_all_locales(definition)
        required_fields = ["result"]

        node_properties: dict[str, Any] = {}

        if definition.takes_settings:
            if definition.settings_model is None:
                raise ValueError(
                    f"Node '{name}' has takes_settings=True but no settings_model"
                )
            settings_schema = _remove_titles_from_schema(
                definition.settings_model.model_json_schema()
            )
            node_properties["settings"] = settings_schema
            required_fields.append("settings")

        result_schema = _remove_titles_from_schema(
            definition.result_model.model_json_schema()
        )
        node_properties["result"] = result_schema

        if definition.takes_inputs and definition.inputs_model:
            inputs_schema = _remove_titles_from_schema(
                definition.inputs_model.model_json_schema()
            )
            node_properties["inputs"] = inputs_schema
            required_fields.append("inputs")

        en_docs = all_locales.get("en")
        title = en_docs.title if en_docs else ""
        description = en_docs.description if en_docs else ""
        categories = en_docs.categories if en_docs else []
        markdown_description = en_docs.body if en_docs else ""

        # Sorted by locale so the exported schema is deterministic regardless of
        # the (filesystem-dependent) order in which locale readmes are discovered.
        locales_data = {
            locale: {
                "title": docs.title,
                "description": docs.description,
                "categories": docs.categories,
                "markdownDescription": docs.body,
            }
            for locale, docs in sorted(all_locales.items())
        }

        nodes_schemas[name] = {
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

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Node Registry Schema",
        "type": "object",
        "additionalProperties": False,
        "properties": nodes_schemas,
    }
