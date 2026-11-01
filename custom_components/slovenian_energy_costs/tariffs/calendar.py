"""Slovenian network tariff calendar (Europe/Ljubljana)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from ..models import DayType, Season, TariffBlockInfo

DATA_DIR = Path(__file__).parent / "data"
TZ = ZoneInfo("Europe/Ljubljana")


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_s, minute_s = value.split(":")
    return int(hour_s), int(minute_s)


def _minutes_since_midnight(local_dt: datetime) -> int:
    return local_dt.hour * 60 + local_dt.minute


@lru_cache(maxsize=1)
def _load_schedules() -> dict:
    with (DATA_DIR / "schedules.json").open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _load_holidays() -> dict[str, set[date]]:
    with (DATA_DIR / "si_holidays.json").open(encoding="utf-8") as handle:
        raw = json.load(handle)
    result: dict[str, set[date]] = {}
    for year, days in raw.get("holidays", {}).items():
        result[year] = {date.fromisoformat(d) for d in days}
    return result


def is_slovenian_holiday(day: date) -> bool:
    """Return True if the date is a configured Slovenian public holiday."""
    holidays = _load_holidays().get(str(day.year), set())
    return day in holidays


def classify_day(day: date) -> DayType:
    """Classify a calendar day for network tariff purposes."""
    if is_slovenian_holiday(day):
        return DayType.HOLIDAY
    if day.weekday() >= 5:
        return DayType.WEEKEND
    return DayType.WORKDAY


def classify_season(day: date, high_season_months: list[int]) -> Season:
    """Classify high/low season from schedule months."""
    if day.month in high_season_months:
        return Season.HIGH
    return Season.LOW


def _select_schedule(when: date) -> dict:
    schedules = _load_schedules()["schedules"]
    for schedule in schedules:
        start = date.fromisoformat(schedule["effective_from"])
        end_raw = schedule.get("effective_until")
        end = date.fromisoformat(end_raw) if end_raw else None
        if when < start:
            continue
        if end is not None and when > end:
            continue
        return schedule
    raise ValueError(
        f"No network tariff schedule covers {when.isoformat()}. "
        "Update bundled tariff schedules."
    )


def _segments_for(
    schedule: dict, day_type: DayType, season: Season
) -> list[dict]:
    key = "workday" if day_type == DayType.WORKDAY else "weekend_holiday"
    season_key = "high" if season == Season.HIGH else "low"
    return list(schedule[key][season_key])


def _block_at_minutes(segments: list[dict], minutes: int) -> tuple[int, int]:
    """Return (block, segment_index) for minutes since local midnight."""
    for idx, segment in enumerate(segments):
        start_h, start_m = _parse_hhmm(segment["start"])
        end_h, end_m = _parse_hhmm(segment["end"])
        start = start_h * 60 + start_m
        end = 24 * 60 if end_h == 24 else end_h * 60 + end_m
        if start <= minutes < end:
            return int(segment["block"]), idx
    # Fallback: last segment
    return int(segments[-1]["block"]), len(segments) - 1


def _next_transition(
    local_dt: datetime, segments: list[dict], segment_idx: int
) -> tuple[int | None, datetime | None]:
    if segment_idx + 1 < len(segments):
        nxt = segments[segment_idx + 1]
        hour, minute = _parse_hhmm(nxt["start"])
        transition = local_dt.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return int(nxt["block"]), transition
    # Next day first segment
    nxt_day = (local_dt + timedelta(days=1)).date()
    schedule = _select_schedule(nxt_day)
    day_type = classify_day(nxt_day)
    season = classify_season(nxt_day, schedule["high_season_months"])
    nxt_segments = _segments_for(schedule, day_type, season)
    nxt = nxt_segments[0]
    hour, minute = _parse_hhmm(nxt["start"])
    transition = datetime(
        nxt_day.year,
        nxt_day.month,
        nxt_day.day,
        hour,
        minute,
        tzinfo=TZ,
    )
    return int(nxt["block"]), transition


class TariffCalendar:
    """Effective-dated Slovenian network tariff calendar."""

    def resolve(self, when: datetime) -> TariffBlockInfo:
        """Resolve network tariff block for an aware or naive datetime."""
        if when.tzinfo is None:
            local = when.replace(tzinfo=TZ)
        else:
            local = when.astimezone(TZ)

        day = local.date()
        schedule = _select_schedule(day)
        day_type = classify_day(day)
        season = classify_season(day, schedule["high_season_months"])
        segments = _segments_for(schedule, day_type, season)
        minutes = _minutes_since_midnight(local)
        block, idx = _block_at_minutes(segments, minutes)
        next_block, next_transition = _next_transition(local, segments, idx)
        return TariffBlockInfo(
            block=block,
            season=season,
            day_type=day_type,
            schedule_id=schedule["schedule_id"],
            local_time=local,
            next_block=next_block,
            next_transition=next_transition,
        )


_DEFAULT_CALENDAR = TariffCalendar()


def get_tariff_block(when: datetime) -> TariffBlockInfo:
    """Resolve the current network tariff block using the default calendar."""
    return _DEFAULT_CALENDAR.resolve(when)


def get_supplier_vt_mt(when: datetime) -> str:
    """Return 'VT' or 'MT' for the default dual-tariff supplier schedule."""
    if when.tzinfo is None:
        local = when.replace(tzinfo=TZ)
    else:
        local = when.astimezone(TZ)
    schedule = _load_schedules()["supplier_vt_mt"]
    day = local.date()
    if schedule.get("holiday_is_mt") and is_slovenian_holiday(day):
        return "MT"
    if schedule.get("weekend_is_mt") and day.weekday() >= 5:
        return "MT"
    start_h, start_m = _parse_hhmm(schedule["vt_start"])
    end_h, end_m = _parse_hhmm(schedule["vt_end"])
    minutes = _minutes_since_midnight(local)
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if start <= minutes < end:
        return "VT"
    return "MT"
