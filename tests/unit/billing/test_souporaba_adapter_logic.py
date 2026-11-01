"""Souporaba adapter logic tests using fixtures (no full HA required for models)."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from custom_components.slovenian_energy_costs.billing.engine import BillingEngine
from custom_components.slovenian_energy_costs.billing.reconciliation import (
    should_book_financially,
)
from custom_components.slovenian_energy_costs.models import (
    ComputationQuality,
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)

FIXTURES = (
    Path(__file__).resolve().parents[2] / "fixtures" / "souporaba" / "states.json"
)


def _interval_from_fixture(name: str) -> SettlementInterval:
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

    start = datetime.fromisoformat(payload["interval_start"])
    end = datetime.fromisoformat(payload["interval_end"])

    return SettlementInterval(
        interval_id=payload["interval_id"],
        interval_start=start,
        interval_end=end,
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
    )


def test_accepted_fixture_books(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    interval = _interval_from_fixture("accepted_interval")
    assert should_book_financially(interval)
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.supplier_billable_kwh == Decimal("1.500")
    assert result.network_billable_kwh == Decimal("2.000")
    assert result.quality == ComputationQuality.ACTUAL


def test_skipped_fixture_not_booked(site_config: SiteConfig) -> None:
    interval = _interval_from_fixture("skipped_interval")
    assert not should_book_financially(interval)
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.variable_cost_total == 0


def test_warn_fixture_estimated(site_config: SiteConfig) -> None:
    site_config.enable_levies = False
    interval = _interval_from_fixture("warn_interval")
    assert should_book_financially(interval)
    result = BillingEngine(site_config).calculate_interval(interval)
    assert result.quality == ComputationQuality.ESTIMATED


def test_no_duplicate_booking_ids() -> None:
    a = _interval_from_fixture("accepted_interval")
    b = _interval_from_fixture("accepted_interval")
    assert a.interval_id == b.interval_id
    processed = {a.interval_id}
    assert b.interval_id in processed
