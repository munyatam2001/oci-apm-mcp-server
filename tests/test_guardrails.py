"""Tests for central tool classification."""

from datetime import UTC, datetime, timedelta

import pytest

from oci_apm_mcp.guardrails import (
    InputValidationError,
    TOOL_POLICIES,
    default_time_window,
    parse_utc_time,
    validate_expert_query,
    validate_limit,
    validate_time_window,
    validate_tool_registry,
)


def test_all_registered_tools_are_read_only_and_non_destructive() -> None:
    assert len(TOOL_POLICIES) == 13
    assert all(policy.read_only for policy in TOOL_POLICIES.values())
    assert all(policy.idempotent for policy in TOOL_POLICIES.values())
    assert not any(policy.destructive for policy in TOOL_POLICIES.values())


def test_registry_validation_accepts_exact_match() -> None:
    validate_tool_registry(set(TOOL_POLICIES))


@pytest.mark.parametrize(
    "names", [{"get_current_context"}, {"get_current_context", "test_connection", "unknown"}]
)
def test_registry_validation_detects_drift(names: set[str]) -> None:
    with pytest.raises(RuntimeError, match="drift"):
        validate_tool_registry(names)


def test_time_window_normalizes_offsets_to_utc() -> None:
    window = validate_time_window(
        "2026-07-13T10:00:00+05:30",
        "2026-07-13T11:00:00+05:30",
        maximum=timedelta(hours=24),
    )

    assert window.as_strings() == ("2026-07-13T04:30:00Z", "2026-07-13T05:30:00Z")


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        ("bad", "2026-07-13T11:00:00Z", "invalid_time"),
        ("2026-07-13T11:00:00Z", "2026-07-13T10:00:00Z", "invalid_time_window"),
        ("2026-07-11T10:00:00Z", "2026-07-13T10:00:00Z", "time_window_too_large"),
    ],
)
def test_invalid_time_windows_fail_before_oci(start: str, end: str, code: str) -> None:
    with pytest.raises(InputValidationError) as caught:
        validate_time_window(start, end, maximum=timedelta(hours=24))
    assert caught.value.code == code


def test_naive_time_and_invalid_limit_fail_closed() -> None:
    with pytest.raises(InputValidationError, match="timezone"):
        parse_utc_time("2026-07-13T10:00:00", field_name="start_time")
    with pytest.raises(InputValidationError) as caught:
        validate_limit(201, maximum=200)
    assert caught.value.code == "invalid_limit"


def test_default_window_is_exactly_one_hour() -> None:
    now = datetime(2026, 7, 13, 12, tzinfo=UTC)
    window = default_time_window(now=now)
    assert window.end - window.start == timedelta(hours=1)


def test_expert_query_classification_and_limits() -> None:
    assert validate_expert_query("show traces TraceId first 10 rows", limit=10) == "raw"
    assert (
        validate_expert_query(
            "show traces ServiceName, count(*) group by ServiceName first 10 rows",
            limit=10,
        )
        == "aggregate"
    )


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("delete traces", "invalid_query"),
        ("show traces SqlText", "sensitive_field_blocked"),
        ("show traces TraceId between now() and now()", "invalid_query"),
        ("show traces TraceId first 51 rows", "query_limit_mismatch"),
        ("show services ServiceName", "invalid_query"),
        ("show traces TraceId; show spans SpanId", "invalid_query"),
    ],
)
def test_expert_query_rejects_unsafe_or_unbounded_syntax(query: str, code: str) -> None:
    with pytest.raises(InputValidationError) as caught:
        validate_expert_query(query, limit=50)
    assert caught.value.code == code
