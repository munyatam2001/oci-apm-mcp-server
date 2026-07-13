"""Central tool safety classification and drift detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Safety metadata independently enforced by the server."""

    read_only: bool
    idempotent: bool
    destructive: bool
    open_world: bool


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "get_current_context": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=False
    ),
    "test_connection": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
}


def validate_tool_registry(tool_names: Iterable[str]) -> None:
    """Fail startup/tests if registered tools and policy classification drift apart."""
    registered = set(tool_names)
    classified = set(TOOL_POLICIES)
    missing = sorted(registered - classified)
    stale = sorted(classified - registered)
    if missing or stale:
        raise RuntimeError(f"Tool policy drift detected: missing={missing}, stale={stale}")
