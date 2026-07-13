"""Offline tests for allowlisted APM-domain discovery."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from oci_apm_mcp.config import Settings, mask_identifier
from oci_apm_mcp.domain_service import DomainService


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.headers = {
            "opc-request-id": "domain-request-id",
            "opc-next-page": "next-page-token",
        }


class FakeDomainClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: BaseException | None = None

    @staticmethod
    def domain(domain_id: str) -> Any:
        return SimpleNamespace(
            id=domain_id,
            display_name="Test Domain",
            description="Safe description",
            lifecycle_state="ACTIVE",
            is_free_tier=False,
            compartment_id="ocid1.compartment.oc1..sensitive",
            time_created=datetime(2026, 7, 13, tzinfo=UTC),
            time_updated=datetime(2026, 7, 13, 1, tzinfo=UTC),
            data_upload_endpoint="https://secret-endpoint.example",
            data_keys=["secret-key"],
            freeform_tags={"owner": "private"},
        )

    def list_apm_domains(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("list", kwargs))
        if self.error:
            raise self.error
        return FakeResponse([self.domain("ocid1.apmdomain.oc1..listed")])

    def get_apm_domain(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(self.domain(kwargs["apm_domain_id"]))


class FakeFactory:
    def __init__(self, client: FakeDomainClient) -> None:
        self.client = client
        self.create_count = 0

    def apm_domain_client(self) -> FakeDomainClient:
        self.create_count += 1
        return self.client


class FakeServiceError(Exception):
    status = 403
    request_id = "domain-denied-request"


def test_list_domains_constructs_exact_bounded_request() -> None:
    compartment = "ocid1.compartment.oc1..configured"
    client = FakeDomainClient()
    service = DomainService(Settings(compartment_id=compartment), FakeFactory(client))

    result = service.list_apm_domains(display_name="Test Domain", limit=25, page="page-1")

    assert result["status"] == "success"
    assert result["request_id"] == "domain-request-id"
    assert result["pagination"]["next_page"] == "next-page-token"
    domain = result["data"]["domains"][0]
    assert domain["id"] == "ocid1.apmdomain.oc1..listed"
    assert domain["compartment_id"] == mask_identifier("ocid1.compartment.oc1..sensitive")
    assert "secret-key" not in str(result)
    assert "secret-endpoint" not in str(result)
    assert "owner" not in str(result)
    method, kwargs = client.calls[0]
    assert method == "list"
    assert kwargs["compartment_id"] == compartment
    assert kwargs["display_name"] == "Test Domain"
    assert kwargs["limit"] == 25
    assert kwargs["page"] == "page-1"


def test_get_domain_is_allowlist_based() -> None:
    domain_id = "ocid1.apmdomain.oc1..configured"
    client = FakeDomainClient()
    result = DomainService(Settings(apm_domain_id=domain_id), FakeFactory(client)).get_apm_domain()

    assert result["status"] == "success"
    assert result["data"]["domain"]["id"] == domain_id
    assert "data_keys" not in result["data"]["domain"]
    assert "data_upload_endpoint" not in result["data"]["domain"]
    assert client.calls[0][1]["apm_domain_id"] == domain_id


def test_domain_discovery_requires_scope_without_creating_client() -> None:
    factory = FakeFactory(FakeDomainClient())

    result = DomainService(Settings(), factory).list_apm_domains()

    assert result["status"] == "needs_clarification"
    assert result["data"]["oci_call_made"] is False
    assert factory.create_count == 0


def test_domain_scope_override_is_blocked_before_oci() -> None:
    configured = "ocid1.compartment.oc1..configured"
    factory = FakeFactory(FakeDomainClient())

    result = DomainService(Settings(compartment_id=configured), factory).list_apm_domains(
        compartment_id="ocid1.compartment.oc1..override"
    )

    assert result["status"] == "invalid_request"
    assert result["data"]["code"] == "scope_override_blocked"
    assert factory.create_count == 0


def test_domain_list_limit_is_rejected_before_oci() -> None:
    factory = FakeFactory(FakeDomainClient())
    result = DomainService(
        Settings(compartment_id="ocid1.compartment.oc1..configured"), factory
    ).list_apm_domains(limit=201)

    assert result["status"] == "invalid_request"
    assert result["data"]["code"] == "invalid_limit"
    assert factory.create_count == 0


def test_list_domain_error_is_safely_mapped() -> None:
    client = FakeDomainClient()
    client.error = FakeServiceError("raw secret")
    result = DomainService(
        Settings(compartment_id="ocid1.compartment.oc1..configured"), FakeFactory(client)
    ).list_apm_domains()

    assert result["status"] == "unauthorized"
    assert result["request_id"] == "domain-denied-request"
    assert "raw secret" not in str(result)


def test_get_domain_error_is_safely_mapped() -> None:
    client = FakeDomainClient()
    client.error = FakeServiceError("raw secret")
    result = DomainService(
        Settings(apm_domain_id="ocid1.apmdomain.oc1..configured"), FakeFactory(client)
    ).get_apm_domain()

    assert result["status"] == "unauthorized"
    assert result["request_id"] == "domain-denied-request"
