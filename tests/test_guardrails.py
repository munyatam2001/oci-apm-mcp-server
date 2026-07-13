"""Tests for central tool classification."""

import pytest

from oci_apm_mcp.guardrails import TOOL_POLICIES, validate_tool_registry


def test_foundation_tools_are_read_only_and_non_destructive() -> None:
    assert set(TOOL_POLICIES) == {"get_current_context", "test_connection"}
    assert all(policy.read_only for policy in TOOL_POLICIES.values())
    assert all(policy.idempotent for policy in TOOL_POLICIES.values())
    assert not any(policy.destructive for policy in TOOL_POLICIES.values())


def test_registry_validation_accepts_exact_match() -> None:
    validate_tool_registry({"get_current_context", "test_connection"})


@pytest.mark.parametrize(
    "names", [{"get_current_context"}, {"get_current_context", "test_connection", "unknown"}]
)
def test_registry_validation_detects_drift(names: set[str]) -> None:
    with pytest.raises(RuntimeError, match="drift"):
        validate_tool_registry(names)
