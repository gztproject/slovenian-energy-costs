"""VAT calculation helpers."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def apply_vat(
    net_amount: Decimal,
    vat_rate: Decimal,
    *,
    round_to_cents: bool = False,
) -> Decimal:
    """Return VAT amount for a net (ex-VAT) base."""
    vat = net_amount * vat_rate
    if round_to_cents:
        return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return vat


def strip_vat(gross_amount: Decimal, vat_rate: Decimal) -> Decimal:
    """Convert a VAT-inclusive amount to ex-VAT."""
    if vat_rate == 0:
        return gross_amount
    return gross_amount / (Decimal("1") + vat_rate)


def round_money(amount: Decimal) -> Decimal:
    """Round monetary amount to euro cents."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
