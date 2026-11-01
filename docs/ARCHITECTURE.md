# Architecture

## Module layout

| Layer | Path | Responsibility |
|-------|------|----------------|
| HA UI / entities | `config_flow.py`, `sensor.py`, `number.py`, `diagnostics.py` | Config wizard, Energy-dashboard sensors |
| Orchestration | `coordinator.py`, `storage.py` | Interval booking, persistence, price refresh |
| Souporaba adapter | `integrations/souporaba.py` | Public `energy_sharing` entity → `SettlementInterval` |
| Billing engine | `billing/` | Pure Decimal mathematics (no HA imports) |
| Tariffs | `tariffs/` | Calendar, rate registry, supplier/network rates |
| Models | `models.py` | Typed DTOs shared by all layers |

## Home Assistant Energy dashboard interfaces

1. **Current price** — `current_variable_price` (`state_class: measurement`, €/kWh, includes VAT as documented).
2. **Accumulated cost** — `grid_variable_cost_total` (`device_class: monetary`, `state_class: total`, `EUR`). Prefer this for Souporaba / complex contracts.

Do **not** use `total_increasing` with `monetary` — Home Assistant expects `total`.

## Regulatory confidence

| Rule | Status |
|------|--------|
| Network 5-block calendar (Europe/Ljubljana) | Implemented (bundled schedule through 2026-12-31) |
| ANJP239 network energy + power rates 1.3.2026–31.12.2026 | Bundled |
| Nov–Dec 2026 reduced block-1 power | Bundled (`network_power_reduced`) |
| Supplier ET / VT-MT / dynamic | Configurable |
| Levies / VAT | Configurable rates (verify against current law) |
| Excess power | Incomplete unless user supplies rate |
| 2027+ official tables | Missing → quality `incomplete` + warning |

## Open assumptions

- Bundled network **time-block** hours follow the published five-block Slovenian schedule; verify against the methodology act if your DSO documentation differs.
- Default levy rates are placeholders — configure your invoice values.
- Excess-power methodology is not fully encoded without an explicit rate input.
