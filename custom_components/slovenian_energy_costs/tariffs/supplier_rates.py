"""Supplier electricity price resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..models import SiteConfig, SupplierMode
from .calendar import get_supplier_vt_mt


@dataclass(frozen=True, slots=True)
class SupplierPriceResult:
    """Resolved supplier commodity price for a timestamp."""

    price_ex_vat: Decimal
    price_inc_vat: Decimal
    tariff_label: str
    includes_vat_configured: bool
    base_price: Decimal
    adjustments_applied: tuple[str, ...]


class SupplierPriceResolver:
    """Resolve ET / VT-MT / dynamic supplier prices with contract adjustments."""

    def __init__(self, config: SiteConfig) -> None:
        self._config = config

    def resolve(
        self,
        when: datetime,
        *,
        dynamic_price: Decimal | None = None,
    ) -> SupplierPriceResult:
        mode = SupplierMode(self._config.supplier_mode)
        adjustments: list[str] = []

        if mode == SupplierMode.ET:
            base = self._config.supplier_et_price
            label = "ET"
        elif mode == SupplierMode.VT_MT:
            label = get_supplier_vt_mt(when)
            base = (
                self._config.supplier_vt_price
                if label == "VT"
                else self._config.supplier_mt_price
            )
        else:
            if dynamic_price is None:
                raise ValueError("Dynamic supplier mode requires a current price")
            base = dynamic_price
            label = "DYNAMIC"
            adjustments.append("dynamic_entity")

        price = base
        if self._config.supplier_markup_fixed:
            price += self._config.supplier_markup_fixed
            adjustments.append("fixed_markup")
        if self._config.supplier_markup_pct:
            price *= Decimal("1") + (
                self._config.supplier_markup_pct / Decimal("100")
            )
            adjustments.append("pct_markup")
        if self._config.supplier_discount_pct:
            price *= Decimal("1") - (
                self._config.supplier_discount_pct / Decimal("100")
            )
            adjustments.append("discount")

        vat = self._config.vat_rate
        if self._config.prices_include_vat:
            price_inc = price
            price_ex = price / (Decimal("1") + vat) if vat else price
        else:
            price_ex = price
            price_inc = price * (Decimal("1") + vat) if vat else price

        return SupplierPriceResult(
            price_ex_vat=price_ex,
            price_inc_vat=price_inc,
            tariff_label=label,
            includes_vat_configured=self._config.prices_include_vat,
            base_price=base,
            adjustments_applied=tuple(adjustments),
        )
