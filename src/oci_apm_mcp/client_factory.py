"""Lazy construction of narrowly scoped OCI SDK clients."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol

from .auth import AuthProvider, OciAuthProvider
from .config import Settings


class ApmDomainClientFactory(Protocol):
    """Factory protocol consumed by the foundation service."""

    def apm_domain_client(self) -> Any:
        """Return a client supporting safe APM-domain read operations."""
        ...


class TraceClientFactory(ApmDomainClientFactory, Protocol):
    """Factory protocol consumed by Milestone 2 read services."""

    def query_client(self) -> Any:
        """Return a client supporting trace queries and Quick Picks."""
        ...

    def trace_client(self) -> Any:
        """Return a client supporting trace, span, and snapshot reads."""
        ...


class SyntheticClientFactory(ApmDomainClientFactory, Protocol):
    """Factory protocol consumed by the bounded synthetic read service."""

    def synthetic_client(self) -> Any:
        """Return a client supporting safe synthetic monitor reads."""
        ...


class OciClientFactory:
    """Create OCI clients only when a tool actually requires an OCI call."""

    def __init__(self, settings: Settings, auth_provider: AuthProvider | None = None) -> None:
        self._settings = settings
        self._auth_provider = auth_provider or OciAuthProvider(settings)

    def _client_kwargs(self) -> dict[str, Any]:
        """Build fresh SDK client arguments without retaining credentials."""
        session = self._auth_provider.create()
        kwargs: dict[str, Any] = {
            "config": session.config,
            "timeout": (
                self._settings.connect_timeout_seconds,
                self._settings.read_timeout_seconds,
            ),
        }
        if session.signer is not None:
            kwargs["signer"] = session.signer
        return kwargs

    def apm_domain_client(self) -> Any:
        oci = import_module("oci")
        return oci.apm_control_plane.ApmDomainClient(**self._client_kwargs())

    def query_client(self) -> Any:
        oci = import_module("oci")
        return oci.apm_traces.QueryClient(**self._client_kwargs())

    def trace_client(self) -> Any:
        oci = import_module("oci")
        return oci.apm_traces.TraceClient(**self._client_kwargs())

    def synthetic_client(self) -> Any:
        oci = import_module("oci")
        return oci.apm_synthetics.ApmSyntheticClient(**self._client_kwargs())
