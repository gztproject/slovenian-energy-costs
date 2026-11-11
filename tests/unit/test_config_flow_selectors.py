"""Ensure monetary config fields allow arbitrary decimals (no step=1 lock-in)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.slovenian_energy_costs.config_flow import (
    _bounded_default,
    _eur_per_kwh_selector,
    build_network_schema,
    build_options_schema,
    build_supplier_schema,
)
from custom_components.slovenian_energy_costs.const import (
    CONF_EXCISE_RATE,
    CONF_FIXED_MONTHLY_SUPPLIER,
    CONF_OVE_SPTE_RATE,
    CONF_SUPPLIER_ET_PRICE,
    CONF_SUPPLIER_MT_PRICE,
    CONF_SUPPLIER_VT_PRICE,
)


def _selector_step(field: Any) -> Any:
    config = getattr(field, "config", field)
    if isinstance(config, dict):
        return config.get("step")
    return getattr(config, "step", None)


def _schema_validators(schema: vol.Schema) -> dict[str, Any]:
    """Map config key -> validator from a voluptuous Schema."""
    result: dict[str, Any] = {}
    for key, validator in schema.schema.items():
        name = getattr(key, "schema", key)
        result[str(name)] = validator
    return result


def test_eur_per_kwh_selector_uses_any_step() -> None:
    assert _selector_step(_eur_per_kwh_selector()) == "any"


def test_supplier_price_fields_use_any_step() -> None:
    fields = _schema_validators(build_supplier_schema())
    for key in (
        CONF_SUPPLIER_ET_PRICE,
        CONF_SUPPLIER_VT_PRICE,
        CONF_SUPPLIER_MT_PRICE,
    ):
        assert _selector_step(fields[key]) == "any"


def test_options_price_fields_use_any_step() -> None:
    fields = _schema_validators(
        build_options_schema(
            {
                CONF_SUPPLIER_ET_PRICE: 0.12,
                CONF_SUPPLIER_VT_PRICE: 124790,
                CONF_SUPPLIER_MT_PRICE: 0.1,
            }
        )
    )
    for key in (
        CONF_SUPPLIER_ET_PRICE,
        CONF_SUPPLIER_VT_PRICE,
        CONF_SUPPLIER_MT_PRICE,
        CONF_FIXED_MONTHLY_SUPPLIER,
    ):
        assert _selector_step(fields[key]) == "any"


def test_network_levy_and_power_fields_use_any_step() -> None:
    fields = _schema_validators(build_network_schema())
    for key in (
        "agreed_power_b1",
        CONF_EXCISE_RATE,
        CONF_OVE_SPTE_RATE,
    ):
        assert _selector_step(fields[key]) == "any"


def test_options_resets_absurd_vt_default() -> None:
    """Poisoned integer VT must not be used as the form default (above max)."""
    assert _bounded_default(124790, 0.14, max_value=5.0) == 0.14
    assert _bounded_default(0.152, 0.14, max_value=5.0) == 0.152
