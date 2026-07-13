"""Tests for lazy, timeout-aware OCI client construction."""

from types import SimpleNamespace
from typing import Any

import pytest

from oci_apm_mcp import client_factory
from oci_apm_mcp.auth import AuthSession
from oci_apm_mcp.client_factory import OciClientFactory
from oci_apm_mcp.config import Settings


class FakeAuthProvider:
    def __init__(self, signer: Any | None) -> None:
        self.signer = signer

    def create(self) -> AuthSession:
        return AuthSession(
            config={"region": "ap-mumbai-1"}, signer=self.signer, auth_type="test"
        )


class RecordingClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_client_factory_applies_timeouts_and_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(
        apm_control_plane=SimpleNamespace(ApmDomainClient=RecordingClient)
    )
    monkeypatch.setattr(client_factory, "import_module", lambda _name: module)
    signer = object()
    factory = OciClientFactory(
        Settings(connect_timeout_seconds=2.0, read_timeout_seconds=9.0),
        auth_provider=FakeAuthProvider(signer),
    )

    client = factory.apm_domain_client()

    assert client.kwargs == {
        "config": {"region": "ap-mumbai-1"},
        "timeout": (2.0, 9.0),
        "signer": signer,
    }


def test_client_factory_omits_empty_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(
        apm_control_plane=SimpleNamespace(ApmDomainClient=RecordingClient)
    )
    monkeypatch.setattr(client_factory, "import_module", lambda _name: module)

    client = OciClientFactory(Settings(), FakeAuthProvider(None)).apm_domain_client()

    assert "signer" not in client.kwargs
