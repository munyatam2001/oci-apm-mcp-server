"""Foundation tools with no trace-query or mutation capability."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

from .client_factory import ApmDomainClientFactory, OciClientFactory
from .config import Settings, mask_identifier
from .errors import normalize_error
from .models import Scope, ToolResponse


def _response_request_id(response: Any, fallback: str) -> str:
    headers = getattr(response, "headers", None)
    if isinstance(headers, dict):
        value = headers.get("opc-request-id") or headers.get("Opc-Request-Id")
        if value:
            return str(value)
    return fallback


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


class FoundationService:
    """Implement the two approved foundation tools."""

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

    def get_current_context(self) -> dict[str, Any]:
        """Return masked startup context without performing an OCI call."""
        started = perf_counter()
        context = self._settings.safe_context()
        return ToolResponse(
            status="success",
            scope=self._scope(),
            data={
                "server_version": "0.1.0",
                "configuration": context,
                "registered_capabilities": ["get_current_context", "test_connection"],
            },
            warnings=(
                []
                if self._settings.read_only
                else [
                    "The process is configured with read_only=false, but this release has "
                    "no mutating tools."
                ]
            ),
            next_steps=[
                "Configure OCI_APM_DOMAIN_ID or OCI_APM_COMPARTMENT_ID before calling "
                "test_connection."
            ]
            if not self._settings.apm_domain_id and not self._settings.compartment_id
            else ["Call test_connection to verify OCI access."],
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    def test_connection(
        self,
        *,
        apm_domain_id: str | None = None,
        compartment_id: str | None = None,
    ) -> dict[str, Any]:
        """Verify OCI APM read access with one bounded control-plane call."""
        started = perf_counter()
        configured_domain = self._settings.apm_domain_id
        configured_compartment = self._settings.compartment_id

        domain_override_blocked = (
            apm_domain_id
            and configured_domain
            and apm_domain_id != configured_domain
            and not self._settings.allow_scope_override
        )
        compartment_override_blocked = (
            compartment_id
            and configured_compartment
            and compartment_id != configured_compartment
            and not self._settings.allow_scope_override
        )
        if domain_override_blocked or compartment_override_blocked:
            return ToolResponse(
                status="invalid_request",
                scope=self._scope(),
                data={
                    "code": "scope_override_blocked",
                    "message": "The requested scope differs from the locked startup scope.",
                    "oci_call_made": False,
                },
                next_steps=[
                    "Use the configured APM scope or restart the server with an approved scope."
                ],
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        effective_domain = apm_domain_id or self._settings.apm_domain_id
        effective_compartment = compartment_id or self._settings.compartment_id
        scope = self._scope(compartment_id=effective_compartment, apm_domain_id=effective_domain)

        if not effective_domain and not effective_compartment:
            return ToolResponse(
                status="needs_clarification",
                scope=scope,
                data={
                    "required": ["apm_domain_id or compartment_id"],
                    "oci_call_made": False,
                },
                next_steps=[
                    "Pass an APM domain OCID, a compartment OCID, or configure one at "
                    "server startup."
                ],
                timing_ms=_elapsed_ms(started),
            ).as_dict()

        client_request_id = uuid4().hex
        try:
            client = self._client_factory.apm_domain_client()
            data: dict[str, Any]
            if effective_domain:
                response = client.get_apm_domain(
                    apm_domain_id=effective_domain,
                    opc_request_id=client_request_id,
                )
                domain = response.data
                data = {
                    "connection": "ok",
                    "check": "get_apm_domain",
                    "domain": {
                        "id": mask_identifier(getattr(domain, "id", effective_domain)),
                        "display_name": getattr(domain, "display_name", None),
                        "lifecycle_state": getattr(domain, "lifecycle_state", None),
                        "is_free_tier": getattr(domain, "is_free_tier", None),
                    },
                }
            else:
                assert effective_compartment is not None
                response = client.list_apm_domains(
                    compartment_id=effective_compartment,
                    limit=1,
                    opc_request_id=client_request_id,
                )
                response_data = response.data
                items = (
                    response_data
                    if isinstance(response_data, list)
                    else (getattr(response_data, "items", []) or [])
                )
                data = {
                    "connection": "ok",
                    "check": "list_apm_domains",
                    "accessible_domain_sample_count": len(items),
                }

            return ToolResponse(
                status="success",
                request_id=_response_request_id(response, client_request_id),
                scope=scope,
                data=data,
                next_steps=["The server foundation is ready for the trace read-path milestone."],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            normalized = normalize_error(error)
            return ToolResponse(
                status=normalized.status,
                request_id=normalized.request_id or client_request_id,
                scope=scope,
                data={"code": normalized.code, "message": normalized.message},
                next_steps=[
                    "Verify the configured auth mode, region, APM scope, and OCI IAM policy."
                ],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
