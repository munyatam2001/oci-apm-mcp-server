"""Tests for MCP registration and transport-safe server construction."""

from typing import Any

from oci_apm_mcp.config import Settings
from oci_apm_mcp.server import INSTRUCTIONS, create_mcp_server


class StubService:
    def get_current_context(self) -> dict[str, Any]:
        return {"status": "success"}

    def test_connection(
        self, *, apm_domain_id: str | None = None, compartment_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "apm_domain_id": apm_domain_id,
            "compartment_id": compartment_id,
        }


def test_server_has_global_read_only_instructions() -> None:
    server = create_mcp_server(Settings(), StubService())  # type: ignore[arg-type]

    assert server.name == "OCI APM MCP"
    assert server.instructions == INSTRUCTIONS
    assert "read-only" in server.instructions
    assert "cannot create" in server.instructions


def test_server_registers_exactly_milestone_three_tools_with_read_only_annotations() -> None:
    server = create_mcp_server(Settings(), StubService())  # type: ignore[arg-type]

    tools = server._tool_manager.list_tools()  # noqa: SLF001 - contract test for SDK registration
    assert {tool.name for tool in tools} == {
        "get_current_context",
        "test_connection",
        "list_apm_domains",
        "get_apm_domain",
        "list_apm_quick_picks",
        "find_traces",
        "run_trace_query",
        "get_trace",
        "get_span",
        "get_trace_snapshot",
        "investigate_latency",
        "investigate_errors",
        "compare_trace_windows",
    }
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.description
        assert tool.parameters["type"] == "object"
