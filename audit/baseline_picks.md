# picks: baseline audit

Picks like him: EMA9/20 agree + strong candle + before 12:00 + not weak

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 2,277 |
| wins | 1,476 |
| losses | 801 |
| win% | 65% |
| net | -7,835.15 |
| per day | -11.69 |
| t | -11.02 |
| PF | 0.54 |
| avg win | 6.32 |
| avg loss | -21.43 |
| R:R | 0.29 |
| expectancy | -3.44 |
| maxDD$ | -7,863.68 |
| sharpe | -7.36 |
| sortino | -10.38 |
| max losses in a row | 6 |
| costs | 4,690.62 |
| top5 share | nan% |
| net without top 5 | -7,957.37 |

**Out of sample (2026, not used to design the rules):** 737 trades, 62% won, -16.50 a day, PF 0.51, max drawdown -3,453.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -12.84 |
| bear (below 50-day avg) | 173 | -9.77 |
| high volatility (top third) | 217 | -8.89 |
| low volatility (bottom third) | 217 | -11.31 |
| trending month | 213 | -12.29 |
| choppy month | 264 | -11.05 |
| big-range day (top 10%) | 67 | +1.20 |
| gap open over 1% | 120 | -8.18 |

| Year | Per day |
|---|---|
| 2024 | -9.74 |
| 2025 | -9.33 |
| 2026 | -16.50 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -173, worst day -94
- Apr 2025 tariff crash and rebound: 8 days, total +274, worst day -28
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -33, worst day -48

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -18.47 | 2,271 |
| costs 3 cents a side | -21.97 | 2,033 |
| costs 5 cents a side | -25.23 | 1,508 |
| costs 10 cents a side | -38.95 | 1,237 |
| orders filled 1 min late | -12.72 | 2,236 |
| orders filled 2 min late | -12.61 | 2,167 |
| 10% of orders rejected | -10.66 | 2,085 |
| one-hour connection outage every day | -9.70 | 2,024 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -13.21 |
| target x1.2 | -9.92 |
| stop x0.8 | -11.31 |
| stop x1.2 | -12.99 |

## Monte Carlo: 5,000 simulated years (856 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -5,281 | -5,295 |
| 5% | -5,006 | -5,022 |
| 25% | -4,594 |  |
| 50% | -4,298 | -4,321 |
| 75% | -4,025 |  |
| 95% | -3,613 |  |
| 99% | -3,345 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 6% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 728 | -21.17 | -15,412 |
| stop (gap) | 65 | -25.95 | -1,687 |
| target | 1,475 | +6.32 | +9,326 |
| time | 9 | -6.95 | -63 |
