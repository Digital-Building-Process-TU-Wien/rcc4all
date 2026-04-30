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
    settings_model: type[NodeModel]
    inputs_model: type[NodeModel] | None
    result_model: type[NodeModel]
    takes_inputs: bool
    takes_context: bool


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
            raise TypeError(f"{func.__name__} must define a 'settings' parameter")
        if parameters[0].name != "settings":
            raise TypeError(f"{func.__name__} must have 'settings' as its first parameter")
        if len(parameters) > 3:
            raise TypeError(f"{func.__name__} may only define 'settings', optional 'inputs', and optional 'context' parameters")
        if any(parameter.kind not in {Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY} for parameter in parameters):
            raise TypeError(f"{func.__name__} must use standard named parameters")

        takes_inputs = False
        takes_context = False
        if len(parameters) >= 2:
            second_parameter_name = parameters[1].name
            if second_parameter_name == "inputs":
                takes_inputs = True
            elif second_parameter_name == "context":
                takes_context = True
            else:
                raise TypeError(f"{func.__name__} may only use 'inputs' or 'context' as its optional second parameter")

        if len(parameters) == 3:
            if not takes_inputs or parameters[2].name != "context":
                raise TypeError(f"{func.__name__} must use 'context' as its third parameter when 'inputs' is present")
            takes_context = True

        settings_model = hints.get("settings")
        inputs_model = hints.get("inputs") if takes_inputs else None
        result_model = hints.get("return")
        if not isinstance(settings_model, type) or not issubclass(settings_model, BaseModel):
            raise TypeError(f"{func.__name__}.settings must be a BaseModel subclass")
        if takes_inputs and (not isinstance(inputs_model, type) or not issubclass(inputs_model, BaseModel)):
            raise TypeError(f"{func.__name__}.inputs must be a BaseModel subclass")
        if not isinstance(result_model, type) or not issubclass(result_model, BaseModel):
            raise TypeError(f"{func.__name__}.return must be a BaseModel subclass")

        key = name or func.__name__
        definition = NodeDefinition(
            name=key,
            handler=func,
            settings_model=cast(type[NodeModel], settings_model),
            inputs_model=cast(type[NodeModel] | None, inputs_model),
            result_model=cast(type[NodeModel], result_model),
            takes_inputs=takes_inputs,
            takes_context=takes_context,
        )
        setattr(func, "meta", definition)
        REGISTRY[key] = definition
        return func

    return decorator


def get_registry() -> dict[str, NodeDefinition]:
    return REGISTRY.copy()


async def dispatch(
    name: str,
    settings_payload: dict[str, Any],
    *,
    inputs_payload: dict[str, Any] | None = None,
    context: ExecutionContext | None = None,
) -> NodeModel:
    definition = REGISTRY.get(name)
    if definition is None:
        raise ValueError(f"Unknown node type '{name}'.")

    settings = definition.settings_model.model_validate(settings_payload)
    inputs: NodeModel | None = None
    if definition.takes_inputs:
        if definition.inputs_model is None:
            raise ValueError(f"Node '{name}' is missing an inputs model.")
        inputs = definition.inputs_model.model_validate(inputs_payload or {})
    elif inputs_payload:
        raise ValueError(f"Node '{name}' does not accept workflow inputs.")

    if definition.takes_inputs and definition.takes_context:
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(settings, inputs, context)
    elif definition.takes_inputs:
        result = definition.handler(settings, inputs)
    elif definition.takes_context:
        if context is None:
            raise ValueError(f"Node '{name}' requires an execution context.")
        result = definition.handler(settings, context)
    else:
        result = definition.handler(settings)

    resolved_result = await result if isawaitable(result) else result
    return definition.result_model.model_validate(resolved_result)


def get_registry_schema() -> dict[str, Any]:
    nodes_schemas: dict[str, Any] = {}
    for name, definition in REGISTRY.items():
        documentation = load_node_documentation(definition)
        required_fields = ["settings", "result"]
        node_properties: dict[str, Any] = {
            "settings": definition.settings_model.model_json_schema(),
            "result": definition.result_model.model_json_schema(),
        }

        if definition.takes_inputs and definition.inputs_model:
            node_properties["inputs"] = definition.inputs_model.model_json_schema()
            required_fields.append("inputs")

        nodes_schemas[name] = {
            "type": "object",
            "title": documentation.title,
            "description": documentation.description,
            "markdownDescription": documentation.body,
            "properties": node_properties,
            "required": required_fields,
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Node Registry Schema",
        "type": "object",
        "properties": nodes_schemas,
    }