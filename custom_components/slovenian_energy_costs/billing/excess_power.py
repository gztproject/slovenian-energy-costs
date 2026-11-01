"""Excess network power (presežna moč) calculation."""

from __future__ import annotations

from decimal import Decimal

from ..models import ChargeLine, ComputationQuality, SiteConfig


def interval_average_power_kw(
    energy_kwh: Decimal, interval_minutes: int = 15
) -> Decimal:
    """Convert interval energy to 15-minute average power.

    P_avg (kW) = energy_kWh / (hours).
    """
    hours = Decimal(interval_minutes) / Decimal("60")
    if hours <= 0:
        return Decimal("0")
    return energy_kwh / hours


def calculate_excess_power(
    *,
    interval_energy_kwh: Decimal,
    agreed_power_kw: Decimal | None,
    network_block: int,
    config: SiteConfig,
    interval_minutes: int = 15,
    excess_rate_eur_per_kw: Decimal | None = None,
) -> tuple[Decimal, ChargeLine | None, ComputationQuality, str | None]:
    """Estimate excess power charge for one interval.

    Returns incomplete quality when methodology inputs or rates are missing.
    Does not invent regulatory excess-power multipliers.
    """
    if not config.has_15min_measurement:
        return (
            Decimal("0"),
            None,
            ComputationQuality.INCOMPLETE,
            "excess_power_requires_15min_measurement",
        )
    if agreed_power_kw is None:
        return (
            Decimal("0"),
            None,
            ComputationQuality.INCOMPLETE,
            "missing_agreed_power_for_block",
        )
    if excess_rate_eur_per_kw is None:
        return (
            Decimal("0"),
            None,
            ComputationQuality.INCOMPLETE,
            "excess_power_rate_not_configured",
        )

    avg_power = interval_average_power_kw(interval_energy_kwh, interval_minutes)
    excess = max(avg_power - agreed_power_kw, Decimal("0"))
    if excess <= 0:
        return Decimal("0"), None, ComputationQuality.ACTUAL, None

    # Interval share of monthly excess is site-specific; expose raw excess kW
    # value using configured rate only when explicitly provided.
    amount = excess * excess_rate_eur_per_kw
    line = ChargeLine(
        charge_id=f"excess_power_b{network_block}",
        name=f"Excess power block {network_block}",
        amount=amount,
        unit="EUR",
        quantity=excess,
        rate=excess_rate_eur_per_kw,
        calculation_base="excess_15min_average_power",
        vat_applicable=True,
        notes=(
            f"avg_power={avg_power} kW, agreed={agreed_power_kw} kW; "
            "rate is user-configured, not a bundled regulatory table"
        ),
    )
    return amount, line, ComputationQuality.ESTIMATED, None
