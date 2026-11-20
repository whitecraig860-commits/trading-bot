# shares_oneaday_2016: baseline audit

Shares one-a-day, 100 QQQ shares, 2016 to 2026 (longest data available)

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 2,057 |
| wins | 1,119 |
| losses | 938 |
| win% | 54% |
| net | 36,658.28 |
| per day | 13.46 |
| t | +2.96 |
| PF | 1.21 |
| avg win | 188.13 |
| avg loss | -185.35 |
| R:R | 1.01 |
| expectancy | 17.82 |
| maxDD$ | -7,877.62 |
| sharpe | +0.83 |
| sortino | +0.90 |
| max losses in a row | 9 |
| costs | 4,114.00 |
| top5 share | 26% |
| net without top 5 | 27,234.78 |

**Out of sample (2026, not used to design the rules):** 165 trades, 57% won, +38.77 a day, PF 1.32, max drawdown -6,084.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 1929 | +7.41 |
| bear (below 50-day avg) | 745 | +30.34 |
| high volatility (top third) | 901 | +17.84 |
| low volatility (bottom third) | 901 | -0.49 |
| trending month | 1019 | -0.71 |
| choppy month | 913 | +21.91 |
| big-range day (top 10%) | 273 | +119.09 |
| gap open over 1% | 413 | +4.21 |

| Year | Per day |
|---|---|
| 2016 | -2.57 |
| 2017 | -1.35 |
| 2018 | +2.20 |
| 2019 | +0.03 |
| 2020 | -12.96 |
| 2021 | +3.26 |
| 2022 | +36.21 |
| 2023 | +28.28 |
| 2024 | +32.88 |
| 2025 | +27.98 |
| 2026 | +38.77 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total +1,500, worst day -123
- Apr 2025 tariff crash and rebound: 8 days, total +2,843, worst day -2,947
- Dec 2024 Fed sell-off (18 Dec): 4 days, total +487, worst day -119
- Dec 2018 sell-off: 15 days, total -800, worst day -558
- Feb-Mar 2020 COVID crash: 23 days, total -2,998, worst day -1,186
- 2022 bear market (full year): 251 days, total +9,090, worst day -1,194
- Mar 2020 rebound: 27 days, total -1,077, worst day -631

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a share a side | +11.95 | 2,057 |
| costs 5 cents a share a side | +7.42 | 2,057 |
| costs 10 cents a share a side | -0.14 | 2,057 |

## Monte Carlo: 5,000 simulated years (190 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -6,593 | -8,916 |
| 5% | -3,563 | -6,750 |
| 25% | +433 |  |
| 50% | +3,125 | -3,169 |
| 75% | +5,896 |  |
| 95% | +9,845 |  |
| 99% | +12,543 |  |

Chance of a losing year: 22%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 100% | 16% |
| $5,000 | 100% | 100% | 96% | 70% | 8% |
| $25,000 | 70% | 16% | 3% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| safety stop | 27 | -523.83 | -14,143 |
| time | 1,827 | +9.07 | +16,567 |
| trail | 203 | +168.65 | +34,235 |
