# trailtrend: baseline audit

Trailing exit + trend: as trail, calls only above the open, puts only below

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 3,590 |
| wins | 1,750 |
| losses | 1,840 |
| win% | 49% |
| net | -4,303.93 |
| per day | -6.42 |
| t | -3.13 |
| PF | 0.86 |
| avg win | 15.07 |
| avg loss | -16.68 |
| R:R | 0.90 |
| expectancy | -1.20 |
| maxDD$ | -4,352.80 |
| sharpe | -2.00 |
| sortino | -5.67 |
| max losses in a row | 12 |
| costs | 7,395.40 |
| top5 share | nan% |
| net without top 5 | -5,429.63 |

**Out of sample (2026, not used to design the rules):** 1179 trades, 49% won, -5.29 a day, PF 0.91, max drawdown -1,412.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -8.95 |
| bear (below 50-day avg) | 173 | +0.21 |
| high volatility (top third) | 217 | +1.25 |
| low volatility (bottom third) | 217 | -6.34 |
| trending month | 213 | -9.34 |
| choppy month | 264 | -3.89 |
| big-range day (top 10%) | 67 | +25.52 |
| gap open over 1% | 120 | -3.86 |

| Year | Per day |
|---|---|
| 2024 | -8.30 |
| 2025 | -5.79 |
| 2026 | -5.29 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -253, worst day -62
- Apr 2025 tariff crash and rebound: 8 days, total +627, worst day -67
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -3, worst day -31

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -14.36 | 3,092 |
| costs 3 cents a side | -20.12 | 2,672 |
| costs 5 cents a side | -29.91 | 2,193 |
| costs 10 cents a side | -50.17 | 1,702 |
| orders filled 1 min late | -7.10 | 3,592 |
| orders filled 2 min late | -6.92 | 3,652 |
| 10% of orders rejected | -7.63 | 3,555 |
| one-hour connection outage every day | -6.07 | 3,501 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -5.52 |
| target x1.2 | -5.45 |
| stop x0.8 | -5.24 |
| stop x1.2 | -8.28 |

## Monte Carlo: 5,000 simulated years (1350 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -5,632 | -5,739 |
| 5% | -5,093 | -5,206 |
| 25% | -4,346 |  |
| 50% | -3,804 | -3,946 |
| 75% | -3,249 |  |
| 95% | -2,418 |  |
| 99% | -1,869 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 97% | 94% |
| $25,000 | 97% | 9% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,139 | -21.48 | -24,460 |
| stop (gap) | 122 | -24.04 | -2,933 |
| time | 23 | -3.15 | -72 |
| trail | 2,306 | +10.04 | +23,162 |
