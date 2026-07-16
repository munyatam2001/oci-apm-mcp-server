"""Allowlisted, bounded OCI APM Synthetic Monitoring reads."""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

from .client_factory import OciClientFactory, SyntheticClientFactory
from .config import Settings, mask_identifier
from .errors import normalize_error
from .guardrails import InputValidationError, MAX_RAW_ROWS, validate_limit, validate_text
from .models import Pagination, Scope, ToolResponse
from .sanitize import safe_scalar


_MONITOR_TYPES = frozenset(
    {"SCRIPTED_BROWSER", "BROWSER", "SCRIPTED_REST", "REST", "NETWORK", "DNS", "FTP", "SQL"}
)
_MONITOR_STATUSES = frozenset({"ENABLED", "DISABLED", "INVALID"})
_MONITOR_SORT_FIELDS = frozenset(
    {
        "displayName",
        "timeCreated",
        "timeUpdated",
        "status",
        "monitorType",
        "maintenanceWindowTimeStarted",
    }
)
_SORT_ORDERS = frozenset({"ASC", "DESC"})


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


def _items(response: Any) -> list[Any]:
    data = response.data
    if isinstance(data, list):
        return data
    return list(getattr(data, "items", None) or [])


class SyntheticService:
    """List safe monitor and public-vantage-point metadata without result artifacts."""

    def __init__(
        self,
        settings: Settings,
        client_factory: SyntheticClientFactory | None = None,
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

    def _invalid(self, error: InputValidationError, started: float) -> dict[str, Any]:
        return ToolResponse(
            status="needs_clarification" if error.code == "missing_scope" else "invalid_request",
            scope=self._scope(),
            data={"code": error.code, "message": error.safe_message, "oci_call_made": False},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    def _failure(
        self, error: Exception, started: float, request_id: str, domain_id: str
    ) -> dict[str, Any]:
        normalized = normalize_error(error)
        return ToolResponse(
            status=normalized.status,
            request_id=normalized.request_id or request_id,
            scope=self._scope(domain_id),
            data={"code": normalized.code, "message": normalized.message},
            timing_ms=_elapsed_ms(started),
        ).as_dict()

    @staticmethod
    def _vantage_point(item: Any) -> dict[str, Any]:
        return {
            "name": safe_scalar(getattr(item, "name", None)),
            "display_name": safe_scalar(getattr(item, "display_name", None)),
            "worker_list_returned": False,
        }

    @classmethod
    def _monitor(cls, item: Any) -> dict[str, Any]:
        schedule = getattr(item, "maintenance_window_schedule", None)
        return {
            "id": safe_scalar(getattr(item, "id", None)),
            "display_name": safe_scalar(getattr(item, "display_name", None)),
            "monitor_type": safe_scalar(getattr(item, "monitor_type", None)),
            "status": safe_scalar(getattr(item, "status", None)),
            "vantage_point_count": getattr(item, "vantage_point_count", None),
            "vantage_points": [
                cls._vantage_point(value)
                for value in (getattr(item, "vantage_points", None) or [])[:50]
            ],
            "script_id": safe_scalar(getattr(item, "script_id", None)),
            "script_name": safe_scalar(getattr(item, "script_name", None)),
            "repeat_interval_seconds": getattr(item, "repeat_interval_in_seconds", None),
            "timeout_seconds": getattr(item, "timeout_in_seconds", None),
            "is_run_once": getattr(item, "is_run_once", None),
            "scheduling_policy": safe_scalar(getattr(item, "scheduling_policy", None)),
            "batch_interval_seconds": getattr(item, "batch_interval_in_seconds", None),
            "is_ipv6": getattr(item, "is_i_pv6", None),
            "maintenance_window": {
                "start_time": safe_scalar(getattr(schedule, "time_started", None)),
                "end_time": safe_scalar(getattr(schedule, "time_ended", None)),
            }
            if schedule
            else None,
            "time_created": safe_scalar(getattr(item, "time_created", None)),
            "time_updated": safe_scalar(getattr(item, "time_updated", None)),
            "target_returned": False,
            "configuration_returned": False,
            "script_parameters_returned": False,
            "tags_returned": False,
            "creator_identity_returned": False,
        }

    @staticmethod
    def _public_vantage_point(item: Any) -> dict[str, Any]:
        geo = getattr(item, "geo", None)
        return {
            "name": safe_scalar(getattr(item, "name", None)),
            "display_name": safe_scalar(getattr(item, "display_name", None)),
            "geo": {
                "city_name": safe_scalar(getattr(geo, "city_name", None)),
                "country_code": safe_scalar(getattr(geo, "country_code", None)),
                "country_name": safe_scalar(getattr(geo, "country_name", None)),
            }
            if geo
            else None,
            "coordinates_returned": False,
        }

    def list_synthetic_monitors(
        self,
        *,
        apm_domain_id: str | None = None,
        display_name: str | None = None,
        monitor_type: str | None = None,
        status: str | None = None,
        sort_by: str = "displayName",
        sort_order: str = "ASC",
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        """List one bounded page of allowlisted monitor metadata."""
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_limit = validate_limit(limit, maximum=MAX_RAW_ROWS)
            validated_name = (
                validate_text(display_name, field_name="display_name") if display_name else None
            )
            normalized_type = monitor_type.upper() if monitor_type else None
            if normalized_type and normalized_type not in _MONITOR_TYPES:
                raise InputValidationError(
                    "invalid_filter",
                    "monitor_type must be SCRIPTED_BROWSER, BROWSER, SCRIPTED_REST, REST, NETWORK, DNS, FTP, or SQL.",
                )
            normalized_status = status.upper() if status else None
            if normalized_status and normalized_status not in _MONITOR_STATUSES:
                raise InputValidationError(
                    "invalid_filter", "status must be ENABLED, DISABLED, or INVALID."
                )
            if sort_by not in _MONITOR_SORT_FIELDS:
                raise InputValidationError("invalid_sort", "sort_by is not supported.")
            normalized_order = sort_order.upper()
            if normalized_order not in _SORT_ORDERS:
                raise InputValidationError("invalid_sort", "sort_order must be ASC or DESC.")
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "sort_by": sort_by,
                "sort_order": normalized_order,
                "limit": validated_limit,
                "opc_request_id": request_id,
            }
            if validated_name:
                kwargs["display_name"] = validated_name
            if normalized_type:
                kwargs["monitor_type"] = normalized_type
            if normalized_status:
                kwargs["status"] = normalized_status
            if validated_page:
                kwargs["page"] = validated_page
            response = self._client_factory.synthetic_client().list_monitors(**kwargs)
            monitors = [self._monitor(item) for item in _items(response)[:validated_limit]]
            next_page = _next_page(response)
            return ToolResponse(
                status="success" if monitors else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                data={"monitors": monitors, "count": len(monitors)},
                pagination=Pagination(next_page=next_page, truncated=bool(next_page)),
                warnings=["Additional monitor pages are available."] if next_page else [],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id)

    def get_synthetic_monitor(
        self, *, monitor_id: str, apm_domain_id: str | None = None
    ) -> dict[str, Any]:
        """Get one monitor through a strict output allowlist."""
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_monitor = validate_text(
                monitor_id, field_name="monitor_id", maximum_length=512
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            response = self._client_factory.synthetic_client().get_monitor(
                apm_domain_id=domain_id,
                monitor_id=validated_monitor,
                opc_request_id=request_id,
            )
            return ToolResponse(
                status="success",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                data={"monitor": self._monitor(response.data)},
                warnings=[
                    "Target, configuration, script parameters, tags, and creator identities are excluded."
                ],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id)

    def list_public_vantage_points(
        self,
        *,
        apm_domain_id: str | None = None,
        display_name: str | None = None,
        name: str | None = None,
        sort_by: str = "displayName",
        sort_order: str = "ASC",
        limit: int = 50,
        page: str | None = None,
    ) -> dict[str, Any]:
        """List one bounded page of public vantage points without coordinates."""
        started = perf_counter()
        try:
            domain_id = self._resolve_domain(apm_domain_id)
            validated_limit = validate_limit(limit, maximum=MAX_RAW_ROWS)
            validated_display = (
                validate_text(display_name, field_name="display_name") if display_name else None
            )
            validated_name = validate_text(name, field_name="name") if name else None
            if sort_by not in {"name", "displayName"}:
                raise InputValidationError("invalid_sort", "sort_by must be name or displayName.")
            normalized_order = sort_order.upper()
            if normalized_order not in _SORT_ORDERS:
                raise InputValidationError("invalid_sort", "sort_order must be ASC or DESC.")
            validated_page = (
                validate_text(page, field_name="page", maximum_length=2_048) if page else None
            )
        except InputValidationError as error:
            return self._invalid(error, started)

        request_id = uuid4().hex
        try:
            kwargs: dict[str, Any] = {
                "apm_domain_id": domain_id,
                "sort_by": sort_by,
                "sort_order": normalized_order,
                "limit": validated_limit,
                "opc_request_id": request_id,
            }
            if validated_display:
                kwargs["display_name"] = validated_display
            if validated_name:
                kwargs["name"] = validated_name
            if validated_page:
                kwargs["page"] = validated_page
            response = self._client_factory.synthetic_client().list_public_vantage_points(**kwargs)
            vantage_points = [
                self._public_vantage_point(item) for item in _items(response)[:validated_limit]
            ]
            next_page = _next_page(response)
            return ToolResponse(
                status="success" if vantage_points else "no_data",
                request_id=_request_id(response, request_id),
                scope=self._scope(domain_id),
                data={"vantage_points": vantage_points, "count": len(vantage_points)},
                pagination=Pagination(next_page=next_page, truncated=bool(next_page)),
                warnings=["Additional vantage-point pages are available."] if next_page else [],
                timing_ms=_elapsed_ms(started),
            ).as_dict()
        except Exception as error:
            return self._failure(error, started, request_id, domain_id)
