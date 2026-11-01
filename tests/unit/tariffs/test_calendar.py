"""Tariff calendar tests including DST and holidays."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.slovenian_energy_costs.models import DayType, Season
from custom_components.slovenian_energy_costs.tariffs.calendar import (
    TariffCalendar,
    classify_day,
    get_supplier_vt_mt,
    get_tariff_block,
    is_slovenian_holiday,
)

TZ = ZoneInfo("Europe/Ljubljana")


def test_ordinary_weekday_low_season() -> None:
    # Wednesday 2026-06-17 10:00 — low season workday → block 2
    info = get_tariff_block(datetime(2026, 6, 17, 10, 0, tzinfo=TZ))
    assert info.season == Season.LOW
    assert info.day_type == DayType.WORKDAY
    assert info.block == 2


def test_weekend_high_season() -> None:
    # Saturday 2026-11-14 10:00 — high season weekend
    info = get_tariff_block(datetime(2026, 11, 14, 10, 0, tzinfo=TZ))
    assert info.season == Season.HIGH
    assert info.day_type == DayType.WEEKEND
    assert info.block == 2


def test_slovenian_public_holiday() -> None:
    assert is_slovenian_holiday(datetime(2026, 12, 25).date())
    assert classify_day(datetime(2026, 12, 25).date()) == DayType.HOLIDAY
    info = get_tariff_block(datetime(2026, 12, 25, 10, 0, tzinfo=TZ))
    assert info.day_type == DayType.HOLIDAY


def test_tariff_block_transition() -> None:
    info = get_tariff_block(datetime(2026, 6, 17, 13, 59, tzinfo=TZ))
    assert info.block == 2
    assert info.next_block == 3
    assert info.next_transition is not None
    assert info.next_transition.hour == 14


def test_missing_future_year_schedule() -> None:
    cal = TariffCalendar()
    with pytest.raises(ValueError, match="No network tariff schedule"):
        cal.resolve(datetime(2030, 1, 1, 12, 0, tzinfo=TZ))


def test_spring_dst_change() -> None:
    # 2026-03-29 spring forward in Europe/Ljubljana (02:00 -> 03:00)
    before = get_tariff_block(datetime(2026, 3, 29, 1, 30, tzinfo=TZ))
    after = get_tariff_block(datetime(2026, 3, 29, 3, 30, tzinfo=TZ))
    assert before.local_time.tzinfo is not None
    assert after.local_time.tzinfo is not None
    assert before.block in {1, 2, 3, 4, 5}
    assert after.block in {1, 2, 3, 4, 5}


def test_autumn_dst_repeated_hour() -> None:
    # 2026-10-25 autumn back — local 02:30 occurs twice; both resolve
    first = datetime(2026, 10, 25, 2, 30, tzinfo=TZ)
    info = get_tariff_block(first)
    assert info.block in {1, 2, 3, 4, 5}


def test_supplier_vt_mt_independent_of_network() -> None:
    # Workday 10:00 is VT for supplier
    assert get_supplier_vt_mt(datetime(2026, 6, 17, 10, 0, tzinfo=TZ)) == "VT"
    assert get_supplier_vt_mt(datetime(2026, 6, 17, 23, 0, tzinfo=TZ)) == "MT"
    # Weekend is MT
    assert get_supplier_vt_mt(datetime(2026, 6, 20, 10, 0, tzinfo=TZ)) == "MT"
    # Holiday is MT
    assert get_supplier_vt_mt(datetime(2026, 12, 25, 10, 0, tzinfo=TZ)) == "MT"
