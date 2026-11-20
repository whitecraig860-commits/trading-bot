# his: baseline audit

His style: trail + 12% stop

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 4,864 |
| wins | 2,762 |
| losses | 2,102 |
| win% | 57% |
| net | -13,053.22 |
| per day | -19.48 |
| t | -8.37 |
| PF | 0.75 |
| avg win | 13.88 |
| avg loss | -24.44 |
| R:R | 0.57 |
| expectancy | -2.68 |
| maxDD$ | -13,088.14 |
| sharpe | -5.09 |
| sortino | -9.72 |
| max losses in a row | 11 |
| costs | 10,019.84 |
| top5 share | nan% |
| net without top 5 | -13,965.12 |

**Out of sample (2026, not used to design the rules):** 1481 trades, 57% won, -23.85 a day, PF 0.75, max drawdown -5,179.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -17.62 |
| bear (below 50-day avg) | 173 | -24.62 |
| high volatility (top third) | 217 | -13.57 |
| low volatility (bottom third) | 217 | -21.67 |
| trending month | 213 | -19.51 |
| choppy month | 264 | -18.21 |
| big-range day (top 10%) | 67 | +2.38 |
| gap open over 1% | 120 | -17.13 |

| Year | Per day |
|---|---|
| 2024 | -15.79 |
| 2025 | -18.95 |
| 2026 | -23.85 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -152, worst day -97
- Apr 2025 tariff crash and rebound: 8 days, total -167, worst day -176
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -109, worst day -94

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -28.00 | 3,833 |
| costs 3 cents a side | -32.96 | 3,136 |
| costs 5 cents a side | -40.90 | 2,434 |
| costs 10 cents a side | -55.70 | 1,752 |
| orders filled 1 min late | -13.15 | 4,899 |
| orders filled 2 min late | -8.47 | 4,772 |
| 10% of orders rejected | -19.55 | 4,748 |
| one-hour connection outage every day | -18.51 | 4,672 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -16.77 |
| target x1.2 | -20.25 |
| stop x0.8 | -16.59 |
| stop x1.2 | -19.80 |

## Monte Carlo: 5,000 simulated years (1829 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -10,385 | -10,460 |
| 5% | -9,634 | -9,745 |
| 25% | -8,576 |  |
| 50% | -7,821 | -7,950 |
| 75% | -7,083 |  |
| 95% | -6,018 |  |
| 99% | -5,184 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 66% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 914 | -40.12 | -36,674 |
| stop (gap) | 99 | -47.51 | -4,704 |
| time | 166 | -16.36 | -2,716 |
| trail | 3,685 | +8.42 | +31,040 |
