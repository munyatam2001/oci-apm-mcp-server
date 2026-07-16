"""Offline tests for bounded, allowlisted synthetic-monitor reads."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from oci_apm_mcp.config import Settings
from oci_apm_mcp.synthetic_service import SyntheticService


DOMAIN_ID = "ocid1.apmdomain.oc1..configured"


class FakeResponse:
    def __init__(self, data: Any, *, next_page: bool = True) -> None:
        self.data = data
        self.headers = {"opc-request-id": "synthetic-request"}
        if next_page:
            self.headers["opc-next-page"] = "next-page"


def monitor() -> Any:
    return SimpleNamespace(
        id="ocid1.apmsyntheticmonitor.oc1..synthetic",
        display_name="Synthetic Test Monitor",
        monitor_type="REST",
        status="ENABLED",
        vantage_point_count=1,
        vantage_points=[
            SimpleNamespace(
                name="public-vp-a",
                display_name="Public VP A",
                worker_list=["private-worker"],
            )
        ],
        script_id="ocid1.apmsyntheticscript.oc1..synthetic",
        script_name="Synthetic Test Script",
        repeat_interval_in_seconds=300,
        timeout_in_seconds=60,
        is_run_once=False,
        scheduling_policy="ROUND_ROBIN",
        batch_interval_in_seconds=10,
        is_i_pv6=False,
        maintenance_window_schedule=SimpleNamespace(
            time_started=datetime(2026, 7, 1, tzinfo=UTC),
            time_ended=datetime(2026, 7, 1, 1, tzinfo=UTC),
        ),
        time_created=datetime(2026, 6, 1, tzinfo=UTC),
        time_updated=datetime(2026, 7, 1, tzinfo=UTC),
        target="https://private-target.invalid/path?token=secret",
        configuration=SimpleNamespace(request_headers=[{"Authorization": "secret"}]),
        script_parameters=[SimpleNamespace(value="secret-parameter")],
        freeform_tags={"owner": "private-owner"},
        created_by="private-user",
    )


def public_vantage_point() -> Any:
    return SimpleNamespace(
        name="public-vp-a",
        display_name="Public VP A",
        geo=SimpleNamespace(
            city_name="Example City",
            country_code="EX",
            country_name="Example Country",
            latitude=12.34,
            longitude=56.78,
        ),
    )


class FakeSyntheticClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: BaseException | None = None

    def list_monitors(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("list_monitors", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(SimpleNamespace(items=[monitor()]))

    def get_monitor(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get_monitor", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(monitor(), next_page=False)

    def list_public_vantage_points(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(("list_public_vantage_points", kwargs))
        if self.error:
            raise self.error
        return FakeResponse(SimpleNamespace(items=[public_vantage_point()]), next_page=False)


class FakeFactory:
    def __init__(self, client: FakeSyntheticClient) -> None:
        self.client = client
        self.create_count = 0

    def synthetic_client(self) -> FakeSyntheticClient:
        self.create_count += 1
        return self.client

    def apm_domain_client(self) -> Any:
        raise AssertionError("not used")


class FakeServiceError(Exception):
    status = 403
    request_id = "synthetic-denied"


def test_list_monitors_is_bounded_filtered_paginated_and_allowlisted() -> None:
    client = FakeSyntheticClient()
    result = SyntheticService(
        Settings(apm_domain_id=DOMAIN_ID), FakeFactory(client)
    ).list_synthetic_monitors(
        display_name="Synthetic Test Monitor",
        monitor_type="rest",
        status="enabled",
        sort_by="timeUpdated",
        sort_order="desc",
        limit=25,
        page="page-1",
    )

    assert result["status"] == "success"
    assert result["request_id"] == "synthetic-request"
    assert result["pagination"] == {"next_page": "next-page", "truncated": True}
    item = result["data"]["monitors"][0]
    assert item["display_name"] == "Synthetic Test Monitor"
    assert item["target_returned"] is False
    assert item["configuration_returned"] is False
    assert item["script_parameters_returned"] is False
    assert item["tags_returned"] is False
    assert item["creator_identity_returned"] is False
    assert item["vantage_points"][0]["worker_list_returned"] is False
    serialized = str(result)
    for secret in (
        "private-target",
        "Authorization",
        "secret-parameter",
        "private-owner",
        "private-worker",
        "private-user",
    ):
        assert secret not in serialized
    _, kwargs = client.calls[0]
    assert kwargs["monitor_type"] == "REST"
    assert kwargs["status"] == "ENABLED"
    assert kwargs["sort_order"] == "DESC"
    assert kwargs["limit"] == 25
    assert kwargs["page"] == "page-1"


def test_get_monitor_excludes_all_sensitive_configuration() -> None:
    client = FakeSyntheticClient()
    result = SyntheticService(
        Settings(apm_domain_id=DOMAIN_ID), FakeFactory(client)
    ).get_synthetic_monitor(monitor_id="ocid1.apmsyntheticmonitor.oc1..synthetic")

    assert result["status"] == "success"
    assert result["data"]["monitor"]["monitor_type"] == "REST"
    assert "target" not in result["data"]["monitor"]
    assert "configuration" not in result["data"]["monitor"]
    assert "script_parameters" not in result["data"]["monitor"]
    assert client.calls[0][1]["apm_domain_id"] == DOMAIN_ID


def test_public_vantage_points_exclude_coordinates() -> None:
    client = FakeSyntheticClient()
    result = SyntheticService(
        Settings(apm_domain_id=DOMAIN_ID), FakeFactory(client)
    ).list_public_vantage_points(
        display_name="Public VP A", name="public-vp-a", sort_by="name", limit=10
    )

    assert result["status"] == "success"
    item = result["data"]["vantage_points"][0]
    assert item["geo"]["city_name"] == "Example City"
    assert item["coordinates_returned"] is False
    assert "latitude" not in item["geo"]
    assert "longitude" not in item["geo"]
    _, kwargs = client.calls[0]
    assert kwargs["display_name"] == "Public VP A"
    assert kwargs["name"] == "public-vp-a"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 201},
        {"monitor_type": "UNSUPPORTED"},
        {"status": "DELETED"},
        {"sort_by": "target"},
        {"sort_order": "SIDEWAYS"},
    ],
)
def test_invalid_monitor_inputs_fail_before_client_creation(kwargs: dict[str, Any]) -> None:
    factory = FakeFactory(FakeSyntheticClient())
    result = SyntheticService(Settings(apm_domain_id=DOMAIN_ID), factory).list_synthetic_monitors(
        **kwargs
    )

    assert result["status"] == "invalid_request"
    assert result["data"]["oci_call_made"] is False
    assert factory.create_count == 0


def test_missing_scope_and_override_fail_before_client_creation() -> None:
    factory = FakeFactory(FakeSyntheticClient())
    service = SyntheticService(Settings(), factory)
    missing = service.list_synthetic_monitors()
    blocked = SyntheticService(Settings(apm_domain_id=DOMAIN_ID), factory).get_synthetic_monitor(
        monitor_id="monitor-id", apm_domain_id="different-domain"
    )

    assert missing["status"] == "needs_clarification"
    assert blocked["data"]["code"] == "scope_override_blocked"
    assert factory.create_count == 0


def test_synthetic_backend_error_is_safely_mapped() -> None:
    client = FakeSyntheticClient()
    client.error = FakeServiceError("private backend payload")
    result = SyntheticService(
        Settings(apm_domain_id=DOMAIN_ID), FakeFactory(client)
    ).list_synthetic_monitors()

    assert result["status"] == "unauthorized"
    assert result["request_id"] == "synthetic-denied"
    assert "private backend payload" not in str(result)
