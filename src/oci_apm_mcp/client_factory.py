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


class OciClientFactory:
    """Create OCI clients only when a tool actually requires an OCI call."""

    def __init__(self, settings: Settings, auth_provider: AuthProvider | None = None) -> None:
        self._settings = settings
        self._auth_provider = auth_provider or OciAuthProvider(settings)

    def apm_domain_client(self) -> Any:
        oci = import_module("oci")
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
        return oci.apm_control_plane.ApmDomainClient(**kwargs)
