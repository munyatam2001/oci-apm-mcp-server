"""Offline tests for OCI authentication selection."""

from types import SimpleNamespace
from typing import Any

import pytest

from oci_apm_mcp import auth
from oci_apm_mcp.auth import OciAuthProvider
from oci_apm_mcp.config import Settings


class FakeConfig:
    def from_file(self, *, file_location: str, profile_name: str) -> dict[str, str]:
        assert file_location.endswith("oci-config")
        assert profile_name == "TEAM"
        return {"region": "us-ashburn-1", "tenancy": "tenancy-value"}


class FakePrincipalSigner:
    region = "eu-frankfurt-1"
    tenancy_id = "tenancy-value"


def fake_oci_module() -> Any:
    return SimpleNamespace(
        config=FakeConfig(),
        auth=SimpleNamespace(
            signers=SimpleNamespace(
                InstancePrincipalsSecurityTokenSigner=FakePrincipalSigner,
                get_resource_principals_signer=FakePrincipalSigner,
            )
        ),
    )


def test_config_file_auth_can_override_region(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(auth, "import_module", lambda _name: fake_oci_module())
    settings = Settings(
        auth_type="config_file",
        config_file=tmp_path / "oci-config",
        config_profile="TEAM",
        region="ap-mumbai-1",
    )

    session = OciAuthProvider(settings).create()

    assert session.config["region"] == "ap-mumbai-1"
    assert session.signer is None
    assert session.auth_type == "config_file"


@pytest.mark.parametrize("auth_type", ["instance_principal", "resource_principal"])
def test_principal_auth_builds_minimal_config(
    monkeypatch: pytest.MonkeyPatch, auth_type: str
) -> None:
    monkeypatch.setattr(auth, "import_module", lambda _name: fake_oci_module())

    session = OciAuthProvider(Settings(auth_type=auth_type)).create()

    assert session.config == {"region": "eu-frankfurt-1", "tenancy": "tenancy-value"}
    assert isinstance(session.signer, FakePrincipalSigner)


def test_principal_requires_a_region(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoRegionSigner:
        region = None

    module = fake_oci_module()
    module.auth.signers.InstancePrincipalsSecurityTokenSigner = NoRegionSigner
    monkeypatch.setattr(auth, "import_module", lambda _name: module)

    with pytest.raises(RuntimeError, match="region"):
        OciAuthProvider(Settings(auth_type="instance_principal")).create()
