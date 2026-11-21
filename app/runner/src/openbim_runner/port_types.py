"""Port type descriptors shared by the runner and the web editor.

Pydantic annotations are the single source of truth. :func:`annotation_to_port_type`
maps them to the closed :data:`PortType` union that the exported ``schema.json``
carries, and :func:`is_assignable` implements the one assignability rule table
that both the runner and the editor use.

The module deliberately depends on nothing from ``openbim_runner`` so it can be
imported from ``nodes`` and from ``workflow`` without creating a cycle.
"""

from __future__ import annotations

import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScalarTypeName = Literal["string", "integer", "number", "boolean", "object", "any"]


class PortModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PortScalar(PortModel):
    type: ScalarTypeName = Field(
        title="Type",
        description="One of the scalar JSON types, or 'any' for an explicit wildcard.",
    )


class PortArray(PortModel):
    type: Literal["array"] = Field(title="Type", description="Always 'array'.")
    items: PortType = Field(title="Item type", description="Type of every element.")


class PortUnion(PortModel):
    type: Literal["union"] = Field(title="Type", description="Always 'union'.")
    members: list[PortType] = Field(
        title="Members",
        description="Every member type an assignable value may have.",
    )

    @field_validator("members")
    @classmethod
    def _require_members(cls, members: list[PortType]) -> list[PortType]:
        if not members:
            raise ValueError("A union port type needs at least one member.")
        return members


PortType = Annotated[PortScalar | PortArray | PortUnion, Field(discriminator="type")]

PortArray.model_rebuild()
PortUnion.model_rebuild()


class UnsupportedPortTypeError(ValueError):
    """Raised when a Pydantic annotation cannot be expressed as a port type."""


# The one assignability table. ``output -> input`` is allowed when the input
# type appears in the output's row. Arrays are compared item-wise and unions are
# expanded before this table is consulted (see ``is_assignable``).
ASSIGNABLE_TYPES: dict[str, tuple[str, ...]] = {
    "string": ("string", "any"),
    "integer": ("integer", "number", "any"),
    "number": ("number", "any"),
    "boolean": ("boolean", "any"),
    "object": ("object", "any"),
    "array": ("array", "any"),
    "any": (
        "string",
        "integer",
        "number",
        "boolean",
        "object",
        "array",
        "any",
    ),
}


def get_compatibility_table() -> dict[str, list[str]]:
    """The assignability table as plain JSON, for ``export-schema``."""
    return {source: list(targets) for source, targets in ASSIGNABLE_TYPES.items()}


def annotation_to_port_type(annotation: Any, *, node: str, field: str) -> PortType:
    """Map a Pydantic field annotation to a :data:`PortType`.

    Raises :class:`UnsupportedPortTypeError` naming ``node`` and ``field`` when
    the annotation has no faithful port representation. There is no fallback:
    a silent ``any`` would hide type mismatches from the editor.
    """
    try:
        return _map_annotation(annotation)
    except UnsupportedPortTypeError as error:
        raise UnsupportedPortTypeError(
            f"Unsupported port type '{annotation}' for node '{node}' field "
            f"'{field}': {error}"
        ) from error


def model_port_types(model: type[BaseModel], *, node: str) -> dict[str, PortType]:
    """Map every field of a Pydantic model to its port type, keyed by field name."""
    return {
        field_name: annotation_to_port_type(
            field_info.annotation, node=node, field=field_name
        )
        for field_name, field_info in model.model_fields.items()
    }


def _map_annotation(annotation: Any) -> PortType:
    if annotation is Any:
        return PortScalar(type="any")
    if annotation is str:
        return PortScalar(type="string")
    if annotation is bool:
        return PortScalar(type="boolean")
    if annotation is int:
        return PortScalar(type="integer")
    if annotation is float:
        return PortScalar(type="number")

    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return PortScalar(type="object")
        raise UnsupportedPortTypeError(
            "Only JSON scalars, lists, dicts, unions, literals and Pydantic "
            "models are supported."
        )

    args = get_args(annotation)
    if origin is list:
        item = args[0] if args else Any
        return PortArray(type="array", items=_map_annotation(item))
    if origin is dict:
        return PortScalar(type="object")
    if origin is Literal:
        return _literal_port_type(args)
    if origin in (Union, types.UnionType):
        return _union_port_type(args)

    raise UnsupportedPortTypeError(f"Unsupported generic origin '{origin}'.")


def _literal_port_type(values: tuple[Any, ...]) -> PortType:
    members: list[PortType] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            member = PortScalar(type="boolean")
        elif isinstance(value, int):
            member = PortScalar(type="integer")
        elif isinstance(value, float):
            member = PortScalar(type="number")
        elif isinstance(value, str):
            member = PortScalar(type="string")
        else:
            member = PortScalar(type="object")
        if member not in members:
            members.append(member)

    return _collapse(members)


def _union_port_type(args: tuple[Any, ...]) -> PortType:
    members: list[PortType] = []
    for argument in args:
        if argument is type(None):
            continue
        member = _map_annotation(argument)
        if member not in members:
            members.append(member)

    return _collapse(members)


def _collapse(members: list[PortType]) -> PortType:
    if not members:
        raise UnsupportedPortTypeError("The type has no representable members.")
    if len(members) == 1:
        return members[0]
    return PortUnion(type="union", members=members)


def is_assignable(output: PortType, input: PortType) -> bool:
    """Whether a value produced as ``output`` may feed a port typed ``input``."""
    if isinstance(output, PortUnion):
        return all(is_assignable(member, input) for member in output.members)
    if isinstance(input, PortUnion):
        return any(is_assignable(output, member) for member in input.members)
    if output.type == "any" or input.type == "any":
        return True
    if output.type == "array" and input.type == "array":
        return is_assignable(output.items, input.items)
    return input.type in ASSIGNABLE_TYPES.get(output.type, ())


def describe_port_type(port_type: PortType) -> str:
    """Human-readable type name for error messages, e.g. ``array<integer | string>``."""
    if isinstance(port_type, PortUnion):
        return " | ".join(describe_port_type(member) for member in port_type.members)
    if isinstance(port_type, PortArray):
        return f"array<{describe_port_type(port_type.items)}>"
    return port_type.type
