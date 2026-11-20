"""Authorization for the monetary-cost reset service.

Non-admin callers must be rejected before euro counters, monthly money, or
stored history change. These tests fail while the service is registered
without an administrator check.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockUser

from custom_components.slovenian_energy_costs.const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    SERVICE_RESET_MONETARY_COSTS,
)
from custom_components.slovenian_energy_costs.coordinator import BillingCoordinator
from custom_components.slovenian_energy_costs.models import (
    CostCounters,
    MonthlyPeriodState,
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)
from custom_components.slovenian_energy_costs.storage import BillingStore, storage_key


@pytest.fixture(scope="session", autouse=True)
def _pycares_shutdown_thread_before_cleanup() -> None:
    """pycares starts a daemon thread on the first HTTP client.

    The Home Assistant pytest plugin treats any thread created during a test
    as a leak. Start that thread during session setup so it is already running
    when each test records its baseline.
    """
    try:
        import pycares
    except ImportError:
        return
    pycares._shutdown_manager.start()


ENTRY_ALPHA = "site-entry-alpha"
ENTRY_BETA = "site-entry-beta"
INTERVAL_ALPHA = "20261120T080000Z"
INTERVAL_BETA = "20261120T081500Z"
SERVICE_URL = f"/api/services/{DOMAIN}/{SERVICE_RESET_MONETARY_COSTS}"


def _counters(amount: str, energy: str) -> CostCounters:
    money = Decimal(amount)
    kwh = Decimal(energy)
    return CostCounters(
        grid_variable_cost_total=money,
        supplier_energy_cost_total=money,
        network_energy_cost_total=money,
        network_power_cost_total=money,
        levies_total=money,
        vat_total=money,
        invoice_cost_total=money,
        souporaba_savings_total=money,
        unused_allocation_value_total=money,
        souporaba_allocated_energy_total=kwh,
        souporaba_used_energy_total=kwh,
        souporaba_unused_energy_total=kwh,
        annual_import_kwh=kwh,
        annual_export_kwh=kwh,
        shared_energy_deducted_kwh=kwh,
    )


def _monthly(amount: str) -> MonthlyPeriodState:
    money = Decimal(amount)
    return MonthlyPeriodState(
        year=2026,
        month=11,
        supplier_energy_cost=money,
        network_energy_cost=money,
        network_power_cost=money,
        other_charges=money,
        vat=money,
        estimated_invoice=money,
        power_charged=True,
    )


def _state(coordinator: BillingCoordinator) -> dict[str, object]:
    data = coordinator.data
    monthly = data.monthly
    assert monthly is not None
    return {
        "counters": coordinator.store.data.counters.to_dict(),
        "monthly": monthly.to_dict(),
        "processed_interval_ids": list(data.processed_interval_ids),
        "last_processed_interval_id": data.last_processed_interval_id,
        "adjustments": copy.deepcopy(data.adjustments),
    }


async def _install_site(
    hass: HomeAssistant,
    entry_id: str,
    site_config: SiteConfig,
    *,
    amount: str,
    energy: str,
    interval_id: str,
) -> BillingCoordinator:
    store = BillingStore(hass, entry_id)
    store.data.counters = _counters(amount, energy)
    store.data.monthly = _monthly(amount)
    store.data.processed_interval_ids = [interval_id]
    store.data.last_processed_interval_id = interval_id
    await store.async_save()
    coordinator = BillingCoordinator(hass, entry_id, site_config, store)
    hass.data.setdefault(DOMAIN, {})[entry_id] = coordinator
    return coordinator


@pytest.fixture
async def costs_hass(
    hass: HomeAssistant, enable_custom_integrations: None
) -> HomeAssistant:
    """Load the integration so it registers reset_monetary_costs."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "websocket_api", {})
    assert await async_setup_component(hass, "api", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, SERVICE_RESET_MONETARY_COSTS)
    return hass


async def _long_lived_access_token(hass: HomeAssistant, user: MockUser) -> str:
    """Mint the same kind of token the auth websocket command creates."""
    refresh_token = await hass.auth.async_create_refresh_token(
        user,
        client_name="household phone",
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3650),
    )
    return hass.auth.async_create_access_token(refresh_token)


async def _household_user(hass: HomeAssistant) -> MockUser:
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    assert group is not None
    user = MockUser(name="Household member", groups=[group]).add_to_hass(hass)
    assert user.is_admin is False
    return user


def _assert_unchanged(
    coordinator: BillingCoordinator,
    before: dict[str, object],
    stored_before: dict[str, object],
    hass_storage: dict[str, object],
    notified: list[str],
) -> None:
    got = _state(coordinator)
    assert got == before, (
        "cost state changed before the caller was refused: "
        f"supplier {before['counters']['supplier_energy_cost_total']} -> "
        f"{got['counters']['supplier_energy_cost_total']}, "
        f"invoice {before['counters']['invoice_cost_total']} -> "
        f"{got['counters']['invoice_cost_total']}, "
        f"monthly {before['monthly']['estimated_invoice']} -> "
        f"{got['monthly']['estimated_invoice']}, "
        f"intervals {before['processed_interval_ids']} -> "
        f"{got['processed_interval_ids']}, "
        f"adjustments {len(before['adjustments'])} -> {len(got['adjustments'])}, "
        f"listeners {notified}"
    )
    assert hass_storage[storage_key(coordinator.entry_id)] == stored_before
    assert notified == []


async def _call_websocket(
    hass: HomeAssistant, ws_client, access_token: str, service_data: dict[str, str]
) -> dict[str, object]:
    websocket = await ws_client(hass, access_token=access_token)
    await websocket.send_json_auto_id(
        {
            "type": "call_service",
            "domain": DOMAIN,
            "service": SERVICE_RESET_MONETARY_COSTS,
            "service_data": service_data,
        }
    )
    response: dict[str, object] = await websocket.receive_json()
    await hass.async_block_till_done()
    return response


def _assert_unauthorized(response: dict[str, object]) -> None:
    assert response["type"] == "result"
    assert response["success"] is False
    error = response["error"]
    assert isinstance(error, dict)
    assert error["code"] == "home_assistant_error"
    assert error["message"] == "Unauthorized"


@pytest.mark.parametrize(
    "service_data",
    [{}, {"config_entry_id": ""}, {"config_entry_id": ENTRY_ALPHA}],
)
async def test_non_admin_long_lived_token_cannot_reset_the_only_site(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_storage: dict,
    site_config: SiteConfig,
    service_data: dict[str, str],
) -> None:
    """A signed-in non-admin wipes the only site when the entry id is omitted."""
    user = await _household_user(costs_hass)
    token = await _long_lived_access_token(costs_hass, user)
    coordinator = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="124790.50",
        energy="101.5",
        interval_id=INTERVAL_ALPHA,
    )
    notified: list[str] = []
    coordinator.add_update_listener(lambda: notified.append("notified"))
    before = _state(coordinator)
    stored_before = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])

    response = await _call_websocket(costs_hass, hass_ws_client, token, service_data)

    _assert_unchanged(coordinator, before, stored_before, hass_storage, notified)
    _assert_unauthorized(response)


async def test_non_admin_service_api_cannot_reset_named_site(
    costs_hass: HomeAssistant,
    hass_client,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """POST /api/services as a non-admin must not zero the named site."""
    user = await _household_user(costs_hass)
    token = await _long_lived_access_token(costs_hass, user)
    alpha = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="124790.50",
        energy="101.5",
        interval_id=INTERVAL_ALPHA,
    )
    beta = await _install_site(
        costs_hass,
        ENTRY_BETA,
        site_config,
        amount="80.25",
        energy="12.0",
        interval_id=INTERVAL_BETA,
    )
    notified: list[str] = []
    alpha.add_update_listener(lambda: notified.append("alpha"))
    beta.add_update_listener(lambda: notified.append("beta"))
    alpha_before = _state(alpha)
    beta_before = _state(beta)
    alpha_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])
    beta_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_BETA)])

    client = await hass_client(access_token=token)
    response = await client.post(
        SERVICE_URL, json={ATTR_CONFIG_ENTRY_ID: ENTRY_ALPHA}
    )
    await costs_hass.async_block_till_done()

    _assert_unchanged(alpha, alpha_before, alpha_stored, hass_storage, notified)
    _assert_unchanged(beta, beta_before, beta_stored, hass_storage, [])
    assert response.status == 401


async def test_non_admin_websocket_cannot_reset_one_site_among_several(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """A dashboard service call naming one entry must not zero that site."""
    user = await _household_user(costs_hass)
    token = await _long_lived_access_token(costs_hass, user)
    alpha = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="124790.50",
        energy="101.5",
        interval_id=INTERVAL_ALPHA,
    )
    beta = await _install_site(
        costs_hass,
        ENTRY_BETA,
        site_config,
        amount="80.25",
        energy="12.0",
        interval_id=INTERVAL_BETA,
    )
    notified: list[str] = []
    alpha.add_update_listener(lambda: notified.append("alpha"))
    beta.add_update_listener(lambda: notified.append("beta"))
    alpha_before = _state(alpha)
    beta_before = _state(beta)
    alpha_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])
    beta_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_BETA)])

    response = await _call_websocket(
        costs_hass,
        hass_ws_client,
        token,
        {ATTR_CONFIG_ENTRY_ID: ENTRY_BETA},
    )

    _assert_unchanged(beta, beta_before, beta_stored, hass_storage, notified)
    _assert_unchanged(alpha, alpha_before, alpha_stored, hass_storage, [])
    _assert_unauthorized(response)


async def test_read_only_user_cannot_reset_named_site(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_read_only_user: MockUser,
    hass_read_only_access_token: str,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """A read-only signed-in user is not an administrator."""
    assert hass_read_only_user.is_admin is False
    coordinator = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="42.00",
        energy="7.5",
        interval_id=INTERVAL_ALPHA,
    )
    notified: list[str] = []
    coordinator.add_update_listener(lambda: notified.append("notified"))
    before = _state(coordinator)
    stored_before = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])

    response = await _call_websocket(
        costs_hass,
        hass_ws_client,
        hass_read_only_access_token,
        {ATTR_CONFIG_ENTRY_ID: ENTRY_ALPHA},
    )

    _assert_unchanged(coordinator, before, stored_before, hass_storage, notified)
    _assert_unauthorized(response)


async def test_omitted_entry_with_several_sites_does_not_wipe_any_site(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_access_token: str,
    hass_admin_user: MockUser,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """Missing entry id with several sites is a validation error, not a wipe."""
    assert hass_admin_user.is_admin is True
    alpha = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="10",
        energy="1",
        interval_id=INTERVAL_ALPHA,
    )
    beta = await _install_site(
        costs_hass,
        ENTRY_BETA,
        site_config,
        amount="20",
        energy="2",
        interval_id=INTERVAL_BETA,
    )
    alpha_before = _state(alpha)
    beta_before = _state(beta)
    alpha_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])
    beta_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_BETA)])

    response = await _call_websocket(
        costs_hass, hass_ws_client, hass_access_token, {}
    )

    assert response["success"] is False
    error = response["error"]
    assert isinstance(error, dict)
    assert error["code"] == "service_validation_error"
    assert _state(alpha) == alpha_before
    assert _state(beta) == beta_before
    assert hass_storage[storage_key(ENTRY_ALPHA)] == alpha_stored
    assert hass_storage[storage_key(ENTRY_BETA)] == beta_stored


async def test_unknown_entry_does_not_change_stored_costs(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_access_token: str,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """An entry id that is not configured must not zero a real site."""
    coordinator = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="10",
        energy="1",
        interval_id=INTERVAL_ALPHA,
    )
    before = _state(coordinator)
    stored_before = copy.deepcopy(hass_storage[storage_key(ENTRY_ALPHA)])

    response = await _call_websocket(
        costs_hass,
        hass_ws_client,
        hass_access_token,
        {ATTR_CONFIG_ENTRY_ID: "missing-site"},
    )

    assert response["success"] is False
    assert _state(coordinator) == before
    assert hass_storage[storage_key(ENTRY_ALPHA)] == stored_before


async def test_admin_reset_zeroes_only_the_named_site_and_keeps_interval_ids(
    costs_hass: HomeAssistant,
    hass_ws_client,
    hass_access_token: str,
    hass_admin_user: MockUser,
    hass_storage: dict,
    site_config: SiteConfig,
) -> None:
    """An administrator can reset one site; processed intervals stay put."""
    assert hass_admin_user.is_admin is True
    alpha = await _install_site(
        costs_hass,
        ENTRY_ALPHA,
        site_config,
        amount="124790.50",
        energy="101.5",
        interval_id=INTERVAL_ALPHA,
    )
    beta = await _install_site(
        costs_hass,
        ENTRY_BETA,
        site_config,
        amount="80.25",
        energy="12.0",
        interval_id=INTERVAL_BETA,
    )
    beta_before = _state(beta)
    beta_stored = copy.deepcopy(hass_storage[storage_key(ENTRY_BETA)])

    response = await _call_websocket(
        costs_hass,
        hass_ws_client,
        hass_access_token,
        {ATTR_CONFIG_ENTRY_ID: ENTRY_ALPHA},
    )

    assert response["success"] is True
    assert alpha.data.counters.supplier_energy_cost_total == Decimal("0")
    assert alpha.data.counters.invoice_cost_total == Decimal("0")
    assert alpha.data.counters.annual_import_kwh == Decimal("101.5")
    assert alpha.data.counters.annual_export_kwh == Decimal("101.5")
    assert alpha.data.monthly is not None
    assert alpha.data.monthly.supplier_energy_cost == Decimal("0")
    assert alpha.data.monthly.estimated_invoice == Decimal("0")
    assert alpha.data.monthly.power_charged is True
    assert alpha.data.processed_interval_ids == [INTERVAL_ALPHA]
    assert alpha.data.last_processed_interval_id == INTERVAL_ALPHA
    assert alpha.data.adjustments[-1]["type"] == "reset_monetary"
    assert _state(beta) == beta_before
    assert hass_storage[storage_key(ENTRY_BETA)] == beta_stored

    stored_alpha = hass_storage[storage_key(ENTRY_ALPHA)]["data"]
    assert stored_alpha["counters"]["supplier_energy_cost_total"] == "0"
    assert stored_alpha["counters"]["annual_import_kwh"] == "101.5"
    assert stored_alpha["processed_interval_ids"] == [INTERVAL_ALPHA]
    assert stored_alpha["monthly"]["estimated_invoice"] == "0"
    assert stored_alpha["monthly"]["power_charged"] is True

    await alpha._book_interval(
        SettlementInterval(
            interval_id=INTERVAL_ALPHA,
            interval_start=datetime(2026, 11, 20, 9, 0),
            interval_end=datetime(2026, 11, 20, 9, 15),
            physical_import_kwh=Decimal("5"),
            supplier_billable_kwh=Decimal("5"),
            source=SettlementSource.PHYSICAL,
        )
    )
    assert alpha.data.counters.supplier_energy_cost_total == Decimal("0")
    assert alpha.data.processed_interval_ids == [INTERVAL_ALPHA]
