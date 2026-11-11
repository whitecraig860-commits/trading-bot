# Study 3: diversified ETF trend following. Pre-registered protocol

**Status:** written and committed on 2026-11-11, before any code for this study was written and before any data was downloaded or looked at. The commit hash and timestamp prove the order. After results are seen, nothing in this file may change. Any mistake found later is recorded in an "Amendments" section at the end, with the date and the reason. The original text stays as it is, and the report says which results the amendment affects.

**Baseline:** `research/REPORT.md` (PR #20). Studies 1 and 2 found no edge in the intraday scalper, the short-term QQQ trend worker or the swing breakout. Those are retired (PR #21).

**Plain-English summary**
- We test whether a slow, once-a-month rule that holds a basket of funds while they are rising, and switches to cash when they are falling, does better than simply holding the funds. "Better" means less risk per unit of return and smaller crashes.
- The rules are fixed below, taken from published research. They are not tuned on our data.
- The test is judged against hard pass/fail lines written now.
- A strategy that fails is not built.
- Nothing here trades: no orders, no paper account, no money.

---

## 1. Hypothesis

**H1 (main):** a long-or-cash, monthly time-series trend rule applied to a fixed, diversified basket of ETFs earns:
- a higher net-of-cost Sharpe ratio than the same basket bought and held, and
- a materially smaller maximum drawdown,

over 2003–2026. It also stays positive in the post-publication holdout (section 16).

**H0 (null):** any advantage is no larger than you would get by being in or out of each ETF at random for the same fraction of months (section 18.4), or is explained by chance across the number of variants tried (sections 18.5–18.6).

**What is NOT claimed:**
- Trend following is not expected to beat SPY or QQQ in total return. In long bull markets it usually lags them.
- Its documented value is crash protection and diversification (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017; Faber 2007). The pass lines reflect that.

## 2. Instruments (fixed universe, chosen before seeing results)

There are 13 US-listed ETFs across four asset classes. Each represents its asset class, is very liquid, and is the oldest widely held fund of its kind:

| Asset class | ETF | What it holds | Approx. first trading day |
|---|---|---|---|
| US equity | SPY | S&P 500 | 1993-01 |
| US equity | QQQ | Nasdaq-100 | 1999-03 |
| US equity | IWM | Russell 2000 small caps | 2000-05 |
| Intl equity | EFA | Developed ex-US | 2001-08 |
| Intl equity | EEM | Emerging markets | 2003-04 |
| Bonds | IEF | 7–10y US Treasuries | 2002-07 |
| Bonds | TLT | 20y+ US Treasuries | 2002-07 |
| Bonds | LQD | US investment-grade corporates | 2002-07 |
| Bonds | TIP | US inflation-linked Treasuries | 2003-12 |
| Real assets | GLD | Gold | 2004-11 |
| Real assets | DBC | Broad commodities | 2006-02 |
| Real assets | VNQ | US real estate (REITs) | 2004-09 |
| Real assets | SLV | Silver | 2006-04 |

- **Cash** is not a universe member. Its treatment is in section 14.
- **No additions, removals or substitutions** after this commit.
- **Point-in-time:** an ETF becomes eligible at the first month-end where it has at least 13 full calendar months of daily history. Before that it is treated as if it did not exist, and its slot does not exist (section 9).
- **Known bias, stated now:** every one of these ETFs still exists today. Choosing survivors with hindsight flatters any strategy that holds them, buy-and-hold included. Because the same universe is used for the strategies and for the diversified buy-and-hold benchmark, the comparison between them is fairer than either absolute number.

## 3. Data period

- **Downloaded:** from each ETF's first day to the last complete calendar month before the run date (expected 2026-10-31).
- **Portfolio evaluation starts** at the first month-end when at least 8 ETFs are eligible, with at least one from each of US equity, bonds and international equity. Expected around 2003-08. The exact date is computed by the code from this rule, not chosen.
- **SPY-only benchmarks** (section 15) are also reported from 1994 as supplementary evidence. They do not count toward pass/fail.

## 4. Data sources

1. **Prices:** Yahoo Finance daily OHLC via `yfinance`, with `auto_adjust=True`. These are total-return adjusted for dividends and splits, which matters because bond ETFs earn most of their return as income.
2. **Cross-check:** Alpaca SIP daily bars with `Adjustment.ALL` for 2016-01 onward, the same source as Studies 1–2 (section 22).
3. **Cash rate:** the 13-week US T-bill yield, `^IRX` on Yahoo, daily. Fallback: FRED `DTB3`.
4. **FX:** `GBPUSD=X` on Yahoo, daily, from 2003-12. Before that date, GBP figures are not reported.
5. **Regimes:** from FRED.
   - `USREC`: NBER recession indicator.
   - `CPIAUCSL`: CPI, used for inflation regimes.
   - If FRED is unreachable from the runner, those two regime cuts are reported as "not available". They are not replaced with something else.

## 5. Trend-detection methods

All signals are computed only from data up to and including the close of the signal day (section 7). No future data, no revision.

- `m(L)`: total return over the last L calendar months, month-end close to month-end close.
- `rf(L)`: compounded T-bill return over the same window.
- `SMA10`: average of the last 10 month-end closes, including this one.
- `σ12`: annualised standard deviation of daily returns over the last 252 trading days.

| Code | Name | Signal for each ETF (1 = hold, 0 = cash) | Source |
|---|---|---|---|
| **A** | 10-month moving average | 1 if month-end close > SMA10 | Faber (2007) |
| **B3** | Time-series momentum, 3m | 1 if m(3) − rf(3) > 0 | MOP (2012) family |
| **B6** | Time-series momentum, 6m | 1 if m(6) − rf(6) > 0 | MOP (2012) family |
| **B12** | Time-series momentum, 12m | 1 if m(12) − rf(12) > 0 | MOP (2012) |
| **C** | Risk-adjusted momentum | exposure = clip((m(12) − rf(12)) / σ12, 0, 1). Full exposure at a trailing Sharpe of 1 or more, proportional below, zero at 0 or less | Sharpe-scaled trend strength (cf. Baltas & Kosowski 2013) |
| **D** | Volatility-adjusted B12 | B12 signal, sized by inverse volatility with a portfolio volatility target (section 10) | Hurst, Ooi & Pedersen (2017) sizing |
| **E** | Combined | exposure = mean of the A, B3, B6 and B12 signals (0, ¼, ½, ¾ or 1), then sized exactly as D | ensemble; fixed now |

- **Long or cash only.** No short selling and no leverage, because a UK retail investor can't sensibly short ETFs or borrow cheaply.
- **Primary family** for multiple-testing purposes: A, B3, B6, B12, C, D and E. That is 7 strategies.
- **Sensitivity variants:** these are reported but can never be "picked", and they count toward the number of trials in sections 18.5–18.6.
  - A with 6-, 8- and 12-month averages.
  - A using a 200-trading-day average on daily closes.
  - D and E at 8% and 12% volatility targets.
  - That is 8 variants, so 15 configurations in total.

## 6. Entry rules

- At each signal month-end, an ETF with exposure > 0 is held at its target weight from section 9 or 10.
- Exposure goes from 0 to above 0: buy at the next session's open.
- Exposure rises or falls but stays above 0: resize at the next open.
- There are no intramonth entries.

## 7. Exit rules

- An ETF whose exposure at a signal month-end is 0 is sold in full at the next session's open, and the money goes to cash.
- There are no stop-losses, profit targets or intramonth exits. The rule is purely monthly, as the published versions are.
- A protective intramonth stop is out of scope. It would add a degree of freedom, and the literature does not specify one.

## 8. Monthly rebalancing and execution

- **Signal day:** the last NYSE trading day of each calendar month, using that day's adjusted close.
- **Execution day:** the next NYSE trading day, at its adjusted **open**. Nothing ever trades at the close it was computed from.
- **Order:** sells first, then buys, all at the same open.
- **Every month:** every position is reset to its target weight. A trade is skipped if it would change that ETF's weight by less than 0.25% of portfolio value, which avoids pointless tiny trades. The skip counts as no trade and no cost.
- **Fractional shares** are allowed, as at Alpaca, Trading 212 and IBKR.
- **Between rebalances,** weights drift with prices.
- **Valuation:** the portfolio is marked to market at every daily close, and drawdowns are measured on those daily marks.

## 9. Portfolio construction (A, B3, B6, B12, C)

- If `N` ETFs are eligible at a month-end, each gets one slot worth `1/N` of the portfolio.
- Target weight of ETF i = `exposure_i / N`. Whatever is not invested goes to cash.
- When a new ETF becomes eligible, `N` grows and every slot shrinks at that rebalance.

## 10. Position sizing and volatility adjustment (D and E)

1. **Raw risk weight.** `w_i = exposure_i × (1/σ60_i) / Σ_j (1/σ60_j)`.
   - `σ60` is the annualised standard deviation of the last 60 daily returns.
   - The sum is over **all eligible** ETFs, not just the held ones. So when an asset is out, its risk budget goes to cash rather than to the remaining assets.
2. **Portfolio volatility target.** Using the 252-day daily covariance matrix of the eligible ETFs, compute the predicted volatility of `w`.
   - Scale `w` so the predicted volatility equals **10% a year**.
   - Then cap the total at **100% invested**: no leverage, so scaling can only reduce exposure, never increase it.
3. **Caps.** Apply the caps in section 12, re-applying them until none binds. Anything removed goes to cash.

## 11. Volatility adjustment for A, B and C

None. They are equal-slot by design, so the effect of volatility sizing is isolated in D and E.

## 12. Risk limits (all strategies)

- **No short positions, no leverage:** gross exposure is at most 100%.
- **Single ETF:** at most 25% of the portfolio. For equal slots this only binds while N < 4, which never happens after the start date.
- **Asset class:**
  - all equities together (US plus international) at most 60%;
  - all real assets at most 40%;
  - bonds are not capped.
- **When a cap binds,** the excess goes to cash. It is not redistributed.
- **Monitoring limit:** there is no portfolio-level stop in the backtest. For any future paper trading, a strategy is halted for review if its live drawdown exceeds 1.5 times its worst backtest drawdown. This is a monitoring rule for later and is not part of this test.

## 13. Costs, slippage and FX

Costs are charged on the traded notional of every trade, on each side.

| Item | Base case | Stress case |
|---|---|---|
| Commission | £0 (as at Alpaca, Trading 212 and IBKR Lite) | £0 |
| Half bid-ask spread | 0.02%: SPY, QQQ, IWM, EFA, IEF, TLT, LQD, GLD. 0.05%: EEM, TIP, VNQ, SLV. 0.10%: DBC | 3× base |
| Slippage at the open | 0.05% on every trade | 3× base |
| FX conversion | 0.15% of traded notional, for a GBP account converting at each trade, as at Trading 212 | 0.50% |
| ETF running costs | already in the adjusted prices | n/a |

- **Gross** (zero costs) and **net** (base case) results are both reported.
- **Stress-cost** results are reported too, and they are part of pass criterion 7.

## 14. Treatment of cash

- Uninvested money earns the daily T-bill rate from `^IRX`, converted to a daily rate, **minus 0.10% a year** to allow for a broker or money-market fund paying less than T-bills.
- The cash rate is never negative.

## 15. Benchmarks

| Code | Benchmark |
|---|---|
| BH-SPY | SPY bought and held |
| BH-QQQ | QQQ bought and held |
| BH-DIV | Equal weight across all eligible ETFs, rebalanced monthly with the same execution and costs. **This is the main comparison.** |
| 60/40 | 60% SPY / 40% IEF, rebalanced monthly |
| CASH | T-bills (section 14) |
| BH-IEF | 7–10y Treasuries bought and held |
| SMA-SPY | SPY or cash on the 10-month moving-average rule (simple moving-average benchmark) |
| TSM-SPY | SPY or cash on 12-month time-series momentum (simple TSMOM benchmark) |

All benchmarks use the same costs, cash rate and execution timing as the strategies.

## 16. Out-of-sample period (holdout)

- **Full period:** the evaluation start (section 3) to 2026-10-31.
- **Pre-holdout:** the start to 2017-12-31.
- **Holdout:** 2018-01-01 to 2026-10-31.
  - Every rule here was published by 2017 at the latest: Faber 2007, MOP 2012, Hurst-Ooi-Pedersen 2017. The holdout is therefore data that the original authors could not have fitted to.
  - None of our rules are tuned on any period, but we report pre-holdout and holdout separately so that a strategy whose record comes only from before publication is visible.

## 17. Walk-forward analysis

Two procedures are run.

1. **Walk-forward selection.** This tests whether picking the recent winner adds value over holding E.
   - Each January from 2009, rank the six strategies A, B3, B6, B12, C and D by net Sharpe over the previous 60 months.
   - Trade the top one for the next 12 months.
   - The stitched returns are reported as strategy **WF**.
   - WF is compared with E and with BH-DIV.
   - WF is not part of the primary family and cannot pass on its own. It is evidence about whether "choosing" is worth anything.
2. **Rolling windows.** For each primary strategy, compute the share of rolling 60-month windows in which:
   - its net Sharpe beats BH-DIV, and
   - its maximum drawdown is smaller than BH-DIV's.

## 18. Statistical tests

1. **Return significance.** Use monthly net excess returns over cash.
   - Report the mean, its Newey-West (HAC, 6 lags) standard error, the t-statistic and the one-sided p-value.
   - **Holm–Bonferroni** correction is applied across the 7 primary strategies.
2. **Sharpe uncertainty.** The annualised Sharpe gets a 95% confidence interval from a **stationary block bootstrap** (Politis & Romano 1994): mean block length 6 months, 10,000 resamples, fixed seed 20261111.
3. **Sharpe difference vs BH-DIV.** Use the same bootstrap, resampling the two return series jointly. Report the 95% interval for the difference and the one-sided p-value.
4. **Random-timing null.** This tests whether the timing itself adds anything.
   - For each primary strategy and each ETF, keep the strategy's own fraction of months in the market but shuffle which months they are.
   - Shuffle in 3-month blocks, so the placebo trades about as often as the strategy.
   - Then rebuild the portfolio with the same sizing, costs and execution. Do this 1,000 times, seed 20261111.
   - Report the percentile of the real strategy's net Sharpe and maximum drawdown among the placebos.
5. **Deflated Sharpe Ratio** (Bailey & López de Prado 2014).
   - Number of trials: 15, the primary family plus the sensitivity variants (section 5).
   - It uses the variance of the trials' Sharpe ratios and the skewness and kurtosis of each strategy's returns.
   - Report the probability that the true Sharpe is above 0 after deflation.
6. **Probability of Backtest Overfitting** (Bailey, Borwein, López de Prado & Zhu 2017).
   - Method: CSCV on the monthly net returns of all 15 configurations, split into 16 blocks.
   - It is reported once for the family.
7. **Harvey–Liu–Zhu reference.** Report whether each t-statistic exceeds 3.0. This is for information only and is not a pass criterion.

## 19. Pass / fail thresholds

A primary strategy is **VALIDATED** only if **all** of these hold. They are evaluated on base-case net returns unless stated.

1. **Significance:** Holm-adjusted one-sided p < 0.05 for its mean monthly excess return over cash (18.1).
2. **Better than diversified buy-and-hold:**
   - its full-period Sharpe point estimate is at least BH-DIV's, **and**
   - its full-period maximum drawdown is no more than 0.75 × BH-DIV's maximum drawdown.
3. **Holdout:**
   - its holdout Sharpe is above 0, **and**
   - its holdout maximum drawdown is no more than BH-DIV's holdout maximum drawdown.
4. **Timing is real:** its net Sharpe is at or above the 95th percentile of the random-timing placebos (18.4).
5. **Not overfitting:**
   - its Deflated Sharpe probability is at least 0.95, **and**
   - the family PBO is at most 0.50.
6. **Stable:** its net CAGR is positive in at least 2 of the 3 sub-periods start–2009, 2010–2017 and 2018–2026.
7. **Survives costs:** its net Sharpe is above 0 under the stress costs (section 13).
8. **Not one bet:** no single ETF contributes more than 50% of its total net profit.

**Verdicts:**
- **VALIDATED:** passes all 8. Only then may a paper-trading engine for that strategy be designed. Its first run would be a separate, forward-only paper test with its own pre-registered review lines.
- **PROMISING:** passes 2, 3, 6, 7 and 8 but fails 1, 4 or 5. This means good risk control but not statistically proven. It is not built. It may be re-tested on more data later, under a new protocol.
- **FAILED:** anything else. It is not built.
- **E specifically:** E is judged on its own record against all 8 lines. It does not pass because its components pass, and its components do not fail because E fails.

## 20. Diversification and regime analysis

This section is descriptive. None of it changes a verdict.

1. **Correlation.**
   - The monthly return correlation matrix of the 13 ETFs: over all months, and over **stress months**, meaning SPY's worst 10% of months.
   - Each strategy's correlation and beta to SPY: over all months, months when SPY fell, and stress months.
2. **Crisis windows.** For each window, report each strategy's return over the window and its worst drawdown inside it, against SPY and BH-DIV.

   | Crisis | Months |
   |---|---|
   | GFC | 2007-10 to 2009-03 |
   | Euro crisis | 2011-05 to 2011-10 |
   | China/oil | 2015-08 to 2016-02 |
   | Q4 2018 | 2018-10 to 2018-12 |
   | COVID | 2020-02 to 2020-03 |
   | 2022 inflation bear | 2022-01 to 2022-10 |
   | 2025 tariff shock | 2025-02 to 2025-04 |

3. **Regime cuts.** For each regime, report each strategy's monthly mean return, Sharpe and number of months.

   | Regime | Definition |
   |---|---|
   | Inflation | CPI year-on-year above 4% vs at or below 4% |
   | Recession | NBER recession vs expansion |
   | Bull/bear | SPY's trailing 12-month return at or above 0 (bull) vs below 0 (bear) |

## 21. Metrics reported

For every strategy and benchmark, gross and net, in USD and in GBP from 2004:
- CAGR, volatility, Sharpe (excess of cash), Sortino, maximum drawdown, longest drawdown in months, Calmar;
- the share of positive months, best and worst month, and worst rolling 12 months;
- skewness, average exposure, annual turnover and annual cost drag.

The breakdowns are:
- by **decade** (2000s, part; 2010s; 2020s, part);
- by **calendar year**;
- by **regime** (section 20);
- by **asset class** and by **ETF**: each one's contribution to net profit and loss;
- every estimate that has an interval gets one (section 18).

## 22. Data-quality requirements

These are checked and printed before any result.

1. No missing adjusted open or close on an NYSE trading day after an ETF's first day. Gaps of up to 3 days are forward-filled and counted. A longer gap stops the run.
2. No price ≤ 0. Every daily move above 25% in absolute size is listed for inspection; a genuine 25% daily move is rare for these funds.
3. Stale prices: 5 or more consecutive identical closes are listed.
4. **Cross-check against Alpaca SIP** for 2016-01 onward.
   - The median absolute difference in monthly total returns must be below 0.10 percentage points for each ETF.
   - Any ETF that fails is flagged in the report. If more than 2 fail, the run's results are labelled "data quality unconfirmed".
5. The `^IRX` series must cover the whole evaluation period. If it has gaps, the last value is carried forward and the gaps are counted.
6. An ETF's eligibility date (section 2) is computed from the data and printed.

## 23. Capital and the £30-a-day question

This section is analysis only, run on the net GBP monthly returns of the best-scoring primary strategy, whatever its verdict, and of BH-DIV, 60/40 and BH-SPY.

- **Target:** £30 per trading day is about £7,560 a year, or £630 a month.
- **Withdrawals:** £630 is taken each month, rising 2.5% a year for inflation.
- **Simulation:**
  - a stationary block bootstrap of the historical GBP net monthly returns, with 6-month blocks, 10,000 paths of 20 years and seed 20261111;
  - starting capital of £25k, £50k, £100k, £150k and £250k.
- **Reported:**
  - the probability that the pot is used up within 20 years;
  - the median and the 10th-percentile pot after 20 years;
  - the share of years with a loss;
  - the worst calendar year in pounds.
- **Tax,** shown as separate lines:
  1. **Stocks & Shares ISA:** no UK tax, but contributions are limited to £20,000 a year, so a large pot takes years to build.
  2. **General account:** capital gains tax of 18% (basic rate) or 24% (higher rate) above the £3,000 allowance, applied to realised gains each year. Dividends and bond income above the £500 allowance are taxed at 8.75% or 33.75%.
  3. **Note:** US-domiciled ETFs are generally **non-reporting offshore funds** for UK tax, so gains on them are taxed as income, not capital gains. In practice a UK investor would use UCITS equivalents listed in London. This is stated as a limitation (section 24), not modelled.
- **No promise:** the output is a range of outcomes with the chance of each, not a forecast.

## 24. Known limitations (stated in advance)

1. **Survivorship and selection bias:** the universe is today's well-known survivors (section 2).
2. **Short history:** about 23 years and two big equity bear markets (2008 and 2022) plus COVID. There are few independent crashes to learn from, so confidence intervals will be wide.
3. **Publication overlap:** the rules were published using data that overlaps 2003–2017. Only the holdout is cleanly after publication.
4. **UK availability:** UK retail investors generally cannot buy US-listed ETFs because of the PRIIPs/KID rules (now moving to the FCA's Consumer Composite Investments regime). The tradable equivalents are London-listed UCITS ETFs, which have different fees, tracking and sometimes currency. US ETF data is used here because it has the longest clean history. Real results with UCITS funds will differ slightly.
5. **Tax:** see 23.3. This is not tax advice.
6. **Opens:** Yahoo's adjusted opens are computed by applying the close-based adjustment factor to the raw open, which is standard. Real fills at the open auction can differ from the printed open, which the slippage allowance in section 13 is meant to cover.
7. **Cash rate:** T-bill yields stand in for what a broker actually pays.
8. **Past performance:** trend following had a well-documented poor decade in 2009–2019. Past results do not guarantee anything.
9. **Not tested here:** cross-sectional momentum (ranking ETFs against each other) is deliberately left out. It gets its own pre-registered study later, after this one.

## 25. What happens after this study

- If **no strategy is VALIDATED**: nothing is built. The report says so plainly, and the next step is the separately pre-registered cross-sectional study, or nothing.
- If **at least one is VALIDATED**: the next step is a written design for a forward-only paper test of that one strategy. It needs its own protocol and the user's approval before any code. The paper-trading engine, dashboard and multi-worker system are **not** built until that point.
- Real-money trading is not part of any plan here.

## References

- Faber, M. (2007). A Quantitative Approach to Tactical Asset Allocation. *Journal of Wealth Management*.
- Moskowitz, T., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics*, 104(2).
- Hurst, B., Ooi, Y. H., & Pedersen, L. H. (2017). A Century of Evidence on Trend-Following Investing. *Journal of Portfolio Management*.
- Baltas, A.-N., & Kosowski, R. (2013). Momentum strategies in futures markets and trend-following funds. Working paper.
- Politis, D., & Romano, J. (1994). The stationary bootstrap. *JASA*, 89(428).
- Bailey, D., & López de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management*.
- Bailey, D., Borwein, J., López de Prado, M., & Zhu, Q. (2017). The Probability of Backtest Overfitting. *Journal of Computational Finance*.
- Harvey, C., Liu, Y., & Zhu, H. (2016). … and the Cross-Section of Expected Returns. *Review of Financial Studies*.
- Newey, W., & West, K. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*.

## Amendments

(none)
