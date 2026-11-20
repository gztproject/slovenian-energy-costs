"""Bounds for the monetary-reset audit trail.

These tests are the spec for the missing limit. They fail while every
reset appends another snapshot and the storage document keeps the whole
list. They pass when both of the following hold:

* A signed-in non-admin user can reset at most 8 times on one local day.
  The day is the calendar date of ``homeassistant.util.dt.now``, the same
  clock the audit timestamp uses. A rejected call must not change the
  coordinator or the storage file.
* The saved adjustments list keeps only the last 500 entries, including
  after a restart that loads the file from disk. 500 is the same bound
  already applied to processed interval ids.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.const import ERR_SERVICE_VALIDATION_ERROR
from homeassistant.components.websocket_api.http import URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    CLIENT_ID,
    MockUser,
    async_test_home_assistant,
)

from custom_components.slovenian_energy_costs import async_setup
from custom_components.slovenian_energy_costs.const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    SERVICE_RESET_MONETARY_COSTS,
)
from custom_components.slovenian_energy_costs.coordinator import BillingCoordinator
from custom_components.slovenian_energy_costs.models import SiteConfig
from custom_components.slovenian_energy_costs.storage import BillingStore, storage_key

LOCAL_TZ = ZoneInfo("Europe/Ljubljana")
MONETARY_RESET_DAILY_QUOTA = 8
STORED_ADJUSTMENT_LIMIT = 500
# More successful resets than the stored cap, spaced so each batch is on its
# own local day and outside a 24 hour window of the previous batch.
_EXTRA_SUCCESSFUL_RESETS = 4
_BATCHES = (
    STORED_ADJUSTMENT_LIMIT + _EXTRA_SUCCESSFUL_RESETS
) // MONETARY_RESET_DAILY_QUOTA


def _storage_path(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(STORAGE_DIR, storage_key(entry_id)))


async def _read_bytes(hass: HomeAssistant, path: Path) -> bytes:
    return await hass.async_add_executor_job(path.read_bytes)


async def _non_admin_token(hass: HomeAssistant) -> tuple[MockUser, str]:
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    assert group is not None
    user = MockUser(name="Household member", groups=[group]).add_to_hass(hass)
    assert user.is_active
    assert not user.is_owner
    assert not user.is_admin
    refresh = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    return user, hass.auth.async_create_access_token(refresh)


class _ServiceClient:
    """Signed-in websocket client calling the reset service."""

    def __init__(self, websocket: Any) -> None:
        self._ws = websocket
        self._next_id = 1

    async def reset(self, entry_id: str | None = None) -> dict[str, Any]:
        service_data: dict[str, str] = {}
        if entry_id is not None:
            service_data[ATTR_CONFIG_ENTRY_ID] = entry_id
        message_id = self._next_id
        self._next_id += 1
        await self._ws.send_json(
            {
                "id": message_id,
                "type": "call_service",
                "domain": DOMAIN,
                "service": SERVICE_RESET_MONETARY_COSTS,
                "service_data": service_data,
            }
        )
        result: dict[str, Any] = await self._ws.receive_json()
        assert result["id"] == message_id
        assert result["type"] == "result"
        return result

    async def close(self) -> None:
        await self._ws.close()


async def _connect(
    hass: HomeAssistant, aiohttp_client: Any, token: str
) -> tuple[Any, _ServiceClient]:
    assert await async_setup_component(hass, "websocket_api", {})
    http_client = await aiohttp_client(hass.http.app)
    websocket = await http_client.ws_connect(URL)
    greeting = await websocket.receive_json()
    assert greeting["type"] == TYPE_AUTH_REQUIRED
    await websocket.send_json({"type": TYPE_AUTH, "access_token": token})
    authenticated = await websocket.receive_json()
    assert authenticated["type"] == TYPE_AUTH_OK
    return http_client, _ServiceClient(websocket)


async def _start_site(
    hass: HomeAssistant, entry_id: str, site_config: SiteConfig
) -> BillingCoordinator:
    store = BillingStore(hass, entry_id)
    coordinator = BillingCoordinator(hass, entry_id, site_config, store)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry_id] = coordinator
    return coordinator


def _freeze_now(clock: dict[str, datetime], monkeypatch: pytest.MonkeyPatch) -> None:
    def now(time_zone: datetime.tzinfo | None = None) -> datetime:
        current = clock["current"]
        if time_zone is not None:
            return current.astimezone(time_zone)
        return current

    monkeypatch.setattr(dt_util, "now", now)


def _assert_rejected(result: dict[str, Any]) -> None:
    assert result["success"] is False
    assert result["error"]["code"] == ERR_SERVICE_VALIDATION_ERROR


async def _assert_unchanged(
    hass: HomeAssistant,
    path: Path,
    coordinator: BillingCoordinator,
    before_bytes: bytes,
    before_count: int,
) -> None:
    assert len(coordinator.data.adjustments) == before_count
    assert await _read_bytes(hass, path) == before_bytes


@pytest.fixture(scope="session", autouse=True)
def _pycares_shutdown_thread() -> None:
    """Start pycares' daemon before per-test thread snapshots.

    Home Assistant's HTTP setup destroys a c-ares channel, which starts this
    thread. The test helper treats any thread created during the test as a leak.
    """
    import pycares

    pycares._shutdown_manager.start()


@pytest.fixture
async def hass() -> Any:
    """Home Assistant with the real storage writer, not the mocked store."""
    async with async_test_home_assistant() as hass_instance:
        yield hass_instance
        await hass_instance.async_stop(force=True)


@pytest.fixture
async def local_clock(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> dict[str, datetime]:
    await hass.config.async_set_time_zone("Europe/Ljubljana")
    clock = {"current": datetime(2026, 6, 1, 12, 0, tzinfo=LOCAL_TZ)}
    _freeze_now(clock, monkeypatch)
    return clock


async def _reload_site(
    hass: HomeAssistant, entry_id: str, site_config: SiteConfig
) -> BillingCoordinator:
    """Start a new coordinator from the file on disk, as a restart does."""
    store = BillingStore(hass, entry_id)
    coordinator = BillingCoordinator(hass, entry_id, site_config, store)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry_id] = coordinator
    return coordinator


@pytest.mark.asyncio
async def test_single_site_reset_stops_after_daily_quota(
    hass: HomeAssistant,
    aiohttp_client: Any,
    socket_enabled: None,
    site_config: SiteConfig,
    local_clock: dict[str, datetime],
) -> None:
    """A non-admin loop against the only site cannot grow that site's file."""
    assert await async_setup(hass, {})
    _user, token = await _non_admin_token(hass)
    http_client, client = await _connect(hass, aiohttp_client, token)
    entry_id = uuid4().hex
    coordinator = await _start_site(hass, entry_id, site_config)
    coordinator.data.counters.supplier_energy_cost_total = Decimal("42.50")
    path = _storage_path(hass, entry_id)

    try:
        first = await client.reset()
        assert first["success"] is True
        saved = await _read_bytes(hass, path)
        assert b'"supplier_energy_cost_total":"42.50"' in saved.replace(b" ", b"")
        assert len(coordinator.data.adjustments) == 1

        for _ in range(MONETARY_RESET_DAILY_QUOTA - 1):
            local_clock["current"] += timedelta(seconds=1)
            allowed = await client.reset()
            assert allowed["success"] is True
        assert len(coordinator.data.adjustments) == MONETARY_RESET_DAILY_QUOTA

        restarted = await _reload_site(hass, entry_id, site_config)
        await coordinator.async_unload()
        coordinator = restarted
        assert len(coordinator.data.adjustments) == MONETARY_RESET_DAILY_QUOTA

        local_clock["current"] += timedelta(seconds=1)
        before_count = len(coordinator.data.adjustments)
        before_bytes = await _read_bytes(hass, path)
        _assert_rejected(await client.reset())
        await _assert_unchanged(hass, path, coordinator, before_bytes, before_count)

        local_clock["current"] += timedelta(days=2)
        next_day = await client.reset()
        assert next_day["success"] is True
        assert len(coordinator.data.adjustments) == MONETARY_RESET_DAILY_QUOTA + 1
    finally:
        await client.close()
        await http_client.close()
        await coordinator.async_unload()
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_named_entry_reset_caps_history_and_leaves_other_site(
    hass: HomeAssistant,
    aiohttp_client: Any,
    socket_enabled: None,
    site_config: SiteConfig,
    local_clock: dict[str, datetime],
) -> None:
    """The entry named in the call is the only one stored, and history is capped."""
    assert _BATCHES * MONETARY_RESET_DAILY_QUOTA == (
        STORED_ADJUSTMENT_LIMIT + _EXTRA_SUCCESSFUL_RESETS
    )
    assert await async_setup(hass, {})
    _user, token = await _non_admin_token(hass)
    http_client, client = await _connect(hass, aiohttp_client, token)
    targeted_id = uuid4().hex
    other_id = uuid4().hex
    targeted = await _start_site(hass, targeted_id, site_config)
    other = await _start_site(hass, other_id, site_config)
    other.data.counters.supplier_energy_cost_total = Decimal("7")
    path = _storage_path(hass, targeted_id)
    other_path = _storage_path(hass, other_id)
    stamps: list[str] = []

    try:
        for batch in range(_BATCHES):
            local_clock["current"] = datetime(
                2026, 6, 1, 12, 0, tzinfo=LOCAL_TZ
            ) + timedelta(days=2 * batch)
            for _ in range(MONETARY_RESET_DAILY_QUOTA):
                stamps.append(local_clock["current"].isoformat())
                allowed = await client.reset(targeted_id)
                assert allowed["success"] is True
                assert other.data.counters.supplier_energy_cost_total == Decimal("7")
                assert other.data.adjustments == []
                local_clock["current"] += timedelta(seconds=1)

            before_count = len(targeted.data.adjustments)
            before_bytes = await _read_bytes(hass, path)
            _assert_rejected(await client.reset(targeted_id))
            await _assert_unchanged(hass, path, targeted, before_bytes, before_count)
            assert not other_path.exists()

        assert len(stamps) == STORED_ADJUSTMENT_LIMIT + _EXTRA_SUCCESSFUL_RESETS
        document = await _read_bytes(hass, path)
        stored = _adjustments_in_document(document)
        assert len(stored) == STORED_ADJUSTMENT_LIMIT
        assert [item["timestamp"] for item in stored] == stamps[
            -STORED_ADJUSTMENT_LIMIT:
        ]

        reloaded = await _reload_site(hass, targeted_id, site_config)
        assert len(reloaded.data.adjustments) == STORED_ADJUSTMENT_LIMIT
        assert [item["timestamp"] for item in reloaded.data.adjustments] == stamps[
            -STORED_ADJUSTMENT_LIMIT:
        ]
        assert other.data.counters.supplier_energy_cost_total == Decimal("7")
        await reloaded.async_unload()
    finally:
        await client.close()
        await http_client.close()
        await targeted.async_unload()
        await other.async_unload()
        path.unlink(missing_ok=True)
        other_path.unlink(missing_ok=True)


def _adjustments_in_document(document: bytes) -> list[dict[str, Any]]:
    payload = json.loads(document)
    adjustments = payload["data"]["adjustments"]
    assert isinstance(adjustments, list)
    return adjustments
