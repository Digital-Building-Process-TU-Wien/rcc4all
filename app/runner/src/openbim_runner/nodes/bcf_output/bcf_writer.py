"""Thin wrapper around the ``bcf-client`` BcfXml writer.

Keeps the bcf-client dependency isolated so the node orchestrator can build
topics / viewpoints without knowing the underlying BCF XML layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bcf.v3.bcfxml import BcfXml


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
        for entity in entities or []:
            if entity is not None:
                topic.add_viewpoint(entity)
                self.viewpoint_count += 1

    def save(self, path: Path) -> None:
        self._bcf.save(path)
