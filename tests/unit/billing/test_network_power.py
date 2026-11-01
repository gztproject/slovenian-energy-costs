"""Network power and excess power tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from custom_components.slovenian_energy_costs.billing.excess_power import (
    calculate_excess_power,
    interval_average_power_kw,
)
from custom_components.slovenian_energy_costs.billing.network_power import (
    calculate_monthly_network_power,
)
from custom_components.slovenian_energy_costs.models import (
    ComputationQuality,
    SiteConfig,
)


def test_agreed_power_ordinary_month() -> None:
    config = SiteConfig(
        site_name="P",
        site_role="consumer",
        customer_category="0",
        has_15min_measurement=True,
        agreed_power={1: Decimal("5"), 2: Decimal("4")},
    )
    amount, charges, warnings = calculate_monthly_network_power(
        when=date(2026, 6, 1),
        config=config,
    )
    assert not warnings
    assert amount > 0
    # Block 1 ordinary rate 3.82301 * 5
    assert any(c.charge_id == "network_power_b1" for c in charges)
    b1 = next(c for c in charges if c.charge_id == "network_power_b1")
    assert b1.rate == Decimal("3.82301")


def test_november_2026_reduced_power() -> None:
    config = SiteConfig(
        site_name="P",
        site_role="consumer",
        customer_category="0",
        has_15min_measurement=True,
        agreed_power={1: Decimal("5")},
    )
    amount, charges, _ = calculate_monthly_network_power(
        when=date(2026, 11, 15),
        config=config,
    )
    assert charges[0].rate == Decimal("2.67611")
    assert "Reduced Nov-Dec 2026" in (charges[0].notes or "")
    assert amount == Decimal("5") * Decimal("2.67611")


def test_december_2026_reduced_power() -> None:
    config = SiteConfig(
        site_name="P",
        site_role="consumer",
        customer_category="0",
        has_15min_measurement=True,
        agreed_power={1: Decimal("1")},
    )
    _, charges, _ = calculate_monthly_network_power(
        when=date(2026, 12, 1),
        config=config,
    )
    assert charges[0].rate == Decimal("2.67611")


def test_missing_agreed_power() -> None:
    config = SiteConfig(
        site_name="P",
        site_role="consumer",
        customer_category="0",
        agreed_power={},
    )
    amount, charges, warnings = calculate_monthly_network_power(
        when=date(2026, 6, 1),
        config=config,
    )
    assert amount == 0
    assert warnings == ["missing_agreed_power"]
    assert charges == []


def test_interval_average_power_not_instantaneous() -> None:
    # 0.5 kWh in 15 min = 2 kW average
    assert interval_average_power_kw(Decimal("0.5"), 15) == Decimal("2")


def test_excess_power_incomplete_without_rate() -> None:
    config = SiteConfig(
        site_name="P",
        site_role="consumer",
        has_15min_measurement=True,
    )
    amount, line, quality, warning = calculate_excess_power(
        interval_energy_kwh=Decimal("1.0"),
        agreed_power_kw=Decimal("2"),
        network_block=1,
        config=config,
    )
    assert amount == 0
    assert line is None
    assert quality == ComputationQuality.INCOMPLETE
    assert warning == "excess_power_rate_not_configured"
