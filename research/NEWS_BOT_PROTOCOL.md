# Study 15: news bot (free word scorer). Pre-registered 27 Nov 2026, before any code was run on real data

**Owner's request.** A bot that reads the news (company, Fed, inflation, tariffs, Trump…), judges whether it is good or
bad for QQQ, and trades on that. Free word scoring, not paid AI.

**Scorer (`tracker/newsscore.py`, fixed now).**
- **Word lists:** a curated finance word list built on the most common positive and negative words in the
  Loughran–McDonald finance dictionary, plus market words. Good examples: beats, record, surge, upgrade, rate cut,
  cools. Bad examples: misses, plunge, downgrade, tariff, sanctions, rate hike, probe, layoffs.
- **Negation:** "not", "no" or "fails to" within 3 words flips a word's sign.
- **Score:** headline score = (good − bad) / √(words matched), capped at ±3.
- **Importance:**
  - 3 for Fed / Powell / CPI / inflation / jobs report / tariffs / Trump / China, or for news on Nvidia, Apple,
    Microsoft, Amazon, Meta, Alphabet, Tesla or Broadcom;
  - 2 for QQQ / Nasdaq / market-wide headlines;
  - 1 otherwise.

**Signal.**
- Every minute 09:45–15:30 NY, news pressure = sum of (score × importance) over headlines from the last 30 minutes,
  halving every 15 minutes.
- A signal fires when pressure first reaches **+4 (call)** or **−4 (put)**, at most once per side per 30 minutes.
- **The chart must agree** (the shared trend, `tracker/context.py`: Bullish for calls, Bearish for puts); otherwise no trade.

**Trade.**
- 1 contract, next expiry, strike nearest the share price, bought at the ask and sold at the bid.
- Exit at **+10% / −10% / 30 minutes**, all fixed now.
- Stop after 2 losses in a row.
- The live bot also stops for the day at **+£50** (owner's daily target) or **−$100**.

**Test** (`research/news_study.py`).
- **Data:** Alpaca historical news (free) for QQQ, SPY and the 8 biggest holdings, and real option bars, Mar 2024 –
  Oct 2026, with costs of 1 and 5 cents a side.
- **Placebos:**
  - (a) the same number of trades at random minutes on the trend's side, 20 runs;
  - (b) the trend alone at the same minutes, ignoring the news.
- **Pass mark** (all needed):
  - positive at 5 cents with Newey–West t ≥ 2;
  - positive in each year, and in 2026 on its own;
  - beats at least 19 of 20 placebos (a);
  - beats placebo (b).

**Running it.** The live bot runs on paper from the next session whatever the result, because the owner asked for it.
It is labelled "untested" or "failed test" on the page until the result is in.
