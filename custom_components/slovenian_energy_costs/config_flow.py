"""Config and options flow for Slovenian Energy Costs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    DOMAIN,
    MODEL_CONVENTIONAL,
    MODEL_NET_METERING,
    MODEL_SOUPORABA_DONOR,
    MODEL_SOUPORABA_RECEIVER,
    ROLE_COMBINED,
    ROLE_CONSUMER,
    ROLE_PRODUCER,
    SETTLEMENT_PHYSICAL,
    SETTLEMENT_SOUPORABA,
    SUPPLIER_DYNAMIC,
    SUPPLIER_ET,
    SUPPLIER_VT_MT,
)
from .integrations.souporaba import (
    discover_souporaba_entries,
    map_souporaba_entities,
    validate_entity_mapping,
)

STEP_SITE = vol.Schema(
    {
        vol.Required(CONF_SITE_NAME, default="Home"): str,
        vol.Required(CONF_SITE_ROLE, default=ROLE_CONSUMER): vol.In(
            [ROLE_CONSUMER, ROLE_PRODUCER, ROLE_COMBINED]
        ),
        vol.Required(CONF_CURRENCY, default="EUR"): str,
    }
)

STEP_MODELS = vol.Schema(
    {
        vol.Required(CONF_BILLING_MODELS, default=[MODEL_CONVENTIONAL]): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    MODEL_CONVENTIONAL,
                    MODEL_NET_METERING,
                    MODEL_SOUPORABA_RECEIVER,
                    MODEL_SOUPORABA_DONOR,
                ],
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", multiple=False)
    )


def _number_selector(
    *,
    min_value: float = 0.0,
    max_value: float,
    unit: str | None = None,
    step: float | str = "any",
) -> selector.NumberSelector:
    """BOX number input with explicit step so decimals are never locked to 1."""
    config: dict[str, Any] = {
        "min": min_value,
        "max": max_value,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(**config))


def _eur_per_kwh_selector(*, max_value: float = 5.0) -> selector.NumberSelector:
    """Commodity / levy price in €/kWh (sane residential range)."""
    return _number_selector(max_value=max_value, unit="€/kWh")


def _percent_selector(*, max_value: float = 100.0) -> selector.NumberSelector:
    return _number_selector(max_value=max_value, unit="%")


def _eur_selector(*, max_value: float = 1000.0) -> selector.NumberSelector:
    return _number_selector(max_value=max_value, unit="€")


def _kw_selector(*, max_value: float = 100.0) -> selector.NumberSelector:
    return _number_selector(max_value=max_value, unit="kW")


def _float_default(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _bounded_default(
    value: Any, fallback: float, *, min_value: float = 0.0, max_value: float
) -> float:
    """Return fallback when stored value is outside selector bounds (recovery)."""
    parsed = _float_default(value, fallback)
    if parsed < min_value or parsed > max_value:
        return fallback
    return parsed


def build_supplier_schema() -> vol.Schema:
    """Schema for initial supplier contract step."""
    return vol.Schema(
        {
            vol.Required(CONF_SUPPLIER_MODE, default=SUPPLIER_ET): vol.In(
                [SUPPLIER_ET, SUPPLIER_VT_MT, SUPPLIER_DYNAMIC]
            ),
            vol.Optional(CONF_SUPPLIER_ET_PRICE, default=0.12): _eur_per_kwh_selector(),
            vol.Optional(CONF_SUPPLIER_VT_PRICE, default=0.14): _eur_per_kwh_selector(),
            vol.Optional(CONF_SUPPLIER_MT_PRICE, default=0.10): _eur_per_kwh_selector(),
            vol.Optional(CONF_DYNAMIC_PRICE_ENTITY): _entity_selector(),
            vol.Optional(
                CONF_SUPPLIER_MARKUP_FIXED, default=0.0
            ): _eur_per_kwh_selector(),
            vol.Optional(CONF_SUPPLIER_MARKUP_PCT, default=0.0): _percent_selector(),
            vol.Optional(CONF_SUPPLIER_DISCOUNT_PCT, default=0.0): _percent_selector(),
            vol.Optional(CONF_PRICES_INCLUDE_VAT, default=False): bool,
            vol.Optional(CONF_VAT_RATE, default=0.22): _number_selector(
                max_value=1.0, unit=None
            ),
            vol.Optional(
                CONF_FIXED_MONTHLY_SUPPLIER, default=0.0
            ): _eur_selector(),
        }
    )


def build_network_schema() -> vol.Schema:
    """Schema for network category / agreed power / levies."""
    return vol.Schema(
        {
            vol.Required(CONF_CUSTOMER_CATEGORY, default="0"): vol.In(
                ["0", "1", "2", "3", "4"]
            ),
            vol.Required(CONF_HAS_15MIN_MEASUREMENT, default=True): bool,
            vol.Optional("agreed_power_b1", default=0.0): _kw_selector(),
            vol.Optional("agreed_power_b2", default=0.0): _kw_selector(),
            vol.Optional("agreed_power_b3", default=0.0): _kw_selector(),
            vol.Optional("agreed_power_b4", default=0.0): _kw_selector(),
            vol.Optional("agreed_power_b5", default=0.0): _kw_selector(),
            vol.Optional(CONF_ENABLE_LEVIES, default=True): bool,
            vol.Optional(CONF_EXCISE_RATE, default=0.00153): _eur_per_kwh_selector(
                max_value=1.0
            ),
            vol.Optional(CONF_OVE_SPTE_RATE, default=0.00899): _eur_per_kwh_selector(
                max_value=1.0
            ),
        }
    )


def build_options_schema(data: dict[str, Any]) -> vol.Schema:
    """Schema for options flow rate edits."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SUPPLIER_ET_PRICE,
                default=_bounded_default(
                    data.get(CONF_SUPPLIER_ET_PRICE), 0.12, max_value=5.0
                ),
            ): _eur_per_kwh_selector(),
            vol.Optional(
                CONF_SUPPLIER_VT_PRICE,
                default=_bounded_default(
                    data.get(CONF_SUPPLIER_VT_PRICE), 0.14, max_value=5.0
                ),
            ): _eur_per_kwh_selector(),
            vol.Optional(
                CONF_SUPPLIER_MT_PRICE,
                default=_bounded_default(
                    data.get(CONF_SUPPLIER_MT_PRICE), 0.10, max_value=5.0
                ),
            ): _eur_per_kwh_selector(),
            vol.Optional(
                CONF_FIXED_MONTHLY_SUPPLIER,
                default=_bounded_default(
                    data.get(CONF_FIXED_MONTHLY_SUPPLIER), 0.0, max_value=1000.0
                ),
            ): _eur_selector(),
            vol.Optional(
                CONF_PRICES_INCLUDE_VAT,
                default=bool(data.get(CONF_PRICES_INCLUDE_VAT, False)),
            ): bool,
            vol.Optional(
                CONF_ENABLE_LEVIES,
                default=bool(data.get(CONF_ENABLE_LEVIES, True)),
            ): bool,
        }
    )


class SlovenianEnergyCostsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_SITE)
        self._data.update(user_input)
        return await self.async_step_models()

    async def async_step_models(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="models", data_schema=STEP_MODELS)
        self._data.update(user_input)
        return await self.async_step_meters()

    async def async_step_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        schema = vol.Schema(
            {
                vol.Required(CONF_GRID_IMPORT_ENTITY): _entity_selector(),
                vol.Optional(CONF_GRID_EXPORT_ENTITY): _entity_selector(),
                vol.Optional(CONF_SOLAR_PRODUCTION_ENTITY): _entity_selector(),
                vol.Optional(CONF_SHARED_ENERGY_ENTITY): _entity_selector(),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id="meters", data_schema=schema)
        self._data.update(user_input)
        return await self.async_step_supplier()

    async def async_step_supplier(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        schema = build_supplier_schema()
        if user_input is None:
            return self.async_show_form(step_id="supplier", data_schema=schema)
        self._data.update(user_input)
        return await self.async_step_network()

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        schema = build_network_schema()
        if user_input is None:
            return self.async_show_form(step_id="network", data_schema=schema)

        agreed = {}
        for block in range(1, 6):
            key = f"agreed_power_b{block}"
            if user_input.get(key):
                agreed[str(block)] = user_input.pop(key)
            elif key in user_input:
                user_input.pop(key)
        self._data.update(user_input)
        self._data[CONF_AGREED_POWER] = agreed
        return await self.async_step_settlement()

    async def async_step_settlement(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        models = set(self._data.get(CONF_BILLING_MODELS) or [])
        wants_souporaba = bool(
            models & {MODEL_SOUPORABA_RECEIVER, MODEL_SOUPORABA_DONOR}
        )
        souporaba_entries = discover_souporaba_entries(self.hass)
        options = [
            {"value": e["entry_id"], "label": e["title"]} for e in souporaba_entries
        ]

        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_SETTLEMENT_SOURCE,
                default=(
                    SETTLEMENT_SOUPORABA if wants_souporaba and options else SETTLEMENT_PHYSICAL
                ),
            ): vol.In([SETTLEMENT_PHYSICAL, SETTLEMENT_SOUPORABA]),
        }
        if options:
            schema_dict[
                vol.Optional(CONF_SOUPORABA_ENTRY_ID)
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        if user_input is None:
            return self.async_show_form(
                step_id="settlement", data_schema=vol.Schema(schema_dict)
            )

        self._data.update(user_input)
        if (
            self._data.get(CONF_SETTLEMENT_SOURCE) == SETTLEMENT_SOUPORABA
            and self._data.get(CONF_SOUPORABA_ENTRY_ID)
        ):
            entry_id = self._data[CONF_SOUPORABA_ENTRY_ID]
            mapping = map_souporaba_entities(self.hass, entry_id)
            problems = validate_entity_mapping(self.hass, entry_id, mapping)
            self._data[CONF_SOUPORABA_ENTITIES] = mapping
            self._data["souporaba_mapping_problems"] = problems
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is None:
            problems = self._data.get("souporaba_mapping_problems") or []
            summary = {
                "site": self._data.get(CONF_SITE_NAME),
                "models": self._data.get(CONF_BILLING_MODELS),
                "supplier_mode": self._data.get(CONF_SUPPLIER_MODE),
                "settlement": self._data.get(CONF_SETTLEMENT_SOURCE),
                "souporaba_problems": problems,
            }
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "summary": str(summary),
                },
            )

        title = self._data.get(CONF_SITE_NAME) or "Slovenian Energy Costs"
        data = dict(self._data)
        data.pop("souporaba_mapping_problems", None)
        # Normalize name key for HA
        data[CONF_NAME] = title
        await self.async_set_unique_id(
            f"{DOMAIN}_{data.get(CONF_GRID_IMPORT_ENTITY)}_{title}"
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return SlovenianEnergyCostsOptionsFlow(config_entry)


class SlovenianEnergyCostsOptionsFlow(config_entries.OptionsFlow):
    """Options flow — safe reconfiguration without wiping history."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        data = {**self._entry.data, **self._entry.options}
        schema = build_options_schema(data)
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)
        return self.async_create_entry(title="", data=user_input)
