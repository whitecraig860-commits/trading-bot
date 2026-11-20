# five: baseline audit

5-minute crosses: +5%/-10%/30 min, stop after 2 losses

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 3,632 |
| wins | 2,342 |
| losses | 1,290 |
| win% | 64% |
| net | -11,025.32 |
| per day | -16.46 |
| t | -7.31 |
| PF | 0.74 |
| avg win | 13.14 |
| avg loss | -32.41 |
| R:R | 0.41 |
| expectancy | -3.04 |
| maxDD$ | -11,002.57 |
| sharpe | -4.91 |
| sortino | -7.93 |
| max losses in a row | 8 |
| costs | 7,481.92 |
| top5 share | nan% |
| net without top 5 | -11,227.72 |

**Out of sample (2026, not used to design the rules):** 1094 trades, 66% won, -14.03 a day, PF 0.80, max drawdown -3,019.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -17.73 |
| bear (below 50-day avg) | 173 | -12.28 |
| high volatility (top third) | 217 | -21.19 |
| low volatility (bottom third) | 217 | -15.92 |
| trending month | 213 | -17.77 |
| choppy month | 264 | -15.88 |
| big-range day (top 10%) | 67 | -23.18 |
| gap open over 1% | 120 | -19.71 |

| Year | Per day |
|---|---|
| 2024 | -19.48 |
| 2025 | -15.93 |
| 2026 | -14.03 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -314, worst day -83
- Apr 2025 tariff crash and rebound: 8 days, total -829, worst day -210
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -171, worst day -74

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -27.30 | 3,632 |
| costs 3 cents a side | -37.95 | 3,628 |
| costs 5 cents a side | -52.62 | 3,205 |
| costs 10 cents a side | -50.83 | 1,641 |
| orders filled 1 min late | -21.00 | 3,451 |
| orders filled 2 min late | -20.87 | 3,432 |
| 10% of orders rejected | -18.21 | 3,419 |
| one-hour connection outage every day | -14.98 | 3,241 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -18.25 |
| target x1.2 | -14.89 |
| stop x0.8 | -14.70 |
| stop x1.2 | -17.09 |

## Monte Carlo: 5,000 simulated years (1366 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -8,393 | -8,449 |
| 5% | -7,790 | -7,871 |
| 25% | -6,930 |  |
| 50% | -6,339 | -6,421 |
| 75% | -5,780 |  |
| 95% | -4,907 |  |
| 99% | -4,301 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 95% | 11% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 1,153 | -32.38 | -37,336 |
| stop (gap) | 116 | -35.85 | -4,159 |
| target | 2,335 | +13.16 | +30,739 |
| time | 28 | -9.63 | -270 |
