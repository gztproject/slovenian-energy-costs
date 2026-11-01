"""Number entities for agreed network power per tariff block."""

from __future__ import annotations

from decimal import Decimal

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MANUFACTURER, MODEL, NETWORK_BLOCKS
from .coordinator import BillingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BillingCoordinator = entry.runtime_data
    entities = [
        AgreedPowerNumber(entry, coordinator, block) for block in NETWORK_BLOCKS
    ]
    async_add_entities(entities)


class AgreedPowerNumber(NumberEntity, RestoreEntity):
    """Editable agreed power (dogovorjena moč) for one network block."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: BillingCoordinator,
        block: int,
    ) -> None:
        self._entry = entry
        self._coordinator = coordinator
        self._block = block
        self._attr_unique_id = f"{entry.entry_id}_agreed_power_b{block}"
        self._attr_translation_key = f"agreed_power_b{block}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.runtime_data.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        configured = entry.runtime_data.config.agreed_power.get(block)
        self._attr_native_value = float(configured) if configured else 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in {"unknown", "unavailable"}:
            try:
                self._attr_native_value = float(last.state)
            except ValueError:
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._entry.runtime_data.config.agreed_power[self._block] = Decimal(
            str(value)
        )
        self.async_write_ha_state()
