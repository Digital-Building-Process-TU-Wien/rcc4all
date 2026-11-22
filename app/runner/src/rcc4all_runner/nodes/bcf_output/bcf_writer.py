"""Thin wrapper around the ``bcf-client`` BcfXml writer.

Keeps the bcf-client dependency isolated so the node orchestrator can build
topics / viewpoints without knowing the underlying BCF XML layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import bcf.v3.model as mdl
from bcf.v3.bcfxml import BcfXml
from bcf.v3.visinfo import VisualizationInfoHandler

HIGHLIGHT_COLOR = "FF0000FF"


def apply_highlight(handler: VisualizationInfoHandler, guids: list[str]) -> None:
    """Color a viewpoint's topic elements red; other components stay visible.

    Colors every member element of the topic (one ``Components.Coloring`` block
    listing all IFC GlobalIds) so multi-member topics highlight all their
    elements in every viewpoint. Leaves the selection and visibility
    (``default_visibility=True``) untouched, so the rest of the model remains
    visible and uncolored.
    """
    vi = handler.visualization_info
    if vi.components is None:
        vi.components = mdl.Components()
    vi.components.coloring = mdl.ComponentColoring(
        color=[
            mdl.ComponentColoringColor(
                color=HIGHLIGHT_COLOR,
                components=mdl.ComponentColoringColorComponents(
                    component=[mdl.Component(ifc_guid=g) for g in guids],
                ),
            )
        ]
    )


class BcfWriter:
    def __init__(
        self,
        *,
        project_name: str,
        author: str,
        topic_type: str,
        topic_status: str,
    ) -> None:
        self._bcf = BcfXml.create_new(project_name=project_name or None)
        self._author = author
        self._topic_type = topic_type
        self._topic_status = topic_status
        self.topic_count = 0
        self.viewpoint_count = 0

    def add_topic(
        self,
        *,
        title: str,
        description: str,
        entities: list[Any] | None = None,
    ) -> None:
        topic = self._bcf.add_topic(
            title=title,
            description=description,
            author=self._author,
            topic_type=self._topic_type,
            topic_status=self._topic_status,
        )
        self.topic_count += 1
        members = [entity for entity in entities or [] if entity is not None]
        guids = [getattr(entity, "GlobalId", None) for entity in members]
        for entity in members:
            handler = topic.add_viewpoint(entity)
            apply_highlight(handler, [g for g in guids if g is not None])
            self.viewpoint_count += 1

    def save(self, path: Path) -> None:
        self._bcf.save(path)
