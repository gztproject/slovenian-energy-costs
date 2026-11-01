"""Sensor platform for Slovenian Energy Costs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import BillingCoordinator
from .tariffs.calendar import get_tariff_block

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SECSensorDescription(SensorEntityDescription):
    """Sensor description with value extractor."""

    value_fn: Callable[[BillingCoordinator], StateType | Decimal | datetime | None]
    attr_fn: Callable[[BillingCoordinator], dict[str, Any]] | None = None


def _dec(value: Decimal | None, places: str = "0.000001") -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal(places)))


SENSORS: tuple[SECSensorDescription, ...] = (
    SECSensorDescription(
        key="current_supplier_price",
        translation_key="current_supplier_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:currency-eur",
        value_fn=lambda c: _dec(c.get_price("supplier"), "0.00001"),
    ),
    SECSensorDescription(
        key="current_network_energy_price",
        translation_key="current_network_energy_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower",
        value_fn=lambda c: _dec(c.get_price("network"), "0.00001"),
    ),
    SECSensorDescription(
        key="current_levies_price",
        translation_key="current_levies_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:receipt-text",
        value_fn=lambda c: _dec(c.get_price("levies"), "0.00001"),
    ),
    SECSensorDescription(
        key="current_variable_price",
        translation_key="current_variable_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cash",
        value_fn=lambda c: _dec(c.get_price("variable"), "0.00001"),
        attr_fn=lambda c: {
            "includes_vat": True,
            "note": "Ordinary marginal cost before Souporaba settlement",
        },
    ),
    SECSensorDescription(
        key="grid_variable_cost_total",
        translation_key="grid_variable_cost_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash-clock",
        value_fn=lambda c: _dec(c.data.counters.grid_variable_cost_total, "0.01"),
    ),
    SECSensorDescription(
        key="supplier_energy_cost_total",
        translation_key="supplier_energy_cost_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:flash",
        value_fn=lambda c: _dec(c.data.counters.supplier_energy_cost_total, "0.01"),
    ),
    SECSensorDescription(
        key="network_energy_cost_total",
        translation_key="network_energy_cost_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-import",
        value_fn=lambda c: _dec(c.data.counters.network_energy_cost_total, "0.01"),
    ),
    SECSensorDescription(
        key="invoice_cost_total",
        translation_key="invoice_cost_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:file-document",
        value_fn=lambda c: _dec(c.data.counters.invoice_cost_total, "0.01"),
    ),
    SECSensorDescription(
        key="souporaba_savings_total",
        translation_key="souporaba_savings_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:piggy-bank",
        value_fn=lambda c: _dec(c.data.counters.souporaba_savings_total, "0.01"),
    ),
    SECSensorDescription(
        key="current_tariff_block",
        translation_key="current_tariff_block",
        icon="mdi:clock-outline",
        value_fn=lambda c: get_tariff_block(dt_util.now()).block,
    ),
    SECSensorDescription(
        key="current_supplier_tariff",
        translation_key="current_supplier_tariff",
        icon="mdi:label",
        value_fn=lambda c: (
            c.data.last_billing_result.supplier_tariff
            if c.data.last_billing_result
            else None
        ),
    ),
    SECSensorDescription(
        key="next_tariff_change",
        translation_key="next_tariff_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-end",
        value_fn=lambda c: get_tariff_block(dt_util.now()).next_transition,
    ),
    SECSensorDescription(
        key="month_estimated_invoice",
        translation_key="month_estimated_invoice",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:calendar-month",
        value_fn=lambda c: (
            _dec(c.data.monthly.estimated_invoice, "0.01") if c.data.monthly else None
        ),
    ),
    SECSensorDescription(
        key="month_supplier_energy_cost",
        translation_key="month_supplier_energy_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.monthly.supplier_energy_cost, "0.01")
            if c.data.monthly
            else None
        ),
    ),
    SECSensorDescription(
        key="month_network_energy_cost",
        translation_key="month_network_energy_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.monthly.network_energy_cost, "0.01")
            if c.data.monthly
            else None
        ),
    ),
    SECSensorDescription(
        key="month_network_power_cost",
        translation_key="month_network_power_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.monthly.network_power_cost, "0.01")
            if c.data.monthly
            else None
        ),
    ),
    SECSensorDescription(
        key="last_processed_interval",
        translation_key="last_processed_interval",
        icon="mdi:identifier",
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.data.last_processed_interval_id,
    ),
    SECSensorDescription(
        key="last_reconciliation_status",
        translation_key="last_reconciliation_status",
        icon="mdi:check-decagram",
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.data.last_reconciliation_status,
    ),
    SECSensorDescription(
        key="billing_data_quality",
        translation_key="billing_data_quality",
        icon="mdi:quality-high",
        value_fn=lambda c: c.data.billing_data_quality,
    ),
    SECSensorDescription(
        key="souporaba_allocated_energy_total",
        translation_key="souporaba_allocated_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _dec(
            c.data.counters.souporaba_allocated_energy_total, "0.001"
        ),
    ),
    SECSensorDescription(
        key="souporaba_used_energy_total",
        translation_key="souporaba_used_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _dec(c.data.counters.souporaba_used_energy_total, "0.001"),
    ),
    SECSensorDescription(
        key="souporaba_unused_energy_total",
        translation_key="souporaba_unused_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _dec(
            c.data.counters.souporaba_unused_energy_total, "0.001"
        ),
    ),
    SECSensorDescription(
        key="souporaba_supplier_savings_total",
        translation_key="souporaba_supplier_savings_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _dec(c.data.counters.souporaba_savings_total, "0.01"),
    ),
    SECSensorDescription(
        key="souporaba_unused_allocation_value_total",
        translation_key="souporaba_unused_allocation_value_total",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _dec(
            c.data.counters.unused_allocation_value_total, "0.01"
        ),
        attr_fn=lambda c: {
            "note": "Opportunity-cost estimate, not an invoice charge"
        },
    ),
    SECSensorDescription(
        key="souporaba_allocation_utilization",
        translation_key="souporaba_allocation_utilization",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            float(
                (
                    c.data.counters.souporaba_used_energy_total
                    / c.data.counters.souporaba_allocated_energy_total
                    * 100
                ).quantize(Decimal("0.01"))
            )
            if c.data.counters.souporaba_allocated_energy_total > 0
            else None
        ),
    ),
    SECSensorDescription(
        key="souporaba_last_settlement_status",
        translation_key="souporaba_last_settlement_status",
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.data.last_reconciliation_status,
    ),
    SECSensorDescription(
        key="souporaba_last_billed_interval",
        translation_key="souporaba_last_billed_interval",
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.data.last_processed_interval_id,
    ),
    SECSensorDescription(
        key="net_metering_balance",
        translation_key="net_metering_balance",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.net_metering.balance_kwh, "0.001")
            if c.data.net_metering
            else None
        ),
    ),
    SECSensorDescription(
        key="eligible_export",
        translation_key="eligible_export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.net_metering.eligible_export_kwh, "0.001")
            if c.data.net_metering
            else None
        ),
    ),
    SECSensorDescription(
        key="shared_energy_deducted",
        translation_key="shared_energy_deducted",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.net_metering.shared_deducted_kwh, "0.001")
            if c.data.net_metering
            else None
        ),
    ),
    SECSensorDescription(
        key="annual_import",
        translation_key="annual_import",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.net_metering.observed_import_kwh, "0.001")
            if c.data.net_metering
            else None
        ),
    ),
    SECSensorDescription(
        key="annual_export",
        translation_key="annual_export",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            _dec(c.data.net_metering.observed_export_kwh, "0.001")
            if c.data.net_metering
            else None
        ),
    ),
    SECSensorDescription(
        key="reserve_status",
        translation_key="reserve_status",
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            "complete"
            if c.data.net_metering and c.data.net_metering.history_complete
            else (
                "opening_balance_known"
                if c.data.net_metering
                and c.data.net_metering.opening_balance_kwh is not None
                else "incomplete_history"
                if c.data.net_metering
                else None
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BillingCoordinator = entry.runtime_data
    async_add_entities(
        [SlovenianEnergyCostsSensor(entry, coordinator, desc) for desc in SENSORS]
    )


class SlovenianEnergyCostsSensor(SensorEntity):
    """Sensor backed by the billing coordinator."""

    _attr_has_entity_name = True
    entity_description: SECSensorDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: BillingCoordinator,
        description: SECSensorDescription,
    ) -> None:
        self.entity_description = description
        self._entry = entry
        self._coordinator = coordinator
        self._unsub: Callable[[], None] | None = None
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        self._attr_translation_key = description.translation_key

    async def async_added_to_hass(self) -> None:
        self._unsub = self._coordinator.add_update_listener(self._handle_update)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    @callback
    def _update_state(self) -> None:
        value = self.entity_description.value_fn(self._coordinator)
        self._attr_native_value = value
        if self.entity_description.attr_fn:
            self._attr_extra_state_attributes = self.entity_description.attr_fn(
                self._coordinator
            )
        self._attr_available = value is not None or self.entity_description.key in {
            "billing_data_quality",
            "last_processed_interval",
            "last_reconciliation_status",
            "current_tariff_block",
            "next_tariff_change",
        }
