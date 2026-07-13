"""MCP registration and STDIO entry point for OCI APM."""

from __future__ import annotations

import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import Settings
from .foundation import FoundationService
from .guardrails import TOOL_POLICIES, validate_tool_registry


INSTRUCTIONS = (
    "Use this server for safe, read-only OCI Application Performance Monitoring access. "
    "First inspect current context, then test the configured APM domain or compartment. "
    "This foundation release does not query traces and cannot create, update, or delete "
    "OCI resources."
)


def _annotations(name: str) -> ToolAnnotations:
    policy = TOOL_POLICIES[name]
    return ToolAnnotations(
        title=name.replace("_", " ").title(),
        readOnlyHint=policy.read_only,
        idempotentHint=policy.idempotent,
        destructiveHint=policy.destructive,
        openWorldHint=policy.open_world,
    )


def create_mcp_server(
    settings: Settings | None = None,
    service: FoundationService | None = None,
) -> FastMCP:
    """Create a server with exactly the tools approved for Milestone 1."""
    effective_settings = settings or Settings.from_env()
    effective_service = service or FoundationService(effective_settings)
    mcp = FastMCP("OCI APM MCP", instructions=INSTRUCTIONS)

    @mcp.tool(annotations=_annotations("get_current_context"), structured_output=True)
    def get_current_context() -> dict[str, Any]:
        """Show masked OCI APM scope, auth mode, limits, and read-only status; makes no OCI call."""
        return effective_service.get_current_context()

    @mcp.tool(annotations=_annotations("test_connection"), structured_output=True)
    def test_connection(
        apm_domain_id: str = "",
        compartment_id: str = "",
    ) -> dict[str, Any]:
        """Verify OCI APM read access using one bounded domain get or list call."""
        return effective_service.test_connection(
            apm_domain_id=apm_domain_id or None,
            compartment_id=compartment_id or None,
        )

    validate_tool_registry({"get_current_context", "test_connection"})
    return mcp


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    """Run the server over STDIO; stdout remains reserved for MCP messages."""
    settings = Settings.from_env()
    _configure_logging(settings.log_level)
    create_mcp_server(settings=settings).run(transport="stdio")
