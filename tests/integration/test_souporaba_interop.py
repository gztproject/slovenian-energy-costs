"""Souporaba interoperability scenarios (fixture-driven, HA-free)."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from custom_components.slovenian_energy_costs.billing.engine import BillingEngine
from custom_components.slovenian_energy_costs.billing.net_metering import (
    apply_interval_to_net_metering,
    create_year_state,
)
from custom_components.slovenian_energy_costs.billing.reconciliation import (
    should_book_financially,
)
from custom_components.slovenian_energy_costs.models import (
    ComputationQuality,
    CostCounters,
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)

FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "souporaba" / "states.json"
)


def _load(name: str) -> SettlementInterval:
    payload = json.loads(FIXTURES.read_text(encoding="utf-8"))[name]
    sensors = payload["sensors"]

    def s(key: str) -> Decimal:
        return Decimal(sensors[key]["state"])

    recon = sensors.get("reconciliation_status", {}).get("state", "not_configured")
    quality = ComputationQuality.ACTUAL
    accumulated = bool(payload["settlement_accumulated"])
    if recon == "mismatch_warn":
        quality = ComputationQuality.ESTIMATED
    elif recon == "mismatch_skip":
        quality = ComputationQuality.INVALID
        accumulated = False

    return SettlementInterval(
        interval_id=payload["interval_id"],
        interval_start=datetime.fromisoformat(payload["interval_start"]),
        interval_end=datetime.fromisoformat(payload["interval_end"]),
        physical_import_kwh=s("receiver_import_last_interval"),
        shared_allocated_kwh=s("shared_energy_last_interval"),
        shared_used_kwh=s("used_shared_last_interval"),
        shared_unused_kwh=s("unused_shared_last_interval"),
        supplier_billable_kwh=s("billable_energy_last_interval"),
        settlement_accumulated=accumulated,
        reconciliation_status=recon,
        operating_mode=payload.get("operating_mode"),
        source=SettlementSource.SOUPORABA,
        quality=quality,
        fixed_allocation_percentage=(
            Decimal(
                sensors["fixed_allocation_percentage_last_interval"]["state"]
            )
            if "fixed_allocation_percentage_last_interval" in sensors
            else None
        ),
    )


def test_ordinary_billing_without_souporaba(site_config: SiteConfig) -> None:
    site_config.settlement_source = "physical"
    site_config.enable_levies = False
    interval = SettlementInterval(
        interval_id="phys",
        interval_start=datetime.fromisoformat("2026-06-15T10:00:00+02:00"),
        interval_end=datetime.fromisoformat("2026-06-15T10:15:00+02:00"),
        physical_import_kwh=Decimal("1"),
        supplier_billable_kwh=Decimal("1"),
        source=SettlementSource.PHYSICAL,
    )
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.shared_allocated_kwh == 0
    assert result.variable_cost_total > 0


def test_no_duplicate_financial_booking(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    counters = CostCounters()
    processed: set[str] = set()
    interval = _load("accepted_interval")
    for _ in range(3):
        if interval.interval_id in processed:
            continue
        result = BillingEngine(site_config).calculate_interval(interval)
        counters.apply_interval(result)
        processed.add(interval.interval_id)
    assert counters.supplier_energy_cost_total == Decimal("0.15000")


def test_skipped_reconciliation_interval(site_config: SiteConfig) -> None:
    interval = _load("skipped_interval")
    assert not should_book_financially(interval)


def test_reconciliation_warning_estimated(site_config: SiteConfig) -> None:
    interval = _load("warn_interval")
    assert should_book_financially(interval)
    assert interval.quality == ComputationQuality.ESTIMATED


def test_percentage_retained_on_interval() -> None:
    interval = _load("accepted_interval")
    assert interval.fixed_allocation_percentage == Decimal("15.0")


def test_unused_allocation_and_donor_deduction() -> None:
    config = SiteConfig(site_name="Donor", site_role="producer")
    state = create_year_state(2026, config)
    interval = SettlementInterval(
        interval_id="d1",
        interval_start=datetime.fromisoformat("2026-06-15T10:00:00+02:00"),
        interval_end=datetime.fromisoformat("2026-06-15T10:15:00+02:00"),
        physical_import_kwh=Decimal("0"),
        physical_export_kwh=Decimal("10"),
        shared_allocated_kwh=Decimal("2"),
        shared_used_kwh=Decimal("1.5"),
        shared_unused_kwh=Decimal("0.5"),
        source=SettlementSource.SOUPORABA,
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.shared_deduction == Decimal("2")
    assert state.eligible_export_kwh == Decimal("8")


def test_network_not_reduced_by_sharing(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    result = BillingEngine(site_config).calculate_interval(_load("accepted_interval"))
    assert result.network_billable_kwh == result.physical_import_kwh


def test_inferred_export_not_required_for_receiver_billing(
    site_config: SiteConfig,
) -> None:
    site_config.enable_levies = False
    base = _load("accepted_interval")
    # Receiver billing uses billable_energy even if export type is inferred
    interval = SettlementInterval(
        interval_id=base.interval_id,
        interval_start=base.interval_start,
        interval_end=base.interval_end,
        physical_import_kwh=base.physical_import_kwh,
        shared_allocated_kwh=base.shared_allocated_kwh,
        shared_used_kwh=base.shared_used_kwh,
        shared_unused_kwh=base.shared_unused_kwh,
        supplier_billable_kwh=base.supplier_billable_kwh,
        settlement_accumulated=base.settlement_accumulated,
        reconciliation_status=base.reconciliation_status,
        operating_mode=base.operating_mode,
        provider_export_source_type="inferred",
        source=SettlementSource.SOUPORABA,
        quality=base.quality,
    )
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.supplier_billable_kwh == Decimal("1.500")
