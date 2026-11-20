# oneaday: baseline audit

One-a-day breakout on next-day at-the-money options (follows the shares bot)

All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; paper-trading results are in `audit/paper_results.md`.

## Metrics (full period)

| Metric | Value |
|---|---|
| trades | 480 |
| wins | 223 |
| losses | 257 |
| win% | 46% |
| net | 9,461.20 |
| per day | 14.12 |
| t | +1.73 |
| PF | 1.27 |
| avg win | 199.53 |
| avg loss | -136.32 |
| R:R | 1.46 |
| expectancy | 19.71 |
| maxDD$ | -3,316.52 |
| sharpe | +1.02 |
| sortino | +2.02 |
| max losses in a row | 11 |
| costs | 988.80 |
| top5 share | 76% |
| net without top 5 | 2,244.50 |

**Out of sample (2026, not used to design the rules):** 164 trades, 46% won, +16.17 a day, PF 1.24, max drawdown -3,317.

## Market conditions (per day)

| Condition | Days | Per day |
|---|---|---|
| bull (above 50-day avg) | 448 | +2.75 |
| bear (below 50-day avg) | 173 | +43.32 |
| high volatility (top third) | 217 | +22.74 |
| low volatility (bottom third) | 217 | +1.18 |
| trending month | 213 | -11.10 |
| choppy month | 264 | +22.08 |
| big-range day (top 10%) | 67 | +263.12 |
| gap open over 1% | 120 | +14.72 |

| Year | Per day |
|---|---|
| 2024 | +13.08 |
| 2025 | +13.28 |
| 2026 | +16.17 |

## Named stress events

- Aug 2024 volatility spike (5 Aug): 7 days, total +510, worst day -166
- Apr 2025 tariff crash and rebound: 8 days, total +3,362, worst day -629
- Dec 2024 Fed sell-off (18 Dec): 4 days, total +209, worst day -77

## Execution stress (per day; each changes one thing)

| Scenario | Per day | Trades |
|---|---|---|
| costs 2 cents a side | +12.69 | 480 |
| costs 3 cents a side | +11.26 | 480 |
| costs 5 cents a side | +8.39 | 480 |
| costs 10 cents a side | +1.23 | 480 |

## Monte Carlo: 5,000 simulated years (181 trades each, random order, extra slippage)

| Percentile | Year's result | Max drawdown |
|---|---|---|
| 1% | -4,628 | -6,315 |
| 5% | -2,287 | -4,819 |
| 25% | +788 |  |
| 50% | +3,053 | -2,438 |
| 75% | +5,521 |  |
| 95% | +9,313 |  |
| 99% | +12,151 |  |

Chance of a losing year: 18%

| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |
|---|---|---|---|---|---|
| $2,000 | 100% | 100% | 100% | 99% | 11% |
| $5,000 | 100% | 99% | 89% | 47% | 5% |
| $25,000 | 47% | 4% | 0% | 0% | 0% |

## Where the money goes (by exit reason)

| Exit | Trades | Average | Total |
|---|---|---|---|
| safety stop | 2 | -370.56 | -741 |
| time | 427 | +3.11 | +1,327 |
| trail | 51 | +174.02 | +8,875 |
