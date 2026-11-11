"""Constants for Slovenian Energy Costs."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "slovenian_energy_costs"
MANUFACTURER: Final = "Slovenian Energy Costs"
MODEL: Final = "Electricity billing estimate"
TIMEZONE: Final = "Europe/Ljubljana"
CURRENCY: Final = "EUR"

CONFIG_ENTRY_VERSION: Final = 1
CONFIG_ENTRY_MINOR_VERSION: Final = 1
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = "slovenian_energy_costs.storage"

# Config keys
CONF_SITE_NAME: Final = "site_name"
CONF_SITE_ROLE: Final = "site_role"
CONF_CURRENCY: Final = "currency"
CONF_BILLING_MODELS: Final = "billing_models"

CONF_GRID_IMPORT_ENTITY: Final = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY: Final = "grid_export_entity"
CONF_SOLAR_PRODUCTION_ENTITY: Final = "solar_production_entity"
CONF_DYNAMIC_PRICE_ENTITY: Final = "dynamic_price_entity"
CONF_DEMAND_ENTITY: Final = "demand_entity"

CONF_SUPPLIER_MODE: Final = "supplier_mode"
CONF_SUPPLIER_ET_PRICE: Final = "supplier_et_price"
CONF_SUPPLIER_VT_PRICE: Final = "supplier_vt_price"
CONF_SUPPLIER_MT_PRICE: Final = "supplier_mt_price"
CONF_SUPPLIER_MARKUP_FIXED: Final = "supplier_markup_fixed"
CONF_SUPPLIER_MARKUP_PCT: Final = "supplier_markup_pct"
CONF_SUPPLIER_DISCOUNT_PCT: Final = "supplier_discount_pct"
CONF_PRICES_INCLUDE_VAT: Final = "prices_include_vat"
CONF_VAT_RATE: Final = "vat_rate"
CONF_FIXED_MONTHLY_SUPPLIER: Final = "fixed_monthly_supplier"

CONF_CUSTOMER_CATEGORY: Final = "customer_category"
CONF_HAS_15MIN_MEASUREMENT: Final = "has_15min_measurement"
CONF_AGREED_POWER: Final = "agreed_power"  # dict block -> kW

CONF_ENABLE_LEVIES: Final = "enable_levies"
CONF_EXCISE_RATE: Final = "excise_rate"
CONF_OVE_SPTE_RATE: Final = "ove_spte_rate"

CONF_SOUPORABA_ENTRY_ID: Final = "souporaba_entry_id"
CONF_SOUPORABA_ENTITIES: Final = "souporaba_entities"
CONF_SETTLEMENT_SOURCE: Final = "settlement_source"

CONF_NET_METERING_OPENING_BALANCE: Final = "net_metering_opening_balance"
CONF_NET_METERING_OPENING_DATE: Final = "net_metering_opening_date"
CONF_DONOR_EXPORT_ALREADY_DEDUCTED: Final = "donor_export_already_deducted"
CONF_SHARED_ENERGY_ENTITY: Final = "shared_energy_entity"

CONF_INTERVAL_MINUTES: Final = "interval_minutes"
CONF_PROCESSING_DELAY: Final = "processing_delay"

# Site roles
ROLE_CONSUMER: Final = "consumer"
ROLE_PRODUCER: Final = "producer"
ROLE_COMBINED: Final = "combined"

# Billing models
MODEL_CONVENTIONAL: Final = "conventional"
MODEL_NET_METERING: Final = "net_metering"
MODEL_SOUPORABA_RECEIVER: Final = "souporaba_receiver"
MODEL_SOUPORABA_DONOR: Final = "souporaba_donor"

# Supplier modes
SUPPLIER_ET: Final = "et"
SUPPLIER_VT_MT: Final = "vt_mt"
SUPPLIER_DYNAMIC: Final = "dynamic"

# Settlement sources
SETTLEMENT_PHYSICAL: Final = "physical"
SETTLEMENT_SOUPORABA: Final = "souporaba"

# Customer categories (uporabniška skupina)
CATEGORY_0: Final = "0"  # NN feeder 400/230
CATEGORY_1: Final = "1"
CATEGORY_2: Final = "2"
CATEGORY_3: Final = "3"
CATEGORY_4: Final = "4"

# Network tariff blocks
NETWORK_BLOCKS: Final = (1, 2, 3, 4, 5)

# Defaults
DEFAULT_NAME: Final = "Slovenian Energy Costs"
DEFAULT_INTERVAL_MINUTES: Final = 15
DEFAULT_PROCESSING_DELAY: Final = 10
DEFAULT_VAT_RATE: Final = "0.22"
DEFAULT_CUSTOMER_CATEGORY: Final = CATEGORY_0
DEFAULT_EXCISE_RATE: Final = "0.00153"  # EUR/kWh typical household placeholder
DEFAULT_OVE_SPTE_RATE: Final = "0.00899"  # EUR/kWh configurable

# Souporaba domain
SOUPORABA_DOMAIN: Final = "energy_sharing"

# Souporaba sensor key suffixes (unique_id = {entry_id}_{key})
SOUPORABA_SENSOR_KEYS: Final = (
    "receiver_import_last_interval",
    "shared_energy_last_interval",
    "used_shared_last_interval",
    "unused_shared_last_interval",
    "billable_energy_last_interval",
    "provider_export_last_interval",
    "reconciliation_status",
    "processing_status",
    "last_processed_interval_id",
    "operating_mode",
)

# Computation quality
QUALITY_ACTUAL: Final = "actual"
QUALITY_ESTIMATED: Final = "estimated"
QUALITY_INCOMPLETE: Final = "incomplete"
QUALITY_INVALID: Final = "invalid"

# Services
SERVICE_APPLY_ADJUSTMENT: Final = "apply_adjustment"
SERVICE_PROCESS_NOW: Final = "process_now"
SERVICE_RESET_MONETARY_COSTS: Final = "reset_monetary_costs"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

PLATFORMS: Final = ("sensor", "number")
