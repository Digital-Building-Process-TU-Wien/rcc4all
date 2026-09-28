from __future__ import annotations

from pydantic import Field

from openbim_runner.nodes.base import NodeModel, node


class FileInputSettings(NodeModel):
    slug: str = Field(
        default="main",
        title="Model",
        description="Slug of the IFC model this File Input refers to. Defaults to the main model.",
    )


class FileInputResult(NodeModel):
    model_slug: str = Field(
        default="main",
        title="Model slug",
        description="Slug of the selected IFC model, for binding to a consumer's model input.",
    )


@node()
async def file_input(settings: FileInputSettings) -> FileInputResult:
    return FileInputResult(model_slug=settings.slug)
