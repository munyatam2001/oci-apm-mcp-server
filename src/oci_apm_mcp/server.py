"""MCP registration and STDIO entry point for OCI APM."""

from __future__ import annotations

import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import Settings
from .domain_service import DomainService
from .foundation import FoundationService
from .guardrails import TOOL_POLICIES, validate_tool_registry
from .investigation_service import InvestigationService
from .synthetic_service import SyntheticService
from .trace_service import TraceService


INSTRUCTIONS = (
    "Use this server for safe, read-only OCI Application Performance Monitoring access. "
    "First inspect current context and verify scope. Prefer find_traces with narrow filters, "
    "then retrieve only the needed trace, span, or summarized snapshot. Use deterministic "
    "investigation tools for bounded first-pass latency, error, and window comparisons. "
    "Synthetic tools expose allowlisted monitor and public-vantage-point metadata only. Expert "
    "queries are disabled by default and sensitive fields are excluded. This server cannot "
    "create, update, or delete OCI resources."
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
    domain_service: DomainService | None = None,
    trace_service: TraceService | None = None,
    investigation_service: InvestigationService | None = None,
    synthetic_service: SyntheticService | None = None,
) -> FastMCP:
    """Create a server with exactly the read-only tools approved through the first M4 slice."""
    effective_settings = settings or Settings.from_env()
    effective_service = service or FoundationService(effective_settings)
    effective_domain_service = domain_service or DomainService(effective_settings)
    effective_trace_service = trace_service or TraceService(effective_settings)
    effective_investigation_service = investigation_service or InvestigationService(
        effective_settings, effective_trace_service
    )
    effective_synthetic_service = synthetic_service or SyntheticService(effective_settings)
    mcp = FastMCP("OCI APM MCP", instructions=INSTRUCTIONS)

    @mcp.tool(annotations=_annotations("get_current_context"), structured_output=True)
    def get_current_context() -> dict[str, Any]:
        """Read masked startup scope, auth mode, and enforced limits; makes no OCI call."""
        return effective_service.get_current_context()

    @mcp.tool(annotations=_annotations("test_connection"), structured_output=True)
    def test_connection(
        apm_domain_id: str = "",
        compartment_id: str = "",
    ) -> dict[str, Any]:
        """Read configured scope with one bounded domain call; no trace data or writes."""
        return effective_service.test_connection(
            apm_domain_id=apm_domain_id or None,
            compartment_id=compartment_id or None,
        )

    @mcp.tool(annotations=_annotations("list_apm_domains"), structured_output=True)
    def list_apm_domains(
        compartment_id: str = "",
        display_name: str = "",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read one domain page in approved compartment; default 50, maximum 200, one OCI call."""
        return effective_domain_service.list_apm_domains(
            compartment_id=compartment_id or None,
            display_name=display_name or None,
            limit=limit,
            page=page or None,
        )

    @mcp.tool(annotations=_annotations("get_apm_domain"), structured_output=True)
    def get_apm_domain(apm_domain_id: str = "") -> dict[str, Any]:
        """Read one approved domain in one OCI call; data keys, endpoints, and tags are excluded."""
        return effective_domain_service.get_apm_domain(apm_domain_id=apm_domain_id or None)

    @mcp.tool(annotations=_annotations("list_apm_quick_picks"), structured_output=True)
    def list_apm_quick_picks(
        apm_domain_id: str = "",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read one Quick Pick page for approved domain; default 50, maximum 200, one OCI call."""
        return effective_trace_service.list_apm_quick_picks(
            apm_domain_id=apm_domain_id or None,
            limit=limit,
            page=page or None,
        )

    @mcp.tool(annotations=_annotations("find_traces"), structured_output=True)
    def find_traces(
        apm_domain_id: str = "",
        start_time: str = "",
        end_time: str = "",
        service_name: str = "",
        operation_name: str = "",
        status: str = "",
        error_type: str = "",
        minimum_duration_ms: int = -1,
        trace_id: str = "",
        sort_by: str = "duration",
        sort_order: str = "desc",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read trace summaries in one call; default 1 hour/50 rows, maximum 24 hours/200 rows."""
        return effective_trace_service.find_traces(
            apm_domain_id=apm_domain_id or None,
            start_time=start_time or None,
            end_time=end_time or None,
            service_name=service_name or None,
            operation_name=operation_name or None,
            status=status or None,
            error_type=error_type or None,
            minimum_duration_ms=(minimum_duration_ms if minimum_duration_ms >= 0 else None),
            trace_id=trace_id or None,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            page=page or None,
        )

    @mcp.tool(annotations=_annotations("run_trace_query"), structured_output=True)
    def run_trace_query(
        query: str,
        start_time: str,
        end_time: str,
        apm_domain_id: str = "",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read validated expert results in one call; explicit window, maximum 200 raw/500 aggregate."""
        return effective_trace_service.run_trace_query(
            query=query,
            start_time=start_time,
            end_time=end_time,
            apm_domain_id=apm_domain_id or None,
            limit=limit,
            page=page or None,
        )

    @mcp.tool(annotations=_annotations("get_trace"), structured_output=True)
    def get_trace(
        trace_id: str,
        apm_domain_id: str = "",
        start_time: str = "",
        end_time: str = "",
        include_span_attributes: bool = False,
        max_spans: int = 100,
    ) -> dict[str, Any]:
        """Read one trace in one call; default 100, maximum 500 returned spans; logs excluded."""
        return effective_trace_service.get_trace(
            trace_id=trace_id,
            apm_domain_id=apm_domain_id or None,
            start_time=start_time or None,
            end_time=end_time or None,
            include_span_attributes=include_span_attributes,
            max_spans=max_spans,
        )

    @mcp.tool(annotations=_annotations("get_span"), structured_output=True)
    def get_span(
        trace_id: str,
        span_id: str,
        apm_domain_id: str = "",
        start_time: str = "",
        end_time: str = "",
        include_attributes: bool = False,
    ) -> dict[str, Any]:
        """Read one span in one call; optional window maximum 24 hours; logs always excluded."""
        return effective_trace_service.get_span(
            trace_id=trace_id,
            span_id=span_id,
            apm_domain_id=apm_domain_id or None,
            start_time=start_time or None,
            end_time=end_time or None,
            include_attributes=include_attributes,
        )

    @mcp.tool(annotations=_annotations("get_trace_snapshot"), structured_output=True)
    def get_trace_snapshot(
        trace_id: str,
        apm_domain_id: str = "",
        thread_id: str = "",
        snapshot_time: str = "",
    ) -> dict[str, Any]:
        """Read one summarized snapshot; at most 100 spans, raw stack/thread values omitted."""
        return effective_trace_service.get_trace_snapshot(
            trace_id=trace_id,
            apm_domain_id=apm_domain_id or None,
            thread_id=thread_id or None,
            snapshot_time=snapshot_time or None,
        )

    @mcp.tool(annotations=_annotations("investigate_latency"), structured_output=True)
    def investigate_latency(
        apm_domain_id: str = "",
        start_time: str = "",
        end_time: str = "",
        service_name: str = "",
        operation_name: str = "",
        minimum_duration_ms: int = -1,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Find slow traces and inspect one representative trace; maximum two OCI calls."""
        return effective_investigation_service.investigate_latency(
            apm_domain_id=apm_domain_id or None,
            start_time=start_time or None,
            end_time=end_time or None,
            service_name=service_name or None,
            operation_name=operation_name or None,
            minimum_duration_ms=(minimum_duration_ms if minimum_duration_ms >= 0 else None),
            top_n=top_n,
        )

    @mcp.tool(annotations=_annotations("investigate_errors"), structured_output=True)
    def investigate_errors(
        apm_domain_id: str = "",
        start_time: str = "",
        end_time: str = "",
        service_name: str = "",
        operation_name: str = "",
        error_type: str = "",
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Find error-bearing traces and inspect one representative trace; maximum two OCI calls."""
        return effective_investigation_service.investigate_errors(
            apm_domain_id=apm_domain_id or None,
            start_time=start_time or None,
            end_time=end_time or None,
            service_name=service_name or None,
            operation_name=operation_name or None,
            error_type=error_type or None,
            top_n=top_n,
        )

    @mcp.tool(annotations=_annotations("compare_trace_windows"), structured_output=True)
    def compare_trace_windows(
        current_start_time: str,
        current_end_time: str,
        baseline_start_time: str,
        baseline_end_time: str,
        apm_domain_id: str = "",
        service_name: str = "",
        operation_name: str = "",
        sample_limit: int = 50,
    ) -> dict[str, Any]:
        """Compare two bounded newest-trace samples; exactly two OCI calls, maximum 50 rows each."""
        return effective_investigation_service.compare_trace_windows(
            current_start_time=current_start_time,
            current_end_time=current_end_time,
            baseline_start_time=baseline_start_time,
            baseline_end_time=baseline_end_time,
            apm_domain_id=apm_domain_id or None,
            service_name=service_name or None,
            operation_name=operation_name or None,
            sample_limit=sample_limit,
        )

    @mcp.tool(annotations=_annotations("list_synthetic_monitors"), structured_output=True)
    def list_synthetic_monitors(
        apm_domain_id: str = "",
        display_name: str = "",
        monitor_type: str = "",
        status: str = "",
        sort_by: str = "displayName",
        sort_order: str = "ASC",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read one monitor page; default 50, maximum 200; targets and configurations excluded."""
        return effective_synthetic_service.list_synthetic_monitors(
            apm_domain_id=apm_domain_id or None,
            display_name=display_name or None,
            monitor_type=monitor_type or None,
            status=status or None,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            page=page or None,
        )

    @mcp.tool(annotations=_annotations("get_synthetic_monitor"), structured_output=True)
    def get_synthetic_monitor(monitor_id: str, apm_domain_id: str = "") -> dict[str, Any]:
        """Read one monitor; target, auth/configuration, parameters, tags, and identities excluded."""
        return effective_synthetic_service.get_synthetic_monitor(
            monitor_id=monitor_id,
            apm_domain_id=apm_domain_id or None,
        )

    @mcp.tool(annotations=_annotations("list_public_vantage_points"), structured_output=True)
    def list_public_vantage_points(
        apm_domain_id: str = "",
        display_name: str = "",
        name: str = "",
        sort_by: str = "displayName",
        sort_order: str = "ASC",
        limit: int = 50,
        page: str = "",
    ) -> dict[str, Any]:
        """Read one public vantage-point page; default 50, maximum 200; coordinates excluded."""
        return effective_synthetic_service.list_public_vantage_points(
            apm_domain_id=apm_domain_id or None,
            display_name=display_name or None,
            name=name or None,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            page=page or None,
        )

    validate_tool_registry(
        {
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
            "list_synthetic_monitors",
            "get_synthetic_monitor",
            "list_public_vantage_points",
        }
    )
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
