from __future__ import annotations

import asyncio

from openbim_runner.nodes.concat_string.concat_string import (
    ConcatStringInputs,
    ConcatStringResult,
    ConcatStringSettings,
    concat_string,
)


def test_concat_string_joins_values_in_order() -> None:
    result = asyncio.run(
        concat_string(
            ConcatStringSettings(separator=" / "),
            ConcatStringInputs(values=["Alpha", "Beta", "Gamma"]),
        )
    )

    assert result == ConcatStringResult(value="Alpha / Beta / Gamma")


def test_concat_string_ignores_none_values() -> None:
    result = asyncio.run(
        concat_string(
            ConcatStringSettings(separator=", "),
            ConcatStringInputs(values=["North", None, "South"]),
        )
    )

    assert result.value == "North, South"
