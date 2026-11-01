"""Settlement provider protocol and physical interval helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from ..models import (
    ComputationQuality,
    MeterBaseline,
    SettlementInterval,
    SettlementSource,
)

TZ = ZoneInfo("Europe/Ljubljana")


class SettlementProvider(Protocol):
    """Protocol for sources of completed settlement intervals."""

    async def get_completed_intervals(self) -> list[SettlementInterval]:
        """Return newly completed intervals ready for financial booking."""
        ...


def align_interval_end(
    when: datetime, interval_minutes: int = 15
) -> datetime:
    """Return the most recent interval end at or before when (local TZ)."""
    if when.tzinfo is None:
        local = when.replace(tzinfo=TZ)
    else:
        local = when.astimezone(TZ)
    minute = (local.minute // interval_minutes) * interval_minutes
    end = local.replace(minute=minute, second=0, microsecond=0)
    if end > local:
        end -= timedelta(minutes=interval_minutes)
    return end


def interval_bounds(
    interval_end: datetime, interval_minutes: int = 15
) -> tuple[datetime, datetime]:
    """Return (start, end) for an interval ending at interval_end."""
    end = interval_end
    start = end - timedelta(minutes=interval_minutes)
    return start, end


def make_interval_id(interval_start: datetime) -> str:
    """Stable interval id from UTC start."""
    if interval_start.tzinfo is None:
        start = interval_start.replace(tzinfo=TZ)
    else:
        start = interval_start
    return start.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def compute_physical_interval(
    *,
    current_import_kwh: Decimal,
    current_export_kwh: Decimal | None,
    baseline: MeterBaseline,
    interval_end: datetime,
    interval_minutes: int = 15,
) -> tuple[SettlementInterval | None, bool]:
    """Compute a physical settlement interval from cumulative deltas.

    Returns (interval_or_None, is_reset).
    """
    if current_import_kwh < baseline.import_total_kwh:
        return None, True

    import_delta = current_import_kwh - baseline.import_total_kwh
    export_delta = Decimal("0")
    if current_export_kwh is not None and baseline.export_total_kwh is not None:
        if current_export_kwh < baseline.export_total_kwh:
            return None, True
        export_delta = current_export_kwh - baseline.export_total_kwh

    start, end = interval_bounds(interval_end, interval_minutes)
    interval = SettlementInterval(
        interval_id=make_interval_id(start),
        interval_start=start,
        interval_end=end,
        physical_import_kwh=import_delta,
        physical_export_kwh=export_delta,
        supplier_billable_kwh=import_delta,
        settlement_accumulated=True,
        reconciliation_status="not_configured",
        source=SettlementSource.PHYSICAL,
        quality=ComputationQuality.ACTUAL,
    )
    return interval, False
