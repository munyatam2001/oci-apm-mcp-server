"""Tests for safe error normalization."""

from typing import Any

import pytest

from oci_apm_mcp.errors import normalize_error


class FakeServiceError(Exception):
    def __init__(self, status: int, *, request_id: str | None = "request-id") -> None:
        super().__init__("SECRET raw backend payload")
        self.status = status
        self.request_id = request_id


@pytest.mark.parametrize(
    ("http_status", "status", "code"),
    [
        (400, "invalid_request", "invalid_request"),
        (401, "unauthorized", "oci_access_denied"),
        (403, "unauthorized", "oci_access_denied"),
        (404, "not_found", "apm_resource_not_found"),
        (429, "rate_limited", "oci_rate_limited"),
        (500, "error", "unexpected_error"),
    ],
)
def test_service_errors_are_safely_mapped(http_status: int, status: str, code: str) -> None:
    result = normalize_error(FakeServiceError(http_status))

    assert result.status == status
    assert result.code == code
    assert result.request_id == "request-id"
    assert "SECRET" not in result.message


@pytest.mark.parametrize("error", [TimeoutError("secret"), ConnectionError("secret")])
def test_connection_failures_do_not_echo_exception_text(error: BaseException) -> None:
    result = normalize_error(error)

    assert result.code == "oci_connection_failed"
    assert "secret" not in result.message


def test_request_id_can_be_read_from_headers() -> None:
    error: Any = RuntimeError("backend")
    error.headers = {"opc-request-id": "header-request-id"}

    assert normalize_error(error).request_id == "header-request-id"
