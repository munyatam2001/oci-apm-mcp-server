"""Offline contract tests for deterministic M3 investigation workflows."""

from __future__ import annotations

from typing import Any

from oci_apm_mcp.config import Settings
from oci_apm_mcp.investigation_service import InvestigationService


WINDOW = {"start": "2026-07-15T10:00:00Z", "end": "2026-07-15T11:00:00Z"}
SCOPE = {"region": "eu-example-1", "compartment_id": "masked", "apm_domain_id": "masked"}


def response(
    *, status: str = "success", traces: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "status": status,
        "request_id": "request-1",
        "scope": SCOPE,
        "time_window": WINDOW,
        "data": {"traces": traces or [], "count": len(traces or [])},
        "warnings": [],
    }


class FakeTraceService:
    def __init__(
        self,
        searches: list[dict[str, Any]],
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.searches = list(searches)
        self.detail = detail or {"status": "error", "data": {"code": "unexpected"}}
        self.find_calls: list[dict[str, Any]] = []
        self.detail_calls: list[dict[str, Any]] = []

    def find_traces(self, **kwargs: Any) -> dict[str, Any]:
        self.find_calls.append(kwargs)
        return self.searches.pop(0)

    def get_trace(self, **kwargs: Any) -> dict[str, Any]:
        self.detail_calls.append(kwargs)
        return self.detail


def trace_detail(*, error: bool = False) -> dict[str, Any]:
    return {
        "status": "success",
        "request_id": "detail-request",
        "scope": SCOPE,
        "data": {
            "trace": {
                "trace_id": "trace-a",
                "service_name": "service-a",
                "operation_name": "operation-a",
                "duration_ms": 900,
                "status": "success",
                "error_span_count": 1 if error else 0,
                "returned_span_count": 2,
                "omitted_span_count": 0,
                "spans": [
                    {
                        "span_id": "span-short",
                        "operation_name": "short",
                        "duration_ms": 100,
                        "is_error": False,
                    },
                    {
                        "span_id": "span-long",
                        "operation_name": "long",
                        "duration_ms": 800,
                        "is_error": error,
                    },
                ],
            }
        },
        "warnings": [],
    }


def service(fake: FakeTraceService) -> InvestigationService:
    return InvestigationService(Settings(region="eu-example-1"), fake)


def test_latency_uses_two_call_budget_and_returns_longest_spans() -> None:
    fake = FakeTraceService(
        [
            response(
                traces=[
                    {"trace_id": "trace-a", "duration_ms": 900, "error_count": 0},
                    {"trace_id": "trace-b", "duration_ms": 500, "error_count": 0},
                ]
            )
        ],
        trace_detail(),
    )

    result = service(fake).investigate_latency(top_n=2)

    assert result["status"] == "success"
    assert result["data"]["call_budget"] == {"maximum_oci_calls": 2, "oci_calls_made": 2}
    assert result["data"]["representative_trace"]["longest_spans"][0]["span_id"] == "span-long"
    assert fake.find_calls[0]["limit"] == 2
    assert fake.find_calls[0]["sort_by"] == "duration"
    assert fake.detail_calls[0]["max_spans"] == 50
    assert fake.detail_calls[0]["include_span_attributes"] is False
    assert fake.detail_calls[0]["start_time"] == WINDOW["start"]
    assert fake.detail_calls[0]["end_time"] == WINDOW["end"]


def test_latency_no_data_stops_after_one_call() -> None:
    fake = FakeTraceService([response(status="no_data")])

    result = service(fake).investigate_latency()

    assert result["status"] == "no_data"
    assert result["data"]["call_budget"]["oci_calls_made"] == 1
    assert not fake.detail_calls


def test_latency_detail_failure_preserves_summary_as_partial() -> None:
    fake = FakeTraceService(
        [response(traces=[{"trace_id": "trace-a", "duration_ms": 900}])],
        {"status": "rate_limited", "data": {"code": "rate_limited"}},
    )

    result = service(fake).investigate_latency()

    assert result["status"] == "partial"
    assert result["partial"] is True
    assert result["data"]["slow_traces"]
    assert "rate_limited" in result["warnings"][0]


def test_initial_failure_keeps_workflow_budget_and_zero_call_validation() -> None:
    fake = FakeTraceService(
        [
            {
                "status": "invalid_request",
                "scope": SCOPE,
                "data": {
                    "code": "invalid_filter",
                    "message": "The filter is invalid.",
                    "oci_call_made": False,
                },
            }
        ]
    )

    result = service(fake).investigate_latency()

    assert result["status"] == "invalid_request"
    assert result["data"]["workflow"] == "latency"
    assert result["data"]["call_budget"]["oci_calls_made"] == 0
    assert result["data"]["failed_step"]["code"] == "invalid_filter"


def test_error_workflow_checks_span_error_count_not_overall_status() -> None:
    fake = FakeTraceService(
        [
            response(
                traces=[
                    {
                        "trace_id": "trace-a",
                        "status": "success",
                        "error_count": 3,
                        "duration_ms": 900,
                    },
                    {"trace_id": "trace-b", "status": "error", "error_count": 0},
                ]
            )
        ],
        trace_detail(error=True),
    )

    result = service(fake).investigate_errors(top_n=3)

    assert result["status"] == "success"
    assert len(result["data"]["error_traces"]) == 1
    assert result["data"]["error_traces"][0]["status"] == "success"
    assert result["data"]["representative_trace"]["error_spans"][0]["span_id"] == "span-long"
    assert fake.find_calls[0]["limit"] == 50
    assert fake.find_calls[0]["sort_by"] == "error_count"


def test_error_workflow_returns_no_data_for_zero_error_sample() -> None:
    fake = FakeTraceService([response(traces=[{"trace_id": "trace-a", "error_count": 0}])])

    result = service(fake).investigate_errors()

    assert result["status"] == "no_data"
    assert result["data"]["sample"]["searched_trace_count"] == 1
    assert not fake.detail_calls


def test_compare_windows_returns_sample_deltas_and_zero_denominator_warning() -> None:
    fake = FakeTraceService(
        [
            response(
                traces=[
                    {"duration_ms": 200, "error_count": 1},
                    {"duration_ms": 100, "error_count": 0},
                ]
            ),
            response(traces=[{"duration_ms": 100, "error_count": 0}]),
        ]
    )

    result = service(fake).compare_trace_windows(
        current_start_time="2026-07-15T10:00:00Z",
        current_end_time="2026-07-15T11:00:00Z",
        baseline_start_time="2026-07-14T10:00:00Z",
        baseline_end_time="2026-07-14T11:00:00Z",
    )

    assert result["status"] == "success"
    assert result["data"]["call_budget"]["oci_calls_made"] == 2
    assert result["data"]["current"]["metrics"]["average_duration_ms"] == 150
    assert result["data"]["deltas"]["average_duration_ms"]["percent"] == 50
    assert result["data"]["deltas"]["error_trace_rate"]["percent"] is None
    assert any("baseline value is zero" in warning for warning in result["warnings"])
    assert all(call["sort_by"] == "start_time" for call in fake.find_calls)


def test_compare_windows_preserves_one_available_sample_as_partial() -> None:
    fake = FakeTraceService(
        [
            response(traces=[{"duration_ms": 100, "error_count": 0}]),
            {"status": "unauthorized", "data": {"code": "not_authorized"}},
        ]
    )

    result = service(fake).compare_trace_windows(
        current_start_time="2026-07-15T10:00:00Z",
        current_end_time="2026-07-15T11:00:00Z",
        baseline_start_time="2026-07-14T10:00:00Z",
        baseline_end_time="2026-07-14T11:00:00Z",
    )

    assert result["status"] == "partial"
    assert result["data"]["current"]["metrics"] is not None
    assert result["data"]["baseline"]["metrics"] is None
    assert result["data"]["deltas"] is None


def test_investigations_reject_limits_and_windows_before_calls() -> None:
    fake = FakeTraceService([])
    investigation = service(fake)

    invalid_limit = investigation.investigate_latency(top_n=11)
    invalid_window = investigation.compare_trace_windows(
        current_start_time="2026-07-15T11:00:00Z",
        current_end_time="2026-07-15T10:00:00Z",
        baseline_start_time="2026-07-14T10:00:00Z",
        baseline_end_time="2026-07-14T11:00:00Z",
    )

    assert invalid_limit["status"] == "invalid_request"
    assert invalid_window["status"] == "invalid_request"
    assert not fake.find_calls
