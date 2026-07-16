"""Offline behavior tests for the approved foundation tools."""

from types import SimpleNamespace
from typing import Any

from oci_apm_mcp.config import Settings, mask_identifier
from oci_apm_mcp.foundation import FoundationService
from oci_apm_mcp.guardrails import TOOL_POLICIES


class FakeResponse:
    def __init__(self, data: Any, request_id: str = "oracle-request-id") -> None:
        self.data = data
        self.headers = {"opc-request-id": request_id}


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: BaseException | None = None

    def get_apm_domain(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(
            SimpleNamespace(
                id=kwargs["apm_domain_id"],
                display_name="Test Domain",
                lifecycle_state="ACTIVE",
                is_free_tier=False,
                data_keys=["must-not-leak"],
            )
        )

    def list_apm_domains(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("list", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(SimpleNamespace(items=[SimpleNamespace(id="hidden")]))


class FakeFactory:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.create_count = 0

    def apm_domain_client(self) -> FakeClient:
        self.create_count += 1
        return self.client


class FakeServiceError(Exception):
    status = 403
    request_id = "denied-request-id"


def test_current_context_is_offline_and_masked() -> None:
    domain_id = "ocid1.apmdomain.oc1..sensitivevalue"
    compartment_id = "ocid1.compartment.oc1..sensitivevalue"
    factory = FakeFactory(FakeClient())
    service = FoundationService(
        Settings(
            region="ap-mumbai-1",
            apm_domain_id=domain_id,
            compartment_id=compartment_id,
        ),
        factory,
    )

    result = service.get_current_context()

    assert result["status"] == "success"
    assert result["data"]["server_version"] == "0.4.0"
    assert result["scope"]["apm_domain_id"] == mask_identifier(domain_id)
    assert domain_id not in str(result)
    assert compartment_id not in str(result)
    assert factory.create_count == 0


def test_connection_requires_explicit_or_configured_scope_without_oci_call() -> None:
    factory = FakeFactory(FakeClient())

    result = FoundationService(Settings(), factory).test_connection()

    assert result["status"] == "needs_clarification"
    assert result["data"]["oci_call_made"] is False
    assert factory.create_count == 0


def test_connection_gets_one_domain_and_allowlists_output() -> None:
    domain_id = "ocid1.apmdomain.oc1..sensitivevalue"
    client = FakeClient()
    service = FoundationService(Settings(apm_domain_id=domain_id), FakeFactory(client))

    result = service.test_connection()

    assert result["status"] == "success"
    assert result["request_id"] == "oracle-request-id"
    assert result["data"]["check"] == "get_apm_domain"
    assert result["data"]["domain"]["display_name"] == "Test Domain"
    assert result["data"]["domain"]["id"] == mask_identifier(domain_id)
    assert domain_id not in str(result)
    assert "must-not-leak" not in str(result)
    assert client.calls[0][0] == "get"


def test_connection_lists_at_most_one_domain() -> None:
    compartment_id = "ocid1.compartment.oc1..sensitivevalue"
    client = FakeClient()
    service = FoundationService(Settings(compartment_id=compartment_id), FakeFactory(client))

    result = service.test_connection()

    assert result["status"] == "success"
    assert result["data"] == {
        "connection": "ok",
        "check": "list_apm_domains",
        "accessible_domain_sample_count": 1,
    }
    method, kwargs = client.calls[0]
    assert method == "list"
    assert kwargs["limit"] == 1
    assert kwargs["compartment_id"] == compartment_id


def test_tool_argument_scope_override_is_blocked_by_default() -> None:
    configured = "ocid1.apmdomain.oc1..configured"
    override = "ocid1.apmdomain.oc1..overridevalue"
    client = FakeClient()
    service = FoundationService(Settings(apm_domain_id=configured), FakeFactory(client))

    result = service.test_connection(apm_domain_id=override)

    assert result["status"] == "invalid_request"
    assert result["data"]["code"] == "scope_override_blocked"
    assert result["data"]["oci_call_made"] is False
    assert not client.calls


def test_tool_argument_scope_override_requires_startup_opt_in() -> None:
    configured = "ocid1.apmdomain.oc1..configured"
    override = "ocid1.apmdomain.oc1..overridevalue"
    client = FakeClient()
    service = FoundationService(
        Settings(apm_domain_id=configured, allow_scope_override=True),
        FakeFactory(client),
    )

    result = service.test_connection(apm_domain_id=override)

    assert result["status"] == "success"
    assert result["scope"]["apm_domain_id"] == mask_identifier(override)
    assert client.calls[0][1]["apm_domain_id"] == override


def test_connection_error_is_structured_and_safe() -> None:
    client = FakeClient()
    client.error = FakeServiceError("SECRET raw request")
    service = FoundationService(
        Settings(apm_domain_id="ocid1.apmdomain.oc1..example"), FakeFactory(client)
    )

    result = service.test_connection()

    assert result["status"] == "unauthorized"
    assert result["request_id"] == "denied-request-id"
    assert result["data"]["code"] == "oci_access_denied"
    assert "SECRET" not in str(result)


def test_non_read_only_configuration_warns_but_adds_no_mutations() -> None:
    result = FoundationService(
        Settings(read_only=False), FakeFactory(FakeClient())
    ).get_current_context()

    assert result["warnings"]
    assert result["data"]["registered_capabilities"] == sorted(TOOL_POLICIES)
