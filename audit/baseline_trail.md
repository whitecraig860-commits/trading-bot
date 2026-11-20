# trail: baseline audit

Trailing exit: main + keep winners from +2.5%, sell 1.5% below best, 15-min limit

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 3,688 |
| wins | 1,749 |
| losses | 1,939 |
| win% | 47% |
| net | -6,744.26 |
| per day | -10.07 |
| t | -6.08 |
| PF | 0.79 |
| avg win | 14.85 |
| avg loss | -16.88 |
| R:R | 0.88 |
| expectancy | -1.83 |
| maxDD$ | -6,746.61 |
| sharpe | -3.68 |
| sortino | -8.92 |
| max losses in a row | 13 |
| costs | 7,597.28 |
| top5 share | nan% |
| net without top 5 | -7,633.15 |

**Out of sample (2026, not used to design the rules):** 1130 trades, 47% won, -10.86 a day, PF 0.82, max drawdown -2,349.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -12.13 |
| bear (below 50-day avg) | 173 | -6.28 |
| high volatility (top third) | 217 | -3.29 |
| low volatility (bottom third) | 217 | -11.06 |
| trending month | 213 | -13.23 |
| choppy month | 264 | -9.72 |
| big-range day (top 10%) | 67 | +16.86 |
| gap open over 1% | 120 | -2.50 |

| Year | Per day |
|---|---|
| 2024 | -9.30 |
| 2025 | -10.04 |
| 2026 | -10.86 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -160, worst day -59
- Apr 2025 tariff crash and rebound: 8 days, total +269, worst day -98
- Dec 2024 Fed sell-off (18 Dec): 4 days, total +22, worst day -63

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -17.07 | 3,077 |
| costs 3 cents a side | -22.40 | 2,654 |
| costs 5 cents a side | -31.80 | 2,224 |
| costs 10 cents a side | -50.29 | 1,726 |
| orders filled 1 min late | -8.90 | 3,615 |
| orders filled 2 min late | -6.29 | 3,731 |
| 10% of orders rejected | -10.38 | 3,643 |
| one-hour connection outage every day | -10.03 | 3,582 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -9.02 |
| target x1.2 | -8.60 |
| stop x0.8 | -7.39 |
| stop x1.2 | -13.14 |

## Monte Carlo: 5,000 simulated years (1387 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -6,524 | -6,618 |
| 5% | -6,001 | -6,087 |
| 25% | -5,250 |  |
| 50% | -4,737 | -4,847 |
| 75% | -4,199 |  |
| 95% | -3,401 |  |
| 99% | -2,867 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 42% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,206 | -21.34 | -25,732 |
| stop (gap) | 125 | -24.36 | -3,045 |
| time | 18 | -7.50 | -135 |
| trail | 2,339 | +9.48 | +22,169 |
