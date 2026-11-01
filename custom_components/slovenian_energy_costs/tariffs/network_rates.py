"""Helpers for looking up network energy and power rates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..models import RateRecord
from .rate_registry import MissingTariffError, RateRegistry, get_default_registry


def get_network_energy_rate(
    when: date,
    *,
    customer_category: str,
    network_block: int,
    registry: RateRegistry | None = None,
) -> RateRecord:
    """Return the network energy rate for a category and block."""
    reg = registry or get_default_registry()
    return reg.find(
        "network_energy",
        when,
        customer_category=customer_category,
        network_block=network_block,
    )


def get_network_power_rate(
    when: date,
    *,
    customer_category: str,
    network_block: int,
    registry: RateRegistry | None = None,
) -> RateRecord:
    """Return network power rate, preferring Nov-Dec 2026 reduced rates."""
    reg = registry or get_default_registry()
    reduced = reg.try_find(
        "network_power_reduced",
        when,
        customer_category=customer_category,
        network_block=network_block,
    )
    if reduced is not None:
        return reduced
    return reg.find(
        "network_power",
        when,
        customer_category=customer_category,
        network_block=network_block,
    )


def network_energy_cost(
    kwh: Decimal,
    when: date,
    *,
    customer_category: str,
    network_block: int,
    registry: RateRegistry | None = None,
) -> tuple[Decimal, RateRecord]:
    """Compute network energy cost for physical import."""
    rate = get_network_energy_rate(
        when,
        customer_category=customer_category,
        network_block=network_block,
        registry=registry,
    )
    return kwh * rate.value, rate


__all__ = [
    "MissingTariffError",
    "get_network_energy_rate",
    "get_network_power_rate",
    "network_energy_cost",
]
