# Slovenian Energy Costs

[![GitHub Release](https://img.shields.io/github/v/release/gztproject/slovenian-energy-costs?include_prereleases&label=pre-release)](https://github.com/gztproject/slovenian-energy-costs/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA](https://img.shields.io/badge/Home%20Assistant-2025.1.0%2B-blue.svg)](https://www.home-assistant.io/)
[![License](https://img.shields.io/github/license/gztproject/slovenian-energy-costs)](https://github.com/gztproject/slovenian-energy-costs/blob/main/LICENSE)

Custom Home Assistant integration that estimates Slovenian electricity costs — supplier energy, network charges (*omrežnina*), levies, VAT, Souporaba savings, and annual net-metering reserves — and feeds the **native Energy dashboard**.

> **Disclaimer:** This integration produces **estimated** financial settlements for home automation. It is **not** an official invoice and may differ from your supplier or DSO bill.

> **Pre-release:** `0.1.0b1` is a beta. In HACS, enable **Show beta versions** before installing.

**Minimum Home Assistant version:** 2025.1.0

**Repository:** https://github.com/gztproject/slovenian-energy-costs  
**Issues:** https://github.com/gztproject/slovenian-energy-costs/issues  
**Releases:** https://github.com/gztproject/slovenian-energy-costs/releases

## Features

- UI configuration (Config Flow + Options Flow) — no YAML required
- HACS custom repository install
- Single tariff (ET), dual tariff (VT/MT), and dynamic supplier pricing
- Internal Slovenian network tariff calendar (`Europe/Ljubljana`, five time blocks)
- Bundled ANJP239 network rates for 1 Mar 2026 – 31 Dec 2026, including **Nov–Dec 2026 reduced power tariffs**
- Accumulated monetary sensors compatible with the Energy dashboard
- Optional first-class Souporaba (`energy_sharing`) interoperability
- Annual net-metering donor accounting with honest incomplete-history handling
- English and Slovenian translations
- Pure Decimal billing engine with automated tests

## HACS installation

1. In HACS, open the overflow menu and enable **Show beta versions** (required while this integration is a pre-release).
2. HACS → Integrations → ⋮ → **Custom repositories**
3. Repository: `https://github.com/gztproject/slovenian-energy-costs`
4. Category: **Integration**
5. Install **Slovenian Energy Costs** (choose the latest pre-release)
6. Restart Home Assistant
7. Settings → Devices & services → Add integration → **Slovenian Energy Costs**

Manual install: copy `custom_components/slovenian_energy_costs` into your Home Assistant `custom_components` folder, then restart.

## Energy dashboard setup

### Simple contracts (ET / VT-MT / dynamic)

**Settings → Dashboards → Energy → Electricity grid → Grid consumption**

- Keep your physical **grid import** energy sensor
- Cost tracking: **Use an entity with current price**
- Select `sensor.<site>_current_variable_price`  
  (includes VAT as configured; see entity attributes)

### Complex contracts / Souporaba

- Keep physical **grid import** (and export) energy sensors unchanged
- Cost tracking: **Use an entity tracking the total costs**
- Select `sensor.<site>_grid_variable_cost_total`

Optional: use `invoice_cost_total` if you want fixed monthly and power charges included in the Energy cost totals (they will no longer appear as separate invoice categories there).

## Main sensors

| Sensor | Unit | Purpose |
|--------|------|---------|
| `current_supplier_price` | €/kWh | Commodity price |
| `current_network_energy_price` | €/kWh | Network energy rate |
| `current_levies_price` | €/kWh | Per-kWh levies |
| `current_variable_price` | €/kWh | Combined marginal price (pre-Souporaba) |
| `grid_variable_cost_total` | € | Preferred Energy dashboard cost total |
| `supplier_energy_cost_total` | € | Supplier commodity total |
| `network_energy_cost_total` | € | Network energy total |
| `invoice_cost_total` | € | Full estimated invoice total |
| `souporaba_savings_total` | € | Receiver commodity savings |

Diagnostic and net-metering sensors are disabled by default in the entity registry.

## Configuration wizard

1. Site name / role / currency  
2. Billing models (conventional, net metering, Souporaba receiver/donor)  
3. Meter entities (import required)  
4. Supplier contract  
5. Network category and agreed power  
6. Settlement source (physical or Souporaba)  
7. Confirmation summary  

Options Flow updates rates **without** wiping historical cost counters or repricing past intervals.

## Souporaba

See [docs/SOUPORABA_INTEGRATION.md](docs/SOUPORABA_INTEGRATION.md).

Install Souporaba separately. This integration never modifies Souporaba and does not recompute sharing allocations when accepted Souporaba results are available.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Billing rules](docs/BILLING_RULES.md)
- [Souporaba integration](docs/SOUPORABA_INTEGRATION.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit -q
ruff check custom_components tests
```

## Validating against a real invoice

1. Configure site category, agreed power, and supplier rates from your contract.
2. Set levy rates from a recent invoice line items.
3. Compare one calendar month of `month_estimated_invoice` to the supplier bill.
4. Expect small differences from interval timing, rounding, and estimate-only excess power.
5. File an issue with redacted diagnostics if a regulatory rate table is wrong or outdated.

## Known limitations

- No official 2027+ rate tables until published (calculations for those dates are incomplete)
- Excess power requires an explicitly configured rate
- No historical replay if Souporaba intervals were missed while this integration was offline
- Estimates only — not legal billing proof

## License

MIT
