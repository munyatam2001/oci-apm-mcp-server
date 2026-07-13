"""Validated, startup-only configuration for the OCI APM MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Mapping


SUPPORTED_AUTH_TYPES = frozenset({"config_file", "instance_principal", "resource_principal"})
SUPPORTED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class ConfigurationError(ValueError):
    """Raised when startup configuration is invalid."""


def _parse_bool(value: str | None, *, default: bool, name: str) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


def _parse_positive_float(value: str | None, *, default: float, name: str) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return parsed


def mask_identifier(value: str | None) -> str | None:
    """Mask an OCI identifier while preserving enough context for troubleshooting."""
    if not value:
        return None
    if len(value) <= 12:
        return "***"
    return f"{value[:8]}...{value[-4:]}"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable server settings loaded once at process startup."""

    auth_type: str = "config_file"
    config_file: Path = Path("~/.oci/config")
    config_profile: str = "DEFAULT"
    region: str | None = None
    compartment_id: str | None = None
    apm_domain_id: str | None = None
    allow_scope_override: bool = False
    read_only: bool = True
    log_level: str = "INFO"
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, source: Mapping[str, str] | None = None) -> Settings:
        """Create settings from environment variables without reading secret values."""
        env = environ if source is None else source
        auth_type = env.get("OCI_APM_AUTH_TYPE", "config_file").strip().lower()
        if auth_type not in SUPPORTED_AUTH_TYPES:
            supported = ", ".join(sorted(SUPPORTED_AUTH_TYPES))
            raise ConfigurationError(f"OCI_APM_AUTH_TYPE must be one of: {supported}")

        log_level = env.get("OCI_APM_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in SUPPORTED_LOG_LEVELS:
            supported_levels = ", ".join(sorted(SUPPORTED_LOG_LEVELS))
            raise ConfigurationError(f"OCI_APM_LOG_LEVEL must be one of: {supported_levels}")

        config_file = Path(env.get("OCI_CONFIG_FILE", "~/.oci/config")).expanduser()
        profile = env.get("OCI_CONFIG_PROFILE", "DEFAULT").strip()
        if not profile:
            raise ConfigurationError("OCI_CONFIG_PROFILE must not be empty")

        return cls(
            auth_type=auth_type,
            config_file=config_file,
            config_profile=profile,
            region=env.get("OCI_REGION") or None,
            compartment_id=env.get("OCI_APM_COMPARTMENT_ID") or None,
            apm_domain_id=env.get("OCI_APM_DOMAIN_ID") or None,
            allow_scope_override=_parse_bool(
                env.get("OCI_APM_ALLOW_SCOPE_OVERRIDE"),
                default=False,
                name="OCI_APM_ALLOW_SCOPE_OVERRIDE",
            ),
            read_only=_parse_bool(
                env.get("OCI_APM_READ_ONLY"), default=True, name="OCI_APM_READ_ONLY"
            ),
            log_level=log_level,
            connect_timeout_seconds=_parse_positive_float(
                env.get("OCI_APM_CONNECT_TIMEOUT_SECONDS"),
                default=10.0,
                name="OCI_APM_CONNECT_TIMEOUT_SECONDS",
            ),
            read_timeout_seconds=_parse_positive_float(
                env.get("OCI_APM_READ_TIMEOUT_SECONDS"),
                default=60.0,
                name="OCI_APM_READ_TIMEOUT_SECONDS",
            ),
        )

    def safe_context(self) -> dict[str, object]:
        """Return configuration metadata that is safe to expose to an MCP caller."""
        return {
            "auth_type": self.auth_type,
            "region": self.region,
            "compartment_id": mask_identifier(self.compartment_id),
            "apm_domain_id": mask_identifier(self.apm_domain_id),
            "allow_scope_override": self.allow_scope_override,
            "read_only": self.read_only,
            "timeouts": {
                "connect_seconds": self.connect_timeout_seconds,
                "read_seconds": self.read_timeout_seconds,
            },
        }
