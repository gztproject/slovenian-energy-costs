"""Physical interval provider helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.slovenian_energy_costs.billing.providers import (
    align_interval_end,
    compute_physical_interval,
    make_interval_id,
)
from custom_components.slovenian_energy_costs.models import MeterBaseline

TZ = ZoneInfo("Europe/Ljubljana")


def test_align_interval_end() -> None:
    now = datetime(2026, 6, 15, 10, 17, 30, tzinfo=TZ)
    end = align_interval_end(now, 15)
    assert end == datetime(2026, 6, 15, 10, 15, tzinfo=TZ)


def test_compute_physical_interval_and_idempotent_id() -> None:
    baseline = MeterBaseline(
        interval_id="prev",
        timestamp=datetime(2026, 6, 15, 10, 0, tzinfo=TZ),
        import_total_kwh=Decimal("100"),
        export_total_kwh=Decimal("50"),
    )
    interval, reset = compute_physical_interval(
        current_import_kwh=Decimal("100.25"),
        current_export_kwh=Decimal("50.10"),
        baseline=baseline,
        interval_end=datetime(2026, 6, 15, 10, 15, tzinfo=TZ),
    )
    assert reset is False
    assert interval is not None
    assert interval.physical_import_kwh == Decimal("0.25")
    assert interval.physical_export_kwh == Decimal("0.10")
    assert interval.interval_id == make_interval_id(interval.interval_start)


def test_counter_reset_detected() -> None:
    baseline = MeterBaseline(
        interval_id="prev",
        timestamp=datetime(2026, 6, 15, 10, 0, tzinfo=TZ),
        import_total_kwh=Decimal("100"),
    )
    interval, reset = compute_physical_interval(
        current_import_kwh=Decimal("1"),
        current_export_kwh=None,
        baseline=baseline,
        interval_end=datetime(2026, 6, 15, 10, 15, tzinfo=TZ),
    )
    assert reset is True
    assert interval is None
