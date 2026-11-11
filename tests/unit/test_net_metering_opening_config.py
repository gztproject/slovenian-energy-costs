"""Net-metering opening balance config/options wiring."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from custom_components.slovenian_energy_costs import build_site_config
from custom_components.slovenian_energy_costs.billing.net_metering import (
    apply_opening_from_config,
    create_year_state,
)
from custom_components.slovenian_energy_costs.config_flow import (
    _wants_net_metering,
    build_net_metering_schema,
    build_options_schema,
)
from custom_components.slovenian_energy_costs.const import (
    CONF_NET_METERING_OPENING_BALANCE,
    CONF_NET_METERING_OPENING_DATE,
    CONF_SETTLEMENT_SOURCE,
    MODEL_CONVENTIONAL,
    MODEL_NET_METERING,
    MODEL_SOUPORABA_DONOR,
    SETTLEMENT_PHYSICAL,
)
from custom_components.slovenian_energy_costs.models import NetMeteringState, SiteConfig


def _schema_keys(schema) -> set[str]:
    keys: set[str] = set()
    for key in schema.schema:
        name = getattr(key, "schema", key)
        keys.add(str(name))
    return keys


def test_wants_net_metering_models() -> None:
    assert _wants_net_metering([MODEL_NET_METERING])
    assert _wants_net_metering([MODEL_SOUPORABA_DONOR])
    assert not _wants_net_metering([MODEL_CONVENTIONAL])


def test_net_metering_schema_has_opening_fields() -> None:
    keys = _schema_keys(build_net_metering_schema())
    assert CONF_NET_METERING_OPENING_BALANCE in keys
    assert CONF_NET_METERING_OPENING_DATE in keys


def test_options_schema_includes_settlement_and_opening() -> None:
    keys = _schema_keys(
        build_options_schema(
            {
                CONF_SETTLEMENT_SOURCE: SETTLEMENT_PHYSICAL,
                CONF_NET_METERING_OPENING_BALANCE: 120.5,
                CONF_NET_METERING_OPENING_DATE: "2026-01-01",
            }
        )
    )
    assert CONF_SETTLEMENT_SOURCE in keys
    assert CONF_NET_METERING_OPENING_BALANCE in keys
    assert CONF_NET_METERING_OPENING_DATE in keys


def test_build_site_config_parses_opening() -> None:
    site = build_site_config(
        {
            "site_name": "Donor",
            "billing_models": [MODEL_NET_METERING],
            CONF_NET_METERING_OPENING_BALANCE: "150.25",
            CONF_NET_METERING_OPENING_DATE: "2026-01-01",
        }
    )
    assert site.net_metering_opening_balance == Decimal("150.25")
    assert site.net_metering_opening_date == date(2026, 1, 1)


def test_build_site_config_clears_opening_with_null() -> None:
    site = build_site_config(
        {
            "site_name": "Donor",
            CONF_NET_METERING_OPENING_BALANCE: None,
            CONF_NET_METERING_OPENING_DATE: None,
        }
    )
    assert site.net_metering_opening_balance is None
    assert site.net_metering_opening_date is None


def test_apply_opening_preserves_observed_totals() -> None:
    state = NetMeteringState(
        year=2026,
        opening_balance_kwh=None,
        opening_date=None,
        history_complete=False,
        observed_import_kwh=Decimal("10"),
        observed_export_kwh=Decimal("40"),
        shared_deducted_kwh=Decimal("5"),
    )
    config = SiteConfig(
        site_name="Donor",
        site_role="producer",
        billing_models=[MODEL_NET_METERING],
        net_metering_opening_balance=Decimal("100"),
        net_metering_opening_date=date(2026, 1, 1),
    )
    apply_opening_from_config(state, config)
    assert state.opening_balance_kwh == Decimal("100")
    assert state.opening_date == date(2026, 1, 1)
    assert state.history_complete is True
    assert state.observed_import_kwh == Decimal("10")
    assert state.observed_export_kwh == Decimal("40")
    assert state.shared_deducted_kwh == Decimal("5")


def test_create_year_state_uses_config_opening() -> None:
    config = SiteConfig(
        site_name="Donor",
        site_role="producer",
        net_metering_opening_balance=Decimal("12"),
        net_metering_opening_date=date(2026, 6, 1),
    )
    state = create_year_state(2026, config)
    assert state.opening_balance_kwh == Decimal("12")
    assert state.history_complete is False  # mid-year opening
