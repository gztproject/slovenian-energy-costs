"""Network energy (omrežnina za energijo) charges."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..models import ChargeLine, SiteConfig
from ..tariffs.calendar import get_tariff_block
from ..tariffs.network_rates import network_energy_cost
from ..tariffs.rate_registry import MissingTariffError, RateRegistry


def calculate_network_energy(
    *,
    physical_import_kwh: Decimal,
    when: datetime,
    config: SiteConfig,
    registry: RateRegistry | None = None,
) -> tuple[Decimal, ChargeLine | None, int | None, str | None]:
    """Calculate network energy cost on physical import.

    Returns (amount, charge_line, block, warning).
    """
    block_info = get_tariff_block(when)
    day = when.date() if isinstance(when, datetime) else when
    try:
        amount, rate = network_energy_cost(
            physical_import_kwh,
            day,
            customer_category=config.customer_category,
            network_block=block_info.block,
            registry=registry,
        )
    except MissingTariffError as exc:
        return Decimal("0"), None, block_info.block, str(exc)

    line = ChargeLine(
        charge_id="network_energy",
        name=f"Network energy block {block_info.block}",
        amount=amount,
        unit="EUR",
        quantity=physical_import_kwh,
        rate=rate.value,
        calculation_base="physical_import",
        vat_applicable=True,
        rate_id=rate.rate_id,
    )
    return amount, line, block_info.block, None
