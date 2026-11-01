"""Diagnostics for Slovenian Energy Costs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import BillingCoordinator

TO_REDACT = {"site_name", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with personal identifiers redacted."""
    coordinator: BillingCoordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(
            {"title": entry.title, "data_keys": list(entry.data.keys())},
            TO_REDACT,
        ),
        "status": coordinator.status,
        "billing_data_quality": data.billing_data_quality,
        "last_processed_interval_id": data.last_processed_interval_id,
        "last_reconciliation_status": data.last_reconciliation_status,
        "processed_interval_count": len(data.processed_interval_ids),
        "baseline_initialized": data.baseline_initialized,
        "counters": data.counters.to_dict(),
        "monthly": data.monthly.to_dict() if data.monthly else None,
        "net_metering": data.net_metering.to_dict() if data.net_metering else None,
        "last_result": (
            data.last_billing_result.to_dict() if data.last_billing_result else None
        ),
        "config": {
            "supplier_mode": coordinator.config.supplier_mode,
            "customer_category": coordinator.config.customer_category,
            "settlement_source": coordinator.config.settlement_source,
            "billing_models": coordinator.config.billing_models,
            "has_15min_measurement": coordinator.config.has_15min_measurement,
            "prices_include_vat": coordinator.config.prices_include_vat,
        },
    }
