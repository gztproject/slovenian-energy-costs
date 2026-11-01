"""Annual net-metering donor accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..models import NetMeteringState, SettlementInterval, SiteConfig


@dataclass(frozen=True, slots=True)
class NetMeteringUpdate:
    """Result of applying one interval to the net-metering account."""

    eligible_export_delta: Decimal
    shared_deduction: Decimal
    import_delta: Decimal
    export_delta: Decimal
    balance: Decimal
    history_complete: bool
    reserve_status: str


def apply_interval_to_net_metering(
    state: NetMeteringState,
    interval: SettlementInterval,
    *,
    config: SiteConfig,
) -> tuple[NetMeteringState, NetMeteringUpdate]:
    """Update annual net-metering state for a donor site.

    Donor deduction uses full allocated shared energy, not only used shared.
    """
    export_delta = interval.physical_export_kwh
    import_delta = interval.physical_import_kwh

    if config.donor_export_already_deducted:
        # Export sensor already excludes administratively shared energy
        shared_deduction = Decimal("0")
        eligible_delta = export_delta
    else:
        shared_deduction = interval.shared_allocated_kwh
        eligible_delta = export_delta - shared_deduction

    state.observed_export_kwh += export_delta
    state.observed_import_kwh += import_delta
    state.shared_deducted_kwh += shared_deduction

    opening = (
        state.opening_balance_kwh
        if state.opening_balance_kwh is not None
        else Decimal("0")
    )
    balance = opening + state.eligible_export_kwh - state.observed_import_kwh

    if state.history_complete:
        status = "complete"
    elif state.opening_balance_kwh is not None and state.opening_date is not None:
        status = "opening_balance_known"
    else:
        status = "incomplete_history"

    update = NetMeteringUpdate(
        eligible_export_delta=eligible_delta,
        shared_deduction=shared_deduction,
        import_delta=import_delta,
        export_delta=export_delta,
        balance=balance,
        history_complete=state.history_complete,
        reserve_status=status,
    )
    return state, update


def create_year_state(
    year: int,
    config: SiteConfig,
    *,
    recording_started: date | None = None,
) -> NetMeteringState:
    """Create net-metering state for a calendar year."""
    opening = config.net_metering_opening_balance
    opening_date = config.net_metering_opening_date
    history_complete = False
    if opening is not None and opening_date is not None:
        history_complete = opening_date <= date(year, 1, 1)
    elif recording_started is not None and recording_started <= date(year, 1, 1):
        history_complete = True
    return NetMeteringState(
        year=year,
        opening_balance_kwh=opening,
        opening_date=opening_date,
        history_complete=history_complete,
    )


def projected_year_end_balance(
    state: NetMeteringState,
    *,
    as_of: date,
) -> Decimal | None:
    """Simple linear projection — clearly a forecast, may return None."""
    if as_of.year != state.year:
        return None
    day_of_year = as_of.timetuple().tm_yday
    if day_of_year <= 0:
        return None
    # Observed net so far
    observed_net = state.eligible_export_kwh - state.observed_import_kwh
    opening = state.opening_balance_kwh or Decimal("0")
    current = opening + observed_net
    # Linear extrapolation to day 365/366
    import calendar

    days_in_year = 366 if calendar.isleap(as_of.year) else 365
    if not state.history_complete and state.opening_date:
        # Only project from observed period; still a forecast
        pass
    scale = Decimal(days_in_year) / Decimal(day_of_year)
    return current * scale
