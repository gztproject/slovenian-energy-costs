"""Persistent storage for Slovenian Energy Costs."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .models import IntegrationStorage


def storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.{entry_id}"


class BillingStore:
    """Versioned Store wrapper around IntegrationStorage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict] = Store(
            hass, STORAGE_VERSION, storage_key(entry_id)
        )
        self.data = IntegrationStorage()

    async def async_load(self) -> IntegrationStorage:
        raw = await self._store.async_load()
        self.data = IntegrationStorage.from_dict(raw)
        return self.data

    async def async_save(self) -> None:
        await self._store.async_save(self.data.to_dict())
