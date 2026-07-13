"""Offline tests for bounded trace, span, query, and snapshot reads."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from oci_apm_mcp.config import Settings
from oci_apm_mcp.trace_service import TraceService


DOMAIN_ID = "ocid1.apmdomain.oc1..configured"


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.headers = {"opc-request-id": "trace-request-id", "opc-next-page": "next-page"}


class FakeQueryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: BaseException | None = None
        self.rows: list[dict[str, Any]] = [
            {
                "trace_id": "trace-1",
                "service_name": "checkout",
                "operation_name": "POST /orders",
                "start_time": 1000,
                "end_time": 1250,
                "duration_ms": 250,
                "status": "error",
                "error_count": 1,
                "span_count": 3,
            }
        ]

    def list_quick_picks(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("quick_picks", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(
            [SimpleNamespace(quick_pick_name="Traces", quick_pick_query="show traces TraceId")]
        )

    def query(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("query", kwargs))
        if self.error:
            raise self.error
        data = SimpleNamespace(
            query_result_rows=[
                SimpleNamespace(query_result_row_data=row, query_result_row_metadata={})
                for row in self.rows
            ],
            query_result_warnings=[SimpleNamespace(message="bounded warning")],
        )
        return FakeResponse(data)


def _tag(name: str, value: str) -> Any:
    return SimpleNamespace(tag_name=name, tag_value=value)


def _span(key: str) -> Any:
    return SimpleNamespace(
        key=key,
        parent_span_key="parent",
        trace_key="trace-1",
        service_name="checkout",
        operation_name="POST /orders",
        kind="SERVER",
        time_started=datetime(2026, 7, 13, 10, tzinfo=UTC),
        time_ended=datetime(2026, 7, 13, 10, 0, 1, tzinfo=UTC),
        duration_in_ms=1000,
        is_error=False,
        source_name="SPANS",
        tags=[_tag("safe.attribute", "visible"), _tag("Authorization", "Bearer secret")],
        logs=[SimpleNamespace(message="must not leak")],
    )


class FakeTraceClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: BaseException | None = None

    def get_trace(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("trace", kwargs))
        if self.error:
            raise self.error
        trace = SimpleNamespace(
            key=kwargs["trace_key"],
            root_span_service_name="checkout",
            root_span_operation_name="POST /orders",
            time_earliest_span_started=datetime(2026, 7, 13, 10, tzinfo=UTC),
            time_latest_span_ended=datetime(2026, 7, 13, 10, 0, 3, tzinfo=UTC),
            trace_duration_in_ms=3000,
            root_span_duration_in_ms=2000,
            trace_status="success",
            is_fault=False,
            trace_error_type=None,
            trace_error_code=None,
            span_count=3,
            error_span_count=0,
            service_summaries=[
                SimpleNamespace(span_service_name="checkout", total_spans=3, error_spans=0)
            ],
            spans=[_span("span-1"), _span("span-2"), _span("span-3")],
        )
        return FakeResponse(trace)

    def get_span(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("span", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(_span(kwargs["span_key"]))

    def get_trace_snapshot(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("snapshot", kwargs))
        if self.error:
            raise self.error
        child = SimpleNamespace(
            key="child-span",
            span_name="child",
            time_started=datetime(2026, 7, 13, 10, tzinfo=UTC),
            time_ended=datetime(2026, 7, 13, 10, 0, 1, tzinfo=UTC),
            span_snapshot_details=[SimpleNamespace(key="stack", value="must not leak")],
            thread_snapshots=[SimpleNamespace(secret="must not leak")],
            children=[],
        )
        root = SimpleNamespace(
            key="root-span",
            span_name="root",
            time_started=datetime(2026, 7, 13, 10, tzinfo=UTC),
            time_ended=datetime(2026, 7, 13, 10, 0, 2, tzinfo=UTC),
            span_snapshot_details=[],
            thread_snapshots=[],
            children=[child],
        )
        snapshot = SimpleNamespace(
            key=kwargs["trace_key"],
            time_started=datetime(2026, 7, 13, 10, tzinfo=UTC),
            time_ended=datetime(2026, 7, 13, 10, 0, 2, tzinfo=UTC),
            trace_snapshot_details=[SimpleNamespace(key="raw", value="must not leak")],
            span_snapshots=[root],
        )
        return FakeResponse(snapshot)


class FakeFactory:
    def __init__(self) -> None:
        self.query = FakeQueryClient()
        self.trace = FakeTraceClient()
        self.query_create_count = 0
        self.trace_create_count = 0

    def apm_domain_client(self) -> Any:
        raise AssertionError("Domain client is not used by TraceService")

    def query_client(self) -> FakeQueryClient:
        self.query_create_count += 1
        return self.query

    def trace_client(self) -> FakeTraceClient:
        self.trace_create_count += 1
        return self.trace


class FakeServiceError(Exception):
    status = 429
    request_id = "trace-rate-limit-request"


def test_list_quick_picks_is_paginated_and_bounded() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).list_apm_quick_picks(
        limit=10, page="page-1"
    )

    assert result["status"] == "success"
    assert result["data"]["quick_picks"][0]["name"] == "Traces"
    assert result["pagination"]["next_page"] == "next-page"
    _, kwargs = factory.query.calls[0]
    assert kwargs["apm_domain_id"] == DOMAIN_ID
    assert kwargs["limit"] == 10
    assert kwargs["page"] == "page-1"


def test_find_traces_builds_exact_sdk_request_and_normalizes_rows() -> None:
    factory = FakeFactory()
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory)

    result = service.find_traces(
        start_time="2026-07-13T10:00:00Z",
        end_time="2026-07-13T11:00:00Z",
        service_name="checkout",
        status="error",
        limit=25,
        page="page-1",
    )

    assert result["status"] == "success"
    assert result["data"]["traces"][0]["trace_id"] == "trace-1"
    assert result["time_window"] == {
        "start": "2026-07-13T10:00:00Z",
        "end": "2026-07-13T11:00:00Z",
    }
    assert result["warnings"] == ["bounded warning"]
    _, kwargs = factory.query.calls[0]
    assert kwargs["limit"] == 25
    assert kwargs["page"] == "page-1"
    assert kwargs["time_span_started_less_than"] - kwargs[
        "time_span_started_greater_than_or_equal_to"
    ] == timedelta(hours=1)
    assert "ServiceName = 'checkout'" in kwargs["query_details"].query_text
    assert kwargs["query_details"].query_text.endswith("first 25 rows")


def test_find_traces_invalid_window_makes_no_oci_call() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).find_traces(
        start_time="2026-07-11T10:00:00Z",
        end_time="2026-07-13T10:00:00Z",
    )

    assert result["status"] == "invalid_request"
    assert result["data"]["code"] == "time_window_too_large"
    assert factory.query_create_count == 0


def test_expert_query_is_disabled_by_default_without_oci_call() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).run_trace_query(
        query="show traces TraceId",
        start_time="2026-07-13T10:00:00Z",
        end_time="2026-07-13T11:00:00Z",
    )

    assert result["status"] == "invalid_request"
    assert result["data"]["code"] == "expert_query_disabled"
    assert factory.query_create_count == 0


def test_enabled_expert_query_sanitizes_rows_and_classifies_aggregate() -> None:
    factory = FakeFactory()
    factory.query.rows = [
        {
            "Service": "checkout",
            "Count": 5,
            "Authorization": "Bearer secret",
            "Nested": {"secret": "value"},
        }
    ]
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID, enable_expert_query=True), factory)

    result = service.run_trace_query(
        query="show traces ServiceName as Service, count(*) as Count group by ServiceName",
        start_time="2026-07-10T10:00:00Z",
        end_time="2026-07-13T10:00:00Z",
        limit=100,
    )

    assert result["status"] == "success"
    assert result["data"]["query_category"] == "aggregate"
    assert result["data"]["rows"][0]["Authorization"] == "[REDACTED]"
    assert result["data"]["rows"][0]["Nested"] == "[COMPLEX_VALUE_OMITTED]"
    assert "Bearer secret" not in str(result)


def test_get_trace_caps_spans_redacts_attributes_and_omits_logs() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).get_trace(
        trace_id="trace-1", include_span_attributes=True, max_spans=2
    )

    trace = result["data"]["trace"]
    assert trace["returned_span_count"] == 2
    assert trace["omitted_span_count"] == 1
    assert trace["spans"][0]["attributes"]["safe.attribute"] == "visible"
    assert trace["spans"][0]["attributes"]["Authorization"] == "[REDACTED]"
    assert trace["spans"][0]["logs_omitted"] is True
    assert "must not leak" not in str(result)
    _, kwargs = factory.trace.calls[0]
    assert kwargs["trace_namespace"] == "TRACES"


def test_get_span_uses_optional_time_bounds_and_excludes_attributes_by_default() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).get_span(
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-07-13T10:00:00Z",
        end_time="2026-07-13T11:00:00Z",
    )

    assert result["status"] == "success"
    assert "attributes" not in result["data"]["span"]
    _, kwargs = factory.trace.calls[0]
    assert kwargs["trace_key"] == "trace-1"
    assert kwargs["span_key"] == "span-1"
    assert kwargs["span_namespace"] == "TRACES"
    assert kwargs["time_span_started_less_than"] - kwargs[
        "time_span_started_greater_than_or_equal_to"
    ] == timedelta(hours=1)


def test_snapshot_is_forced_summarized_and_raw_details_never_return() -> None:
    factory = FakeFactory()
    result = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory).get_trace_snapshot(
        trace_id="trace-1", thread_id="123", snapshot_time="456"
    )

    snapshot = result["data"]["snapshot"]
    assert snapshot["summarized"] is True
    assert len(snapshot["spans"]) == 2
    assert snapshot["trace_details_omitted_count"] == 1
    assert snapshot["spans"][1]["details_omitted_count"] == 1
    assert "must not leak" not in str(result)
    _, kwargs = factory.trace.calls[0]
    assert kwargs["is_summarized"] is True
    assert kwargs["thread_id"] == "123"
    assert kwargs["snapshot_time"] == "456"


def test_query_tool_limits_are_rejected_before_client_creation() -> None:
    factory = FakeFactory()
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID, enable_expert_query=True), factory)

    results = [
        service.list_apm_quick_picks(limit=201),
        service.find_traces(limit=201),
        service.run_trace_query(
            query="show traces TraceId",
            start_time="2026-07-13T10:00:00Z",
            end_time="2026-07-13T11:00:00Z",
            limit=201,
        ),
    ]

    assert all(result["status"] == "invalid_request" for result in results)
    assert all(result["data"]["code"] == "invalid_limit" for result in results)
    assert factory.query_create_count == 0


def test_trace_and_span_limits_are_rejected_before_client_creation() -> None:
    factory = FakeFactory()
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory)

    trace_result = service.get_trace(trace_id="trace-1", max_spans=501)
    span_result = service.get_span(
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-07-11T10:00:00Z",
        end_time="2026-07-13T10:00:00Z",
    )

    assert trace_result["data"]["code"] == "invalid_limit"
    assert span_result["data"]["code"] == "time_window_too_large"
    assert factory.trace_create_count == 0


def test_snapshot_normalizer_caps_returned_spans() -> None:
    spans = [
        SimpleNamespace(
            key=f"span-{index}",
            span_name="bounded",
            time_started=None,
            time_ended=None,
            span_snapshot_details=[],
            thread_snapshots=[],
            children=[],
        )
        for index in range(101)
    ]

    normalized, omitted = TraceService._snapshot_spans(spans)  # noqa: SLF001

    assert len(normalized) == 100
    assert omitted == 1


@pytest.mark.parametrize("operation", ["quick_picks", "find_traces", "run_trace_query"])
def test_query_tool_errors_are_safely_mapped(operation: str) -> None:
    factory = FakeFactory()
    factory.query.error = FakeServiceError("raw query secret")
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID, enable_expert_query=True), factory)

    if operation == "quick_picks":
        result = service.list_apm_quick_picks()
    elif operation == "find_traces":
        result = service.find_traces()
    else:
        result = service.run_trace_query(
            query="show traces TraceId",
            start_time="2026-07-13T10:00:00Z",
            end_time="2026-07-13T11:00:00Z",
        )

    assert result["status"] == "rate_limited"
    assert result["request_id"] == "trace-rate-limit-request"
    assert "raw query secret" not in str(result)


@pytest.mark.parametrize("operation", ["get_trace", "get_span", "get_trace_snapshot"])
def test_trace_detail_errors_are_safely_mapped(operation: str) -> None:
    factory = FakeFactory()
    factory.trace.error = FakeServiceError("raw trace secret")
    service = TraceService(Settings(apm_domain_id=DOMAIN_ID), factory)

    if operation == "get_trace":
        result = service.get_trace(trace_id="trace-1")
    elif operation == "get_span":
        result = service.get_span(trace_id="trace-1", span_id="span-1")
    else:
        result = service.get_trace_snapshot(trace_id="trace-1")

    assert result["status"] == "rate_limited"
    assert result["request_id"] == "trace-rate-limit-request"
    assert "raw trace secret" not in str(result)
