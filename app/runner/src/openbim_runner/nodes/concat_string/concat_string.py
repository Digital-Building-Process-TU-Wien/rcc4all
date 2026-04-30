from __future__ import annotations

from pydantic import Field

from openbim_runner.nodes.base import NodeModel, node


class ConcatStringSettings(NodeModel):
    separator: str = Field(
        default=", ",
        title="Separator",
        description="String inserted between the resolved input strings.",
    )


class ConcatStringInputs(NodeModel):
    values: list[str | None] = Field(
        default=[],
        title="Input values",
        description="Resolved values to concatenate.",
    )


class ConcatStringResult(NodeModel):
    value: str = Field(
        default="",
        title="Concatenated string",
        description="Final string assembled from the input strings.",
    )


@node()
async def concat_string(settings: ConcatStringSettings, inputs: ConcatStringInputs) -> ConcatStringResult:
    filtered_strings = [str(value) for value in inputs.values if value is not None]
    return ConcatStringResult(value=settings.separator.join(filtered_strings))
