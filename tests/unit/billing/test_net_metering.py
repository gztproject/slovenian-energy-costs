"""Annual net-metering donor accounting tests."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.slovenian_energy_costs.billing.net_metering import (
    apply_interval_to_net_metering,
    create_year_state,
)
from custom_components.slovenian_energy_costs.models import (
    SettlementInterval,
    SiteConfig,
)

TZ = ZoneInfo("Europe/Ljubljana")


def test_annual_surplus() -> None:
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(2026, config, recording_started=date(2026, 1, 1))
    state.history_complete = True
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("1"),
        physical_export_kwh=Decimal("3"),
        shared_allocated_kwh=Decimal("0"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.balance == Decimal("2")
    assert state.eligible_export_kwh == Decimal("3")


def test_annual_deficit() -> None:
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(2026, config)
    state.history_complete = True
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("5"),
        physical_export_kwh=Decimal("2"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.balance == Decimal("-3")


def test_shared_energy_deduction_full_allocation() -> None:
    """Donor deducts full allocated shared energy, not only used."""
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(2026, config)
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("0"),
        physical_export_kwh=Decimal("10"),
        shared_allocated_kwh=Decimal("2.0"),
        shared_used_kwh=Decimal("1.5"),
        shared_unused_kwh=Decimal("0.5"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.shared_deduction == Decimal("2.0")
    assert state.eligible_export_kwh == Decimal("8.0")
    assert update.balance == Decimal("8.0")


def test_unused_allocation_still_deducted_from_donor() -> None:
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(2026, config)
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("0"),
        physical_export_kwh=Decimal("10"),
        shared_allocated_kwh=Decimal("2.0"),
        shared_used_kwh=Decimal("0"),
        shared_unused_kwh=Decimal("2.0"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.shared_deduction == Decimal("2.0")


def test_incomplete_january_april() -> None:
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(
        2026, config, recording_started=date(2026, 5, 1)
    )
    assert state.history_complete is False
    _, update = apply_interval_to_net_metering(
        state,
        SettlementInterval(
            interval_id="1",
            interval_start=datetime(2026, 5, 1, 12, 0, tzinfo=TZ),
            interval_end=datetime(2026, 5, 1, 12, 15, tzinfo=TZ),
            physical_import_kwh=Decimal("1"),
            physical_export_kwh=Decimal("2"),
        ),
        config=config,
    )
    assert update.reserve_status == "incomplete_history"


def test_known_opening_balance() -> None:
    config = SiteConfig(
        site_name="D",
        site_role="producer",
        net_metering_opening_balance=Decimal("100"),
        net_metering_opening_date=date(2026, 5, 1),
    )
    state = create_year_state(2026, config)
    assert state.opening_balance_kwh == Decimal("100")
    _, update = apply_interval_to_net_metering(
        state,
        SettlementInterval(
            interval_id="1",
            interval_start=datetime(2026, 5, 1, 12, 0, tzinfo=TZ),
            interval_end=datetime(2026, 5, 1, 12, 15, tzinfo=TZ),
            physical_import_kwh=Decimal("10"),
            physical_export_kwh=Decimal("5"),
        ),
        config=config,
    )
    assert update.reserve_status == "opening_balance_known"
    assert update.balance == Decimal("95")  # 100 + 5 - 10


def test_no_double_deduct_when_export_already_deducted() -> None:
    config = SiteConfig(
        site_name="D",
        site_role="producer",
        donor_export_already_deducted=True,
    )
    state = create_year_state(2026, config)
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("0"),
        physical_export_kwh=Decimal("8"),  # already net of sharing
        shared_allocated_kwh=Decimal("2"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.shared_deduction == 0
    assert state.eligible_export_kwh == Decimal("8")


def test_donor_without_souporaba() -> None:
    config = SiteConfig(site_name="D", site_role="producer")
    state = create_year_state(2026, config, recording_started=date(2026, 1, 1))
    state.history_complete = True
    interval = SettlementInterval(
        interval_id="1",
        interval_start=datetime(2026, 6, 1, 12, 0, tzinfo=TZ),
        interval_end=datetime(2026, 6, 1, 12, 15, tzinfo=TZ),
        physical_import_kwh=Decimal("6000"),
        physical_export_kwh=Decimal("8000"),
        shared_allocated_kwh=Decimal("0"),
    )
    state, update = apply_interval_to_net_metering(state, interval, config=config)
    assert update.balance == Decimal("2000")
