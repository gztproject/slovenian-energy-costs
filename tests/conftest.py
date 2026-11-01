"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.slovenian_energy_costs.models import (
    SettlementInterval,
    SettlementSource,
    SiteConfig,
)

TZ = ZoneInfo("Europe/Ljubljana")


@pytest.fixture
def site_config() -> SiteConfig:
    return SiteConfig(
        site_name="Test Site",
        site_role="consumer",
        supplier_mode="et",
        supplier_et_price=Decimal("0.10000"),
        prices_include_vat=False,
        vat_rate=Decimal("0.22"),
        customer_category="0",
        has_15min_measurement=True,
        agreed_power={1: Decimal("4"), 2: Decimal("3"), 3: Decimal("2")},
        enable_levies=True,
        excise_rate=Decimal("0.00100"),
        ove_spte_rate=Decimal("0.00200"),
    )


@pytest.fixture
def sample_interval() -> SettlementInterval:
    start = datetime(2026, 6, 15, 10, 0, tzinfo=TZ)
    end = datetime(2026, 6, 15, 10, 15, tzinfo=TZ)
    return SettlementInterval(
        interval_id="20260615T080000Z",
        interval_start=start,
        interval_end=end,
        physical_import_kwh=Decimal("1.000"),
        physical_export_kwh=Decimal("0"),
        supplier_billable_kwh=Decimal("1.000"),
        source=SettlementSource.PHYSICAL,
    )
