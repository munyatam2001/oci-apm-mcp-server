"""Tests for startup configuration and safe context rendering."""

from pathlib import Path

import pytest

from oci_apm_mcp.config import ConfigurationError, Settings, mask_identifier


def test_defaults_are_read_only() -> None:
    settings = Settings.from_env({})

    assert settings.auth_type == "config_file"
    assert settings.read_only is True
    assert settings.enable_expert_query is False
    assert settings.config_profile == "DEFAULT"
    assert settings.connect_timeout_seconds == 10.0
    assert settings.read_timeout_seconds == 60.0


def test_environment_is_validated_and_normalized(tmp_path: Path) -> None:
    config_path = tmp_path / "oci-config"
    settings = Settings.from_env(
        {
            "OCI_APM_AUTH_TYPE": "INSTANCE_PRINCIPAL",
            "OCI_CONFIG_FILE": str(config_path),
            "OCI_CONFIG_PROFILE": "TEAM",
            "OCI_REGION": "ap-mumbai-1",
            "OCI_APM_COMPARTMENT_ID": "ocid1.compartment.example",
            "OCI_APM_DOMAIN_ID": "ocid1.apmdomain.example",
            "OCI_APM_ALLOW_SCOPE_OVERRIDE": "true",
            "OCI_APM_ENABLE_EXPERT_QUERY": "true",
            "OCI_APM_READ_ONLY": "yes",
            "OCI_APM_LOG_LEVEL": "warning",
            "OCI_APM_CONNECT_TIMEOUT_SECONDS": "3.5",
            "OCI_APM_READ_TIMEOUT_SECONDS": "45",
        }
    )

    assert settings.auth_type == "instance_principal"
    assert settings.config_file == config_path
    assert settings.config_profile == "TEAM"
    assert settings.region == "ap-mumbai-1"
    assert settings.read_only is True
    assert settings.allow_scope_override is True
    assert settings.enable_expert_query is True
    assert settings.log_level == "WARNING"
    assert settings.connect_timeout_seconds == 3.5
    assert settings.read_timeout_seconds == 45.0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("OCI_APM_AUTH_TYPE", "magic"),
        ("OCI_APM_READ_ONLY", "sometimes"),
        ("OCI_APM_ALLOW_SCOPE_OVERRIDE", "sometimes"),
        ("OCI_APM_ENABLE_EXPERT_QUERY", "sometimes"),
        ("OCI_APM_LOG_LEVEL", "verbose"),
        ("OCI_APM_CONNECT_TIMEOUT_SECONDS", "zero"),
        ("OCI_APM_READ_TIMEOUT_SECONDS", "0"),
        ("OCI_CONFIG_PROFILE", ""),
    ],
)
def test_invalid_values_fail_closed(key: str, value: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env({key: value})


def test_safe_context_masks_identifiers_and_omits_config_path() -> None:
    compartment = "ocid1.compartment.oc1..sensitiveexample"
    domain = "ocid1.apmdomain.oc1..sensitiveexample"
    settings = Settings(compartment_id=compartment, apm_domain_id=domain)

    result = settings.safe_context()

    assert result["compartment_id"] == mask_identifier(compartment)
    assert result["apm_domain_id"] == mask_identifier(domain)
    assert compartment not in str(result)
    assert domain not in str(result)
    assert "config_file" not in result


def test_short_identifier_is_fully_masked() -> None:
    assert mask_identifier("short") == "***"
    assert mask_identifier(None) is None
