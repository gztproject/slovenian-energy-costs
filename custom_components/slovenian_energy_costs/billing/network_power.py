"""Agreed network power (dogovorjena obračunska moč) monthly charges."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..models import ChargeLine, SiteConfig
from ..tariffs.network_rates import get_network_power_rate
from ..tariffs.rate_registry import MissingTariffError, RateRegistry


def calculate_monthly_network_power(
    *,
    when: date,
    config: SiteConfig,
    registry: RateRegistry | None = None,
) -> tuple[Decimal, list[ChargeLine], list[str]]:
    """Calculate monthly agreed-power charges for all configured blocks.

    Applies ANJP239 reduced block-1 power rates for Nov–Dec 2026 when present.
    """
    if not config.agreed_power:
        return Decimal("0"), [], ["missing_agreed_power"]

    if not config.has_15min_measurement:
        # Flat power charge path for sites without 15-min measurement
        warnings: list[str] = []
        try:
            from ..tariffs.rate_registry import get_default_registry

            reg = registry or get_default_registry()
            reduced = reg.try_find(
                "network_power_flat_reduced",
                when,
                customer_category=config.customer_category,
            )
            rate = reduced or reg.find(
                "network_power_flat",
                when,
                customer_category=config.customer_category,
            )
        except MissingTariffError as exc:
            return Decimal("0"), [], [str(exc)]

        # Use max agreed power or block 1 if present
        power = max(config.agreed_power.values()) if config.agreed_power else Decimal(
            "0"
        )
        amount = power * rate.value
        line = ChargeLine(
            charge_id="network_power_flat",
            name="Network power (no 15-min)",
            amount=amount,
            unit="EUR",
            quantity=power,
            rate=rate.value,
            calculation_base="contracted_power",
            vat_applicable=True,
            rate_id=rate.rate_id,
        )
        return amount, [line], warnings

    total = Decimal("0")
    charges: list[ChargeLine] = []
    warnings: list[str] = []

    for block, power_kw in sorted(config.agreed_power.items()):
        try:
            rate = get_network_power_rate(
                when,
                customer_category=config.customer_category,
                network_block=int(block),
                registry=registry,
            )
        except MissingTariffError as exc:
            warnings.append(str(exc))
            continue
        amount = power_kw * rate.value
        total += amount
        note = None
        if rate.rate_type == "network_power_reduced":
            note = "Reduced Nov-Dec 2026 high-season power tariff (ANJP239)"
        charges.append(
            ChargeLine(
                charge_id=f"network_power_b{block}",
                name=f"Agreed power block {block}",
                amount=amount,
                unit="EUR",
                quantity=power_kw,
                rate=rate.value,
                calculation_base="contracted_power",
                vat_applicable=True,
                rate_id=rate.rate_id,
                notes=note,
            )
        )

    return total, charges, warnings
