# brakes: baseline audit

Brakes: main + stop for the day at +$50 or -$100

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 6,205 |
| wins | 3,948 |
| losses | 2,257 |
| win% | 64% |
| net | -23,713.93 |
| per day | -35.39 |
| t | -28.29 |
| PF | 0.48 |
| avg win | 5.63 |
| avg loss | -20.36 |
| R:R | 0.28 |
| expectancy | -3.82 |
| maxDD$ | -23,679.46 |
| sharpe | -18.08 |
| sortino | -27.09 |
| max losses in a row | 12 |
| costs | 12,782.30 |
| top5 share | nan% |
| net without top 5 | -23,826.16 |

**Out of sample (2026, not used to design the rules):** 1735 trades, 62% won, -38.21 a day, PF 0.50, max drawdown -7,978.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -36.05 |
| bear (below 50-day avg) | 173 | -34.53 |
| high volatility (top third) | 217 | -32.96 |
| low volatility (bottom third) | 217 | -34.98 |
| trending month | 213 | -35.26 |
| choppy month | 264 | -36.04 |
| big-range day (top 10%) | 67 | -19.81 |
| gap open over 1% | 120 | -31.36 |

| Year | Per day |
|---|---|
| 2024 | -33.60 |
| 2025 | -34.56 |
| 2026 | -38.21 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -250, worst day -74
- Apr 2025 tariff crash and rebound: 8 days, total -1, worst day -104
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -207, worst day -63

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -52.93 | 6,038 |
| costs 3 cents a side | -53.41 | 4,432 |
| costs 5 cents a side | -39.73 | 2,150 |
| costs 10 cents a side | -45.20 | 1,346 |
| orders filled 1 min late | -34.28 | 5,959 |
| orders filled 2 min late | -32.22 | 5,935 |
| 10% of orders rejected | -33.96 | 5,934 |
| one-hour connection outage every day | -33.38 | 5,865 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -41.53 |
| target x1.2 | -29.10 |
| stop x0.8 | -29.43 |
| stop x1.2 | -40.68 |

## Monte Carlo: 5,000 simulated years (2334 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -14,176 | -14,189 |
| 5% | -13,730 | -13,742 |
| 25% | -13,085 |  |
| 50% | -12,641 | -12,658 |
| 75% | -12,196 |  |
| 95% | -11,573 |  |
| 99% | -11,154 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 100% | 60% | 59% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,973 | -20.38 | -40,201 |
| stop (gap) | 227 | -22.90 | -5,198 |
| target | 3,945 | +5.64 | +22,232 |
| time | 60 | -9.13 | -548 |
