"""Monetary counter reset helpers and storage audit trail."""

from __future__ import annotations

from decimal import Decimal

from custom_components.slovenian_energy_costs.models import (
    CostCounters,
    IntegrationStorage,
    MonthlyPeriodState,
)


def test_cost_counters_reset_monetary_keeps_energy() -> None:
    counters = CostCounters(
        grid_variable_cost_total=Decimal("100"),
        supplier_energy_cost_total=Decimal("80"),
        network_energy_cost_total=Decimal("5"),
        network_power_cost_total=Decimal("12"),
        levies_total=Decimal("1"),
        vat_total=Decimal("20"),
        invoice_cost_total=Decimal("118"),
        souporaba_savings_total=Decimal("3"),
        unused_allocation_value_total=Decimal("0.5"),
        souporaba_allocated_energy_total=Decimal("2.2"),
        souporaba_used_energy_total=Decimal("2.0"),
        souporaba_unused_energy_total=Decimal("0.2"),
        annual_import_kwh=Decimal("101"),
        annual_export_kwh=Decimal("32"),
        shared_energy_deducted_kwh=Decimal("2.2"),
    )
    snapshot = counters.monetary_snapshot()
    assert snapshot["supplier_energy_cost_total"] == "80"

    counters.reset_monetary()

    assert counters.supplier_energy_cost_total == Decimal("0")
    assert counters.grid_variable_cost_total == Decimal("0")
    assert counters.network_energy_cost_total == Decimal("0")
    assert counters.network_power_cost_total == Decimal("0")
    assert counters.levies_total == Decimal("0")
    assert counters.vat_total == Decimal("0")
    assert counters.invoice_cost_total == Decimal("0")
    assert counters.souporaba_savings_total == Decimal("0")
    assert counters.unused_allocation_value_total == Decimal("0")
    assert counters.annual_import_kwh == Decimal("101")
    assert counters.annual_export_kwh == Decimal("32")
    assert counters.souporaba_allocated_energy_total == Decimal("2.2")
    assert counters.souporaba_used_energy_total == Decimal("2.0")
    assert counters.souporaba_unused_energy_total == Decimal("0.2")
    assert counters.shared_energy_deducted_kwh == Decimal("2.2")


def test_monthly_reset_preserves_power_charged() -> None:
    monthly = MonthlyPeriodState(
        year=2026,
        month=11,
        supplier_energy_cost=Decimal("5000"),
        network_energy_cost=Decimal("2"),
        network_power_cost=Decimal("12"),
        other_charges=Decimal("1"),
        vat=Decimal("1000"),
        estimated_invoice=Decimal("6015"),
        power_charged=True,
    )
    monthly.reset_monetary()
    assert monthly.supplier_energy_cost == Decimal("0")
    assert monthly.estimated_invoice == Decimal("0")
    assert monthly.year == 2026
    assert monthly.month == 11
    assert monthly.power_charged is True


def test_storage_adjustment_audit_shape() -> None:
    data = IntegrationStorage(
        counters=CostCounters(supplier_energy_cost_total=Decimal("124790")),
        monthly=MonthlyPeriodState(year=2026, month=11, power_charged=True),
        processed_interval_ids=["a", "b"],
    )
    previous = data.counters.monetary_snapshot()
    monthly_previous = data.monthly.to_dict() if data.monthly else None
    data.counters.reset_monetary()
    assert data.monthly is not None
    data.monthly.reset_monetary()
    data.adjustments.append(
        {
            "type": "reset_monetary",
            "timestamp": "2026-11-11T12:00:00+01:00",
            "previous_counters": previous,
            "previous_monthly": monthly_previous,
        }
    )
    assert data.processed_interval_ids == ["a", "b"]
    assert data.adjustments[0]["type"] == "reset_monetary"
    assert data.adjustments[0]["previous_counters"]["supplier_energy_cost_total"] == (
        "124790"
    )
    assert data.monthly.power_charged is True
    assert data.counters.supplier_energy_cost_total == Decimal("0")
