"""Central tool safety classification and drift detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Iterable, Literal


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Safety metadata independently enforced by the server."""

    read_only: bool
    idempotent: bool
    destructive: bool
    open_world: bool


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "get_current_context": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=False
    ),
    "test_connection": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "list_apm_domains": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "get_apm_domain": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "list_apm_quick_picks": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "find_traces": ToolPolicy(read_only=True, idempotent=True, destructive=False, open_world=True),
    "run_trace_query": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "get_trace": ToolPolicy(read_only=True, idempotent=True, destructive=False, open_world=True),
    "get_span": ToolPolicy(read_only=True, idempotent=True, destructive=False, open_world=True),
    "get_trace_snapshot": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "investigate_latency": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "investigate_errors": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
    "compare_trace_windows": ToolPolicy(
        read_only=True, idempotent=True, destructive=False, open_world=True
    ),
}


DEFAULT_ROWS = 50
MAX_RAW_ROWS = 200
MAX_AGGREGATE_ROWS = 500
MAX_TRACE_SPANS = 500
MAX_INVESTIGATION_RESULTS = 10
MAX_INVESTIGATION_SAMPLE = 50
MAX_INVESTIGATION_SPANS = 50
MAX_QUERY_LENGTH = 4_000
MAX_RAW_WINDOW = timedelta(hours=24)
MAX_AGGREGATE_WINDOW = timedelta(days=7)
DEFAULT_WINDOW = timedelta(hours=1)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_AGGREGATE_QUERY = re.compile(
    r"\b(group\s+by|count\s*\(|sum\s*\(|avg\s*\(|min\s*\(|max\s*\(|percentile\s*\()",
    re.IGNORECASE,
)
_FIRST_ROWS = re.compile(r"\bfirst\s+(\d+)\s+rows\b", re.IGNORECASE)
_FORBIDDEN_QUERY_TOKENS = re.compile(
    r"\b(delete|update|insert|create|drop|alter|merge|execute|call|grant|revoke)\b",
    re.IGNORECASE,
)
_SENSITIVE_QUERY_FIELDS = re.compile(
    r"\b(sqltext|stacktrace|requestbody|responsebody|httpheaders?|cookies?|password|"
    r"authorization|accesstoken|refreshtoken|secret|username|userid|sessionid|url|queryparams?)\b",
    re.IGNORECASE,
)


class InputValidationError(ValueError):
    """Safe, structured rejection raised before any OCI client is created."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class ValidatedWindow:
    start: datetime
    end: datetime

    def as_strings(self) -> tuple[str, str]:
        return (_utc_string(self.start), _utc_string(self.end))


def _utc_string(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_utc_time(value: str, *, field_name: str) -> datetime:
    """Parse an RFC 3339 timestamp and require explicit timezone information."""
    cleaned = value.strip()
    if not cleaned:
        raise InputValidationError("missing_time", f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputValidationError(
            "invalid_time", f"{field_name} must be an RFC 3339 timestamp."
        ) from exc
    if parsed.tzinfo is None:
        raise InputValidationError(
            "invalid_time", f"{field_name} must include a timezone offset or Z."
        )
    return parsed.astimezone(UTC)


def validate_time_window(
    start_time: str,
    end_time: str,
    *,
    maximum: timedelta,
) -> ValidatedWindow:
    start = parse_utc_time(start_time, field_name="start_time")
    end = parse_utc_time(end_time, field_name="end_time")
    if start >= end:
        raise InputValidationError("invalid_time_window", "start_time must be before end_time.")
    if end - start > maximum:
        raise InputValidationError(
            "time_window_too_large",
            f"The requested time window exceeds {int(maximum.total_seconds() // 3600)} hours.",
        )
    return ValidatedWindow(start=start, end=end)


def default_time_window(*, now: datetime | None = None) -> ValidatedWindow:
    end = (now or datetime.now(UTC)).astimezone(UTC)
    return ValidatedWindow(start=end - DEFAULT_WINDOW, end=end)


def validate_limit(limit: int, *, maximum: int) -> int:
    if limit < 1 or limit > maximum:
        raise InputValidationError("invalid_limit", f"limit must be between 1 and {maximum}.")
    return limit


def validate_text(value: str, *, field_name: str, maximum_length: int = 256) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InputValidationError("invalid_filter", f"{field_name} must not be empty.")
    if len(cleaned) > maximum_length or _CONTROL_CHARACTERS.search(cleaned):
        raise InputValidationError("invalid_filter", f"{field_name} contains unsupported content.")
    return cleaned


QueryCategory = Literal["raw", "aggregate"]


def validate_expert_query(query: str, *, limit: int) -> QueryCategory:
    cleaned = query.strip()
    if not cleaned or len(cleaned) > MAX_QUERY_LENGTH:
        raise InputValidationError(
            "invalid_query", f"query must contain 1 to {MAX_QUERY_LENGTH} characters."
        )
    if _CONTROL_CHARACTERS.search(cleaned) or ";" in cleaned:
        raise InputValidationError("invalid_query", "query contains unsupported characters.")
    if not re.match(r"^show\s*(\(|\b)", cleaned, re.IGNORECASE):
        raise InputValidationError("invalid_query", "query must start with SHOW.")
    if not re.search(r"\b(traces|spans)\b", cleaned, re.IGNORECASE):
        raise InputValidationError("invalid_query", "query must read from traces or spans.")
    if re.search(r"\bbetween\b", cleaned, re.IGNORECASE):
        raise InputValidationError(
            "invalid_query", "BETWEEN is not allowed; use the explicit tool time window."
        )
    if _FORBIDDEN_QUERY_TOKENS.search(cleaned):
        raise InputValidationError("invalid_query", "query contains a forbidden operation.")
    if _SENSITIVE_QUERY_FIELDS.search(cleaned):
        raise InputValidationError(
            "sensitive_field_blocked", "query requests a field excluded by the security policy."
        )
    first_rows = [int(match) for match in _FIRST_ROWS.findall(cleaned)]
    if first_rows and max(first_rows) > limit:
        raise InputValidationError(
            "query_limit_mismatch", "FIRST n ROWS must not exceed the tool limit."
        )
    return "aggregate" if _AGGREGATE_QUERY.search(cleaned) else "raw"


def validate_tool_registry(tool_names: Iterable[str]) -> None:
    """Fail startup/tests if registered tools and policy classification drift apart."""
    registered = set(tool_names)
    classified = set(TOOL_POLICIES)
    missing = sorted(registered - classified)
    stale = sorted(classified - registered)
    if missing or stale:
        raise RuntimeError(f"Tool policy drift detected: missing={missing}, stale={stale}")
