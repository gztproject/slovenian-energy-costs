"""Souporaba (energy_sharing) interoperability adapter.

Consumes public Home Assistant sensor states only. Does not import Souporaba
private manager APIs or recompute sharing settlement.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..const import SOUPORABA_DOMAIN, SOUPORABA_SENSOR_KEYS
from ..models import (
    ComputationQuality,
    SettlementInterval,
    SettlementSource,
)

REQUIRED_INTERVAL_KEYS = (
    "receiver_import_last_interval",
    "shared_energy_last_interval",
    "used_shared_last_interval",
    "unused_shared_last_interval",
    "billable_energy_last_interval",
)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"", "unknown", "unavailable", "none"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return dt_util.parse_datetime(str(value))


def discover_souporaba_entries(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Discover loaded energy_sharing config entries."""
    entries = hass.config_entries.async_entries(SOUPORABA_DOMAIN)
    result: list[dict[str, Any]] = []
    for entry in entries:
        result.append(
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "domain": entry.domain,
            }
        )
    return result


def map_souporaba_entities(
    hass: HomeAssistant, souporaba_entry_id: str
) -> dict[str, str]:
    """Map sensor keys to entity_ids for a Souporaba config entry."""
    registry = er.async_get(hass)
    mapping: dict[str, str] = {}
    for ent in registry.entities.values():
        if ent.domain != "sensor":
            continue
        # Match by config entry id (stable across renames)
        if ent.config_entry_id != souporaba_entry_id:
            continue
        unique_id = ent.unique_id or ""
        prefix = f"{souporaba_entry_id}_"
        if not unique_id.startswith(prefix):
            continue
        key = unique_id[len(prefix) :]
        if key in SOUPORABA_SENSOR_KEYS or key.endswith("_last_interval"):
            mapping[key] = ent.entity_id
    return mapping


def validate_entity_mapping(
    hass: HomeAssistant,
    souporaba_entry_id: str,
    entities: dict[str, str],
) -> list[str]:
    """Return list of validation problems."""
    problems: list[str] = []
    registry = er.async_get(hass)
    for key in REQUIRED_INTERVAL_KEYS:
        entity_id = entities.get(key)
        if not entity_id:
            problems.append(f"missing:{key}")
            continue
        entry = registry.async_get(entity_id)
        if entry is None:
            problems.append(f"unknown_entity:{key}")
            continue
        if entry.config_entry_id != souporaba_entry_id:
            problems.append(f"wrong_instance:{key}")
    return problems


class SouporabaAdapter:
    """Observes Souporaba interval sensors and emits SettlementInterval objects."""

    def __init__(
        self,
        hass: HomeAssistant,
        entities: dict[str, str],
        *,
        processed_ids: set[str] | None = None,
    ) -> None:
        self.hass = hass
        self.entities = entities
        self._processed_ids = processed_ids or set()
        self._pending: dict[str, dict[str, Any]] = {}
        self._unsub: Callable[[], None] | None = None
        self._callback: Callable[[list[SettlementInterval]], Awaitable[None]] | None = (
            None
        )
        self._emitted: list[SettlementInterval] = []

    async def async_setup(
        self,
        on_intervals: Callable[[list[SettlementInterval]], Awaitable[None]],
    ) -> None:
        self._callback = on_intervals
        entity_ids = list(self.entities.values())
        if entity_ids:
            self._unsub = async_track_state_change_event(
                self.hass, entity_ids, self._handle_state_change
            )

    async def async_unload(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_state_change(self, event: Event) -> None:
        self.hass.async_create_task(self.async_poll())

    async def async_poll(self) -> None:
        intervals = await self.get_completed_intervals()
        if intervals and self._callback is not None:
            await self._callback(intervals)

    async def get_completed_intervals(self) -> list[SettlementInterval]:
        """Collect a consistent interval snapshot and return new intervals."""
        snapshot = self._collect_snapshot()
        if snapshot is None:
            return []
        interval = self._to_interval(snapshot)
        if interval is None:
            return []
        if interval.interval_id in self._processed_ids:
            return []
        # Only emit when settlement_accumulated is True for financial booking;
        # still mark skipped IDs to avoid silent re-processing loops.
        if not interval.settlement_accumulated:
            self._processed_ids.add(interval.interval_id)
            return []
        self._processed_ids.add(interval.interval_id)
        self._emitted.append(interval)
        return [interval]

    def _collect_snapshot(self) -> dict[str, Any] | None:
        values: dict[str, Any] = {}
        interval_ids: set[str] = set()
        for key in REQUIRED_INTERVAL_KEYS:
            entity_id = self.entities.get(key)
            if not entity_id:
                return None
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {"unknown", "unavailable"}:
                return None
            attrs = state.attributes
            iid = attrs.get("interval_id")
            if not iid:
                return None
            interval_ids.add(str(iid))
            values[key] = {
                "state": state.state,
                "attributes": dict(attrs),
            }

        if len(interval_ids) != 1:
            return None

        # Optional sensors
        for key in (
            "provider_export_last_interval",
            "reconciliation_status",
            "operating_mode",
            "fixed_allocation_percentage_last_interval",
        ):
            entity_id = self.entities.get(key)
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            values[key] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }

        values["interval_id"] = next(iter(interval_ids))
        return values

    def _to_interval(self, snapshot: dict[str, Any]) -> SettlementInterval | None:
        primary = snapshot["shared_energy_last_interval"]["attributes"]
        start = _parse_dt(primary.get("interval_start"))
        end = _parse_dt(primary.get("interval_end"))
        if start is None or end is None:
            return None

        def qty(key: str) -> Decimal:
            return _to_decimal(snapshot[key]["state"]) or Decimal("0")

        accumulated = bool(primary.get("settlement_accumulated", False))
        recon = "not_configured"
        if "reconciliation_status" in snapshot:
            recon = str(snapshot["reconciliation_status"]["state"])

        operating_mode = primary.get("operating_mode")
        if "operating_mode" in snapshot:
            operating_mode = snapshot["operating_mode"]["state"]

        fixed_pct = None
        if "fixed_allocation_percentage_last_interval" in snapshot:
            fixed_pct = _to_decimal(
                snapshot["fixed_allocation_percentage_last_interval"]["state"]
            )

        export = Decimal("0")
        export_type = None
        if "provider_export_last_interval" in snapshot:
            export = _to_decimal(
                snapshot["provider_export_last_interval"]["state"]
            ) or Decimal("0")
            export_type = snapshot["provider_export_last_interval"]["attributes"].get(
                "source_type"
            )

        quality = ComputationQuality.ACTUAL
        if recon == "mismatch_warn":
            quality = ComputationQuality.ESTIMATED
        elif recon == "mismatch_skip":
            quality = ComputationQuality.INVALID
            accumulated = False

        return SettlementInterval(
            interval_id=str(snapshot["interval_id"]),
            interval_start=start,
            interval_end=end,
            physical_import_kwh=qty("receiver_import_last_interval"),
            physical_export_kwh=export,
            shared_allocated_kwh=qty("shared_energy_last_interval"),
            shared_used_kwh=qty("used_shared_last_interval"),
            shared_unused_kwh=qty("unused_shared_last_interval"),
            supplier_billable_kwh=qty("billable_energy_last_interval"),
            settlement_accumulated=accumulated,
            reconciliation_status=recon,
            operating_mode=str(operating_mode) if operating_mode else None,
            provider_export_source_type=str(export_type) if export_type else None,
            fixed_allocation_percentage=fixed_pct,
            source=SettlementSource.SOUPORABA,
            quality=quality,
        )
