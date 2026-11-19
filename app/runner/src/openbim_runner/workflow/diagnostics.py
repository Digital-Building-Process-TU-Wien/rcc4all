"""Non-fatal diagnostics emitted while a workflow is loaded or run."""

from __future__ import annotations

import sys


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)
