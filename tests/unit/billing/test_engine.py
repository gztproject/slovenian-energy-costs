"""Billing engine and supplier pricing tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.slovenian_energy_costs.billing.engine import BillingEngine
from custom_components.slovenian_energy_costs.models import (
    ComputationQuality,
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)
from custom_components.slovenian_energy_costs.tariffs.supplier_rates import (
    SupplierPriceResolver,
)

TZ = ZoneInfo("Europe/Ljubljana")


def test_et_contract(
    site_config: SiteConfig, sample_interval: SettlementInterval
) -> None:
    engine = BillingEngine(site_config)
    result = engine.calculate_interval(sample_interval)
    assert result.supplier_energy_cost == Decimal("0.10000")
    assert result.network_billable_kwh == Decimal("1.000")
    assert result.quality == ComputationQuality.ACTUAL
    assert result.variable_cost_total > 0


def test_vt_mt_contract() -> None:
    config = SiteConfig(
        site_name="VTMT",
        site_role="consumer",
        supplier_mode="vt_mt",
        supplier_vt_price=Decimal("0.14"),
        supplier_mt_price=Decimal("0.08"),
        enable_levies=False,
        customer_category="0",
    )
    engine = BillingEngine(config)
    day = datetime(2026, 6, 17, 10, 0, tzinfo=TZ)
    night = datetime(2026, 6, 17, 23, 0, tzinfo=TZ)
    interval_day = SettlementInterval(
        interval_id="d",
        interval_start=day,
        interval_end=day,
        physical_import_kwh=Decimal("1"),
        supplier_billable_kwh=Decimal("1"),
    )
    interval_night = SettlementInterval(
        interval_id="n",
        interval_start=night,
        interval_end=night,
        physical_import_kwh=Decimal("1"),
        supplier_billable_kwh=Decimal("1"),
    )
    assert engine.calculate_interval(interval_day).supplier_tariff == "VT"
    assert engine.calculate_interval(interval_night).supplier_tariff == "MT"


def test_dynamic_tariff_and_markup() -> None:
    config = SiteConfig(
        site_name="Dyn",
        site_role="consumer",
        supplier_mode="dynamic",
        supplier_markup_fixed=Decimal("0.01"),
        supplier_markup_pct=Decimal("10"),
        supplier_discount_pct=Decimal("0"),
        enable_levies=False,
        prices_include_vat=False,
        vat_rate=Decimal("0.22"),
        customer_category="0",
    )
    price = SupplierPriceResolver(config).resolve(
        datetime(2026, 6, 15, 12, 0, tzinfo=TZ),
        dynamic_price=Decimal("0.100"),
    )
    # 0.10 + 0.01 = 0.11; * 1.10 = 0.121
    assert price.price_ex_vat == Decimal("0.121")


def test_vat_inclusive_no_double_vat(site_config: SiteConfig) -> None:
    site_config.prices_include_vat = True
    site_config.supplier_et_price = Decimal("0.122")
    site_config.enable_levies = False
    engine = BillingEngine(site_config)
    when = datetime(2026, 6, 15, 10, 0, tzinfo=TZ)
    interval = SettlementInterval(
        interval_id="v",
        interval_start=when,
        interval_end=when,
        physical_import_kwh=Decimal("1"),
        supplier_billable_kwh=Decimal("1"),
    )
    result = engine.calculate_interval(interval)
    assert "supplier_prices_include_vat_no_double_vat" in result.notes


def test_contract_discount() -> None:
    config = SiteConfig(
        site_name="Disc",
        site_role="consumer",
        supplier_mode="et",
        supplier_et_price=Decimal("0.10"),
        supplier_discount_pct=Decimal("10"),
        enable_levies=False,
        prices_include_vat=False,
        customer_category="0",
    )
    price = SupplierPriceResolver(config).resolve(
        datetime(2026, 6, 15, 12, 0, tzinfo=TZ)
    )
    assert price.price_ex_vat == Decimal("0.090")


def test_network_energy_on_physical_import(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    engine = BillingEngine(site_config)
    when = datetime(2026, 6, 15, 10, 0, tzinfo=TZ)
    # Shared energy reduces supplier billable but NOT network
    interval = SettlementInterval(
        interval_id="s",
        interval_start=when,
        interval_end=when,
        physical_import_kwh=Decimal("2.0"),
        shared_allocated_kwh=Decimal("0.5"),
        shared_used_kwh=Decimal("0.5"),
        shared_unused_kwh=Decimal("0"),
        supplier_billable_kwh=Decimal("1.5"),
        source=SettlementSource.SOUPORABA,
    )
    result = engine.calculate_interval(interval)
    assert result.network_billable_kwh == Decimal("2.0")
    assert result.supplier_billable_kwh == Decimal("1.5")
    assert result.souporaba_savings == Decimal("0.5") * Decimal("0.10000")


def test_skipped_settlement_not_booked(site_config: SiteConfig) -> None:
    engine = BillingEngine(site_config)
    when = datetime(2026, 6, 15, 10, 0, tzinfo=TZ)
    interval = SettlementInterval(
        interval_id="skip",
        interval_start=when,
        interval_end=when,
        physical_import_kwh=Decimal("1"),
        settlement_accumulated=False,
        quality=ComputationQuality.INVALID,
    )
    result = engine.calculate_interval(interval)
    assert result.variable_cost_total == 0
    assert result.quality == ComputationQuality.INVALID


def test_missing_network_rate_marks_incomplete(site_config: SiteConfig) -> None:
    """Rates start 2026-03-01; June 2025 has a schedule but no ANJP239 rates."""
    engine = BillingEngine(site_config)
    when = datetime(2025, 6, 15, 10, 0, tzinfo=TZ)
    interval = SettlementInterval(
        interval_id="old",
        interval_start=when,
        interval_end=when,
        physical_import_kwh=Decimal("1"),
        supplier_billable_kwh=Decimal("1"),
    )
    result = engine.calculate_interval(interval)
    assert result.quality == ComputationQuality.INCOMPLETE
    assert result.network_energy_cost == 0
    assert any("No network_energy rate" in n for n in result.notes)
