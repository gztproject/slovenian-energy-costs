"""Souporaba financial accounting (does not recompute sharing settlement)."""

from __future__ import annotations

from decimal import Decimal

from ..models import SettlementInterval


def receiver_supplier_billable(interval: SettlementInterval) -> Decimal:
    """Supplier-billable energy from accepted Souporaba settlement."""
    return interval.resolved_billable_kwh()


def receiver_network_billable(interval: SettlementInterval) -> Decimal:
    """Network charges remain on full physical import."""
    return interval.physical_import_kwh


def receiver_savings(
    *,
    used_shared_kwh: Decimal,
    supplier_price_ex_vat: Decimal,
) -> Decimal:
    """Commodity savings from usable shared energy."""
    return used_shared_kwh * supplier_price_ex_vat


def unused_allocation_opportunity_cost(
    *,
    unused_shared_kwh: Decimal,
    supplier_price_ex_vat: Decimal,
) -> Decimal:
    """Opportunity-cost estimate of unused allocation (not an invoice charge)."""
    return unused_shared_kwh * supplier_price_ex_vat


def verify_souporaba_invariants(interval: SettlementInterval) -> list[str]:
    """Check mathematical invariants without replacing Souporaba results."""
    issues: list[str] = []
    used = interval.shared_used_kwh
    unused = interval.shared_unused_kwh
    allocated = interval.shared_allocated_kwh
    if used + unused != allocated and abs(used + unused - allocated) > Decimal(
        "0.0001"
    ):
        issues.append("used_plus_unused_ne_allocated")
    expected_used = min(allocated, interval.physical_import_kwh)
    if abs(used - expected_used) > Decimal("0.0001"):
        issues.append("used_shared_mismatch")
    expected_billable = max(
        interval.physical_import_kwh - allocated, Decimal("0")
    )
    if (
        interval.supplier_billable_kwh is not None
        and abs(interval.supplier_billable_kwh - expected_billable)
        > Decimal("0.0001")
    ):
        issues.append("billable_mismatch")
    return issues
