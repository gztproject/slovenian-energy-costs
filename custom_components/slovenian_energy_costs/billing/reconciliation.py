"""Billing reconciliation and quality classification."""

from __future__ import annotations

from ..models import ComputationQuality, SettlementInterval


def classify_settlement(interval: SettlementInterval) -> ComputationQuality:
    """Classify financial booking quality for a settlement interval."""
    if not interval.settlement_accumulated:
        return ComputationQuality.INVALID
    if interval.quality == ComputationQuality.INVALID:
        return ComputationQuality.INVALID
    if interval.quality == ComputationQuality.INCOMPLETE:
        return ComputationQuality.INCOMPLETE
    if interval.reconciliation_status in {
        "mismatch_skip",
    }:
        return ComputationQuality.INVALID
    if interval.reconciliation_status in {
        "mismatch_warn",
    }:
        return ComputationQuality.ESTIMATED
    return interval.quality


def should_book_financially(interval: SettlementInterval) -> bool:
    """Return True if the interval may be booked into monetary counters."""
    quality = classify_settlement(interval)
    return quality in {
        ComputationQuality.ACTUAL,
        ComputationQuality.ESTIMATED,
    }
