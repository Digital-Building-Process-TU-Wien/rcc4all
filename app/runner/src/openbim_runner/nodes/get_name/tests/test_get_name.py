from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.get_name.get_name import GetNameResult, GetNameSettings, get_name


class FakeEntity:
    def __init__(self, name: str | None) -> None:
        self.Name = name


class FakeIfcModel:
    def __init__(self, entities_by_id: dict[int, FakeEntity], *, failing_ids: set[int] | None = None) -> None:
        self.entities_by_id = entities_by_id
        self.failing_ids = set() if failing_ids is None else failing_ids

    def by_id(self, express_id: int) -> FakeEntity:
        if express_id in self.failing_ids:
            raise RuntimeError("Unknown express ID")

        return self.entities_by_id[express_id]


def test_get_name_returns_names_in_input_order() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({1: FakeEntity("Wall A"), 2: FakeEntity("Wall B")})),
        node_outputs={},
    )

    result = asyncio.run(
        get_name(
            GetNameSettings(allow_missing=True, express_ids=[2, 1]),
            context,
        )
    )

    assert result == GetNameResult(object_names=["Wall B", "Wall A"])


def test_get_name_allows_missing_entities_when_configured() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({1: FakeEntity("Wall A")}, failing_ids={99})),
        node_outputs={},
    )

    result = asyncio.run(
        get_name(
            GetNameSettings(allow_missing=True, express_ids=[1, 99]),
            context,
        )
    )

    assert result.object_names == ["Wall A", None]


def test_get_name_rejects_missing_entities_when_not_allowed() -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, FakeIfcModel({1: FakeEntity("Wall A")}, failing_ids={99})),
        node_outputs={},
    )

    with pytest.raises(ValueError, match="Could not resolve a name for express ID 99"):
        asyncio.run(
            get_name(
                GetNameSettings(allow_missing=False, express_ids=[99]),
                context,
            )
        )