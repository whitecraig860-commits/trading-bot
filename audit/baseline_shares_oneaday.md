# shares_oneaday: baseline audit

Shares one-a-day: 100 QQQ shares on the same breakout (the live bot trades about $1,000)

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 485 |
| wins | 284 |
| losses | 201 |
| win% | 59% |
| net | 23,907.95 |
| per day | 35.68 |
| t | +2.71 |
| PF | 1.39 |
| avg win | 300.44 |
| avg loss | -305.55 |
| R:R | 0.98 |
| expectancy | 49.29 |
| maxDD$ | -6,083.58 |
| sharpe | +1.48 |
| sortino | +1.63 |
| max losses in a row | 5 |
| costs | 970.00 |
| top5 share | 39% |
| net without top 5 | 14,484.45 |

**Out of sample (2026, not used to design the rules):** 165 trades, 57% won, +38.77 a day, PF 1.32, max drawdown -6,084.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | +21.64 |
| bear (below 50-day avg) | 173 | +78.18 |
| high volatility (top third) | 217 | +35.98 |
| low volatility (bottom third) | 217 | +20.73 |
| trending month | 213 | -0.31 |
| choppy month | 264 | +38.57 |
| big-range day (top 10%) | 67 | +321.46 |
| gap open over 1% | 120 | +18.97 |

| Year | Per day |
|---|---|
| 2024 | +41.75 |
| 2025 | +27.98 |
| 2026 | +38.77 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total +1,500, worst day -123
- Apr 2025 tariff crash and rebound: 8 days, total +2,843, worst day -2,947
- Dec 2024 Fed sell-off (18 Dec): 4 days, total +487, worst day -119

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | +34.24 | 485 |
| costs 3 cents a side | +32.79 | 485 |
| costs 5 cents a side | +29.89 | 485 |
| costs 10 cents a side | +22.65 | 485 |

## Monte Carlo: 5,000 simulated years (182 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -5,342 | -11,030 |
| 5% | -1,310 | -8,097 |
| 25% | +4,411 |  |
| 50% | +8,554 | -3,962 |
| 75% | +12,722 |  |
| 95% | +18,804 |  |
| 99% | +22,851 |  |

Chance of a losing year: 8%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 6% |
| $5,000 | 100% | 100% | 99% | 87% | 3% |
| $25,000 | 87% | 30% | 7% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| safety stop | 2 | -1297.50 | -2,595 |
| time | 431 | +23.11 | +9,961 |
| trail | 52 | +318.11 | +16,542 |
