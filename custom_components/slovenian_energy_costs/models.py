"""Typed models for Slovenian Energy Costs (HA-independent)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ComputationQuality(StrEnum):
    """Quality of a computed billing result."""

    ACTUAL = "actual"
    ESTIMATED = "estimated"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


class Season(StrEnum):
    """Network tariff season."""

    HIGH = "high"  # višja sezona
    LOW = "low"  # nižja sezona


class DayType(StrEnum):
    """Day classification for network tariff calendar."""

    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class SupplierMode(StrEnum):
    """Supplier pricing mode."""

    ET = "et"
    VT_MT = "vt_mt"
    DYNAMIC = "dynamic"


class SettlementSource(StrEnum):
    """Source of settled energy intervals."""

    PHYSICAL = "physical"
    SOUPORABA = "souporaba"


def _d(value: Any, default: str = "0") -> Decimal:
    """Convert to Decimal safely."""
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _dt_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


@dataclass(frozen=True, slots=True)
class RateRecord:
    """Effective-dated regulatory or contractual rate."""

    rate_id: str
    rate_type: str
    value: Decimal
    unit: str
    effective_from: date
    effective_until: date | None
    customer_category: str | None = None
    network_block: int | None = None
    source_url: str | None = None
    source_date: date | None = None
    notes: str | None = None

    def covers(self, when: date) -> bool:
        """Return True if the rate applies on the given date."""
        if when < self.effective_from:
            return False
        if self.effective_until is not None and when > self.effective_until:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate_id": self.rate_id,
            "rate_type": self.rate_type,
            "value": str(self.value),
            "unit": self.unit,
            "effective_from": self.effective_from.isoformat(),
            "effective_until": (
                self.effective_until.isoformat() if self.effective_until else None
            ),
            "customer_category": self.customer_category,
            "network_block": self.network_block,
            "source_url": self.source_url,
            "source_date": (
                self.source_date.isoformat() if self.source_date else None
            ),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateRecord:
        return cls(
            rate_id=data["rate_id"],
            rate_type=data["rate_type"],
            value=_d(data["value"]),
            unit=data["unit"],
            effective_from=date.fromisoformat(data["effective_from"]),
            effective_until=(
                date.fromisoformat(data["effective_until"])
                if data.get("effective_until")
                else None
            ),
            customer_category=data.get("customer_category"),
            network_block=data.get("network_block"),
            source_url=data.get("source_url"),
            source_date=(
                date.fromisoformat(data["source_date"])
                if data.get("source_date")
                else None
            ),
            notes=data.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class TariffBlockInfo:
    """Resolved network tariff block for a timestamp."""

    block: int
    season: Season
    day_type: DayType
    schedule_id: str
    local_time: datetime
    next_block: int | None = None
    next_transition: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChargeLine:
    """Auditable invoice charge line."""

    charge_id: str
    name: str
    amount: Decimal
    unit: str
    quantity: Decimal
    rate: Decimal
    calculation_base: str
    vat_applicable: bool
    rate_id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "charge_id": self.charge_id,
            "name": self.name,
            "amount": str(self.amount),
            "unit": self.unit,
            "quantity": str(self.quantity),
            "rate": str(self.rate),
            "calculation_base": self.calculation_base,
            "vat_applicable": self.vat_applicable,
            "rate_id": self.rate_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChargeLine:
        return cls(
            charge_id=data["charge_id"],
            name=data["name"],
            amount=_d(data["amount"]),
            unit=data["unit"],
            quantity=_d(data["quantity"]),
            rate=_d(data["rate"]),
            calculation_base=data["calculation_base"],
            vat_applicable=bool(data["vat_applicable"]),
            rate_id=data.get("rate_id"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class SettlementInterval:
    """Normalized energy quantities for one settlement interval."""

    interval_id: str
    interval_start: datetime
    interval_end: datetime
    physical_import_kwh: Decimal
    physical_export_kwh: Decimal = Decimal("0")
    shared_allocated_kwh: Decimal = Decimal("0")
    shared_used_kwh: Decimal = Decimal("0")
    shared_unused_kwh: Decimal = Decimal("0")
    supplier_billable_kwh: Decimal | None = None
    settlement_accumulated: bool = True
    reconciliation_status: str = "not_configured"
    operating_mode: str | None = None
    provider_export_source_type: str | None = None
    fixed_allocation_percentage: Decimal | None = None
    source: SettlementSource = SettlementSource.PHYSICAL
    quality: ComputationQuality = ComputationQuality.ACTUAL

    def resolved_billable_kwh(self) -> Decimal:
        """Supplier-billable energy, defaulting to physical import."""
        if self.supplier_billable_kwh is not None:
            return self.supplier_billable_kwh
        return self.physical_import_kwh

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_id": self.interval_id,
            "interval_start": self.interval_start.isoformat(),
            "interval_end": self.interval_end.isoformat(),
            "physical_import_kwh": str(self.physical_import_kwh),
            "physical_export_kwh": str(self.physical_export_kwh),
            "shared_allocated_kwh": str(self.shared_allocated_kwh),
            "shared_used_kwh": str(self.shared_used_kwh),
            "shared_unused_kwh": str(self.shared_unused_kwh),
            "supplier_billable_kwh": (
                str(self.supplier_billable_kwh)
                if self.supplier_billable_kwh is not None
                else None
            ),
            "settlement_accumulated": self.settlement_accumulated,
            "reconciliation_status": self.reconciliation_status,
            "operating_mode": self.operating_mode,
            "provider_export_source_type": self.provider_export_source_type,
            "fixed_allocation_percentage": (
                str(self.fixed_allocation_percentage)
                if self.fixed_allocation_percentage is not None
                else None
            ),
            "source": self.source.value,
            "quality": self.quality.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettlementInterval:
        start = _parse_dt(data["interval_start"])
        end = _parse_dt(data["interval_end"])
        assert start is not None and end is not None
        return cls(
            interval_id=data["interval_id"],
            interval_start=start,
            interval_end=end,
            physical_import_kwh=_d(data["physical_import_kwh"]),
            physical_export_kwh=_d(data.get("physical_export_kwh", "0")),
            shared_allocated_kwh=_d(data.get("shared_allocated_kwh", "0")),
            shared_used_kwh=_d(data.get("shared_used_kwh", "0")),
            shared_unused_kwh=_d(data.get("shared_unused_kwh", "0")),
            supplier_billable_kwh=(
                _d(data["supplier_billable_kwh"])
                if data.get("supplier_billable_kwh") is not None
                else None
            ),
            settlement_accumulated=bool(data.get("settlement_accumulated", True)),
            reconciliation_status=data.get(
                "reconciliation_status", "not_configured"
            ),
            operating_mode=data.get("operating_mode"),
            provider_export_source_type=data.get("provider_export_source_type"),
            fixed_allocation_percentage=(
                _d(data["fixed_allocation_percentage"])
                if data.get("fixed_allocation_percentage") is not None
                else None
            ),
            source=SettlementSource(data.get("source", "physical")),
            quality=ComputationQuality(data.get("quality", "actual")),
        )


@dataclass(frozen=True, slots=True)
class BillingIntervalResult:
    """Detailed monetary result for one interval."""

    interval_id: str
    interval_start: datetime
    interval_end: datetime
    physical_import_kwh: Decimal
    physical_export_kwh: Decimal
    shared_allocated_kwh: Decimal
    shared_used_kwh: Decimal
    shared_unused_kwh: Decimal
    supplier_billable_kwh: Decimal
    network_billable_kwh: Decimal
    supplier_energy_cost: Decimal
    network_energy_cost: Decimal
    applicable_levies: Decimal
    vat: Decimal
    variable_cost_total: Decimal
    souporaba_savings: Decimal
    unused_allocation_value: Decimal
    quality: ComputationQuality
    tariff_version: str
    network_block: int | None = None
    supplier_tariff: str | None = None
    charges: tuple[ChargeLine, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_id": self.interval_id,
            "interval_start": self.interval_start.isoformat(),
            "interval_end": self.interval_end.isoformat(),
            "physical_import_kwh": str(self.physical_import_kwh),
            "physical_export_kwh": str(self.physical_export_kwh),
            "shared_allocated_kwh": str(self.shared_allocated_kwh),
            "shared_used_kwh": str(self.shared_used_kwh),
            "shared_unused_kwh": str(self.shared_unused_kwh),
            "supplier_billable_kwh": str(self.supplier_billable_kwh),
            "network_billable_kwh": str(self.network_billable_kwh),
            "supplier_energy_cost": str(self.supplier_energy_cost),
            "network_energy_cost": str(self.network_energy_cost),
            "applicable_levies": str(self.applicable_levies),
            "vat": str(self.vat),
            "variable_cost_total": str(self.variable_cost_total),
            "souporaba_savings": str(self.souporaba_savings),
            "unused_allocation_value": str(self.unused_allocation_value),
            "quality": self.quality.value,
            "tariff_version": self.tariff_version,
            "network_block": self.network_block,
            "supplier_tariff": self.supplier_tariff,
            "charges": [c.to_dict() for c in self.charges],
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BillingIntervalResult:
        start = _parse_dt(data["interval_start"])
        end = _parse_dt(data["interval_end"])
        assert start is not None and end is not None
        return cls(
            interval_id=data["interval_id"],
            interval_start=start,
            interval_end=end,
            physical_import_kwh=_d(data["physical_import_kwh"]),
            physical_export_kwh=_d(data["physical_export_kwh"]),
            shared_allocated_kwh=_d(data["shared_allocated_kwh"]),
            shared_used_kwh=_d(data["shared_used_kwh"]),
            shared_unused_kwh=_d(data["shared_unused_kwh"]),
            supplier_billable_kwh=_d(data["supplier_billable_kwh"]),
            network_billable_kwh=_d(data["network_billable_kwh"]),
            supplier_energy_cost=_d(data["supplier_energy_cost"]),
            network_energy_cost=_d(data["network_energy_cost"]),
            applicable_levies=_d(data["applicable_levies"]),
            vat=_d(data["vat"]),
            variable_cost_total=_d(data["variable_cost_total"]),
            souporaba_savings=_d(data.get("souporaba_savings", "0")),
            unused_allocation_value=_d(data.get("unused_allocation_value", "0")),
            quality=ComputationQuality(data["quality"]),
            tariff_version=data["tariff_version"],
            network_block=data.get("network_block"),
            supplier_tariff=data.get("supplier_tariff"),
            charges=tuple(
                ChargeLine.from_dict(c) for c in data.get("charges", [])
            ),
            notes=tuple(data.get("notes", [])),
        )


@dataclass(slots=True)
class SiteConfig:
    """Metering site and contract configuration."""

    site_name: str
    site_role: str
    currency: str = "EUR"
    billing_models: list[str] = field(default_factory=lambda: ["conventional"])
    grid_import_entity: str | None = None
    grid_export_entity: str | None = None
    solar_production_entity: str | None = None
    dynamic_price_entity: str | None = None
    demand_entity: str | None = None
    supplier_mode: str = "et"
    supplier_et_price: Decimal = Decimal("0")
    supplier_vt_price: Decimal = Decimal("0")
    supplier_mt_price: Decimal = Decimal("0")
    supplier_markup_fixed: Decimal = Decimal("0")
    supplier_markup_pct: Decimal = Decimal("0")
    supplier_discount_pct: Decimal = Decimal("0")
    prices_include_vat: bool = False
    vat_rate: Decimal = Decimal("0.22")
    fixed_monthly_supplier: Decimal = Decimal("0")
    customer_category: str = "0"
    has_15min_measurement: bool = True
    agreed_power: dict[int, Decimal] = field(default_factory=dict)
    enable_levies: bool = True
    excise_rate: Decimal = Decimal("0.00153")
    ove_spte_rate: Decimal = Decimal("0.00899")
    settlement_source: str = "physical"
    souporaba_entry_id: str | None = None
    souporaba_entities: dict[str, str] = field(default_factory=dict)
    net_metering_opening_balance: Decimal | None = None
    net_metering_opening_date: date | None = None
    donor_export_already_deducted: bool = False
    shared_energy_entity: str | None = None
    interval_minutes: int = 15
    processing_delay: int = 10

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key, value in list(data.items()):
            if isinstance(value, Decimal):
                data[key] = str(value)
            elif isinstance(value, date):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = {
                    str(k): (str(v) if isinstance(v, Decimal) else v)
                    for k, v in value.items()
                }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SiteConfig:
        agreed_raw = data.get("agreed_power") or {}
        agreed: dict[int, Decimal] = {
            int(k): _d(v) for k, v in agreed_raw.items()
        }
        opening_date = data.get("net_metering_opening_date")
        return cls(
            site_name=data["site_name"],
            site_role=data.get("site_role", "consumer"),
            currency=data.get("currency", "EUR"),
            billing_models=list(
                data.get("billing_models") or ["conventional"]
            ),
            grid_import_entity=data.get("grid_import_entity"),
            grid_export_entity=data.get("grid_export_entity"),
            solar_production_entity=data.get("solar_production_entity"),
            dynamic_price_entity=data.get("dynamic_price_entity"),
            demand_entity=data.get("demand_entity"),
            supplier_mode=data.get("supplier_mode", "et"),
            supplier_et_price=_d(data.get("supplier_et_price", "0")),
            supplier_vt_price=_d(data.get("supplier_vt_price", "0")),
            supplier_mt_price=_d(data.get("supplier_mt_price", "0")),
            supplier_markup_fixed=_d(data.get("supplier_markup_fixed", "0")),
            supplier_markup_pct=_d(data.get("supplier_markup_pct", "0")),
            supplier_discount_pct=_d(data.get("supplier_discount_pct", "0")),
            prices_include_vat=bool(data.get("prices_include_vat", False)),
            vat_rate=_d(data.get("vat_rate", "0.22")),
            fixed_monthly_supplier=_d(data.get("fixed_monthly_supplier", "0")),
            customer_category=str(data.get("customer_category", "0")),
            has_15min_measurement=bool(data.get("has_15min_measurement", True)),
            agreed_power=agreed,
            enable_levies=bool(data.get("enable_levies", True)),
            excise_rate=_d(data.get("excise_rate", "0.00153")),
            ove_spte_rate=_d(data.get("ove_spte_rate", "0.00899")),
            settlement_source=data.get("settlement_source", "physical"),
            souporaba_entry_id=data.get("souporaba_entry_id"),
            souporaba_entities=dict(data.get("souporaba_entities") or {}),
            net_metering_opening_balance=(
                _d(data["net_metering_opening_balance"])
                if data.get("net_metering_opening_balance") is not None
                else None
            ),
            net_metering_opening_date=(
                date.fromisoformat(opening_date) if opening_date else None
            ),
            donor_export_already_deducted=bool(
                data.get("donor_export_already_deducted", False)
            ),
            shared_energy_entity=data.get("shared_energy_entity"),
            interval_minutes=int(data.get("interval_minutes", 15)),
            processing_delay=int(data.get("processing_delay", 10)),
        )


@dataclass(slots=True)
class CostCounters:
    """Persistent cumulative monetary counters."""

    grid_variable_cost_total: Decimal = Decimal("0")
    supplier_energy_cost_total: Decimal = Decimal("0")
    network_energy_cost_total: Decimal = Decimal("0")
    network_power_cost_total: Decimal = Decimal("0")
    levies_total: Decimal = Decimal("0")
    vat_total: Decimal = Decimal("0")
    invoice_cost_total: Decimal = Decimal("0")
    souporaba_savings_total: Decimal = Decimal("0")
    unused_allocation_value_total: Decimal = Decimal("0")
    souporaba_allocated_energy_total: Decimal = Decimal("0")
    souporaba_used_energy_total: Decimal = Decimal("0")
    souporaba_unused_energy_total: Decimal = Decimal("0")
    annual_import_kwh: Decimal = Decimal("0")
    annual_export_kwh: Decimal = Decimal("0")
    shared_energy_deducted_kwh: Decimal = Decimal("0")

    def apply_interval(self, result: BillingIntervalResult) -> None:
        self.grid_variable_cost_total += result.variable_cost_total
        self.supplier_energy_cost_total += result.supplier_energy_cost
        self.network_energy_cost_total += result.network_energy_cost
        self.levies_total += result.applicable_levies
        self.vat_total += result.vat
        self.invoice_cost_total += result.variable_cost_total
        self.souporaba_savings_total += result.souporaba_savings
        self.unused_allocation_value_total += result.unused_allocation_value
        self.souporaba_allocated_energy_total += result.shared_allocated_kwh
        self.souporaba_used_energy_total += result.shared_used_kwh
        self.souporaba_unused_energy_total += result.shared_unused_kwh
        self.annual_import_kwh += result.physical_import_kwh
        self.annual_export_kwh += result.physical_export_kwh
        self.shared_energy_deducted_kwh += result.shared_allocated_kwh

    def to_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostCounters:
        kwargs = {k: _d(data.get(k, "0")) for k in cls.__dataclass_fields__}
        return cls(**kwargs)


@dataclass(slots=True)
class MonthlyPeriodState:
    """Aggregates for the current calendar month."""

    year: int
    month: int
    supplier_energy_cost: Decimal = Decimal("0")
    network_energy_cost: Decimal = Decimal("0")
    network_power_cost: Decimal = Decimal("0")
    other_charges: Decimal = Decimal("0")
    vat: Decimal = Decimal("0")
    estimated_invoice: Decimal = Decimal("0")
    power_charged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "month": self.month,
            "supplier_energy_cost": str(self.supplier_energy_cost),
            "network_energy_cost": str(self.network_energy_cost),
            "network_power_cost": str(self.network_power_cost),
            "other_charges": str(self.other_charges),
            "vat": str(self.vat),
            "estimated_invoice": str(self.estimated_invoice),
            "power_charged": self.power_charged,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonthlyPeriodState:
        return cls(
            year=int(data["year"]),
            month=int(data["month"]),
            supplier_energy_cost=_d(data.get("supplier_energy_cost", "0")),
            network_energy_cost=_d(data.get("network_energy_cost", "0")),
            network_power_cost=_d(data.get("network_power_cost", "0")),
            other_charges=_d(data.get("other_charges", "0")),
            vat=_d(data.get("vat", "0")),
            estimated_invoice=_d(data.get("estimated_invoice", "0")),
            power_charged=bool(data.get("power_charged", False)),
        )


@dataclass(slots=True)
class NetMeteringState:
    """Annual net-metering account state."""

    year: int
    opening_balance_kwh: Decimal | None = None
    opening_date: date | None = None
    history_complete: bool = False
    observed_import_kwh: Decimal = Decimal("0")
    observed_export_kwh: Decimal = Decimal("0")
    shared_deducted_kwh: Decimal = Decimal("0")

    @property
    def eligible_export_kwh(self) -> Decimal:
        return self.observed_export_kwh - self.shared_deducted_kwh

    @property
    def balance_kwh(self) -> Decimal:
        return self.eligible_export_kwh - self.observed_import_kwh

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "opening_balance_kwh": (
                str(self.opening_balance_kwh)
                if self.opening_balance_kwh is not None
                else None
            ),
            "opening_date": (
                self.opening_date.isoformat() if self.opening_date else None
            ),
            "history_complete": self.history_complete,
            "observed_import_kwh": str(self.observed_import_kwh),
            "observed_export_kwh": str(self.observed_export_kwh),
            "shared_deducted_kwh": str(self.shared_deducted_kwh),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NetMeteringState:
        opening_date = data.get("opening_date")
        return cls(
            year=int(data["year"]),
            opening_balance_kwh=(
                _d(data["opening_balance_kwh"])
                if data.get("opening_balance_kwh") is not None
                else None
            ),
            opening_date=(
                date.fromisoformat(opening_date) if opening_date else None
            ),
            history_complete=bool(data.get("history_complete", False)),
            observed_import_kwh=_d(data.get("observed_import_kwh", "0")),
            observed_export_kwh=_d(data.get("observed_export_kwh", "0")),
            shared_deducted_kwh=_d(data.get("shared_deducted_kwh", "0")),
        )


@dataclass(slots=True)
class MeterBaseline:
    """Cumulative meter snapshot at last accepted boundary."""

    interval_id: str
    timestamp: datetime
    import_total_kwh: Decimal
    export_total_kwh: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_id": self.interval_id,
            "timestamp": self.timestamp.isoformat(),
            "import_total_kwh": str(self.import_total_kwh),
            "export_total_kwh": (
                str(self.export_total_kwh)
                if self.export_total_kwh is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeterBaseline:
        ts = _parse_dt(data["timestamp"])
        assert ts is not None
        return cls(
            interval_id=data["interval_id"],
            timestamp=ts,
            import_total_kwh=_d(data["import_total_kwh"]),
            export_total_kwh=(
                _d(data["export_total_kwh"])
                if data.get("export_total_kwh") is not None
                else None
            ),
        )


@dataclass(slots=True)
class IntegrationStorage:
    """Versioned persistent storage payload."""

    version: int = 1
    baseline_initialized: bool = False
    meter_baseline: MeterBaseline | None = None
    last_processed_interval_id: str | None = None
    processed_interval_ids: list[str] = field(default_factory=list)
    last_billing_result: BillingIntervalResult | None = None
    counters: CostCounters = field(default_factory=CostCounters)
    monthly: MonthlyPeriodState | None = None
    net_metering: NetMeteringState | None = None
    last_reconciliation_status: str | None = None
    billing_data_quality: str = ComputationQuality.INCOMPLETE.value
    adjustments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "baseline_initialized": self.baseline_initialized,
            "meter_baseline": (
                self.meter_baseline.to_dict() if self.meter_baseline else None
            ),
            "last_processed_interval_id": self.last_processed_interval_id,
            "processed_interval_ids": list(self.processed_interval_ids[-500:]),
            "last_billing_result": (
                self.last_billing_result.to_dict()
                if self.last_billing_result
                else None
            ),
            "counters": self.counters.to_dict(),
            "monthly": self.monthly.to_dict() if self.monthly else None,
            "net_metering": (
                self.net_metering.to_dict() if self.net_metering else None
            ),
            "last_reconciliation_status": self.last_reconciliation_status,
            "billing_data_quality": self.billing_data_quality,
            "adjustments": list(self.adjustments),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> IntegrationStorage:
        if not data:
            return cls()
        baseline = data.get("meter_baseline")
        last_result = data.get("last_billing_result")
        monthly = data.get("monthly")
        net = data.get("net_metering")
        return cls(
            version=int(data.get("version", 1)),
            baseline_initialized=bool(data.get("baseline_initialized", False)),
            meter_baseline=(
                MeterBaseline.from_dict(baseline)
                if isinstance(baseline, dict)
                else None
            ),
            last_processed_interval_id=data.get("last_processed_interval_id"),
            processed_interval_ids=list(data.get("processed_interval_ids") or []),
            last_billing_result=(
                BillingIntervalResult.from_dict(last_result)
                if isinstance(last_result, dict)
                else None
            ),
            counters=CostCounters.from_dict(data.get("counters") or {}),
            monthly=(
                MonthlyPeriodState.from_dict(monthly)
                if isinstance(monthly, dict)
                else None
            ),
            net_metering=(
                NetMeteringState.from_dict(net) if isinstance(net, dict) else None
            ),
            last_reconciliation_status=data.get("last_reconciliation_status"),
            billing_data_quality=data.get(
                "billing_data_quality", ComputationQuality.INCOMPLETE.value
            ),
            adjustments=list(data.get("adjustments") or []),
        )
