"""Effective-dated rate registry for network and levy rates."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from ..models import RateRecord

DATA_DIR = Path(__file__).parent / "data"


class MissingTariffError(LookupError):
    """Raised when no rate covers the requested date."""


class RateRegistry:
    """Versioned collection of effective-dated rates."""

    def __init__(self, rates: list[RateRecord], tariff_version: str) -> None:
        self._rates = rates
        self.tariff_version = tariff_version

    def find(
        self,
        rate_type: str,
        when: date,
        *,
        customer_category: str | None = None,
        network_block: int | None = None,
    ) -> RateRecord:
        """Find the unique matching rate or raise MissingTariffError."""
        matches: list[RateRecord] = []
        for rate in self._rates:
            if rate.rate_type != rate_type:
                continue
            if not rate.covers(when):
                continue
            if (
                customer_category is not None
                and rate.customer_category is not None
                and rate.customer_category != customer_category
            ):
                continue
            if (
                network_block is not None
                and rate.network_block is not None
                and rate.network_block != network_block
            ):
                continue
            matches.append(rate)
        if not matches:
            raise MissingTariffError(
                f"No {rate_type} rate for {when} "
                f"(category={customer_category}, block={network_block})"
            )
        # Prefer most specific match (with category/block)
        matches.sort(
            key=lambda r: (
                0 if r.customer_category is not None else 1,
                0 if r.network_block is not None else 1,
                r.effective_from,
            )
        )
        return matches[0]

    def try_find(
        self,
        rate_type: str,
        when: date,
        *,
        customer_category: str | None = None,
        network_block: int | None = None,
    ) -> RateRecord | None:
        try:
            return self.find(
                rate_type,
                when,
                customer_category=customer_category,
                network_block=network_block,
            )
        except MissingTariffError:
            return None


def _build_from_network_json(payload: dict) -> list[RateRecord]:
    effective_from = date.fromisoformat(payload["effective_from"])
    effective_until = date.fromisoformat(payload["effective_until"])
    source_url = payload.get("source_url")
    source_date = (
        date.fromisoformat(payload["source_date"])
        if payload.get("source_date")
        else None
    )
    rates: list[RateRecord] = []
    reduced_months = set(payload.get("reduced_power_months") or [])
    reduced_year = payload.get("reduced_power_year")

    for category, blocks in payload.get("combined", {}).items():
        for block_s, values in blocks.items():
            block = int(block_s)
            rates.append(
                RateRecord(
                    rate_id=f"net_energy_{category}_b{block}_{payload['tariff_version']}",
                    rate_type="network_energy",
                    value=Decimal(values["energy"]),
                    unit="EUR/kWh",
                    effective_from=effective_from,
                    effective_until=effective_until,
                    customer_category=str(category),
                    network_block=block,
                    source_url=source_url,
                    source_date=source_date,
                )
            )
            rates.append(
                RateRecord(
                    rate_id=f"net_power_{category}_b{block}_{payload['tariff_version']}",
                    rate_type="network_power",
                    value=Decimal(values["power"]),
                    unit="EUR/kW/month",
                    effective_from=effective_from,
                    effective_until=effective_until,
                    customer_category=str(category),
                    network_block=block,
                    source_url=source_url,
                    source_date=source_date,
                )
            )
            reduced = values.get("power_reduced_high_2026")
            if reduced and reduced_year:
                # Reduced block-1 power only for Nov-Dec of the special year
                for month in sorted(reduced_months):
                    month_start = date(int(reduced_year), int(month), 1)
                    if month == 12:
                        month_end = date(int(reduced_year), 12, 31)
                    else:
                        month_end = date(int(reduced_year), int(month) + 1, 1)
                        from datetime import timedelta

                        month_end = month_end - timedelta(days=1)
                    rates.append(
                        RateRecord(
                            rate_id=(
                                f"net_power_reduced_{category}_b{block}_"
                                f"{reduced_year}-{month:02d}"
                            ),
                            rate_type="network_power_reduced",
                            value=Decimal(reduced),
                            unit="EUR/kW/month",
                            effective_from=month_start,
                            effective_until=month_end,
                            customer_category=str(category),
                            network_block=block,
                            source_url=source_url,
                            source_date=source_date,
                            notes="ANJP239 reduced high-season power Nov-Dec 2026",
                        )
                    )

    without = payload.get("without_15min", {}).get("nn")
    if without:
        rates.append(
            RateRecord(
                rate_id=f"net_energy_et_nn_{payload['tariff_version']}",
                rate_type="network_energy_et",
                value=Decimal(without["energy_et"]),
                unit="EUR/kWh",
                effective_from=effective_from,
                effective_until=effective_until,
                customer_category="0",
                source_url=source_url,
                source_date=source_date,
            )
        )
        rates.append(
            RateRecord(
                rate_id=f"net_energy_vt_nn_{payload['tariff_version']}",
                rate_type="network_energy_vt",
                value=Decimal(without["energy_vt"]),
                unit="EUR/kWh",
                effective_from=effective_from,
                effective_until=effective_until,
                customer_category="0",
                source_url=source_url,
                source_date=source_date,
            )
        )
        rates.append(
            RateRecord(
                rate_id=f"net_energy_mt_nn_{payload['tariff_version']}",
                rate_type="network_energy_mt",
                value=Decimal(without["energy_mt"]),
                unit="EUR/kWh",
                effective_from=effective_from,
                effective_until=effective_until,
                customer_category="0",
                source_url=source_url,
                source_date=source_date,
            )
        )
        rates.append(
            RateRecord(
                rate_id=f"net_power_flat_nn_{payload['tariff_version']}",
                rate_type="network_power_flat",
                value=Decimal(without["power"]),
                unit="EUR/kW/month",
                effective_from=effective_from,
                effective_until=effective_until,
                customer_category="0",
                source_url=source_url,
                source_date=source_date,
            )
        )
        if without.get("power_reduced_high_2026") and reduced_year:
            for month in sorted(reduced_months):
                month_start = date(int(reduced_year), int(month), 1)
                if month == 12:
                    month_end = date(int(reduced_year), 12, 31)
                else:
                    from datetime import timedelta

                    month_end = date(
                        int(reduced_year), int(month) + 1, 1
                    ) - timedelta(days=1)
                rates.append(
                    RateRecord(
                        rate_id=f"net_power_flat_reduced_nn_{reduced_year}-{month:02d}",
                        rate_type="network_power_flat_reduced",
                        value=Decimal(without["power_reduced_high_2026"]),
                        unit="EUR/kW/month",
                        effective_from=month_start,
                        effective_until=month_end,
                        customer_category="0",
                        source_url=source_url,
                        source_date=source_date,
                    )
                )
    return rates


@lru_cache(maxsize=1)
def get_default_registry() -> RateRegistry:
    """Load the bundled ANJP239 2026 rate tables."""
    with (DATA_DIR / "network_rates_2026.json").open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rates = _build_from_network_json(payload)
    return RateRegistry(rates, tariff_version=payload["tariff_version"])
