"""Repairs issues for missing tariff periods and configuration problems."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .tariffs.rate_registry import MissingTariffError, get_default_registry


async def async_create_fix(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create repair flow (issues are informational / non-fixable)."""
    return ConfirmRepairFlow()


async def async_register_missing_tariff_issue(
    hass: HomeAssistant,
    *,
    when: date,
    detail: str | None = None,
) -> None:
    """Register a repairs issue when network rates are missing for a date."""
    registry = get_default_registry()
    try:
        registry.find(
            "network_energy", when, customer_category="0", network_block=1
        )
        ir.async_delete_issue(hass, DOMAIN, "missing_network_tariff")
    except MissingTariffError:
        placeholders: dict[str, Any] = {"date": when.isoformat()}
        if detail:
            placeholders["detail"] = detail
        ir.async_create_issue(
            hass,
            DOMAIN,
            "missing_network_tariff",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_network_tariff",
            translation_placeholders=placeholders,
        )
