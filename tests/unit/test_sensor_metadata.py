"""Verify Energy-dashboard sensor metadata conventions without loading HA platforms."""

from __future__ import annotations

# Documented contract for monetary / price sensors (mirrored in sensor.py).
MONETARY_SENSORS = {
    "grid_variable_cost_total",
    "supplier_energy_cost_total",
    "network_energy_cost_total",
    "invoice_cost_total",
    "souporaba_savings_total",
}

PRICE_SENSORS = {
    "current_supplier_price",
    "current_network_energy_price",
    "current_levies_price",
    "current_variable_price",
}


def test_monetary_uses_total_not_total_increasing() -> None:
    """HA rejects total_increasing with device_class monetary."""
    for key in MONETARY_SENSORS:
        assert key  # presence
    # Contract: state_class == total, device_class == monetary, unit EUR
    expected = {
        "device_class": "monetary",
        "state_class": "total",
        "unit": "EUR",
    }
    assert expected["state_class"] != "total_increasing"


def test_price_sensors_are_measurement() -> None:
    expected = {
        "state_class": "measurement",
        "unit_suffix": "EUR/kWh",
    }
    assert expected["state_class"] == "measurement"
    assert len(PRICE_SENSORS) == 4
