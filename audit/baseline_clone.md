# clone: baseline audit

His clone: picks like him + +3.5%/-10%/6 min

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 2,277 |
| wins | 1,539 |
| losses | 738 |
| win% | 68% |
| net | -7,467.75 |
| per day | -11.15 |
| t | -7.20 |
| PF | 0.66 |
| avg win | 9.58 |
| avg loss | -30.09 |
| R:R | 0.32 |
| expectancy | -3.28 |
| maxDD$ | -7,506.71 |
| sharpe | -4.83 |
| sortino | -6.66 |
| max losses in a row | 5 |
| costs | 4,690.62 |
| top5 share | nan% |
| net without top 5 | -7,642.98 |

**Out of sample (2026, not used to design the rules):** 752 trades, 66% won, -17.15 a day, PF 0.62, max drawdown -3,580.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -12.93 |
| bear (below 50-day avg) | 173 | -6.48 |
| high volatility (top third) | 217 | -7.18 |
| low volatility (bottom third) | 217 | -11.28 |
| trending month | 213 | -11.86 |
| choppy month | 264 | -11.02 |
| big-range day (top 10%) | 67 | +8.99 |
| gap open over 1% | 120 | -11.93 |

| Year | Per day |
|---|---|
| 2024 | -9.51 |
| 2025 | -7.51 |
| 2026 | -17.15 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -202, worst day -95
- Apr 2025 tariff crash and rebound: 8 days, total +327, worst day -162
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -34, worst day -78

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -17.94 | 2,277 |
| costs 3 cents a side | -24.64 | 2,263 |
| costs 5 cents a side | -30.46 | 1,866 |
| costs 10 cents a side | -39.31 | 1,270 |
| orders filled 1 min late | -12.72 | 2,255 |
| orders filled 2 min late | -13.47 | 2,190 |
| 10% of orders rejected | -10.42 | 2,067 |
| one-hour connection outage every day | -9.38 | 2,019 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -13.30 |
| target x1.2 | -11.25 |
| stop x0.8 | -9.54 |
| stop x1.2 | -11.67 |

## Monte Carlo: 5,000 simulated years (856 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -5,582 | -5,623 |
| 5% | -5,174 | -5,217 |
| 25% | -4,569 |  |
| 50% | -4,162 | -4,220 |
| 75% | -3,758 |  |
| 95% | -3,169 |  |
| 99% | -2,803 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 9% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 518 | -34.39 | -17,815 |
| stop (gap) | 49 | -38.82 | -1,902 |
| target | 1,527 | +9.62 | +14,691 |
| time | 183 | -13.34 | -2,441 |
