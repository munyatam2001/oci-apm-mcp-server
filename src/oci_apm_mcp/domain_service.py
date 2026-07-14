"""Safe APM-domain discovery for Milestone 2."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

from .client_factory import ApmDomainClientFactory, OciClientFactory
from .config import Settings, mask_identifier
from .errors import normalize_error
from .guardrails import InputValidationError, MAX_RAW_ROWS, validate_limit, validate_text
from .models import Pagination, Scope, ToolResponse
from .sanitize import safe_scalar


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


class DomainService:
    """List and get APM domains without exposing data keys or upload endpoints."""

    def __init__(
        self,
        settings: Settings,
        client_factory: ApmDomainClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory or OciClientFactory(settings)

    def _scope(
        self, *, compartment_id: str | None = None, apm_domain_id: str | None = None
    ) -> Scope:
        return Scope(
            region=self._settings.region,
            compartment_id=mask_identifier(compartment_id or self._settings.compartment_id),
            apm_domain_id=mask_identifier(apm_domain_id or self._settings.apm_domain_id),
        )

    def _resolve_scope(self, explicit: str | None, configured: str | None, name: str) -> str:
        if (
            explicit
            and configured
            and explicit != configured
            and not self._settings.allow_scope_override
        ):
            raise InputValidationError(
                "scope_override_blocked",
                f"{name} differs from the locked startup scope.",
            )
        value = explicit or configured
        if not value:
            raise InputValidationError("missing_scope", f"{name} is required.")
        return validate_text(value, field_name=name, maximum_length=512)

    def _invalid(self, error: InputValidationError, started: float) -> dict[str, Any]:
        return ToolResponse(
            status="invalid_request" if error.code != "missing_scope" else "needs_clarification",
            scope=self._scope(),
            data={"code": error.code, "message": error.safe_message, "oci_call_made": False},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _domain(domain: Any) -> dict[str, Any]:
        return {
            "id": getattr(domain, "id", None),
            "display_name": safe_scalar(getattr(domain, "display_name", None)),
            "description": safe_scalar(getattr(domain, "description", None)),
            "lifecycle_state": safe_scalar(getattr(domain, "lifecycle_state", None)),
            "is_free_tier": getattr(domain, "is_free_tier", None),
            "compartment_id": mask_identifier(getattr(domain, "compartment_id", None)),
            "time_created": safe_scalar(getattr(domain, "time_created", None)),
            "time_updated": safe_scalar(getattr(domain, "time_updated", None)),
        }

    def list_apm_domains(
        self,
        *,
        compartment_id: str | None = None,
        display_name: str | None = None,
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            effective_compartment = self._resolve_scope(
                compartment_id, self._settings.compartment_id, "compartment_id"
            )
            validated_limit = validate_limit(limit, maximum=MAX_RAW_ROWS)
            validated_name = (
                validate_text(display_name, field_name="display_name") if display_name else None
            )
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "compartment_id": effective_compartment,
                "limit": validated_limit,
                "opc_request_id": request_id,
            }
            if validated_name:
                kwargs["display_name"] = validated_name
            if validated_page:
                kwargs["page"] = validated_page
            response = self._client_factory.apm_domain_client().list_apm_domains(**kwargs)
            response_data = response.data
            items = (
                response_data
                if isinstance(response_data, list)
                else (getattr(response_data, "items", []) or [])
            )
            domains = [self._domain(item) for item in items[:validated_limit]]
            return ToolResponse(
                status="success" if domains else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(compartment_id=effective_compartment),
                data={"domains": domains, "count": len(domains)},
                pagination=Pagination(next_page=_next_page(response), truncated=False),
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            normalized = normalize_error(error)
            return ToolResponse(
                status=normalized.status,
                request_id=normalized.request_id or request_id,
                scope=self._scope(compartment_id=effective_compartment),
                data={"code": normalized.code, "message": normalized.message},
                timing_ms=_elapsed_ms(started),
            ).as_dict()

    def get_apm_domain(self, *, apm_domain_id: str | None = None) -> dict[str, Any]:
        started = perf_counter()
        try:
            effective_domain = self._resolve_scope(
                apm_domain_id, self._settings.apm_domain_id, "apm_domain_id"
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            response = self._client_factory.apm_domain_client().get_apm_domain(
                apm_domain_id=effective_domain,
                opc_request_id=request_id,
            )
            return ToolResponse(
                status="success",
                request_id=_request_id(response, request_id),
                scope=self._scope(apm_domain_id=effective_domain),
                data={"domain": self._domain(response.data)},
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            normalized = normalize_error(error)
            return ToolResponse(
                status=normalized.status,
                request_id=normalized.request_id or request_id,
                scope=self._scope(apm_domain_id=effective_domain),
                data={"code": normalized.code, "message": normalized.message},
                timing_ms=_elapsed_ms(started),
            ).as_dict()
