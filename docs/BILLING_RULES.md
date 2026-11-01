# Billing rules and regulatory sources

This integration produces **estimated** settlements. Official invoices from your supplier / DSO remain authoritative.

## Network energy (omrežnina za energijo)

| Item | Value |
|------|--------|
| Base | Physical grid import (kWh) |
| Rate | Combined transmission + distribution by user category and time block |
| Source | [ANJP239](https://pisrs.si/pregledPredpisa?id=ANJP239) / [URO tariff tables](https://www.uro.si/documents/d/guest/tp_od_1_3_2026_do_31_12_2026) |
| Effective | 2026-03-01 … 2026-12-31 |
| Souporaba | Does **not** reduce network-billable kWh |

## Network power (dogovorjena obračunska moč)

| Item | Value |
|------|--------|
| Base | Configured agreed power per block (kW) |
| Rate | EUR/kW/month from ANJP239 |
| Special | Nov–Dec 2026 block 1 uses **reduced** high-season tariffs (`power_reduced_high_2026`) |
| Source | ANJP239 NPB special article |

## Excess power (presežna moč)

| Item | Value |
|------|--------|
| Status | **Partial** — requires 15-min average power and an explicitly configured rate |
| Method | `P_avg = interval_kWh / 0.25h`; excess = max(0, P_avg − agreed) |
| Note | Instantaneous peak power is not used |

## Supplier commodity

| Mode | Rule |
|------|------|
| ET | Single €/kWh |
| VT/MT | Independent of network blocks; default 06:00–22:00 workdays = VT; weekends/holidays = MT |
| Dynamic | Home Assistant price entity + optional markup/discount |
| VAT | Never applied twice when prices are VAT-inclusive |

## Levies

Configurable per-kWh charges (trošarina, OVE/SPTE) applied to **physical import**. Defaults are illustrative — set from your invoice.

## Souporaba (receiver)

| Quantity | Owner | Financial use |
|----------|-------|---------------|
| `billable_energy` | Souporaba | Supplier energy charge |
| `receiver_import` | Souporaba / meter | Network + levies |
| `used_shared` | Souporaba | Savings estimate |
| `unused_shared` | Souporaba | Opportunity cost (not invoiced) |

## Annual net metering (donor)

```
eligible_export = physical_export − allocated_shared_energy
balance = opening + eligible_export − physical_import
```

Unused allocation is still deducted from the donor. Incomplete history is marked explicitly.

## Energy dashboard cost sensor vs invoice sensor

| Sensor | Includes |
|--------|----------|
| `grid_variable_cost_total` | Supplier energy + network energy + per-kWh levies + VAT on those |
| `invoice_cost_total` | Above + network power + fixed monthly charges |
