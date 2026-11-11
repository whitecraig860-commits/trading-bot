# Study 4: trend following for a UK investor, in pounds. Pre-registered protocol

**Status:** written and committed on 2026-11-11, before any code for this study was written and before any of its data was downloaded or looked at. After results are seen, nothing here changes except an "Amendments" section at the end, where each amendment is dated and explained.

**Builds on:** Study 3 (`research/TREND_FOLLOWING_PROTOCOL.md`, `research/TREND_FOLLOWING_REPORT.md`). Unless this file says otherwise, every Study 3 rule applies unchanged, and its section numbers (§) are referenced here as "S3 §n".

**Plain English:**
- Study 3 measured everything in US dollars.
- Measured in pounds, the crash protection mostly disappeared. The pound tends to fall in a crisis, which cushions a UK investor holding dollar funds.
- So this study asks the question that actually matters to a UK investor: **in pounds, using fund types a UK investor can buy, does trend following beat simply holding the same funds?**
- It tests two ways of owning the funds:
  - **unhedged:** you carry the currency swings;
  - **pound-hedged:** the currency swings are removed, at a small cost, as London-listed "GBP Hedged" share classes do.

## 1. Hypothesis

**H1:** for a GBP investor, at least one of the three simple rules that came closest in Study 3 earns a higher net Sharpe ratio than holding the same funds in the same currency treatment, and a much smaller maximum drawdown. It also passes every line in §9.

The three rules are A (10-month moving average), B6 and B12.

**H0:** any advantage is no larger than random timing would give, or is explained by the number of configurations tried.

**Expected, stated in advance:** hedged versions should show a bigger benefit from trend following than unhedged ones, because hedging removes the pound's crisis cushion. This is a prediction, not a pass line.

## 2. Configurations (fixed; no new variants)

| Code | Rule (S3 §5, unchanged) | Currency treatment |
|---|---|---|
| A-U | 10-month moving average | unhedged GBP |
| B6-U | 6-month time-series momentum | unhedged GBP |
| B12-U | 12-month time-series momentum | unhedged GBP |
| A-H | 10-month moving average | GBP-hedged |
| B6-H | 6-month time-series momentum | GBP-hedged |
| B12-H | 12-month time-series momentum | GBP-hedged |

- Portfolio construction is equal slots (S3 §9), with the risk caps of S3 §12 and the execution of S3 §8.
- B3, C, D and E are **not** carried forward: they failed Study 3.
- There are no sensitivity variants. That gives 6 configurations in this study, and **21 in total across Studies 3 and 4**, which §8.5 uses.

## 3. Instruments and data

- **Universe:** the same 13 ETFs as S3 §2, with the same point-in-time eligibility. They stand in for their London-listed UCITS equivalents, whose own histories are mostly too short (for example, many GBP-hedged classes start in the 2010s).
- **ETF prices:** Yahoo, total-return adjusted, as in Study 3.
- **Exchange rate:** FRED `DEXUSUK` (US dollars per pound, daily), forward-filled over UK/US holiday mismatches. It is cross-checked against Yahoo `GBPUSD=X` from 2004 (§10).
- **Interest rates:**
  - US: `^IRX`, the 13-week T-bill, as in S3.
  - UK: FRED `IR3TIB01GBM156N`, the 3-month UK interbank rate (monthly). Each value applies to every day of its month.
  - If the UK series is unreachable, the run stops; nothing is substituted.
- **Evaluation period:** same rule as S3 §3, so it starts at 2004-05-28. Holdout from 2018-01-01. Sub-periods: start–2009, 2010–2017, 2018 onward. All as in Study 3.

## 4. Building the pound series (all known at the time; no look-ahead)

1. **Unhedged GBP price:**
   - close in GBP = close in USD ÷ USD-per-GBP rate on the same day;
   - open in GBP = open in USD ÷ **the previous day's** USD-per-GBP rate, so the open never uses a rate from later that day.
2. **GBP-hedged price.** It is built as a daily return, compounded:
   - hedged return = USD price return + (UK rate − US rate) ÷ 252 − 0.15% a year ÷ 252;
   - the rate difference is covered interest parity, the carry earned or paid by rolling a currency hedge;
   - the 0.15% a year covers the extra cost of a hedged share class and its forward contracts;
   - the hedged open = the previous hedged close × (USD open ÷ previous USD close).
3. **Cash for a UK investor:** UK 3-month rate minus 0.10% a year, never below 0 (as S3 §14).
4. **Signals:** every rule's signal is computed on the series the investor actually holds (unhedged GBP or hedged), with excess returns measured over **UK** cash.

## 5. Costs

These are London-listed UCITS ETFs bought in pounds, so there is **no per-trade FX conversion fee**. Spreads are wider than for the US-listed funds.

| Item | Base | Stress |
|---|---|---|
| Half bid-ask spread | 0.05%: SPY, QQQ, IWM, EFA, IEF, TLT, LQD, GLD equivalents. 0.10%: EEM, TIP, VNQ, SLV equivalents. 0.15%: DBC equivalent | 3× base |
| Slippage at the open | 0.05% | 3× base |
| Commission | £0 | £0 |
| Hedged share-class extra cost | 0.15% a year (in the price series) | 0.30% a year |
| Stamp duty | none on ETFs | none |

Gross, net and stress results are all reported.

## 6. Benchmarks (all in GBP, with the same costs and execution)

| Code | Benchmark |
|---|---|
| BH-DIV-U | equal-weight hold of the eligible ETFs, unhedged. **This is the comparison for the -U configurations.** |
| BH-DIV-H | the same, hedged. **This is the comparison for the -H configurations.** |
| 60/40-U | 60% SPY / 40% IEF equivalents, unhedged |
| 60/40-H | 60% SPY / 40% IEF equivalents, hedged |
| SPY-U | S&P 500 held, unhedged |
| SPY-H | S&P 500 held, hedged |
| CASH-UK | UK cash, §4.3 |

## 7. Statistical tests

These are as in S3 §18, with these changes:
- Excess returns are over UK cash.
- Holm correction is applied across the 6 configurations.
- Placebos and bootstraps use the same seed, 20261111.
- The Sharpe difference is measured against the benchmark with the same currency treatment.

## 8. Changes to the overfitting test, and why

In Study 3 the family PBO was 0.54, against a pass line of 0.50. PBO asks whether the variant that looks best in one half of history is also best in the other half. When the variants are close cousins, that is close to a coin flip, so it fails at random even when every variant works.

For that reason Study 4 changes the test as follows:

1. **PBO** is computed across the 6 configurations and **reported for information only**. It is not a pass line.
2. **The deflated Sharpe ratio is made stricter**, to cover all the selection done so far:
   - number of trials = **21**, every configuration tried in Studies 3 and 4;
   - variance of trial Sharpe ratios = the variance across the 6 configurations here.
3. **No other pass line is loosened.**

**Disclosure:** this change was decided after Study 3's results were seen. It is written here, before any Study 4 data is seen, so that you can judge it. Under these rules Study 3's verdicts do **not** change: they were judged by Study 3's own rules, and they stand.

## 9. Pass / fail (for each configuration, base-case net, in GBP)

A configuration is **VALIDATED** only if all of these hold:

1. **Significance:** Holm-adjusted (across 6) one-sided p < 0.05 for the mean monthly return over UK cash (Newey-West, 6 lags).
2. **Beats holding:**
   - its full-period Sharpe is at least that of its own benchmark (BH-DIV-U or BH-DIV-H), **and**
   - its maximum drawdown is no more than 0.75 × that benchmark's.
3. **Holdout (2018 onward):**
   - Sharpe above 0, **and**
   - maximum drawdown no worse than its own benchmark's holdout drawdown.
4. **Timing is real:** its net Sharpe is at or above the 95th percentile of 1,000 random-timing placebos (S3 §18.4).
5. **Not luck from searching:** deflated Sharpe probability at least 0.95, with 21 trials (§8).
6. **Stable:** net CAGR positive in at least 2 of the 3 sub-periods.
7. **Survives costs:** Sharpe above 0 at stress costs (§5).
8. **Not one bet:** no single ETF contributes more than 50% of net profit.

**Verdicts:**
- **VALIDATED:** all 8.
- **PROMISING:** passes 2, 3, 6, 7 and 8 but fails 1, 4 or 5.
- **FAILED:** anything else.

**What happens next:**
- **If any configuration is VALIDATED:** the next step is a written design for a **forward-only paper test** of that one configuration, using real London-listed funds. It needs its own pre-registered review lines and the user's approval before any code is written.
- **If none is VALIDATED:** nothing is built.

## 10. Data checks (descriptive; the run stops only where stated)

1. All of the S3 §22 checks on the ETF prices are repeated.
2. **FRED versus Yahoo exchange rate:** median absolute daily difference from 2004, which must be under 0.5%. If it is not, the run is labelled "FX unconfirmed".
3. **Real UK funds.** Where Yahoo has them, monthly returns of real London-listed UCITS funds are compared with the series built in §4:
   - S&P 500 unhedged: `VUSA.L`
   - S&P 500 GBP-hedged: `IGUS.L`
   - Nasdaq-100: `EQQQ.L`
   - gold: `SGLN.L`

   For each, the report gives the correlation, the median absolute monthly difference and the average yearly gap.
   - A ticker that is missing or broken (for example, a 100× jump from switching between pounds and pence) is reported as such. It is not fixed by hand.
   - This check is descriptive only.

## 11. Also reported

- Every S3 §21 metric, in GBP, for every configuration and benchmark.
- The year-by-year table, crisis windows (S3 §20.2) and correlation/beta to S&P 500 in GBP.
- **Hedged against unhedged:** the drawdown and Sharpe difference for each rule.
- **The £30-a-day capital simulation** (S3 §23) for the best-scoring configuration and for both BH-DIV benchmarks.

## 12. Limitations (stated in advance)

All of S3 §24 applies, plus:

1. The hedged series is a model of a hedged share class, not real fund prices. §10.3 checks it against a real fund where one exists.
2. The UK rate is monthly, so daily hedge carry is approximate.
3. The US-listed ETFs stand in for UCITS funds. Real UCITS funds differ slightly in fees, tracking and dividend withholding tax.
4. Holding the funds in an ISA is assumed for the main results.

## Amendments

(none)
