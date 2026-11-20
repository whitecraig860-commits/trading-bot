# combo: baseline audit

Combo: skip weak + signals from 09:31 + strike in the money

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 5,751 |
| wins | 3,685 |
| losses | 2,066 |
| win% | 64% |
| net | -23,166.09 |
| per day | -34.58 |
| t | -23.99 |
| PF | 0.52 |
| avg win | 6.87 |
| avg loss | -23.46 |
| R:R | 0.29 |
| expectancy | -4.03 |
| maxDD$ | -23,138.08 |
| sharpe | -17.09 |
| sortino | -22.52 |
| max losses in a row | 9 |
| costs | 11,847.06 |
| top5 share | nan% |
| net without top 5 | -23,292.87 |

**Out of sample (2026, not used to design the rules):** 1856 trades, 64% won, -39.26 a day, PF 0.56, max drawdown -8,171.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -30.70 |
| bear (below 50-day avg) | 173 | -46.33 |
| high volatility (top third) | 217 | -37.27 |
| low volatility (bottom third) | 217 | -28.31 |
| trending month | 213 | -33.18 |
| choppy month | 264 | -35.05 |
| big-range day (top 10%) | 67 | -41.85 |
| gap open over 1% | 120 | -38.64 |

| Year | Per day |
|---|---|
| 2024 | -29.33 |
| 2025 | -35.09 |
| 2026 | -39.26 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -404, worst day -101
- Apr 2025 tariff crash and rebound: 8 days, total -720, worst day -221
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -203, worst day -75

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -51.48 | 5,732 |
| costs 3 cents a side | -59.47 | 4,920 |
| costs 5 cents a side | -47.40 | 2,609 |
| costs 10 cents a side | -45.39 | 1,375 |
| orders filled 1 min late | -31.40 | 5,492 |
| orders filled 2 min late | -32.88 | 5,282 |
| 10% of orders rejected | -32.15 | 5,636 |
| one-hour connection outage every day | -32.32 | 5,464 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -39.84 |
| target x1.2 | -29.36 |
| stop x0.8 | -28.99 |
| stop x1.2 | -38.63 |

## Monte Carlo: 5,000 simulated years (2163 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -13,878 | -13,921 |
| 5% | -13,392 | -13,418 |
| 25% | -12,656 |  |
| 50% | -12,154 | -12,175 |
| 75% | -11,673 |  |
| 95% | -10,967 |  |
| 99% | -10,452 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 100% | 33% | 32% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,775 | -23.30 | -41,355 |
| stop (gap) | 243 | -27.44 | -6,668 |
| target | 3,678 | +6.87 | +25,282 |
| time | 55 | -7.73 | -425 |
