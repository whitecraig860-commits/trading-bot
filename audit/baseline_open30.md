# open30: baseline audit

Opening move at 10:00: +10%/-10%/60 min, one a day

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 337 |
| wins | 156 |
| losses | 181 |
| win% | 46% |
| net | -1,647.82 |
| per day | -2.46 |
| t | -2.32 |
| PF | 0.76 |
| avg win | 33.27 |
| avg loss | -37.78 |
| R:R | 0.88 |
| expectancy | -4.89 |
| maxDD$ | -1,675.86 |
| sharpe | -1.45 |
| sortino | -3.38 |
| max losses in a row | 7 |
| costs | 694.22 |
| top5 share | nan% |
| net without top 5 | -2,066.92 |

**Out of sample (2026, not used to design the rules):** 116 trades, 38% won, -6.91 a day, PF 0.54, max drawdown -1,464.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -2.63 |
| bear (below 50-day avg) | 173 | -2.28 |
| high volatility (top third) | 217 | -2.51 |
| low volatility (bottom third) | 217 | -2.18 |
| trending month | 213 | -3.86 |
| choppy month | 264 | -3.03 |
| big-range day (top 10%) | 67 | +7.65 |
| gap open over 1% | 120 | -4.07 |

| Year | Per day |
|---|---|
| 2024 | -0.76 |
| 2025 | -0.17 |
| 2026 | -6.91 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -22, worst day -52
- Apr 2025 tariff crash and rebound: 8 days, total +409, worst day -52
- Dec 2024 Fed sell-off (18 Dec): 4 days, total +32, worst day +0

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -3.47 | 337 |
| costs 3 cents a side | -4.47 | 337 |
| costs 5 cents a side | -6.48 | 337 |
| costs 10 cents a side | -11.51 | 337 |
| orders filled 1 min late | -1.86 | 337 |
| orders filled 2 min late | -3.23 | 337 |
| 10% of orders rejected | -2.56 | 302 |
| one-hour connection outage every day | -2.22 | 272 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -2.51 |
| target x1.2 | -2.34 |
| stop x0.8 | -2.21 |
| stop x1.2 | -2.74 |

## Monte Carlo: 5,000 simulated years (127 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -1,824 | -1,886 |
| 5% | -1,526 | -1,613 |
| 25% | -1,121 |  |
| 50% | -835 | -997 |
| 75% | -548 |  |
| 95% | -122 |  |
| 99% | +150 |  |

Chance of a losing year: 97%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 98% | 88% | 49% | 35% |
| $5,000 | 93% | 49% | 9% | 0% | 0% |
| $25,000 | 0% | 0% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 174 | -37.30 | -6,491 |
| stop (gap) | 7 | -49.63 | -347 |
| target | 156 | +33.27 | +5,191 |
