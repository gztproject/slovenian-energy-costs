# Souporaba interoperability

**Principle:** Souporaba (`energy_sharing`) decides *how much* electricity was shared. Slovenian Energy Costs decides *what that electricity is worth*.

Install Souporaba separately: https://github.com/gztproject/Souporaba

Souporaba is **optional**. Ordinary billing works without it.

## Ownership

| Responsibility | Owner |
|----------------|-------|
| 15-minute sharing settlement | Souporaba |
| Allocation %, used/unused/billable kWh | Souporaba |
| Supplier / network / levies / VAT € | Slovenian Energy Costs |
| Receiver savings sensors | Slovenian Energy Costs |
| Donor annual netting | Slovenian Energy Costs |
| Energy dashboard cost entity | Slovenian Energy Costs |

## Setup

1. Install and configure Souporaba on the Prejemnik (receiver) instance.
2. Add Slovenian Energy Costs → billing model **Souporaba receiver**.
3. Settlement source **souporaba** → select the Souporaba config entry.
4. The flow auto-maps entities by `unique_id` pattern `{entry_id}_{sensor_key}`.
5. In Energy dashboard → Grid consumption → **Use an entity tracking the total costs** → select `grid_variable_cost_total`.
6. Keep physical import/export sensors for energy statistics (do not replace with billable energy).

## Synchronization

- Listens to public sensor state changes (not private Souporaba APIs).
- Waits until all required last-interval sensors share the same `interval_id`.
- Books only when `settlement_accumulated = true`.
- `mismatch_warn` → book as `estimated`; `mismatch_skip` / not accumulated → do not book money.
- Idempotent: each `interval_id` is booked at most once (persisted).

## Resets

- Souporaba `reset_totals` does **not** reset Slovenian Energy Costs lifetime € counters.
- Missing historical intervals are marked incomplete — never fabricated.

## Donor (Oddajnik)

- May run on a separate Home Assistant instance.
- Configure mirrored export / shared-energy entities locally.
- Deduction = **full allocated** shared energy (including unused).
- Set `donor_export_already_deducted` if the export sensor already excludes sharing.

## Optional upstream enhancement

A versioned `energy_sharing` settlement event (or short history buffer) would improve atomic delivery and offline recovery. Compatibility with current public sensors is implemented first; any upstream change should remain backward-compatible.

## Double-counting checks

- Never recompute sharing allocation when Souporaba accepted a result.
- Network charges always use physical import.
- Lifetime financial counters are independent of Souporaba cumulative totals.
