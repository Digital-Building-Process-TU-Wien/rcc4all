"""Shared test helpers.

Pytest inserts this directory on ``sys.path`` while collecting, so test
modules anywhere under ``app/runner`` can ``from conftest import main_ref``.
"""

from __future__ import annotations


def main_ref(express_id: int) -> str:
    """Qualified element reference for an express ID in the main model."""
    return f"main:expr:{express_id}"


def main_guid(guid: str) -> str:
    """Qualified GUID reference for a GlobalId in the main model."""
    return f"main:guid:{guid}"
