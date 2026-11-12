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
4. **For £30 a day, the trend rule needs more money, not less.**
   - Taking £630 a month, rising with inflation, out of an ISA:
     - starting from **£100,000**, A-H ran out in 61% of simulated futures; unhedged holding ran out in 14%, and 60/40 in 10%;
     - starting from **£150,000**, every approach was 0–2%.

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

## 5. £30 a day (ISA, £630 a month rising 2.5% a year, 20 years, 10,000 simulated futures)

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

**The rule:** A-H is VALIDATED, so the protocol allows one next step: a **written design** for a forward-only **paper** test with real London-listed funds. It needs its own pre-registered review lines and **your approval before any code is written.** No engine or dashboard is built yet.

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
