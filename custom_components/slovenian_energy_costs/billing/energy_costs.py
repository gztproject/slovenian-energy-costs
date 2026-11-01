"""Supplier commodity energy cost calculation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..models import ChargeLine, SiteConfig
from ..tariffs.supplier_rates import SupplierPriceResolver, SupplierPriceResult


def calculate_supplier_energy_cost(
    *,
    billable_kwh: Decimal,
    when: datetime,
    config: SiteConfig,
    dynamic_price: Decimal | None = None,
    include_vat_in_line: bool = False,
) -> tuple[Decimal, SupplierPriceResult, ChargeLine]:
    """Calculate supplier energy cost for billable kWh."""
    resolver = SupplierPriceResolver(config)
    price = resolver.resolve(when, dynamic_price=dynamic_price)
    unit = price.price_inc_vat if include_vat_in_line else price.price_ex_vat
    amount = billable_kwh * unit
    line = ChargeLine(
        charge_id="supplier_energy",
        name=f"Supplier energy ({price.tariff_label})",
        amount=amount,
        unit="EUR",
        quantity=billable_kwh,
        rate=unit,
        calculation_base="supplier_billable",
        vat_applicable=not include_vat_in_line,
        notes=(
            "VAT-inclusive unit price"
            if include_vat_in_line
            else "Ex-VAT unit price"
        ),
    )
    return amount, price, line
