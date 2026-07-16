"""Bounded trace queries and allowlisted trace/span normalization."""

from __future__ import annotations

from importlib import import_module
import re
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4

from .client_factory import OciClientFactory, TraceClientFactory
from .config import Settings, mask_identifier
from .errors import normalize_error
from .guardrails import (
    InputValidationError,
    MAX_AGGREGATE_ROWS,
    MAX_AGGREGATE_WINDOW,
    MAX_RAW_ROWS,
    MAX_RAW_WINDOW,
    MAX_TRACE_SPANS,
    QueryCategory,
    ValidatedWindow,
    default_time_window,
    validate_expert_query,
    validate_limit,
    validate_text,
    validate_time_window,
)
from .models import Pagination, ResponseStatus, Scope, TimeWindow, ToolResponse
from .sanitize import safe_scalar, sanitize_mapping, sanitize_tags
from .trace_query_builder import build_find_traces_query


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _request_id(response: Any, fallback: str) -> str:
    headers = getattr(response, "headers", None)
    if isinstance(headers, dict):
        value = headers.get("opc-request-id") or headers.get("Opc-Request-Id")
        if value:
            return str(value)
    return fallback


def _next_page(response: Any) -> str | None:
    headers = getattr(response, "headers", None)
    if isinstance(headers, dict):
        value = headers.get("opc-next-page") or headers.get("Opc-Next-Page")
        if value:
            return str(value)
    return None


def _time_window(window: ValidatedWindow) -> TimeWindow:
    start, end = window.as_strings()
    return TimeWindow(start=start, end=end)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _row_value(values: Mapping[str, Any], *names: str) -> Any:
    normalized = {_normalized_key(str(key)): value for key, value in values.items()}
    for name in names:
        if _normalized_key(name) in normalized:
            return normalized[_normalized_key(name)]
    return None


class TraceService:
    """Implement query, trace, span, and summarized snapshot reads."""

    def __init__(
        self,
        settings: Settings,
        client_factory: TraceClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory or OciClientFactory(settings)

    def _scope(self, domain_id: str | None = None) -> Scope:
        return Scope(
            region=self._settings.region,
            compartment_id=mask_identifier(self._settings.compartment_id),
            apm_domain_id=mask_identifier(domain_id or self._settings.apm_domain_id),
        )

    def _resolve_domain(self, explicit: str | None) -> str:
        configured = self._settings.apm_domain_id
        if (
            explicit
            and configured
            and explicit != configured
            and not self._settings.allow_scope_override
        ):
            raise InputValidationError(
                "scope_override_blocked",
                "apm_domain_id differs from the locked startup scope.",
            )
        value = explicit or configured
        if not value:
            raise InputValidationError("missing_scope", "apm_domain_id is required.")
        return validate_text(value, field_name="apm_domain_id", maximum_length=512)

    def _resolve_window(
        self,
        start_time: str | None,
        end_time: str | None,
        *,
        maximum: Any,
        allow_default: bool,
    ) -> ValidatedWindow:
        if not start_time and not end_time and allow_default:
            return default_time_window()
        if not start_time or not end_time:
            raise InputValidationError(
                "missing_time", "start_time and end_time must be provided together."
            )
        return validate_time_window(start_time, end_time, maximum=maximum)

    def _invalid(
        self,
        error: InputValidationError,
        started: float,
        *,
        domain_id: str | None = None,
    ) -> dict[str, Any]:
        status: ResponseStatus = (
            "needs_clarification"
            if error.code in {"missing_scope", "missing_time"}
            else "invalid_request"
        )
        return ToolResponse(
            status=status,
            scope=self._scope(domain_id),
            data={"code": error.code, "message": error.safe_message, "oci_call_made": False},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    def _failure(
        self,
        error: Exception,
        started: float,
        request_id: str,
        domain_id: str,
        *,
        window: ValidatedWindow | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_error(error)
        return ToolResponse(
            status=normalized.status,
            request_id=normalized.request_id or request_id,
            scope=self._scope(domain_id),
            time_window=_time_window(window) if window else None,
            data={"code": normalized.code, "message": normalized.message},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _query_details(query: str) -> Any:
        models = import_module("oci.apm_traces.models")
        return models.QueryDetails(query_text=query)

    @staticmethod
    def _query_rows(response: Any) -> list[Mapping[str, Any]]:
        rows = getattr(response.data, "query_result_rows", None) or []
        result: list[Mapping[str, Any]] = []
        for row in rows:
            values = getattr(row, "query_result_row_data", row)
            if isinstance(values, Mapping):
                result.append(values)
        return result

    @staticmethod
    def _query_warnings(response: Any) -> list[str]:
        warnings = getattr(response.data, "query_result_warnings", None) or []
        return [
            str(safe_scalar(getattr(item, "message", "OCI query warning")))
            for item in warnings[:10]
        ]

    def list_apm_quick_picks(
        self,
        *,
        apm_domain_id: str | None = None,
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_limit = validate_limit(limit, maximum=MAX_RAW_ROWS)
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "limit": validated_limit,
                "opc_request_id": request_id,
            }
            if validated_page:
                kwargs["page"] = validated_page
            response = self._client_factory.query_client().list_quick_picks(**kwargs)
            response_data = response.data
            items = (
                response_data
                if isinstance(response_data, list)
                else (getattr(response_data, "items", []) or [])
            )
            quick_picks = [
                {
                    "name": safe_scalar(getattr(item, "quick_pick_name", None)),
                    "query": safe_scalar(getattr(item, "quick_pick_query", None)),
                }
                for item in items[:validated_limit]
            ]
            return ToolResponse(
                status="success" if quick_picks else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                data={"quick_picks": quick_picks, "count": len(quick_picks)},
                pagination=Pagination(next_page=_next_page(response), truncated=False),
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id)

    def _execute_query(
        self,
        *,
        domain_id: str,
        window: ValidatedWindow,
        query: str,
        limit: int,
        page: str | None,
    ) -> tuple[Any, str]:
        request_id = uuid4().hex
        kwargs: dict[str, Any] = {
            "apm_domain_id": domain_id,
            "time_span_started_greater_than_or_equal_to": window.start,
            "time_span_started_less_than": window.end,
            "query_details": self._query_details(query),
            "limit": limit,
            "opc_request_id": request_id,
        }
        if page:
            kwargs["page"] = page
        response = self._client_factory.query_client().query(**kwargs)
        return response, request_id

    @staticmethod
    def _trace_query_row(values: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "trace_id": safe_scalar(_row_value(values, "trace_id", "TraceId")),
            "service_name": safe_scalar(_row_value(values, "service_name", "ServiceName")),
            "operation_name": safe_scalar(_row_value(values, "operation_name", "OperationName")),
            "start_time": safe_scalar(_row_value(values, "start_time", "TraceFirstSpanStartTime")),
            "end_time": safe_scalar(_row_value(values, "end_time", "TraceLatestSpanEndTime")),
            "duration_ms": safe_scalar(_row_value(values, "duration_ms", "TraceDuration")),
            "status": safe_scalar(_row_value(values, "status", "TraceStatus")),
            "error_count": safe_scalar(_row_value(values, "error_count", "ErrorCount")),
            "span_count": safe_scalar(_row_value(values, "span_count", "SpanCount")),
        }

    def find_traces(
        self,
        *,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        service_name: str | None = None,
        operation_name: str | None = None,
        status: str | None = None,
        error_type: str | None = None,
        minimum_duration_ms: int | None = None,
        trace_id: str | None = None,
        sort_by: str = "duration",
        sort_order: str = "desc",
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            window = self._resolve_window(
                start_time, end_time, maximum=MAX_RAW_WINDOW, allow_default=True
            )
            validated_limit = validate_limit(limit, maximum=MAX_RAW_ROWS)
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
            query = build_find_traces_query(
                service_name=service_name,
                operation_name=operation_name,
                status=status,
                error_type=error_type,
                minimum_duration_ms=minimum_duration_ms,
                trace_id=trace_id,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=validated_limit,
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            response, request_id = self._execute_query(
                domain_id=domain_id,
                window=window,
                query=query,
                limit=validated_limit,
                page=validated_page,
            )
            traces = [self._trace_query_row(row) for row in self._query_rows(response)]
            return ToolResponse(
                status="success" if traces else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                time_window=_time_window(window),
                data={"traces": traces, "count": len(traces), "query_mode": "deterministic"},
                pagination=Pagination(next_page=_next_page(response), truncated=False),
                warnings=self._query_warnings(response),
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id, window=window)

    def run_trace_query(
        self,
        *,
        query: str,
        start_time: str,
        end_time: str,
        apm_domain_id: str | None = None,
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        if not self._settings.enable_expert_query:
            return self._invalid(
                InputValidationError(
                    "expert_query_disabled",
                    "Expert queries are disabled; use find_traces or enable them at startup.",
                ),
                started,
            )
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            category: QueryCategory = validate_expert_query(query, limit=limit)
            maximum_rows = MAX_AGGREGATE_ROWS if category == "aggregate" else MAX_RAW_ROWS
            maximum_window = MAX_AGGREGATE_WINDOW if category == "aggregate" else MAX_RAW_WINDOW
            validated_limit = validate_limit(limit, maximum=maximum_rows)
            window = self._resolve_window(
                start_time, end_time, maximum=maximum_window, allow_default=False
            )
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            response, request_id = self._execute_query(
                domain_id=domain_id,
                window=window,
                query=query.strip(),
                limit=validated_limit,
                page=validated_page,
            )
            rows: list[dict[str, Any]] = []
            redacted_fields = 0
            omitted_fields = 0
            for row in self._query_rows(response):
                safe_row, redacted, omitted = sanitize_mapping(row)
                rows.append(safe_row)
                redacted_fields += redacted
                omitted_fields += omitted
            return ToolResponse(
                status="success" if rows else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                time_window=_time_window(window),
                data={
                    "rows": rows,
                    "count": len(rows),
                    "query_category": category,
                    "redacted_field_count": redacted_fields,
                    "omitted_field_count": omitted_fields,
                },
                pagination=Pagination(next_page=_next_page(response), truncated=False),
                warnings=self._query_warnings(response),
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id, window=window)

    @staticmethod
    def _service_summaries(trace: Any) -> list[dict[str, Any]]:
        return [
            {
                "service_name": safe_scalar(getattr(item, "span_service_name", None)),
                "span_count": getattr(item, "total_spans", None),
                "error_span_count": getattr(item, "error_spans", None),
            }
            for item in (getattr(trace, "service_summaries", None) or [])[:50]
        ]

    @staticmethod
    def _span(span: Any, *, include_attributes: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "span_id": safe_scalar(getattr(span, "key", None)),
            "parent_span_id": safe_scalar(getattr(span, "parent_span_key", None)),
            "trace_id": safe_scalar(getattr(span, "trace_key", None)),
            "service_name": safe_scalar(getattr(span, "service_name", None)),
            "operation_name": safe_scalar(getattr(span, "operation_name", None)),
            "kind": safe_scalar(getattr(span, "kind", None)),
            "start_time": safe_scalar(getattr(span, "time_started", None)),
            "end_time": safe_scalar(getattr(span, "time_ended", None)),
            "duration_ms": getattr(span, "duration_in_ms", None),
            "is_error": getattr(span, "is_error", None),
            "source_name": safe_scalar(getattr(span, "source_name", None)),
            "logs_returned": False,
            "logs_omitted": bool(getattr(span, "logs", None)),
        }
        if include_attributes:
            attributes, redacted, omitted = sanitize_tags(getattr(span, "tags", None))
            result["attributes"] = attributes
            result["attribute_redacted_count"] = redacted
            result["attribute_omitted_count"] = omitted
        return result

    @classmethod
    def _trace(cls, trace: Any, *, include_attributes: bool, max_spans: int) -> dict[str, Any]:
        spans = getattr(trace, "spans", None) or []
        normalized_spans = [
            cls._span(span, include_attributes=include_attributes) for span in spans[:max_spans]
        ]
        return {
            "trace_id": safe_scalar(getattr(trace, "key", None)),
            "service_name": safe_scalar(getattr(trace, "root_span_service_name", None)),
            "operation_name": safe_scalar(getattr(trace, "root_span_operation_name", None)),
            "start_time": safe_scalar(getattr(trace, "time_earliest_span_started", None)),
            "end_time": safe_scalar(getattr(trace, "time_latest_span_ended", None)),
            "duration_ms": getattr(trace, "trace_duration_in_ms", None),
            "root_span_duration_ms": getattr(trace, "root_span_duration_in_ms", None),
            "status": safe_scalar(getattr(trace, "trace_status", None)),
            "is_fault": getattr(trace, "is_fault", None),
            "error_type": safe_scalar(getattr(trace, "trace_error_type", None)),
            "error_code": safe_scalar(getattr(trace, "trace_error_code", None)),
            "span_count": getattr(trace, "span_count", len(spans)),
            "error_span_count": getattr(trace, "error_span_count", None),
            "service_summaries": cls._service_summaries(trace),
            "spans": normalized_spans,
            "returned_span_count": len(normalized_spans),
            "omitted_span_count": max(0, len(spans) - len(normalized_spans)),
        }

    def _optional_lookup_window(
        self, start_time: str | None, end_time: str | None
    ) -> ValidatedWindow | None:
        if not start_time and not end_time:
            return None
        return self._resolve_window(
            start_time, end_time, maximum=MAX_RAW_WINDOW, allow_default=False
        )

    def get_trace(
        self,
        *,
        trace_id: str,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        include_span_attributes: bool = False,
        max_spans: int = 100,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_trace_id = validate_text(trace_id, field_name="trace_id", maximum_length=512)
            validated_max_spans = validate_limit(max_spans, maximum=MAX_TRACE_SPANS)
            window = self._optional_lookup_window(start_time, end_time)
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "trace_key": validated_trace_id,
                "trace_namespace": "TRACES",
                "opc_request_id": request_id,
            }
            if window:
                kwargs["time_trace_started_greater_than_or_equal_to"] = window.start
                kwargs["time_trace_started_less_than"] = window.end
            response = self._client_factory.trace_client().get_trace(**kwargs)
            return ToolResponse(
                status="success",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                time_window=_time_window(window) if window else None,
                data={
                    "trace": self._trace(
                        response.data,
                        include_attributes=include_span_attributes,
                        max_spans=validated_max_spans,
                    )
                },
                warnings=["Span attributes were explicitly requested and redacted."]
                if include_span_attributes
                else [],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id, window=window)

    def get_span(
        self,
        *,
        trace_id: str,
        span_id: str,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        include_attributes: bool = False,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_trace_id = validate_text(trace_id, field_name="trace_id", maximum_length=512)
            validated_span_id = validate_text(span_id, field_name="span_id", maximum_length=512)
            window = self._optional_lookup_window(start_time, end_time)
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "trace_key": validated_trace_id,
                "span_key": validated_span_id,
                "span_namespace": "TRACES",
                "opc_request_id": request_id,
            }
            if window:
                kwargs["time_span_started_greater_than_or_equal_to"] = window.start
                kwargs["time_span_started_less_than"] = window.end
            response = self._client_factory.trace_client().get_span(**kwargs)
            return ToolResponse(
                status="success",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                time_window=_time_window(window) if window else None,
                data={"span": self._span(response.data, include_attributes=include_attributes)},
                warnings=["Span attributes were explicitly requested and redacted."]
                if include_attributes
                else [],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id, window=window)

    @staticmethod
    def _snapshot_spans(
        span_snapshots: list[Any], *, maximum: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        result: list[dict[str, Any]] = []
        seen = 0

        def visit(items: list[Any]) -> None:
            nonlocal seen
            for item in items:
                seen += 1
                if len(result) < maximum:
                    children = getattr(item, "children", None) or []
                    result.append(
                        {
                            "span_id": safe_scalar(getattr(item, "key", None)),
                            "span_name": safe_scalar(getattr(item, "span_name", None)),
                            "start_time": safe_scalar(getattr(item, "time_started", None)),
                            "end_time": safe_scalar(getattr(item, "time_ended", None)),
                            "child_count": len(children),
                            "thread_snapshot_count": len(
                                getattr(item, "thread_snapshots", None) or []
                            ),
                            "details_omitted_count": len(
                                getattr(item, "span_snapshot_details", None) or []
                            ),
                        }
                    )
                visit(getattr(item, "children", None) or [])

        visit(span_snapshots)
        return result, max(0, seen - len(result))

    def get_trace_snapshot(
        self,
        *,
        trace_id: str,
        apm_domain_id: str | None = None,
        thread_id: str | None = None,
        snapshot_time: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_trace_id = validate_text(trace_id, field_name="trace_id", maximum_length=512)
            validated_thread = (
                validate_text(thread_id, field_name="thread_id", maximum_length=128)
                if thread_id
                else None
            )
            validated_snapshot_time = (
                validate_text(snapshot_time, field_name="snapshot_time", maximum_length=64)
                if snapshot_time
                else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "trace_key": validated_trace_id,
                "is_summarized": True,
                "opc_request_id": request_id,
            }
            if validated_thread:
                kwargs["thread_id"] = validated_thread
            if validated_snapshot_time:
                kwargs["snapshot_time"] = validated_snapshot_time
            response = self._client_factory.trace_client().get_trace_snapshot(**kwargs)
            snapshot = response.data
            span_snapshots, omitted = self._snapshot_spans(
                getattr(snapshot, "span_snapshots", None) or []
            )
            return ToolResponse(
                status="success" if span_snapshots else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                data={
                    "snapshot": {
                        "trace_id": safe_scalar(getattr(snapshot, "key", validated_trace_id)),
                        "start_time": safe_scalar(getattr(snapshot, "time_started", None)),
                        "end_time": safe_scalar(getattr(snapshot, "time_ended", None)),
                        "spans": span_snapshots,
                        "omitted_span_count": omitted,
                        "trace_details_omitted_count": len(
                            getattr(snapshot, "trace_snapshot_details", None) or []
                        ),
                        "summarized": True,
                    }
                },
                warnings=["Stack frames, thread details, and raw snapshot values are omitted."],
                partial=omitted > 0,
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id)
