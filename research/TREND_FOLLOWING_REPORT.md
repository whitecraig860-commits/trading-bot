# Study 3: diversified ETF trend following. Results

**Run:** 2026-11-11 on GitHub Actions, on data to 2026-10-30. Full output: `research/study3_output.txt`. Code: `research/trend_following_study.py`.

**Rules:** `research/TREND_FOLLOWING_PROTOCOL.md`, committed (3d33f67) before any code was written or data looked at.
- **Amendment #1** (walk-forward start year) was committed before any real data was downloaded.
- No rule was changed after the results came in.

**Contents:**
- Part A: plain-English summary
- Part B: comparison report
- Part C: validation report (pass/fail)
- Part D: diversification and regimes
- Part E: the £30-a-day question
- Part F: future plan
- Part G: limitations

Everything here is a simulation. No trades, paper or real, were placed.

---

## Part A: plain-English summary

1. **Trend following did what it is known for: it made the crashes much smaller.**
   - The simple 10-month moving-average rule (A) lost at most **12.7%** from a peak over 22 years. Holding the same 13 funds lost up to **36%**, and holding SPY lost up to **55%**.
   - In 2008 rule A lost 4%, holding the same funds lost 19%, and SPY lost 37%.
   - It was smaller-loss in **every** 5-year window tested.
2. **It did not make more money.**
   - Rule A grew about **6.0% a year** after costs. Holding the same funds grew 8.0%, SPY 10.9% and QQQ 14.9%.
   - Return per unit of risk (Sharpe) was about the same as simply holding the funds: 0.67 against 0.62. The gap is well within the margin of error.
   - A plain 60% shares / 40% bonds mix scored a higher Sharpe (0.73) than every trend rule.
3. **The verdict: none of the 7 strategies is VALIDATED, so nothing gets built.**
   - Three of them came close: A (10-month average), B6 and B12 (6- and 12-month momentum). Each passed 7 of the 8 tests.
   - All three failed the overfitting test. Among 15 close variants, the one that looked best in one half of history was not reliably the best in the other half (PBO 0.54; the line was 0.50).
   - Under the rules we wrote first, that means **PROMISING, not built**. The other four (B3, C, D, E) failed several tests.
4. **The pound matters a lot for you.** This was the most important surprise.
   - When markets crash, the pound usually falls against the dollar. A UK investor holding dollar funds is partly cushioned by that.
   - Measured in pounds, simply holding the 13 funds fell at most **18.5%**, and rule A fell **17.8%**: almost the same. Rule A also earned less (7.5% a year against 9.5%).
   - **In pounds, trend following's main benefit mostly disappeared.**
5. **£30 a day still needs roughly £150,000, whichever approach you choose.**
   - The simulation took out £630 a month, rising with inflation, for 20 years.
   - With rule A in an ISA:
     - starting with £100k, the money ran out in about 44% of simulated futures;
     - starting with £150k, it ran out in about 1%.
   - Simply holding the funds, or a 60/40 mix, did slightly better at the same starting amounts.
   - No strategy here turns a small account into £30 a day.

## Part B: comparison report

### B1. Main table: full period, May 2004 to October 2026, US dollars, after base-case costs

| | CAGR | Volatility | Sharpe | Max drawdown | Worst 12 months | Turnover/yr | Cost/yr |
|---|---|---|---|---|---|---|---|
| **A** 10-month MA | 6.0% | 6.4% | **0.67** | **−12.7%** | −9.6% | 100% | 0.5% |
| **B3** 3m momentum | 5.0% | 6.2% | 0.55 | −14.0% | −10.9% | 152% | 0.7% |
| **B6** 6m momentum | 5.6% | 6.4% | 0.62 | −12.2% | −7.0% | 111% | 0.5% |
| **B12** 12m momentum | 6.0% | 6.7% | 0.66 | −14.0% | −7.2% | 78% | 0.4% |
| **C** risk-adjusted | 4.5% | 5.4% | 0.54 | −10.8% | −8.7% | 75% | 0.3% |
| **D** vol-sized B12 | 5.3% | 7.0% | 0.53 | −18.2% | −15.1% | 171% | 0.8% |
| **E** combined | 5.0% | 6.7% | 0.51 | −15.1% | −12.5% | 178% | 0.8% |
| BH-DIV (same 13 funds, held) | 8.0% | 10.7% | 0.62 | −36.0% | −28.8% | 18% | 0.1% |
| 60/40 SPY/IEF | 8.1% | 9.0% | 0.73 | −32.6% | −26.0% | 13% | 0.1% |
| SPY held | 10.9% | 14.6% | 0.67 | −55.2% | −43.5% | — | — |
| QQQ held | 14.9% | 18.4% | 0.76 | −53.5% | −43.1% | — | — |
| SPY 10-month MA | 7.9% | 10.5% | 0.62 | −25.3% | −21.3% | 78% | 0.3% |
| SPY 12m momentum | 9.1% | 11.6% | 0.67 | −33.8% | −14.6% | 34% | 0.1% |
| 7–10y Treasuries | 3.3% | 6.5% | 0.27 | −24.0% | −16.4% | — | — |
| Cash (T-bills) | 1.7% | 0.5% | 0.00 | 0% | 0% | — | — |

**Cost effect on rule A's Sharpe:** gross 0.74, net 0.67, stress (three times the spread and slippage, 0.5% FX) 0.51. Every strategy stayed positive at stress costs, but the high-turnover D and E fell to about 0.25.

The sensitivity variants were reported but never picked: 6-, 8- and 12-month averages, a 200-day average, and 8% and 12% volatility targets. They all landed within about ±0.05 Sharpe of their parent rule. That is good: the results don't hinge on one lucky setting.

### B2. Before and after the rules were published

| | Pre-holdout Sharpe | Pre-holdout max DD | Holdout Sharpe | Holdout max DD |
|---|---|---|---|---|
| A | 0.72 | −12.7% | 0.60 | −9.1% |
| B6 | 0.70 | −9.2% | 0.51 | −12.2% |
| B12 | 0.78 | −10.9% | 0.46 | −14.0% |
| D | 0.81 | −13.6% | **0.15** | −18.2% |
| E | 0.70 | −15.1% | **0.26** | −14.7% |
| BH-DIV | 0.66 | −36.0% | 0.55 | −22.4% |
| SPY | 0.61 | −55.2% | 0.75 | −33.7% |

- **Pre-holdout** runs from 2004 to 2017. **Holdout** runs from 2018, after the rules were published.
- Every strategy stayed positive after publication, and the simple ones held up.
- **Volatility sizing (D and E) degraded badly.** In 2018 and 2022, shares and bonds fell together, so the "safe, low-volatility" bond positions it leaned on were exactly what lost money. D lost 13% in 2018 and 11% in 2022.

### B3. In pounds, which is what you would actually experience, from 2004

| | CAGR | Max drawdown | Worst 12 months |
|---|---|---|---|
| A | 7.5% | −17.8% | −9.4% |
| B12 | 7.5% | −19.3% | −8.6% |
| BH-DIV | **9.5%** | −18.5% | −7.6% |
| 60/40 | 9.6% | **−16.6%** | −6.6% |
| SPY held | 12.4% | −35.0% | −21.3% |
| QQQ held | 16.5% | −34.4% | −24.5% |

- Measured in pounds, "cash" here means US T-bills, so it swings with the exchange rate: up to 20% down.
- The pound fell about 30% against the dollar in 2008, which cushioned every dollar holding.
- So a UK investor holding unhedged US funds already had much of the crash protection that trend following provides in dollars.
- This is not tested here, but it implies something important: trend following would matter more with pound-hedged funds, where that cushion isn't there.

### B4. By decade, net, USD

| | 2004–09 | 2010s | 2020s (to Oct 2026) |
|---|---|---|---|
| A: CAGR / Sharpe / max DD | 8.1% / 0.81 / −12.7% | 3.7% / 0.59 / −9.4% | 7.5% / 0.66 / −9.1% |
| B12 | 7.5% / 0.78 / −9.9% | 4.9% / 0.68 / −10.9% | 6.5% / 0.53 / −14.0% |
| BH-DIV | 8.5% / 0.52 / −36.0% | 7.1% / 0.77 / −12.8% | 9.0% / 0.55 / −22.4% |
| SPY | 1.9% / 0.04 / −55.2% | 13.4% / 1.04 / −19.3% | 14.9% / 0.75 / −33.7% |

This matches the published record. Trend following shines when there are crashes (the 2000s) and lags in a calm bull market (the 2010s).

### B5. Calendar years

The full table for every strategy and every year from 2004 to 2026 is in `research/study3_output.txt`.

| Year | A | BH-DIV | SPY |
|---|---|---|---|
| 2008 | −4.2% | −19.0% | −36.9% |
| 2009 | +13.7% | +24.2% | +26.4% |
| 2013 | +5.4% | +0.4% | +32.3% |
| 2022 | −4.4% | −14.6% | −18.2% |
| 2023 | +1.4% | +12.3% | +26.2% |
| 2025 | +21.0% | +24.9% | +17.7% |

- **Rule A's losing years** (USD): 2008, 2015, 2018 and 2022. None was worse than −4.4%.
- **The cost:** it badly lags the rebound years after a crash, such as 2009 and 2023, because it re-enters late.

### B6. Walk-forward selection (§17.1)

**Method:** each January, switch to whichever of the six strategies had the best previous 5 years.

**Result:** from 2010, Sharpe 0.52, against 0.54 for E and 0.66 for BH-DIV. Chasing the recent best variant added nothing, which agrees with the overfitting test.

### B7. Where the profit came from

- **Rule A's net profit by asset class:**
  - US shares 33%
  - real assets 31%
  - international shares 18%
  - bonds 10%
  - cash interest 9%
- **Largest single fund:** QQQ, at 15%.
- **No single fund came close to the 50% limit** for any strategy. The result is genuinely diversified, not one lucky bet.

## Part C: validation report

**Pre-registered pass lines (§19).** A strategy is VALIDATED only if it passes all 8.

| Test | A | B3 | B6 | B12 | C | D | E |
|---|---|---|---|---|---|---|---|
| 1. Return beats cash, significant after Holm correction | ✅ p=0.005 | ✅ | ✅ p=0.008 | ✅ p=0.004 | ✅ | ✅ | ✅ |
| 2. Sharpe ≥ BH-DIV and max DD ≤ 0.75× BH-DIV | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 3. Holdout Sharpe > 0 and DD ≤ BH-DIV's | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4. Beats 95% of random-timing placebos | ✅ 98.6% | ❌ 85% | ✅ 95.2% | ✅ 96.5% | ❌ 70% | ❌ 93% | ❌ 90% |
| 5. Deflated Sharpe ≥ 0.95 **and** family PBO ≤ 0.50 | ❌ (DSR 0.995, PBO 0.54) | ❌ | ❌ (0.991, 0.54) | ❌ (0.992, 0.54) | ❌ | ❌ | ❌ |
| 6. Positive in at least 2 of 3 sub-periods | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 7. Sharpe > 0 at stress costs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8. No fund over 50% of profit | ✅ 15% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Verdict** | **PROMISING** | FAILED | **PROMISING** | **PROMISING** | FAILED | FAILED | FAILED |

**Statistical detail (§18):**
- **Rule A:**
  - mean excess return over cash +0.36% a month, Newey-West t = 3.17. It clears the stricter Harvey-Liu-Zhu bar of t > 3, as does B12 (3.28).
  - Sharpe 95% interval [0.29, 1.05], against BH-DIV's [0.18, 1.09].
  - Sharpe minus BH-DIV's: 95% interval [−0.22, +0.30], p = 0.39. So there is **no evidence that it beats holding the funds on risk-adjusted return.**
- **Random timing:** across 1,000 shuffles, every strategy's drawdown was smaller than that of essentially all of the randomly timed versions. This means **the crash protection comes from the timing, not just from holding less.** The extra return per unit of risk was only borderline: 95–99th percentile for A, B6 and B12, below the line for the rest.
- **Overfitting:** each strategy's deflated Sharpe passed comfortably. The family PBO of 0.54 failed.
  - The 15 variants are close cousins, so which one tops a given half of history is close to a coin flip.
  - The honest reading is that **none of these variants can be trusted to beat the others**. The rules required this test as well, so the verdict stands.

**What PROMISING means (§19):** it is not built. It may be re-tested on more data later, but only under a new pre-registered protocol. Nothing in this study is re-run with different settings.

## Part D: diversification and regimes (§20)

**Correlations:**
- Average correlation between the 13 funds was 0.36 over all months and 0.34 in SPY's worst 10% of months. Diversification held up in stress overall.
- Treasuries (IEF, TLT) stayed slightly negatively correlated with shares.
- **Real estate (VNQ), small caps (IWM), commodities (DBC) and inflation-linked bonds (TIP) moved more closely with SPY in bad months.** For TIP, the correlation rose from 0.31 to 0.63.

**Correlation and beta to SPY in its worst 10% of months:**
- Rule A: −0.02 correlation, beta −0.01. It is effectively uncorrelated with the stock market exactly when it matters.
- BH-DIV: 0.82 correlation, beta 1.01.
- D and E: 0.36 and 0.30. Volatility sizing kept them more exposed.

**Crisis windows** (return over the window, USD):

| Crisis | A | B12 | E | BH-DIV | SPY |
|---|---|---|---|---|---|
| GFC 2007–09 | −1.9% | −0.3% | +0.7% | −22.0% | −46.0% |
| Euro crisis 2011 | −6.2% | −6.3% | +0.1% | −3.1% | −7.1% |
| China/oil 2015–16 | −4.0% | −2.5% | −7.4% | −4.4% | −7.0% |
| Q4 2018 | −3.2% | −5.2% | −8.9% | −5.9% | −13.5% |
| COVID 2020 | −3.2% | −6.6% | −4.3% | −12.4% | −19.4% |
| 2022 inflation bear | −4.2% | −5.4% | −12.3% | −18.4% | −17.7% |
| 2025 tariff shock | +0.9% | +0.6% | +0.7% | +0.2% | −7.6% |

**Regimes:**

| Regime | Months | Rule A | BH-DIV | SPY |
|---|---|---|---|---|
| NBER recession | 20 | −0.25%/month | −0.75% | −1.88% |
| Inflation above 4% | 43 | +0.05%/month | −0.25% | −0.28% |
| SPY 12-month return negative ("bear") | 39 | +0.14%/month | +0.66% | — |

- In recessions, trend following lost much less.
- Above 4% inflation, it was roughly flat while everything else lost.
- In bear-market months it did **worse** than holding. Those months include sharp rebounds, such as spring 2009, that trend following misses because it is still in cash.

## Part E: the £30-a-day question (§23)

**Assumptions:**
- £30 per trading day is about £7,560 a year, taken as **£630 a month, rising 2.5% a year**.
- 10,000 simulated 20-year futures, built by resampling real historical monthly returns in pounds, after costs.
- In the tables, "runs out" means the chance the pot hits zero within 20 years.

**Inside an ISA (no UK tax):**

| Starting pot | Rule A runs out | BH-DIV runs out | 60/40 runs out | SPY runs out |
|---|---|---|---|---|
| £50,000 | 100% | 100% | 100% | 93% |
| £100,000 | 44% | 15% | 11% | 6% |
| £150,000 | 1% | 0% | 0% | 0% |
| £250,000 | 0% | 0% | 0% | 0% |

**In a general account (capital gains tax approximated):**

| Starting pot | Rule A, basic-rate taxpayer | Rule A, higher-rate taxpayer | BH-DIV, basic | BH-DIV, higher |
|---|---|---|---|---|
| £100,000 | 60% | 66% | 25% | 31% |
| £150,000 | 1% | 1% | 0% | 0% |

**Losing years and worst year, from history in pounds:**

| | Rule A | BH-DIV | SPY |
|---|---|---|---|
| Losing calendar years | 4 of 22 | 3 of 22 | 2 of 22 |
| Worst year | −4.0% (2023) | −4.4% (2022) | −14.4% (2008) |
| Worst year on £150k | about −£6,000 | about −£6,500 | about −£21,600 |

**What this means:**
- **About £150,000 is needed for £30 a day.** Below about £100,000, every approach tested here runs out within 20 years more often than not.
  - This is higher than the £62.5k in `research/REPORT.md`. That earlier figure assumed a steady 12% a year with no bad years, no withdrawals during losses and no inflation.
  - This one includes all of those, which is why the honest number is bigger.
- **Trend following does not lower that number.** It earns less, so it needs a bit more capital. What it buys is smaller drops in dollar terms, and in pounds even that benefit was mostly gone.
- **The ISA limit:** you can only add £20,000 a year, so getting £150k into an ISA takes about 7–8 years of deposits.
- **Tax and fund type:** the general-account figures understate tax for higher-rate payers, because income isn't taxed separately here. US-listed ETFs are usually "non-reporting" funds for UK tax, so a UK investor would use the London-listed UCITS versions instead.

## Part F: future plan

1. **Build nothing now.** No paper-trading engine, dashboard or five-worker system: no strategy is VALIDATED (§25).
2. **Keep the retirements.**
   - PR #21, which retires the scalper and swing breakout, is ready to merge.
   - PR #19, the QQQ trend worker, stays unmerged.
   - PR #20 and this study are the research record.
3. **Next study options.** Each needs its own pre-registered protocol committed before any test.
   - **Study 4, recommended: a UK investor version of trend following.**
     - The same simple rules (A, B6, B12 only, fixed now: no new variants), judged **in pounds** as the main currency.
     - Compared using London-listed UCITS funds, including pound-hedged versions where they exist.
     - Part B3 shows the currency is the deciding factor for you, so this is the question that actually matters.
     - It also tests on a fresh, smaller set of variants, which is what failed here.
   - **Study 5: cross-sectional momentum** (ranking funds against each other), as the master instruction says, after Study 4.
   - **Separately: a forward-only Discord signal tracker.** This would score every call the group posts, using the price at the minute it was posted, for 6–8 weeks. It never places trades.
4. **If something is validated later:** the next step is a written design for a forward-only paper test of that one strategy, with its own review lines and your approval, before any code.
5. **What doesn't change:** no real money, no live trading, no strategy reactivated without a passing pre-registered test.

## Part G: limitations

1. **Survivorship and selection bias:** the 13 funds are today's well-known survivors. This flatters every strategy and benchmark alike, so the comparison between them is fairer than any absolute number.
2. **About 22 years of data,** with only two big equity bear markets (2008 and 2022) plus COVID. All the confidence intervals are wide.
3. **Publication overlap:** the rules were published using data that overlaps 2004–2017. The 2018–2026 holdout is the clean test, and A, B6 and B12 held up there.
4. **US-listed funds:** UK retail investors generally can't buy them (PRIIPs/KID rules, being replaced by the FCA's Consumer Composite Investments regime). UCITS equivalents have slightly different fees and tracking.
5. **Prices:** Yahoo adjusted opens, with slippage allowed for. Cross-checked against Alpaca SIP from 2016: all 13 funds matched within 0.02 percentage points a month.
6. **SLV:** there was one real −28.5% day, on 2026-01-30, during the silver crash. Alpaca's data confirms it.
7. **Cash:** the cash return assumes T-bill yields less 0.10% a year. GBP Sharpe ratios are measured over USD T-bills, so treat them as indicative.
8. **Tax:** the tax model is a simplification and is not tax advice.
9. **No guarantee:** past results don't guarantee future ones. Trend following had a famously poor 2010s, visible above.
