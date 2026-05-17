from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, getfile, isawaitable, signature
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast, get_type_hints

from pydantic import BaseModel, ConfigDict
if TYPE_CHECKING:
    import ifcopenshell


class NodeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionContext:
    def __init__(self, ifc_model: ifcopenshell.file, node_outputs: dict[str, NodeModel]) -> None:
        self.ifc_model = ifc_model
        self.node_outputs = node_outputs


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
        raise ValueError(f"{readme_path} must contain a closing frontmatter delimiter.") from error

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
    markdown_body = body.strip()

    if not title:
        raise ValueError(f"{readme_path} must define a non-empty 'title' frontmatter field.")
    if not description:
        raise ValueError(f"{readme_path} must define a non-empty 'description' frontmatter field.")
    if not markdown_body:
        raise ValueError(f"{readme_path} must include markdown body content after the frontmatter.")

    return NodeDocumentation(title=title, description=description, body=markdown_body)


def load_node_documentation(definition: NodeDefinition) -> NodeDocumentation:
    handler_path = Path(getfile(definition.handler)).resolve()
    readme_path = handler_path.parent / "README.md"
    if not readme_path.exists():
        raise ValueError(f"Node '{definition.name}' is missing documentation file {readme_path}.")

    return parse_node_documentation(readme_path)


def node(name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        hints = get_type_hints(func)
        sig = signature(func)
        parameters = list(sig.parameters.values())

        if not parameters:
            raise TypeError(f"{func.__name__} must define at least a 'settings' or 'inputs' parameter")
        
        takes_settings = False
        takes_inputs = False
        takes_context = False
        
        if parameters[0].name == "settings":
            takes_settings = True
            if len(parameters) > 1:
                second_param = parameters[1].name
                if second_param == "inputs":
                    takes_inputs = True
                elif second_param == "context":
                    takes_context = True
                else:
                    raise TypeError(f"{func.__name__} may only use 'inputs' or 'context' after 'settings'")
        elif parameters[0].name == "inputs":
            takes_inputs = True
            if len(parameters) > 1 and parameters[1].name == "context":
                takes_context = True
        else:
            raise TypeError(f"{func.__name__} must start with 'settings' or 'inputs' parameter")
        
        if len(parameters) > 3:
            raise TypeError(f"{func.__name__} may only define 'settings', optional 'inputs', and optional 'context' parameters")
        if any(parameter.kind not in {Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY} for parameter in parameters):
            raise TypeError(f"{func.__name__} must use standard named parameters")

        if len(parameters) == 2 and takes_settings and takes_context:
            pass
        elif len(parameters) == 2 and takes_inputs and not takes_context:
            pass
        elif len(parameters) == 3:
            if not (takes_settings or takes_inputs) or not takes_context:
                raise TypeError(f"{func.__name__} must use 'context' as third parameter")
            if takes_settings and not takes_inputs:
                raise TypeError(f"{func.__name__} cannot have 'context' as second parameter after 'settings', use 'inputs' first")

        settings_model = hints.get("settings") if takes_settings else None
        inputs_model = hints.get("inputs") if takes_inputs else None
        result_model = hints.get("return")
        
        if takes_settings and (not isinstance(settings_model, type) or not issubclass(settings_model, BaseModel)):
            raise TypeError(f"{func.__name__}.settings must be a BaseModel subclass")
        if takes_inputs and (not isinstance(inputs_model, type) or not issubclass(inputs_model, BaseModel)):
            raise TypeError(f"{func.__name__}.inputs must be a BaseModel subclass")
        if not isinstance(result_model, type) or not issubclass(result_model, BaseModel):
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
        setattr(func, "meta", definition)
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

    if definition.takes_settings and definition.takes_inputs and definition.takes_context:
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
    result.pop("title", None)
    
    if "properties" in result:
        result["properties"] = {
            key: _remove_titles_from_schema(value) if isinstance(value, dict) else value
            for key, value in result["properties"].items()
        }
    
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _remove_titles_from_schema(result["items"])
    
    if "anyOf" in result:
        result["anyOf"] = [
            _remove_titles_from_schema(item) if isinstance(item, dict) else item
            for item in result["anyOf"]
        ]
    
    return result


def get_registry_schema() -> dict[str, Any]:
    nodes_schemas: dict[str, Any] = {}
    for name, definition in REGISTRY.items():
        documentation = load_node_documentation(definition)
        required_fields = ["result"]
        
        node_properties: dict[str, Any] = {}
        
        if definition.takes_settings:
            if definition.settings_model is None:
                raise ValueError(f"Node '{name}' has takes_settings=True but no settings_model")
            settings_schema = _remove_titles_from_schema(definition.settings_model.model_json_schema())
            node_properties["settings"] = settings_schema
            required_fields.append("settings")
        
        result_schema = _remove_titles_from_schema(definition.result_model.model_json_schema())
        node_properties["result"] = result_schema

        if definition.takes_inputs and definition.inputs_model:
            inputs_schema = _remove_titles_from_schema(definition.inputs_model.model_json_schema())
            node_properties["inputs"] = inputs_schema
            required_fields.append("inputs")

        nodes_schemas[name] = {
            "type": "object",
            "title": documentation.title,
            "description": documentation.description,
            "markdownDescription": documentation.body,
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