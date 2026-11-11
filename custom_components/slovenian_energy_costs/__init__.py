"""Slovenian Energy Costs Home Assistant integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_RESET_MONETARY_COSTS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .coordinator import BillingCoordinator
    from .models import SiteConfig

    type SlovenianEnergyCostsConfigEntry = ConfigEntry[BillingCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from YAML (unsupported — UI only)."""
    import voluptuous as vol
    from homeassistant.core import ServiceCall
    from homeassistant.exceptions import ServiceValidationError

    hass.data.setdefault(DOMAIN, {})

    async def _handle_reset_monetary_costs(call: ServiceCall) -> None:
        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        coordinators = hass.data.get(DOMAIN) or {}
        if entry_id:
            coordinator = coordinators.get(entry_id)
            if coordinator is None:
                raise ServiceValidationError(f"Unknown config entry: {entry_id}")
            await coordinator.async_reset_monetary_counters()
            return
        if len(coordinators) != 1:
            raise ServiceValidationError(
                f"config_entry_id required when {len(coordinators)} sites are configured"
            )
        await next(iter(coordinators.values())).async_reset_monetary_counters()

    if not hass.services.has_service(DOMAIN, SERVICE_RESET_MONETARY_COSTS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET_MONETARY_COSTS,
            _handle_reset_monetary_costs,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
                }
            ),
        )
    return True


def build_site_config(data: dict[str, Any]) -> SiteConfig:
    """Build SiteConfig from config entry data/options."""
    from decimal import Decimal

    from .const import (
        CONF_AGREED_POWER,
        CONF_BILLING_MODELS,
        CONF_CURRENCY,
        CONF_CUSTOMER_CATEGORY,
        CONF_DYNAMIC_PRICE_ENTITY,
        CONF_ENABLE_LEVIES,
        CONF_EXCISE_RATE,
        CONF_FIXED_MONTHLY_SUPPLIER,
        CONF_GRID_EXPORT_ENTITY,
        CONF_GRID_IMPORT_ENTITY,
        CONF_HAS_15MIN_MEASUREMENT,
        CONF_OVE_SPTE_RATE,
        CONF_PRICES_INCLUDE_VAT,
        CONF_SETTLEMENT_SOURCE,
        CONF_SHARED_ENERGY_ENTITY,
        CONF_SITE_NAME,
        CONF_SITE_ROLE,
        CONF_SOLAR_PRODUCTION_ENTITY,
        CONF_SOUPORABA_ENTITIES,
        CONF_SOUPORABA_ENTRY_ID,
        CONF_SUPPLIER_DISCOUNT_PCT,
        CONF_SUPPLIER_ET_PRICE,
        CONF_SUPPLIER_MARKUP_FIXED,
        CONF_SUPPLIER_MARKUP_PCT,
        CONF_SUPPLIER_MODE,
        CONF_SUPPLIER_MT_PRICE,
        CONF_SUPPLIER_VT_PRICE,
        CONF_VAT_RATE,
    )
    from .models import SiteConfig

    agreed_raw = data.get(CONF_AGREED_POWER) or {}
    agreed = {int(k): Decimal(str(v)) for k, v in agreed_raw.items() if v}

    def d(key: str, default: str = "0") -> Decimal:
        return Decimal(str(data.get(key, default)))

    return SiteConfig(
        site_name=str(data.get(CONF_SITE_NAME) or data.get("name") or "Site"),
        site_role=str(data.get(CONF_SITE_ROLE, "consumer")),
        currency=str(data.get(CONF_CURRENCY, "EUR")),
        billing_models=list(data.get(CONF_BILLING_MODELS) or ["conventional"]),
        grid_import_entity=data.get(CONF_GRID_IMPORT_ENTITY),
        grid_export_entity=data.get(CONF_GRID_EXPORT_ENTITY),
        solar_production_entity=data.get(CONF_SOLAR_PRODUCTION_ENTITY),
        dynamic_price_entity=data.get(CONF_DYNAMIC_PRICE_ENTITY),
        shared_energy_entity=data.get(CONF_SHARED_ENERGY_ENTITY),
        supplier_mode=str(data.get(CONF_SUPPLIER_MODE, "et")),
        supplier_et_price=d(CONF_SUPPLIER_ET_PRICE, "0"),
        supplier_vt_price=d(CONF_SUPPLIER_VT_PRICE, "0"),
        supplier_mt_price=d(CONF_SUPPLIER_MT_PRICE, "0"),
        supplier_markup_fixed=d(CONF_SUPPLIER_MARKUP_FIXED, "0"),
        supplier_markup_pct=d(CONF_SUPPLIER_MARKUP_PCT, "0"),
        supplier_discount_pct=d(CONF_SUPPLIER_DISCOUNT_PCT, "0"),
        prices_include_vat=bool(data.get(CONF_PRICES_INCLUDE_VAT, False)),
        vat_rate=d(CONF_VAT_RATE, "0.22"),
        fixed_monthly_supplier=d(CONF_FIXED_MONTHLY_SUPPLIER, "0"),
        customer_category=str(data.get(CONF_CUSTOMER_CATEGORY, "0")),
        has_15min_measurement=bool(data.get(CONF_HAS_15MIN_MEASUREMENT, True)),
        agreed_power=agreed,
        enable_levies=bool(data.get(CONF_ENABLE_LEVIES, True)),
        excise_rate=d(CONF_EXCISE_RATE, "0.00153"),
        ove_spte_rate=d(CONF_OVE_SPTE_RATE, "0.00899"),
        settlement_source=str(data.get(CONF_SETTLEMENT_SOURCE, "physical")),
        souporaba_entry_id=data.get(CONF_SOUPORABA_ENTRY_ID),
        souporaba_entities=dict(data.get(CONF_SOUPORABA_ENTITIES) or {}),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a billing site from a config entry."""
    from homeassistant.const import Platform

    from .const import SETTLEMENT_SOUPORABA
    from .coordinator import BillingCoordinator
    from .integrations.souporaba import SouporabaAdapter
    from .storage import BillingStore

    hass.data.setdefault(DOMAIN, {})
    data = {**entry.data, **entry.options}
    site = build_site_config(data)
    store = BillingStore(hass, entry.entry_id)

    souporaba = None
    if site.settlement_source == SETTLEMENT_SOUPORABA and site.souporaba_entities:
        souporaba = SouporabaAdapter(hass, site.souporaba_entities)

    coordinator = BillingCoordinator(
        hass, entry.entry_id, site, store, souporaba_adapter=souporaba
    )
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.NUMBER]
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.NUMBER]
    )
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.async_unload()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
