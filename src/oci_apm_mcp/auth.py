"""OCI signer construction isolated from tools and business services."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol

from .config import Settings


@dataclass(frozen=True, slots=True)
class AuthSession:
    """OCI SDK configuration and optional explicit signer."""

    config: dict[str, Any]
    signer: Any | None
    auth_type: str


class AuthProvider(Protocol):
    """Protocol used by the client factory and offline tests."""

    def create(self) -> AuthSession:
        """Build an OCI authentication session."""
        ...


class OciAuthProvider:
    """Build OCI SDK authentication from immutable startup settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self) -> AuthSession:
        oci = import_module("oci")
        settings = self._settings

        if settings.auth_type == "config_file":
            config = oci.config.from_file(
                file_location=str(settings.config_file),
                profile_name=settings.config_profile,
            )
            if settings.region:
                config["region"] = settings.region
            return AuthSession(config=dict(config), signer=None, auth_type=settings.auth_type)

        if settings.auth_type == "instance_principal":
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        elif settings.auth_type == "resource_principal":
            signer = oci.auth.signers.get_resource_principals_signer()
        else:  # Defensive: Settings validation should make this unreachable.
            raise RuntimeError("Unsupported OCI authentication type")

        region = settings.region or getattr(signer, "region", None)
        if not region:
            raise RuntimeError("OCI region could not be determined for the selected principal")

        principal_config: dict[str, Any] = {"region": region}
        tenancy_id = getattr(signer, "tenancy_id", None)
        if tenancy_id:
            principal_config["tenancy"] = tenancy_id
        return AuthSession(
            config=principal_config,
            signer=signer,
            auth_type=settings.auth_type,
        )
