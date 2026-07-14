"""Golden tests for deterministic OCI APM query construction."""

import pytest

from oci_apm_mcp.guardrails import InputValidationError
from oci_apm_mcp.trace_query_builder import build_find_traces_query


def test_default_query_is_bounded_and_allowlisted() -> None:
    query = build_find_traces_query(limit=50)

    assert query == (
        'show (traces) TraceId as "trace_id", TraceStatus as "status", '
        'TraceFirstSpanStartTime as "start_time", TraceLatestSpanEndTime as "end_time", '
        'ServiceName as "service_name", OperationName as "operation_name", '
        'TraceDuration as "duration_ms", ErrorCount as "error_count", '
        'SpanCount as "span_count" order by TraceDuration desc first 50 rows'
    )


def test_filters_are_typed_escaped_and_ordered() -> None:
    query = build_find_traces_query(
        service_name="checkout's api",
        operation_name="POST /orders",
        status="ERROR",
        error_type="Timeout",
        minimum_duration_ms=250,
        trace_id="trace-123",
        sort_by="error_count",
        sort_order="ASC",
        limit=20,
    )

    assert "ServiceName = 'checkout''s api'" in query
    assert "OperationName = 'POST /orders'" in query
    assert "TraceStatus = 'error'" in query
    assert "TraceErrorType = 'Timeout'" in query
    assert "TraceDuration >= 250" in query
    assert "TraceId = 'trace-123'" in query
    assert query.endswith("order by ErrorCount asc first 20 rows")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "unknown"},
        {"minimum_duration_ms": -1},
        {"sort_by": "service"},
        {"sort_order": "sideways"},
        {"service_name": "bad\nvalue"},
    ],
)
def test_invalid_builder_inputs_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(InputValidationError):
        build_find_traces_query(**kwargs)  # type: ignore[arg-type]
