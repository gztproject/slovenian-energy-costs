"""Electricity levies (trošarina, OVE/SPTE, etc.)."""

from __future__ import annotations

from decimal import Decimal

from ..models import ChargeLine, SiteConfig


def calculate_levies(
    *,
    physical_import_kwh: Decimal,
    config: SiteConfig,
) -> tuple[Decimal, list[ChargeLine]]:
    """Calculate per-kWh levies on physical imported energy.

    Souporaba must not reduce levies that remain based on physical import.
    """
    if not config.enable_levies:
        return Decimal("0"), []

    charges: list[ChargeLine] = []
    total = Decimal("0")

    if config.excise_rate:
        amount = physical_import_kwh * config.excise_rate
        total += amount
        charges.append(
            ChargeLine(
                charge_id="excise",
                name="Trošarina",
                amount=amount,
                unit="EUR",
                quantity=physical_import_kwh,
                rate=config.excise_rate,
                calculation_base="physical_import",
                vat_applicable=True,
                notes="Configurable excise; verify against current regulation",
            )
        )

    if config.ove_spte_rate:
        amount = physical_import_kwh * config.ove_spte_rate
        total += amount
        charges.append(
            ChargeLine(
                charge_id="ove_spte",
                name="Prispevek OVE/SPTE",
                amount=amount,
                unit="EUR",
                quantity=physical_import_kwh,
                rate=config.ove_spte_rate,
                calculation_base="physical_import",
                vat_applicable=True,
                notes="Configurable OVE/SPTE levy",
            )
        )

    return total, charges
