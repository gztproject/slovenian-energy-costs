"""Deterministic billing engine — no Home Assistant imports."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..models import (
    BillingIntervalResult,
    ChargeLine,
    ComputationQuality,
    SettlementInterval,
    SiteConfig,
)
from ..tariffs.rate_registry import RateRegistry, get_default_registry
from .energy_costs import calculate_supplier_energy_cost
from .levies import calculate_levies
from .network_energy import calculate_network_energy
from .reconciliation import classify_settlement, should_book_financially
from .souporaba import (
    receiver_network_billable,
    receiver_savings,
    receiver_supplier_billable,
    unused_allocation_opportunity_cost,
    verify_souporaba_invariants,
)
from .vat import apply_vat


class BillingEngine:
    """Pure billing calculator for one settlement interval."""

    def __init__(
        self,
        config: SiteConfig,
        *,
        registry: RateRegistry | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or get_default_registry()

    def calculate_interval(
        self,
        interval: SettlementInterval,
        *,
        dynamic_price: Decimal | None = None,
    ) -> BillingIntervalResult:
        """Produce a detailed, auditable interval billing result."""
        notes: list[str] = []
        charges: list[ChargeLine] = []
        quality = classify_settlement(interval)

        if not should_book_financially(interval):
            notes.append("settlement_not_accumulated_or_invalid")
            return BillingIntervalResult(
                interval_id=interval.interval_id,
                interval_start=interval.interval_start,
                interval_end=interval.interval_end,
                physical_import_kwh=interval.physical_import_kwh,
                physical_export_kwh=interval.physical_export_kwh,
                shared_allocated_kwh=interval.shared_allocated_kwh,
                shared_used_kwh=interval.shared_used_kwh,
                shared_unused_kwh=interval.shared_unused_kwh,
                supplier_billable_kwh=interval.resolved_billable_kwh(),
                network_billable_kwh=interval.physical_import_kwh,
                supplier_energy_cost=Decimal("0"),
                network_energy_cost=Decimal("0"),
                applicable_levies=Decimal("0"),
                vat=Decimal("0"),
                variable_cost_total=Decimal("0"),
                souporaba_savings=Decimal("0"),
                unused_allocation_value=Decimal("0"),
                quality=quality,
                tariff_version=self.registry.tariff_version,
                notes=tuple(notes),
            )

        invariant_issues = verify_souporaba_invariants(interval)
        notes.extend(invariant_issues)

        billable = receiver_supplier_billable(interval)
        network_kwh = receiver_network_billable(interval)

        supplier_cost, price, supplier_line = calculate_supplier_energy_cost(
            billable_kwh=billable,
            when=interval.interval_start,
            config=self.config,
            dynamic_price=dynamic_price,
            include_vat_in_line=False,
        )
        charges.append(supplier_line)

        network_cost, network_line, block, network_warning = calculate_network_energy(
            physical_import_kwh=network_kwh,
            when=interval.interval_start,
            config=self.config,
            registry=self.registry,
        )
        if network_warning:
            notes.append(network_warning)
            quality = ComputationQuality.INCOMPLETE
        if network_line:
            charges.append(network_line)

        levies_total, levy_lines = calculate_levies(
            physical_import_kwh=network_kwh,
            config=self.config,
        )
        charges.extend(levy_lines)

        # VAT on VAT-applicable net components (supplier if ex-VAT, network, levies)
        vat_base = Decimal("0")
        if not self.config.prices_include_vat:
            vat_base += supplier_cost
        else:
            notes.append("supplier_prices_include_vat_no_double_vat")
        vat_base += network_cost + levies_total
        vat = apply_vat(vat_base, self.config.vat_rate)

        # Variable cost for Energy dashboard: supplier + network energy + levies + VAT
        # when configured to include VAT in displayed variable cost.
        variable = supplier_cost + network_cost + levies_total + vat

        savings = receiver_savings(
            used_shared_kwh=interval.shared_used_kwh,
            supplier_price_ex_vat=price.price_ex_vat,
        )
        unused_value = unused_allocation_opportunity_cost(
            unused_shared_kwh=interval.shared_unused_kwh,
            supplier_price_ex_vat=price.price_ex_vat,
        )

        return BillingIntervalResult(
            interval_id=interval.interval_id,
            interval_start=interval.interval_start,
            interval_end=interval.interval_end,
            physical_import_kwh=interval.physical_import_kwh,
            physical_export_kwh=interval.physical_export_kwh,
            shared_allocated_kwh=interval.shared_allocated_kwh,
            shared_used_kwh=interval.shared_used_kwh,
            shared_unused_kwh=interval.shared_unused_kwh,
            supplier_billable_kwh=billable,
            network_billable_kwh=network_kwh,
            supplier_energy_cost=supplier_cost,
            network_energy_cost=network_cost,
            applicable_levies=levies_total,
            vat=vat,
            variable_cost_total=variable,
            souporaba_savings=savings,
            unused_allocation_value=unused_value,
            quality=quality,
            tariff_version=self.registry.tariff_version,
            network_block=block,
            supplier_tariff=price.tariff_label,
            charges=tuple(charges),
            notes=tuple(notes),
        )

    def current_variable_price(
        self,
        when: datetime,
        *,
        dynamic_price: Decimal | None = None,
        include_vat: bool = True,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Return (supplier, network_energy, levies, combined) prices €/kWh.

        Combined is the ordinary marginal cost of physical grid electricity
        before Souporaba settlement.
        """
        from ..tariffs.calendar import get_tariff_block
        from ..tariffs.network_rates import get_network_energy_rate
        from ..tariffs.supplier_rates import SupplierPriceResolver

        supplier = SupplierPriceResolver(self.config).resolve(
            when, dynamic_price=dynamic_price
        )
        supplier_unit = (
            supplier.price_inc_vat if include_vat else supplier.price_ex_vat
        )

        block = get_tariff_block(when).block
        try:
            net_rate = get_network_energy_rate(
                when.date(),
                customer_category=self.config.customer_category,
                network_block=block,
                registry=self.registry,
            ).value
        except Exception:  # noqa: BLE001
            net_rate = Decimal("0")

        levies = Decimal("0")
        if self.config.enable_levies:
            levies = self.config.excise_rate + self.config.ove_spte_rate

        net_and_levies = net_rate + levies
        if include_vat and not self.config.prices_include_vat:
            # Supplier already optionally includes VAT; add VAT on network+levies
            combined = supplier_unit + apply_vat(
                net_and_levies, self.config.vat_rate
            ) + net_and_levies
            # clearer: combined = supplier_inc_or_ex + (network+levies)*(1+vat)
            combined = supplier_unit + net_and_levies * (
                Decimal("1") + self.config.vat_rate
            )
        elif include_vat and self.config.prices_include_vat:
            combined = supplier_unit + net_and_levies * (
                Decimal("1") + self.config.vat_rate
            )
        else:
            combined = supplier_unit + net_and_levies

        return supplier_unit, net_rate, levies, combined
