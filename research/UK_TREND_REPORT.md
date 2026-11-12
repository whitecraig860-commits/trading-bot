# Study 4: trend following for a UK investor, in pounds. Results

**Run:** 2026-11-12 on GitHub Actions, on data to 2026-10-30. Full output: `research/study4_output.txt`. Code: `research/uk_trend_study.py` (it reuses Study 3's engine).

**Rules:** `research/UK_TREND_PROTOCOL.md`, committed (f047a21) before any code was written or data looked at. There were no amendments. Nothing has been traded.

---

## 1. Plain-English summary

1. **One configuration passed all 8 pre-registered tests: rule A with pound-hedged funds (A-H).**
   - Rule A is the 10-month moving average: hold each fund while its price is above its average of the last 10 month-ends, otherwise cash.
   - Over 22 years in pounds it returned **6.5% a year** after UK costs, with a worst fall of **13.5%**.
   - Holding the same hedged funds returned 8.4% a year, with a worst fall of **34.5%**.
   - B6-H and B12-H passed 7 of 8 (PROMISING). All three unhedged versions FAILED.
2. **There are three catches, and they matter.**
   - **It only just passed one test.** It beat 95.8% of the random-timing versions; the line was 95%.
   - **It would have failed under Study 3's rules.** Study 3 also required the family overfitting score (PBO) to be at most 0.50. After Study 3, I made PBO information-only, and said so in the protocol before seeing this data (§8). Here PBO was **0.84**. A-H was judged by the rules as written for this study, but you should know this.
   - **The hedged version is almost Study 3's rule A in dollars, re-measured.** It passes mainly because holding hedged funds is a weak comparison.
3. **The most useful finding for you: the simplest option beat everything.**
   - Simply holding the 13 funds **unhedged** in pounds returned **9.6% a year**, with a Sharpe of 0.76 and a worst fall of **18.8%**.
   - That is more return and a better risk-adjusted return than A-H, with only a slightly bigger worst fall.
   - Without hedging, the pound's habit of falling in a crisis did most of the protecting for free.
   - A plain 60% shares / 40% bonds mix, unhedged, did about as well: 9.7% a year, worst fall 18.1%.
   - **That cushion is a historical pattern, not a guarantee.**
4. **The £30-a-day figures are context only.**
   - They are now in §5 and are not part of any verdict.
   - They are simulations of past patterns, not a promise of future income.

**Read the Addendum (§8).** Under the stricter overfitting standard from Study 3, **no configuration is VALIDATED**: A-H becomes PROMISING.

## 2. Comparison (net of UK costs, in GBP, May 2004 to October 2026)

| | CAGR | Volatility | Sharpe (over UK cash) | Max drawdown | Worst 12 months |
|---|---|---|---|---|---|
| **A-H** ✅ VALIDATED | 6.5% | 6.5% | 0.67 | −13.5% | −9.3% |
| B6-H (PROMISING) | 6.2% | 6.4% | 0.64 | −12.2% | −6.0% |
| B12-H (PROMISING) | 6.5% | 6.8% | 0.65 | −14.0% | −7.3% |
| A-U (FAILED) | 7.0% | 7.3% | 0.65 | −13.4% | −7.4% |
| B6-U (FAILED) | 6.3% | 6.9% | 0.60 | −13.0% | −6.3% |
| B12-U (FAILED) | 6.9% | 6.9% | 0.70 | −11.4% | −3.4% |
| Hold 13 funds, hedged (BH-DIV-H) | 8.4% | 10.7% | 0.61 | −34.5% | −26.0% |
| **Hold 13 funds, unhedged (BH-DIV-U)** | **9.6%** | 9.8% | **0.76** | −18.8% | −7.4% |
| 60/40 unhedged | 9.7% | 9.4% | 0.79 | −18.1% | −6.7% |
| 60/40 hedged | 8.5% | 8.9% | 0.71 | −29.8% | −23.1% |
| S&P 500 unhedged | 12.4% | 13.2% | 0.79 | −35.0% | −21.3% |
| S&P 500 hedged | 11.3% | 14.6% | 0.66 | −52.9% | −41.2% |
| UK cash | 2.2% | 0.6% | — | 0% | 0% |

**Holdout, 2018 onward (after the rules were published):**

| | Sharpe | Max drawdown |
|---|---|---|
| A-H | 0.63 | −9.0% |
| BH-DIV-H | 0.54 | −22.4% |
| A-U | 0.74 | −7.2% |
| BH-DIV-U | 0.75 | −15.3% |

**Hedging removes the pound's crisis cushion.**

| | 2008 | GFC window |
|---|---|---|
| Unhedged diversified holding | +10.0% | +11.4% |
| Hedged diversified holding | −15.6% | −17.7% |
| A-H | −4.1% | −0.7% |

That is why trend following only adds clear value once the funds are hedged.

## 3. Validation

| Test (§9) | A-U | B6-U | B12-U | **A-H** | B6-H | B12-H |
|---|---|---|---|---|---|---|
| 1. Significant vs UK cash (Holm) | ✅ | ✅ | ✅ | ✅ p=0.004 | ✅ | ✅ |
| 2. Sharpe ≥ own benchmark and DD ≤ 0.75× | ❌ | ❌ | ❌ | ✅ 0.67 vs 0.61; −13.5% vs line −25.9% | ✅ | ✅ |
| 3. Holdout Sharpe > 0 and DD ≤ benchmark | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4. ≥ 95th percentile of random timing | ❌ 40% | ❌ 22% | ❌ 56% | ✅ **95.8%** | ❌ 91.6% | ❌ 90.7% |
| 5. Deflated Sharpe (21 trials) ≥ 0.95 | ✅ | ✅ | ✅ | ✅ 0.998 | ✅ | ✅ |
| 6. Positive in at least 2 of 3 sub-periods | ✅ | ✅ | ✅ | ✅ +9.7% / +4.4% / +6.4% | ✅ | ✅ |
| 7. Sharpe > 0 at stress costs | ✅ | ✅ | ✅ | ✅ 0.58 | ✅ | ✅ |
| 8. No fund over 50% of profit | ✅ | ✅ | ✅ | ✅ 14% | ✅ | ✅ |
| **Verdict** | FAILED | FAILED | FAILED | **VALIDATED** | PROMISING | PROMISING |

**Other numbers:**
- **A-H's Sharpe minus its benchmark's:** 95% interval [−0.20, +0.29], p = 0.35. Its risk-adjusted advantage over holding hedged funds is **not** statistically clear. What is clear is the much smaller worst fall.
- **The unhedged rules** had Sharpe ratios at or below the median of their random-timing versions. Without hedging, being in or out at the right time added nothing beyond holding less.
- **PBO across the 6 configurations: 0.84.** This is information only under §8. Which configuration comes out "best" is largely luck, so A-H being the winner, rather than B6-H or B12-H, should not be over-read.

## 4. Checking the model against real London-listed funds (§10.3)

| Real fund | Compared with | Months | Correlation | Typical monthly gap | Average yearly gap |
|---|---|---|---|---|---|
| VUSA.L (S&P 500, GBP) | modelled unhedged S&P 500 | 173 | 0.963 | 0.53 pp | −0.35% a year |
| IGUS.L (S&P 500, GBP-hedged) | modelled hedged S&P 500 | 193 | 0.969 | 0.57 pp | **−1.33% a year** |
| SGLN.L (gold, GBP) | modelled unhedged gold | 186 | 0.853 | 0.38 pp | −2.28% a year |
| EQQQ.L (Nasdaq-100) | modelled unhedged QQQ | 209 | 0.62 | — | Yahoo data broken (4 bad months, pence/pound mix-ups); unusable |

**What this means:**
- **The model fits real funds month by month** (correlation 0.96–0.97 for the S&P 500 funds).
- **But it is optimistic.** The real hedged S&P 500 fund did about **1.3% a year worse** than the model, likely because of fees, US dividend withholding tax and real hedging costs.
- **Expect real-world hedged results to be lower than shown,** perhaps by 0.5–1% a year for A-H, since it is invested about 70% of the time.
- **Data note:** the FRED UK interest rate series stops about 9 months before the end of the data, so its last value is carried forward. This affects the hedge carry slightly in 2026.

## 5. Context only: £30 a day (ISA, £630 a month rising 2.5% a year, 20 years, 10,000 simulated futures)

**This section is not part of the strategy test and plays no part in any verdict.**
- It resamples past returns, so it assumes the future looks like 2004–2026 shuffled around. That is not a reliable promise of future income.
- It also uses the modelled fund returns, which §4 shows to be optimistic.


| Starting pot | A-H runs out | Hold unhedged | Hold hedged | 60/40 unhedged |
|---|---|---|---|---|
| £50,000 | 100% | 100% | 100% | 100% |
| £100,000 | 61% | **14%** | 31% | **10%** |
| £150,000 | 1% | 0% | 2% | 0% |
| £250,000 | 0% | 0% | 0% | 0% |

| Worst calendar year | A-H | Unhedged holding | Hedged holding |
|---|---|---|---|
| Worst year | −4.1% | −4.5% | −15.6% |
| On £150k | about −£6,100 | about −£6,700 | about −£23,400 |

## 6. What happens now (§9)

**The rule:** A-H is VALIDATED under Study 4's rules, though only PROMISING under the stricter Study 3 standard (see §8). The protocol allows one next step: a **written design** for a forward-only **paper** test with real London-listed funds. It needs its own pre-registered review lines and **your approval before any code is written.** No engine or dashboard is built yet.

**My recommendation:**
1. **Your realistic main option is unhedged diversified holding (or 60/40) in an ISA**, not trend following. It earned more and made the £30-a-day target easier on the same money. Its downside is that it relies on the pound falling in a crisis, which isn't guaranteed.
2. **If you want crash protection that doesn't rely on the pound,** A-H is the one candidate that passed. It's worth a paper test **alongside** unhedged holding as the comparison.
   - It only trades once a month, so a paper test mainly checks the mechanics: real fund prices, fills, and which hedged UCITS funds exist for each of the 13 slots. Some may not exist.
   - Proving it works going forward would take years, not weeks.
3. **Nothing changes about money:** no real trades. Retired strategies stay retired.

## 7. Limitations

Everything in S3 §24 and protocol §12 applies, plus:

1. **The pass hinged on a protocol change.** A-H would have failed Study 3's PBO line. That change was made after seeing Study 3 and is disclosed in the protocol.
2. **The model is optimistic,** by about 1.3% a year for hedged funds (§4).
3. **The unhedged result rests on the pound tending to fall in crises:** in 2008, 2016 and 2022. That pattern can change.
4. **Data:** EQQQ.L's Yahoo history is unusable, and the UK rate data stops about 9 months early.

---

## 8. Addendum (2026-11-12, after review): the protocol change, the narrow pass, and the stricter standard

This addendum was written after the results, in response to review. It changes no pre-registered rule and no number above. It sets out exactly what was changed between Studies 3 and 4, and what the verdicts would be under Study 3's stricter standard.

### 8.1 Exactly what was changed

| | Study 3, criterion 5 | Study 4, criterion 5 |
|---|---|---|
| Rule | Deflated Sharpe probability ≥ 0.95 **AND** family PBO ≤ 0.50 | Deflated Sharpe probability ≥ 0.95 **only** |
| Trials counted in the deflated Sharpe | 15 (Study 3's configurations) | **21** (Studies 3 and 4 combined) |
| PBO | a pass line | **reported for information only** |

- **The test dropped:** the Probability of Backtest Overfitting (Bailey, Borwein, López de Prado & Zhu 2017), calculated by combinatorially symmetric cross-validation over the family of configurations, with a pass line of ≤ 0.50.
- **When:** after Study 3's results were seen (PBO 0.54, failing all its strategies on that line). The change was written into `UK_TREND_PROTOCOL.md` §8 and committed (f047a21) before any Study 4 data was downloaded.
- **Why:**
  - PBO measures whether the configuration that ranks best in one half of history also ranks well in the other half.
  - When the configurations are close cousins, their ranking is close to a coin flip, so PBO can fail even when every configuration has a real edge. It measures the reliability of **choosing among** variants, not whether the **type** of strategy works.
  - To compensate, the deflated Sharpe was made stricter, from 15 to 21 trials.
- **Why this is still a real weakness:**
  - The change was made after seeing a failure, so it is exactly the kind of decision that can make a later "pass" look better than it is.
  - Study 4's PBO was 0.84, higher than Study 3's 0.54. That is strong evidence that which of the six configurations came out "best" is largely luck.

### 8.2 Verdicts under the stricter Study 3 standard

Applying PBO ≤ 0.50 as part of criterion 5 means every configuration fails criterion 5, because PBO = 0.84. All other results are unchanged.

| | Criteria passed (Study 4 rules) | Verdict (Study 4 rules) | Criteria passed (Study 3 standard) | Verdict (Study 3 standard) |
|---|---|---|---|---|
| **A-H** | 8/8 | VALIDATED | **7/8** (fails 5) | **PROMISING** |
| B6-H | 7/8 (fails 4) | PROMISING | 6/8 (fails 4, 5) | PROMISING |
| B12-H | 7/8 (fails 4) | PROMISING | 6/8 (fails 4, 5) | PROMISING |
| A-U | 6/8 (fails 2, 4) | FAILED | 5/8 | FAILED |
| B6-U | 6/8 (fails 2, 4) | FAILED | 5/8 | FAILED |
| B12-U | 6/8 (fails 2, 4) | FAILED | 5/8 | FAILED |

- **Under the stricter standard, nothing is VALIDATED in either study.**
- Study 4's pass of A-H depends on the protocol change.

### 8.3 The random-timing pass was narrow

- A-H's net Sharpe was 0.67. The 95th percentile of its 1,000 random-timing placebos was 0.66. The margin is **0.01 in Sharpe**.
- The estimated percentile was **95.8%**.
- With 1,000 placebos, the Monte-Carlo standard error of that estimate is about √(0.958 × 0.042 / 1000) ≈ **0.6 percentage points**. 95.8% is only about 1.3 standard errors above the 95% line.
- **A different random seed would put it below 95% roughly 1 time in 10.** No extra seeds were run, to avoid searching after the fact.
- B6-H and B12-H, which are nearly the same strategy, came in at 91.6% and 90.7%.
- **Conclusion:** the evidence that A-H's timing adds risk-adjusted return beyond holding less is **weak**. The evidence that it reduces drawdowns is much stronger: every configuration had a smaller drawdown than nearly all of its placebos (Study 3), and A-H's drawdown was 13.5% against 34.5% for holding.

### 8.4 The model-versus-real-fund gap is material

- The real GBP-hedged S&P 500 fund (IGUS.L) ran **1.33% a year** below the modelled hedged series.
- Over 22 years, a 1.3% yearly gap compounds to about **25% less final wealth** (0.987²² ≈ 0.75).
- Any next step must therefore use **real London-listed fund prices**, not the model. See the paper-test plan.

### 8.5 What this means

- Study 4 should be read as: **A-H is PROMISING, and its pass under Study 4's own rules is narrow and depends on a disclosed protocol change.**
- It does **not** justify building anything beyond a carefully limited, ledger-only paper test on real UK-listed funds. The purpose of that test is to find out whether the rule works in practice, not to make money.
