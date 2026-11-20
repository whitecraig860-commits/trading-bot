# skipweak: baseline audit

Skip weak crosses: main, skipping closes less than $0.10 past the line

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 5,544 |
| wins | 3,561 |
| losses | 1,983 |
| win% | 64% |
| net | -21,149.48 |
| per day | -31.57 |
| t | -24.71 |
| PF | 0.51 |
| avg win | 6.07 |
| avg loss | -21.57 |
| R:R | 0.28 |
| expectancy | -3.81 |
| maxDD$ | -21,111.58 |
| sharpe | -16.78 |
| sortino | -21.86 |
| max losses in a row | 12 |
| costs | 11,420.64 |
| top5 share | nan% |
| net without top 5 | -21,271.95 |

**Out of sample (2026, not used to design the rules):** 1744 trades, 64% won, -35.85 a day, PF 0.54, max drawdown -7,480.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -29.27 |
| bear (below 50-day avg) | 173 | -38.99 |
| high volatility (top third) | 217 | -34.24 |
| low volatility (bottom third) | 217 | -26.17 |
| trending month | 213 | -30.39 |
| choppy month | 264 | -33.36 |
| big-range day (top 10%) | 67 | -31.48 |
| gap open over 1% | 120 | -32.46 |

| Year | Per day |
|---|---|
| 2024 | -26.31 |
| 2025 | -32.42 |
| 2026 | -35.85 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -320, worst day -74
- Apr 2025 tariff crash and rebound: 8 days, total -590, worst day -195
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -111, worst day -41

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -47.28 | 5,424 |
| costs 3 cents a side | -51.09 | 4,286 |
| costs 5 cents a side | -40.42 | 2,229 |
| costs 10 cents a side | -45.58 | 1,367 |
| orders filled 1 min late | -28.60 | 5,404 |
| orders filled 2 min late | -29.45 | 4,990 |
| 10% of orders rejected | -28.78 | 5,328 |
| one-hour connection outage every day | -28.98 | 5,154 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -35.41 |
| target x1.2 | -26.70 |
| stop x0.8 | -25.50 |
| stop x1.2 | -34.67 |

## Monte Carlo: 5,000 simulated years (2085 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -12,834 | -12,870 |
| 5% | -12,392 | -12,414 |
| 25% | -11,747 |  |
| 50% | -11,286 | -11,308 |
| 75% | -10,849 |  |
| 95% | -10,198 |  |
| 99% | -9,738 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 100% | 4% | 4% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,733 | -21.29 | -36,890 |
| stop (gap) | 208 | -26.53 | -5,518 |
| target | 3,556 | +6.08 | +21,606 |
| time | 47 | -7.38 | -347 |
