"""Souporaba financial accounting tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.slovenian_energy_costs.billing.engine import BillingEngine
from custom_components.slovenian_energy_costs.billing.souporaba import (
    receiver_network_billable,
    verify_souporaba_invariants,
)
from custom_components.slovenian_energy_costs.models import (
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)

TZ = ZoneInfo("Europe/Ljubljana")


def _interval(**kwargs: object) -> SettlementInterval:
    base = dict(
        interval_id="i1",
        interval_start=datetime(2026, 6, 15, 10, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 15, 10, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("2.0"),
        shared_allocated_kwh=Decimal("0.5"),
        shared_used_kwh=Decimal("0.5"),
        shared_unused_kwh=Decimal("0"),
        supplier_billable_kwh=Decimal("1.5"),
        source=SettlementSource.SOUPORABA,
        settlement_accumulated=True,
    )
    base.update(kwargs)
    return SettlementInterval(**base)  # type: ignore[arg-type]


def test_shared_smaller_than_import(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    engine = BillingEngine(site_config)
    result = engine.calculate_interval(_interval())
    assert result.supplier_billable_kwh == Decimal("1.5")
    assert result.network_billable_kwh == Decimal("2.0")


def test_shared_greater_than_import(site_config: SiteConfig) -> None:
    interval = _interval(
        physical_import_kwh=Decimal("1.0"),
        shared_allocated_kwh=Decimal("1.5"),
        shared_used_kwh=Decimal("1.0"),
        shared_unused_kwh=Decimal("0.5"),
        supplier_billable_kwh=Decimal("0"),
    )
    assert verify_souporaba_invariants(interval) == []
    site_config.enable_levies = False
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.supplier_billable_kwh == 0
    assert result.unused_allocation_value == Decimal("0.5") * Decimal("0.10000")
    assert result.network_billable_kwh == Decimal("1.0")


def test_zero_provider_export() -> None:
    interval = _interval(
        physical_export_kwh=Decimal("0"),
        shared_allocated_kwh=Decimal("0"),
        shared_used_kwh=Decimal("0"),
        supplier_billable_kwh=Decimal("2.0"),
    )
    assert receiver_network_billable(interval) == Decimal("2.0")


def test_zero_receiver_import() -> None:
    interval = _interval(
        physical_import_kwh=Decimal("0"),
        shared_allocated_kwh=Decimal("0.2"),
        shared_used_kwh=Decimal("0"),
        shared_unused_kwh=Decimal("0.2"),
        supplier_billable_kwh=Decimal("0"),
    )
    assert verify_souporaba_invariants(interval) == []


def test_sharing_does_not_reduce_network_kwh(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    result = BillingEngine(site_config).calculate_interval(_interval())
    assert result.network_billable_kwh == result.physical_import_kwh
