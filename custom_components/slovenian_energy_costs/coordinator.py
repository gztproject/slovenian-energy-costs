"""Billing coordinator — interval processing and persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .billing.engine import BillingEngine
from .billing.net_metering import apply_interval_to_net_metering, create_year_state
from .billing.network_power import calculate_monthly_network_power
from .billing.providers import (
    align_interval_end,
    compute_physical_interval,
    make_interval_id,
)
from .billing.vat import apply_vat
from .const import (
    MODEL_NET_METERING,
    MODEL_SOUPORABA_DONOR,
    SETTLEMENT_SOUPORABA,
    TIMEZONE,
)
from .models import (
    ComputationQuality,
    MeterBaseline,
    MonthlyPeriodState,
    SettlementInterval,
    SiteConfig,
)
from .storage import BillingStore

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

TZ = ZoneInfo(TIMEZONE)


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


def _entity_kwh(hass: HomeAssistant, entity_id: str | None) -> Decimal | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    value = _to_decimal(state.state)
    if value is None:
        return None
    unit = (state.attributes.get("unit_of_measurement") or "").strip()
    if unit == "Wh":
        return value / Decimal("1000")
    return value


class BillingCoordinator:
    """Orchestrates settlement providers, billing engine, and storage."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: SiteConfig,
        store: BillingStore,
        *,
        souporaba_adapter: Any | None = None,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.config = config
        self.store = store
        self.engine = BillingEngine(config)
        self.souporaba_adapter = souporaba_adapter
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._current_prices: dict[str, Decimal | None] = {
            "supplier": None,
            "network": None,
            "levies": None,
            "variable": None,
        }
        self._last_status: str = "initializing"
        self.data = store.data

    @property
    def device_name(self) -> str:
        return self.config.site_name

    def add_update_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_setup(self) -> None:
        await self.store.async_load()
        self.data = self.store.data
        self._ensure_monthly()
        self._ensure_net_metering()
        self._refresh_prices(dt_util.now())

        # Schedule interval boundary processing
        minutes = list(range(0, 60, self.config.interval_minutes))
        delay = self.config.processing_delay

        async def _on_boundary(now: datetime) -> None:
            # Fire after processing delay via call_later semantics using now
            await self.async_process_due_intervals(now)

        # Track at :00/:15/... plus delay using second-based tracker approximation:
        # listen every minute and process when (minute % interval)==0 and second>=delay
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._handle_time_tick, second=delay
            )
        )

        entities = [
            e
            for e in (
                self.config.grid_import_entity,
                self.config.grid_export_entity,
                self.config.dynamic_price_entity,
                self.config.shared_energy_entity,
            )
            if e
        ]
        if self.config.souporaba_entities:
            entities.extend(self.config.souporaba_entities.values())

        if entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, entities, self._handle_state_change
                )
            )

        if self.souporaba_adapter is not None:
            await self.souporaba_adapter.async_setup(self._on_souporaba_intervals)

        self._last_status = "ready"
        self._notify()
        _ = minutes
        _ = _on_boundary

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self.souporaba_adapter is not None:
            await self.souporaba_adapter.async_unload()

    @callback
    def _handle_time_tick(self, now: datetime) -> None:
        local = now.astimezone(TZ) if now.tzinfo else now.replace(tzinfo=TZ)
        if local.minute % self.config.interval_minutes != 0:
            return
        self.hass.async_create_task(self.async_process_due_intervals(local))

    @callback
    def _handle_state_change(self, _event: Any) -> None:
        self._refresh_prices(dt_util.now())
        self._notify()
        if self.souporaba_adapter is not None:
            self.hass.async_create_task(self.souporaba_adapter.async_poll())

    async def _on_souporaba_intervals(
        self, intervals: list[SettlementInterval]
    ) -> None:
        for interval in intervals:
            await self._book_interval(interval)
        await self.store.async_save()
        self._notify()

    async def async_process_due_intervals(
        self, now: datetime | None = None
    ) -> None:
        now = now or dt_util.now()
        self._refresh_prices(now)
        self._ensure_monthly(now.date())
        self._ensure_net_metering(now.date())

        if self.config.settlement_source == SETTLEMENT_SOUPORABA:
            if self.souporaba_adapter is not None:
                intervals = await self.souporaba_adapter.get_completed_intervals()
                for interval in intervals:
                    await self._book_interval(interval)
        else:
            await self._process_physical(now)

        # Monthly power charge once per month
        await self._maybe_charge_monthly_power(now.date())
        await self.store.async_save()
        self._notify()

    async def _process_physical(self, now: datetime) -> None:
        import_kwh = _entity_kwh(self.hass, self.config.grid_import_entity)
        if import_kwh is None:
            self._last_status = "source_unavailable"
            self.data.billing_data_quality = ComputationQuality.INCOMPLETE.value
            return

        export_kwh = _entity_kwh(self.hass, self.config.grid_export_entity)
        interval_end = align_interval_end(now, self.config.interval_minutes)

        if not self.data.baseline_initialized or self.data.meter_baseline is None:
            start = interval_end - timedelta(minutes=self.config.interval_minutes)
            self.data.meter_baseline = MeterBaseline(
                interval_id=make_interval_id(start),
                timestamp=interval_end,
                import_total_kwh=import_kwh,
                export_total_kwh=export_kwh,
            )
            self.data.baseline_initialized = True
            self._last_status = "baseline_initialized"
            return

        baseline = self.data.meter_baseline
        # Only process if we moved to a new boundary
        if baseline.timestamp >= interval_end:
            return

        interval, is_reset = compute_physical_interval(
            current_import_kwh=import_kwh,
            current_export_kwh=export_kwh,
            baseline=baseline,
            interval_end=interval_end,
            interval_minutes=self.config.interval_minutes,
        )

        # Advance baseline always
        start = interval_end - timedelta(minutes=self.config.interval_minutes)
        self.data.meter_baseline = MeterBaseline(
            interval_id=make_interval_id(start),
            timestamp=interval_end,
            import_total_kwh=import_kwh,
            export_total_kwh=export_kwh,
        )

        if is_reset or interval is None:
            self._last_status = "source_counter_reset"
            self.data.billing_data_quality = ComputationQuality.INCOMPLETE.value
            return

        # Optional shared energy from mirrored entity (donor without local Souporaba)
        if self.config.shared_energy_entity:
            shared_total = _entity_kwh(self.hass, self.config.shared_energy_entity)
            # Without baseline for shared, skip deduction this interval
            _ = shared_total

        await self._book_interval(interval)
        self._last_status = "ready"

    async def _book_interval(self, interval: SettlementInterval) -> None:
        if interval.interval_id in self.data.processed_interval_ids:
            return

        dynamic = None
        if self.config.dynamic_price_entity:
            dynamic = _to_decimal(
                getattr(
                    self.hass.states.get(self.config.dynamic_price_entity),
                    "state",
                    None,
                )
            )

        result = self.engine.calculate_interval(interval, dynamic_price=dynamic)

        if result.quality in {
            ComputationQuality.ACTUAL,
            ComputationQuality.ESTIMATED,
        }:
            self.data.counters.apply_interval(result)
            if self.data.monthly:
                self.data.monthly.supplier_energy_cost += result.supplier_energy_cost
                self.data.monthly.network_energy_cost += result.network_energy_cost
                self.data.monthly.vat += result.vat
                self.data.monthly.other_charges += result.applicable_levies
                self.data.monthly.estimated_invoice = (
                    self.data.monthly.supplier_energy_cost
                    + self.data.monthly.network_energy_cost
                    + self.data.monthly.network_power_cost
                    + self.data.monthly.other_charges
                    + self.data.monthly.vat
                    + self.config.fixed_monthly_supplier
                )

            models = set(self.config.billing_models)
            if models & {MODEL_NET_METERING, MODEL_SOUPORABA_DONOR}:
                if self.data.net_metering is None:
                    self._ensure_net_metering(interval.interval_start.date())
                assert self.data.net_metering is not None
                apply_interval_to_net_metering(
                    self.data.net_metering, interval, config=self.config
                )

        self.data.processed_interval_ids.append(interval.interval_id)
        self.data.last_processed_interval_id = interval.interval_id
        self.data.last_billing_result = result
        self.data.last_reconciliation_status = interval.reconciliation_status
        self.data.billing_data_quality = result.quality.value

        # Keep invoice total including fixed components booked so far
        if result.quality in {
            ComputationQuality.ACTUAL,
            ComputationQuality.ESTIMATED,
        }:
            # fixed monthly is applied in monthly power routine once
            pass

    async def _maybe_charge_monthly_power(self, today: date) -> None:
        monthly = self.data.monthly
        if monthly is None or monthly.power_charged:
            return
        if today.day < 1:
            return
        # Charge once after first successful interval of the month
        if not self.data.last_processed_interval_id:
            return

        amount, _charges, warnings = calculate_monthly_network_power(
            when=today,
            config=self.config,
            registry=self.engine.registry,
        )
        if warnings and amount == 0:
            return

        vat = apply_vat(amount, self.config.vat_rate)
        monthly.network_power_cost += amount
        monthly.vat += vat
        monthly.estimated_invoice = (
            monthly.supplier_energy_cost
            + monthly.network_energy_cost
            + monthly.network_power_cost
            + monthly.other_charges
            + monthly.vat
            + self.config.fixed_monthly_supplier
        )
        self.data.counters.network_power_cost_total += amount
        self.data.counters.vat_total += vat
        self.data.counters.invoice_cost_total += amount + vat
        if self.config.fixed_monthly_supplier and not monthly.power_charged:
            fixed = self.config.fixed_monthly_supplier
            fixed_vat = apply_vat(fixed, self.config.vat_rate)
            monthly.other_charges += fixed
            monthly.vat += fixed_vat
            self.data.counters.invoice_cost_total += fixed + fixed_vat
        monthly.power_charged = True

    def _ensure_monthly(self, today: date | None = None) -> None:
        today = today or dt_util.now().date()
        if (
            self.data.monthly is None
            or self.data.monthly.year != today.year
            or self.data.monthly.month != today.month
        ):
            self.data.monthly = MonthlyPeriodState(
                year=today.year, month=today.month
            )

    def _ensure_net_metering(self, today: date | None = None) -> None:
        today = today or dt_util.now().date()
        models = set(self.config.billing_models)
        if not models & {MODEL_NET_METERING, MODEL_SOUPORABA_DONOR}:
            return
        if (
            self.data.net_metering is None
            or self.data.net_metering.year != today.year
        ):
            self.data.net_metering = create_year_state(today.year, self.config)

    def _refresh_prices(self, when: datetime) -> None:
        dynamic = None
        if self.config.dynamic_price_entity:
            state = self.hass.states.get(self.config.dynamic_price_entity)
            if state is not None:
                dynamic = _to_decimal(state.state)
        try:
            supplier, network, levies, variable = self.engine.current_variable_price(
                when, dynamic_price=dynamic, include_vat=True
            )
            self._current_prices = {
                "supplier": supplier,
                "network": network,
                "levies": levies,
                "variable": variable,
            }
        except Exception:  # noqa: BLE001
            pass

    def get_price(self, key: str) -> Decimal | None:
        return self._current_prices.get(key)

    @property
    def status(self) -> str:
        return self._last_status
