"""Deterministic, bounded multi-call APM investigation workflows."""

from __future__ import annotations

from math import ceil
from time import perf_counter
from typing import Any, Protocol, cast

from .config import Settings, mask_identifier
from .guardrails import (
    InputValidationError,
    MAX_INVESTIGATION_RESULTS,
    MAX_INVESTIGATION_SAMPLE,
    MAX_INVESTIGATION_SPANS,
    MAX_RAW_WINDOW,
    validate_limit,
    validate_time_window,
)
from .models import ResponseStatus, Scope, TimeWindow, ToolResponse
from .trace_service import TraceService


class TraceReader(Protocol):
    """Narrow trace-service contract used by deterministic workflows."""

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
    ) -> dict[str, Any]: ...

    def get_trace(
        self,
        *,
        trace_id: str,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        include_span_attributes: bool = False,
        max_spans: int = 100,
    ) -> dict[str, Any]: ...


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int:
    number = _number(value)
    return max(0, int(number)) if number is not None else 0


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, ceil(percentile * len(ordered)) - 1)]


def _delta(current: float | int | None, baseline: float | int | None) -> dict[str, Any]:
    if current is None or baseline is None:
        return {"absolute": None, "percent": None}
    absolute = float(current) - float(baseline)
    percent = None if float(baseline) == 0 else round(absolute / float(baseline) * 100, 2)
    return {"absolute": round(absolute, 3), "percent": percent}


class InvestigationService:
    """Compose bounded TraceService reads without natural-language inference."""

    def __init__(self, settings: Settings, trace_service: TraceReader | None = None) -> None:
        self._settings = settings
        self._trace_service = trace_service or TraceService(settings)

    def _scope(self) -> Scope:
        return Scope(
            region=self._settings.region,
            compartment_id=mask_identifier(self._settings.compartment_id),
            apm_domain_id=mask_identifier(self._settings.apm_domain_id),
        )

    @staticmethod
    def _scope_from(response: dict[str, Any], fallback: Scope) -> Scope:
        try:
            return Scope.model_validate(response.get("scope", {}))
        except ValueError:
            return fallback

    @staticmethod
    def _window_from(response: dict[str, Any]) -> TimeWindow | None:
        value = response.get("time_window")
        if not value:
            return None
        try:
            return TimeWindow.model_validate(value)
        except ValueError:
            return None

    def _invalid(self, error: InputValidationError, started: float) -> dict[str, Any]:
        status: ResponseStatus = (
            "needs_clarification"
            if error.code in {"missing_scope", "missing_time"}
            else "invalid_request"
        )
        return ToolResponse(
            status=status,
            scope=self._scope(),
            data={"code": error.code, "message": error.safe_message, "oci_call_made": False},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _trace_summaries(response: dict[str, Any]) -> list[dict[str, Any]]:
        traces = response.get("data", {}).get("traces", [])
        return [item for item in traces if isinstance(item, dict)]

    @staticmethod
    def _failed(response: dict[str, Any]) -> bool:
        return response.get("status") not in {"success", "no_data"}

    @staticmethod
    def _oci_calls(response: dict[str, Any]) -> int:
        return 0 if response.get("data", {}).get("oci_call_made") is False else 1

    @staticmethod
    def _response_status(response: dict[str, Any]) -> ResponseStatus:
        status = response.get("status")
        allowed = {
            "success",
            "no_data",
            "needs_clarification",
            "invalid_request",
            "unauthorized",
            "not_found",
            "rate_limited",
            "partial",
            "error",
        }
        return cast(ResponseStatus, status if status in allowed else "error")

    def _workflow_failure(
        self,
        *,
        workflow: str,
        response: dict[str, Any],
        maximum_calls: int,
        calls_made: int,
        started: float,
    ) -> dict[str, Any]:
        data = response.get("data", {})
        return ToolResponse(
            status=self._response_status(response),
            request_id=response.get("request_id"),
            scope=self._scope_from(response, self._scope()),
            time_window=self._window_from(response),
            data={
                "workflow": workflow,
                "call_budget": {
                    "maximum_oci_calls": maximum_calls,
                    "oci_calls_made": calls_made,
                },
                "failed_step": {
                    "code": data.get("code", response.get("status", "error")),
                    "message": data.get("message", "The initial bounded read did not complete."),
                },
            },
            warnings=list(response.get("warnings", [])),
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _failure_warning(label: str, response: dict[str, Any]) -> str:
        data = response.get("data", {})
        code = data.get("code", response.get("status", "error"))
        return f"{label} did not complete ({code}); available evidence is partial."

    def investigate_latency(
        self,
        *,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        service_name: str | None = None,
        operation_name: str | None = None,
        minimum_duration_ms: int | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Find slow traces and inspect one representative trace within two OCI calls."""
        started = perf_counter()
        try:
            validated_top_n = validate_limit(top_n, maximum=MAX_INVESTIGATION_RESULTS)
        except InputValidationError as error:
            return self._invalid(error, started)

        search = self._trace_service.find_traces(
            apm_domain_id=apm_domain_id,
            start_time=start_time,
            end_time=end_time,
            service_name=service_name,
            operation_name=operation_name,
            minimum_duration_ms=minimum_duration_ms,
            sort_by="duration",
            sort_order="desc",
            limit=validated_top_n,
        )
        if self._failed(search):
            return self._workflow_failure(
                workflow="latency",
                response=search,
                maximum_calls=2,
                calls_made=self._oci_calls(search),
                started=started,
            )

        scope = self._scope_from(search, self._scope())
        window = self._window_from(search)
        traces = self._trace_summaries(search)
        common_data: dict[str, Any] = {
            "workflow": "latency",
            "call_budget": {"maximum_oci_calls": 2, "oci_calls_made": 1},
            "sample": {"returned_trace_count": len(traces), "maximum_trace_count": validated_top_n},
            "slow_traces": traces,
            "representative_trace": None,
        }
        if not traces:
            return ToolResponse(
                status="no_data",
                request_id=search.get("request_id"),
                scope=scope,
                time_window=window,
                data=common_data,
                warnings=list(search.get("warnings", [])),
                next_steps=["Expand the time window or relax the duration and operation filters."],
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        trace_id = traces[0].get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            return ToolResponse(
                status="partial",
                request_id=search.get("request_id"),
                scope=scope,
                time_window=window,
                data=common_data,
                warnings=[*search.get("warnings", []), "The slowest row had no usable trace ID."],
                next_steps=["Inspect a returned trace that has a trace ID."],
                partial=True,
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        detail = self._trace_service.get_trace(
            trace_id=trace_id,
            apm_domain_id=apm_domain_id,
            start_time=window.start if window else start_time,
            end_time=window.end if window else end_time,
            include_span_attributes=False,
            max_spans=MAX_INVESTIGATION_SPANS,
        )
        common_data["call_budget"]["oci_calls_made"] = 1 + self._oci_calls(detail)
        warnings = list(search.get("warnings", []))
        partial = self._failed(detail)
        if partial:
            warnings.append(self._failure_warning("Representative trace retrieval", detail))
        else:
            trace = detail.get("data", {}).get("trace", {})
            spans = [item for item in trace.get("spans", []) if isinstance(item, dict)]
            spans.sort(key=lambda item: _number(item.get("duration_ms")) or -1, reverse=True)
            common_data["representative_trace"] = {
                "trace_id": trace.get("trace_id"),
                "service_name": trace.get("service_name"),
                "operation_name": trace.get("operation_name"),
                "duration_ms": trace.get("duration_ms"),
                "status": trace.get("status"),
                "error_span_count": trace.get("error_span_count"),
                "longest_spans": spans[:validated_top_n],
                "returned_span_count": trace.get("returned_span_count"),
                "omitted_span_count": trace.get("omitted_span_count"),
            }
            warnings.extend(detail.get("warnings", []))

        return ToolResponse(
            status="partial" if partial else "success",
            request_id=search.get("request_id"),
            scope=scope,
            time_window=window,
            data=common_data,
            warnings=warnings,
            next_steps=[
                "Use the trace and span timing evidence to choose the next narrow read; timing alone does not establish root cause."
            ],
            partial=partial,
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    def investigate_errors(
        self,
        *,
        apm_domain_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        service_name: str | None = None,
        operation_name: str | None = None,
        error_type: str | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Find error-bearing traces and inspect one representative trace within two calls."""
        started = perf_counter()
        try:
            validated_top_n = validate_limit(top_n, maximum=MAX_INVESTIGATION_RESULTS)
        except InputValidationError as error:
            return self._invalid(error, started)

        search = self._trace_service.find_traces(
            apm_domain_id=apm_domain_id,
            start_time=start_time,
            end_time=end_time,
            service_name=service_name,
            operation_name=operation_name,
            error_type=error_type,
            sort_by="error_count",
            sort_order="desc",
            limit=MAX_INVESTIGATION_SAMPLE,
        )
        if self._failed(search):
            return self._workflow_failure(
                workflow="errors",
                response=search,
                maximum_calls=2,
                calls_made=self._oci_calls(search),
                started=started,
            )

        all_traces = self._trace_summaries(search)
        error_traces = [item for item in all_traces if _integer(item.get("error_count")) > 0][
            :validated_top_n
        ]
        scope = self._scope_from(search, self._scope())
        window = self._window_from(search)
        common_data: dict[str, Any] = {
            "workflow": "errors",
            "call_budget": {"maximum_oci_calls": 2, "oci_calls_made": 1},
            "sample": {
                "searched_trace_count": len(all_traces),
                "maximum_searched_trace_count": MAX_INVESTIGATION_SAMPLE,
                "returned_error_trace_count": len(error_traces),
                "maximum_error_trace_count": validated_top_n,
            },
            "error_traces": error_traces,
            "representative_trace": None,
        }
        if not error_traces:
            return ToolResponse(
                status="no_data",
                request_id=search.get("request_id"),
                scope=scope,
                time_window=window,
                data=common_data,
                warnings=[
                    *search.get("warnings", []),
                    "No trace with a positive span-error count appeared in the bounded sample.",
                ],
                next_steps=[
                    "Expand the time window or relax the service, operation, and error filters."
                ],
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        trace_id = error_traces[0].get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            return ToolResponse(
                status="partial",
                request_id=search.get("request_id"),
                scope=scope,
                time_window=window,
                data=common_data,
                warnings=[
                    *search.get("warnings", []),
                    "The highest-error row had no usable trace ID.",
                ],
                partial=True,
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        detail = self._trace_service.get_trace(
            trace_id=trace_id,
            apm_domain_id=apm_domain_id,
            start_time=window.start if window else start_time,
            end_time=window.end if window else end_time,
            include_span_attributes=False,
            max_spans=MAX_INVESTIGATION_SPANS,
        )
        common_data["call_budget"]["oci_calls_made"] = 1 + self._oci_calls(detail)
        warnings = list(search.get("warnings", []))
        partial = self._failed(detail)
        if partial:
            warnings.append(self._failure_warning("Representative error trace retrieval", detail))
        else:
            trace = detail.get("data", {}).get("trace", {})
            error_spans = [
                item
                for item in trace.get("spans", [])
                if isinstance(item, dict) and item.get("is_error") is True
            ][:MAX_INVESTIGATION_RESULTS]
            common_data["representative_trace"] = {
                "trace_id": trace.get("trace_id"),
                "service_name": trace.get("service_name"),
                "operation_name": trace.get("operation_name"),
                "status": trace.get("status"),
                "error_span_count": trace.get("error_span_count"),
                "error_spans": error_spans,
                "returned_span_count": trace.get("returned_span_count"),
                "omitted_span_count": trace.get("omitted_span_count"),
            }
            warnings.extend(detail.get("warnings", []))

        return ToolResponse(
            status="partial" if partial else "success",
            request_id=search.get("request_id"),
            scope=scope,
            time_window=window,
            data=common_data,
            warnings=warnings,
            next_steps=[
                "Inspect only the safe attributes needed to explain an error marker; error correlation alone does not establish root cause."
            ],
            partial=partial,
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _sample_metrics(traces: list[dict[str, Any]]) -> dict[str, Any]:
        durations = [
            value for item in traces if (value := _number(item.get("duration_ms"))) is not None
        ]
        error_traces = sum(_integer(item.get("error_count")) > 0 for item in traces)
        error_spans = sum(_integer(item.get("error_count")) for item in traces)
        return {
            "returned_trace_count": len(traces),
            "duration_observation_count": len(durations),
            "average_duration_ms": round(sum(durations) / len(durations), 3) if durations else None,
            "p95_duration_ms": _percentile(durations, 0.95),
            "error_trace_count": error_traces,
            "error_trace_rate": round(error_traces / len(traces), 4) if traces else None,
            "error_span_count": error_spans,
        }

    def compare_trace_windows(
        self,
        *,
        current_start_time: str,
        current_end_time: str,
        baseline_start_time: str,
        baseline_end_time: str,
        apm_domain_id: str | None = None,
        service_name: str | None = None,
        operation_name: str | None = None,
        sample_limit: int = MAX_INVESTIGATION_SAMPLE,
    ) -> dict[str, Any]:
        """Compare two bounded newest-trace samples using exactly two search calls."""
        started = perf_counter()
        try:
            current_window = validate_time_window(
                current_start_time, current_end_time, maximum=MAX_RAW_WINDOW
            )
            baseline_window = validate_time_window(
                baseline_start_time, baseline_end_time, maximum=MAX_RAW_WINDOW
            )
            validated_limit = validate_limit(sample_limit, maximum=MAX_INVESTIGATION_SAMPLE)
        except InputValidationError as error:
            return self._invalid(error, started)

        current = self._trace_service.find_traces(
            apm_domain_id=apm_domain_id,
            start_time=current_start_time,
            end_time=current_end_time,
            service_name=service_name,
            operation_name=operation_name,
            sort_by="start_time",
            sort_order="desc",
            limit=validated_limit,
        )
        baseline = self._trace_service.find_traces(
            apm_domain_id=apm_domain_id,
            start_time=baseline_start_time,
            end_time=baseline_end_time,
            service_name=service_name,
            operation_name=operation_name,
            sort_by="start_time",
            sort_order="desc",
            limit=validated_limit,
        )
        current_ok = not self._failed(current)
        baseline_ok = not self._failed(baseline)
        if not current_ok and not baseline_ok:
            return self._workflow_failure(
                workflow="window_comparison",
                response=current,
                maximum_calls=2,
                calls_made=self._oci_calls(current) + self._oci_calls(baseline),
                started=started,
            )

        current_traces = self._trace_summaries(current) if current_ok else []
        baseline_traces = self._trace_summaries(baseline) if baseline_ok else []
        current_metrics = self._sample_metrics(current_traces) if current_ok else None
        baseline_metrics = self._sample_metrics(baseline_traces) if baseline_ok else None
        warnings = [
            "Metrics describe bounded newest-trace samples, not full-window population aggregates."
        ]
        warnings.extend(current.get("warnings", []) if current_ok else [])
        warnings.extend(baseline.get("warnings", []) if baseline_ok else [])
        if current_window.end - current_window.start != baseline_window.end - baseline_window.start:
            warnings.append("The current and baseline windows have different durations.")
        if not current_ok:
            warnings.append(self._failure_warning("Current-window search", current))
        if not baseline_ok:
            warnings.append(self._failure_warning("Baseline-window search", baseline))

        comparisons: dict[str, Any] | None = None
        if current_metrics is not None and baseline_metrics is not None:
            comparisons = {
                key: _delta(current_metrics.get(key), baseline_metrics.get(key))
                for key in (
                    "returned_trace_count",
                    "average_duration_ms",
                    "p95_duration_ms",
                    "error_trace_rate",
                    "error_span_count",
                )
            }
            zero_baselines = [
                key
                for key, value in comparisons.items()
                if value["absolute"] is not None and value["percent"] is None
            ]
            if zero_baselines:
                warnings.append(
                    "Percentage deltas are unavailable where the baseline value is zero: "
                    + ", ".join(zero_baselines)
                    + "."
                )
            if min(len(current_traces), len(baseline_traces)) < 10:
                warnings.append(
                    "At least one window has fewer than 10 returned traces; interpret deltas cautiously."
                )

        scope_source = current if current_ok else baseline
        no_data = current_ok and baseline_ok and not current_traces and not baseline_traces
        partial = not (current_ok and baseline_ok)
        return ToolResponse(
            status="partial" if partial else ("no_data" if no_data else "success"),
            request_id=scope_source.get("request_id"),
            scope=self._scope_from(scope_source, self._scope()),
            data={
                "workflow": "window_comparison",
                "call_budget": {
                    "maximum_oci_calls": 2,
                    "oci_calls_made": self._oci_calls(current) + self._oci_calls(baseline),
                },
                "sample_limit_per_window": validated_limit,
                "current": {
                    "time_window": TimeWindow(
                        start=current_window.as_strings()[0], end=current_window.as_strings()[1]
                    ).model_dump(),
                    "metrics": current_metrics,
                },
                "baseline": {
                    "time_window": TimeWindow(
                        start=baseline_window.as_strings()[0], end=baseline_window.as_strings()[1]
                    ).model_dump(),
                    "metrics": baseline_metrics,
                },
                "deltas": comparisons,
            },
            warnings=warnings,
            next_steps=[
                "Use a larger approved sample or aggregate query before treating a sample delta as a trend."
            ],
            partial=partial,
            timing_ms=_elapsed_ms(started),
        ).as_dict()
