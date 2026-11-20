# options_stop2: baseline audit

Main options bot: 1-minute VWAP/EMA50 crosses + 15-min range break, +2.5%/-6%/10 min, stop after 2 losses

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 6,477 |
| wins | 4,113 |
| losses | 2,364 |
| win% | 64% |
| net | -25,626.00 |
| per day | -38.25 |
| t | -32.14 |
| PF | 0.48 |
| avg win | 5.85 |
| avg loss | -21.02 |
| R:R | 0.28 |
| expectancy | -3.96 |
| maxDD$ | -25,591.53 |
| sharpe | -21.87 |
| sortino | -26.48 |
| max losses in a row | 12 |
| costs | 13,342.62 |
| top5 share | nan% |
| net without top 5 | -25,748.48 |

**Out of sample (2026, not used to design the rules):** 1886 trades, 62% won, -42.52 a day, PF 0.50, max drawdown -8,879.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -37.08 |
| bear (below 50-day avg) | 173 | -42.92 |
| high volatility (top third) | 217 | -39.67 |
| low volatility (bottom third) | 217 | -35.53 |
| trending month | 213 | -38.62 |
| choppy month | 264 | -39.20 |
| big-range day (top 10%) | 67 | -37.25 |
| gap open over 1% | 120 | -37.24 |

| Year | Per day |
|---|---|
| 2024 | -34.33 |
| 2025 | -37.98 |
| 2026 | -42.52 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -277, worst day -74
- Apr 2025 tariff crash and rebound: 8 days, total -593, worst day -199
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -207, worst day -63

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -55.86 | 6,240 |
| costs 3 cents a side | -57.23 | 4,653 |
| costs 5 cents a side | -44.03 | 2,337 |
| costs 10 cents a side | -46.20 | 1,367 |
| orders filled 1 min late | -35.66 | 6,208 |
| orders filled 2 min late | -34.27 | 6,219 |
| 10% of orders rejected | -37.07 | 6,370 |
| one-hour connection outage every day | -35.83 | 6,127 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -43.90 |
| target x1.2 | -32.03 |
| stop x0.8 | -31.22 |
| stop x1.2 | -44.92 |

## Monte Carlo: 5,000 simulated years (2436 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -15,157 | -15,175 |
| 5% | -14,683 | -14,705 |
| 25% | -14,004 |  |
| 50% | -13,525 | -13,543 |
| 75% | -13,064 |  |
| 95% | -12,392 |  |
| 99% | -11,951 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 100% | 94% | 93% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 2,051 | -20.86 | -42,790 |
| stop (gap) | 251 | -25.13 | -6,308 |
| target | 4,110 | +5.85 | +24,058 |
| time | 65 | -9.01 | -586 |
