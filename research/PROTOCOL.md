# Research protocol (pre-registered 11 Nov 2026, before any result below was run)

This file is committed before the tests it describes. Its git timestamp is the proof that the rules and pass/fail
thresholds were fixed before the results were seen. Changing a threshold after seeing results voids the test.

## Study 1: does the intraday trend signal predict the share price? (why the options bot loses)

Question: the QQQ trend worker lost money with real option prices on all six markets tested (Mar 2024 to Nov 2026).
Is that because the *signal* has no edge, or because *options* (time decay, spread) ate an edge that exists?

Method (`research/trend_signal_check.py`):
- Same signal code as the live worker (`trendworker.signal`, settings now in config: day move 0.6%), same exits
  (2R target, break-even after 1R, trail after 1.5R, stop under the pullback, flat by 15:50), but on the SHARE.
- Cost per side 0.02% (SPY/QQQ/IWM/GLD) and 0.05% (NVDA/TSLA): roughly the spread plus slippage on liquid ETFs/shares.
- Also: the average 30- and 60-minute forward return after each signal versus all bars at the same time of day
  (does the signal predict direction at all?).

Reading: if the share result is also negative, the signal has no edge and no option structure can fix it.

## Study 2: the swing breakout, tested properly

Hypothesis: the existing 55-day breakout (score >= 50, long only, exits unchanged from `bot.py`) has positive expectancy
after realistic costs on a point-in-time stock universe, out of sample. This is the time-series/cross-sectional
momentum effect documented in the literature; the question is whether THIS implementation captures it.

Rules: unchanged from `bot.py` (`compute_signals`, `run_backtest_symbol`, `step_bar`, `try_fill`). No parameter is
changed in this study. Entry at the next day's open; stop 2 ATR; trailing exit under the 20-day low.

Universe: S&P 500 members AS OF EACH SIGNAL DATE, rebuilt from the current list and the public change history
(Wikipedia "List of S&P 500 companies"), including companies later removed. A trade counts only if the share was a
member on the signal date, closed >= $5 and traded >= $10m a day (20-day average) then. Coverage of removed
companies depends on what Alpaca still serves; the share of removed members with data is reported (residual
survivorship bias is stated, not hidden).

Data: Alpaca daily bars, all US exchanges (SIP), adjusted for splits and dividends, 2016 to Nov 2026. SPY as benchmark.

Periods (fixed now):
- Development: 2016-01-01 to 2021-12-31
- Validation: 2022-01-01 to 2023-12-31
- Untouched holdout: 2024-01-01 to 2026-11-10
Since no parameter is fitted in this study, "walk-forward" here means the result must hold period by period and year
by year, not just in total.

Costs: 0.10%, 0.25% and 0.50% per side (each reported). Stops fill at the stop price unless the bar opens beyond it.

Null benchmark: the same exits from RANDOM entry days (same shares, same membership rules, same number of entries,
3 seeds). If real signals do no better than random entries, the entry has no edge (any profit is the exit rule plus the
market's drift).

### Pass thresholds (all must hold, on the HOLDOUT, at 0.25% per side)
1. At least 150 trades.
2. Expectancy > +0.15R per trade.
3. Profit factor > 1.3.
4. Expectancy still > 0 after removing the 10 biggest winning trades.
5. Expectancy still > 0 after removing the 10 best shares.
6. Beats the random-entry benchmark by at least 0.10R per trade.
7. Positive expectancy in the development AND validation periods too (not only one).
8. A £1,000 cash-limited portfolio replay (2% risk a trade, max 10 open) has a worst fall under 35%.

If any fails, the strategy fails this test. The result is reported as it is; the rules are not changed and re-run on
the same data to make it pass.
