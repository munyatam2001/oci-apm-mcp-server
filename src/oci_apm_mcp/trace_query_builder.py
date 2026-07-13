"""Deterministic OCI APM Defined Query Syntax construction."""

from __future__ import annotations

from .guardrails import InputValidationError, validate_text


_SORT_FIELDS = {
    "start_time": "TraceFirstSpanStartTime",
    "duration": "TraceDuration",
    "error_count": "ErrorCount",
}
_TRACE_STATUSES = frozenset({"complete", "success", "incomplete", "error"})


def _literal(value: str, *, field_name: str) -> str:
    cleaned = validate_text(value, field_name=field_name)
    escaped = cleaned.replace("'", "''")
    return f"'{escaped}'"


def build_find_traces_query(
    *,
    service_name: str | None = None,
    operation_name: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    minimum_duration_ms: int | None = None,
    trace_id: str | None = None,
    sort_by: str = "duration",
    sort_order: str = "desc",
    limit: int = 50,
) -> str:
    """Build one bounded trace query from typed, escaped filters."""
    if sort_by not in _SORT_FIELDS:
        raise InputValidationError(
            "invalid_sort", "sort_by must be start_time, duration, or error_count."
        )
    normalized_order = sort_order.lower()
    if normalized_order not in {"asc", "desc"}:
        raise InputValidationError("invalid_sort", "sort_order must be asc or desc.")
    if minimum_duration_ms is not None and minimum_duration_ms < 0:
        raise InputValidationError("invalid_filter", "minimum_duration_ms must be zero or greater.")
    normalized_status = status.lower() if status else None
    if normalized_status and normalized_status not in _TRACE_STATUSES:
        raise InputValidationError(
            "invalid_filter",
            "status must be complete, success, incomplete, or error.",
        )

    filters: list[str] = []
    if service_name:
        filters.append(f"ServiceName = {_literal(service_name, field_name='service_name')}")
    if operation_name:
        filters.append(f"OperationName = {_literal(operation_name, field_name='operation_name')}")
    if normalized_status:
        filters.append(f"TraceStatus = '{normalized_status}'")
    if error_type:
        filters.append(f"TraceErrorType = {_literal(error_type, field_name='error_type')}")
    if minimum_duration_ms is not None:
        filters.append(f"TraceDuration >= {minimum_duration_ms}")
    if trace_id:
        filters.append(f"TraceId = {_literal(trace_id, field_name='trace_id')}")

    query = (
        'show (traces) TraceId as "trace_id", TraceStatus as "status", '
        'TraceFirstSpanStartTime as "start_time", '
        'TraceLatestSpanEndTime as "end_time", ServiceName as "service_name", '
        'OperationName as "operation_name", TraceDuration as "duration_ms", '
        'ErrorCount as "error_count", SpanCount as "span_count"'
    )
    if filters:
        query += " where " + " and ".join(filters)
    query += f" order by {_SORT_FIELDS[sort_by]} {normalized_order} first {limit} rows"
    return query
