# original: baseline audit

Original: same as main, no stop after losses

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 18,201 |
| wins | 11,794 |
| losses | 6,407 |
| win% | 65% |
| net | -63,778.36 |
| per day | -95.19 |
| t | -28.24 |
| PF | 0.50 |
| avg win | 5.48 |
| avg loss | -20.05 |
| R:R | 0.27 |
| expectancy | -3.50 |
| maxDD$ | -63,705.89 |
| sharpe | -19.43 |
| sortino | -20.89 |
| max losses in a row | 9 |
| costs | 37,494.06 |
| top5 share | nan% |
| net without top 5 | -63,900.84 |

**Out of sample (2026, not used to design the rules):** 5644 trades, 64% won, -105.10 a day, PF 0.55, max drawdown -21,872.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | -92.47 |
| bear (below 50-day avg) | 173 | -108.90 |
| high volatility (top third) | 217 | -95.04 |
| low volatility (bottom third) | 217 | -89.21 |
| trending month | 213 | -103.87 |
| choppy month | 264 | -95.24 |
| big-range day (top 10%) | 67 | -79.87 |
| gap open over 1% | 120 | -90.48 |

| Year | Per day |
|---|---|
| 2024 | -83.64 |
| 2025 | -96.66 |
| 2026 | -105.10 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total -1,235, worst day -424
- Apr 2025 tariff crash and rebound: 8 days, total -1,170, worst day -329
- Dec 2024 Fed sell-off (18 Dec): 4 days, total -384, worst day -163

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | -149.52 | 18,201 |
| costs 3 cents a side | -203.85 | 18,201 |
| costs 5 cents a side | -312.52 | 18,201 |
| costs 10 cents a side | -584.17 | 18,201 |
| orders filled 1 min late | -83.12 | 15,879 |
| orders filled 2 min late | -71.45 | 14,278 |
| 10% of orders rejected | -88.23 | 16,820 |
| one-hour connection outage every day | -82.88 | 15,344 |

## Settings wobbled (per day)

| Variant | Per day |
|---|---|
| target x0.8 | -102.53 |
| target x1.2 | -86.28 |
| stop x0.8 | -97.10 |
| stop x1.2 | -92.33 |

## Monte Carlo: 5,000 simulated years (6846 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -37,559 | -37,571 |
| 5% | -36,753 | -36,784 |
| 25% | -35,684 |  |
| 50% | -34,940 | -34,956 |
| 75% | -34,164 |  |
| 95% | -33,088 |  |
| 99% | -32,272 |  |

Chance of a losing year: 100%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 100% |
| $5,000 | 100% | 100% | 100% | 100% | 100% |
| $25,000 | 100% | 100% | 100% | 100% | 100% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| stop | 5,384 | -20.10 | -108,245 |
| stop (gap) | 777 | -23.28 | -18,088 |
| target | 11,769 | +5.49 | +64,626 |
| time | 271 | -7.64 | -2,071 |
