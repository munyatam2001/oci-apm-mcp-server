"""Safe normalization of OCI and local failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ResponseStatus


@dataclass(frozen=True, slots=True)
class NormalizedError:
    """An error safe to expose to an MCP caller."""

    status: ResponseStatus
    code: str
    message: str
    request_id: str | None


def _request_id(error: BaseException) -> str | None:
    value = getattr(error, "request_id", None)
    if value:
        return str(value)
    headers = getattr(error, "headers", None)
    if isinstance(headers, dict):
        header_value = headers.get("opc-request-id") or headers.get("Opc-Request-Id")
        if header_value:
            return str(header_value)
    return None


def normalize_error(error: BaseException) -> NormalizedError:
    """Map failures without returning raw exception text or request payloads."""
    http_status: Any = getattr(error, "status", None)
    request_id = _request_id(error)

    if http_status == 400:
        return NormalizedError(
            "invalid_request", "invalid_request", "OCI rejected the request parameters.", request_id
        )
    if http_status in {401, 403}:
        return NormalizedError(
            "unauthorized",
            "oci_access_denied",
            "OCI authentication or authorization failed for the configured APM scope.",
            request_id,
        )
    if http_status == 404:
        return NormalizedError(
            "not_found",
            "apm_resource_not_found",
            "The requested APM resource was not found.",
            request_id,
        )
    if http_status == 429:
        return NormalizedError(
            "rate_limited",
            "oci_rate_limited",
            "OCI rate-limited the request. Retry after a short delay.",
            request_id,
        )
    if isinstance(error, (TimeoutError, ConnectionError)):
        return NormalizedError(
            "error",
            "oci_connection_failed",
            "Could not reach OCI within the configured timeout.",
            request_id,
        )
    return NormalizedError(
        "error", "unexpected_error", "The APM connectivity check failed.", request_id
    )
