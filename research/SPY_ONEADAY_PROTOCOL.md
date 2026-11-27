# Study 16: the shares one-a-day rule on SPY. Pre-registered 27 Nov 2026

**Question.** The shares one-a-day rule is the only bot that has passed (QQQ, Study 6 and audit part 2). Does the same
rule, unchanged, work on SPY (the S&P 500 fund)?

**Rule.** Exactly `research/one_a_day_study.py` `run()`, shares column:
- opening-range break by 0.3 ATR, beyond VWAP and beyond the 14-day noise band;
- checked every 10 minutes 10:00–14:00;
- one trade a day, long or short;
- trail at 4 ATR giving back half, safety stop at 10 ATR, out at 15:44;
- 100 shares, $2 a round trip.

**Data.** SPY one-minute bars (SIP) from 2016-01 to 2026-10.

**Judged.**
- Mean per day > 0 with t ≥ 2 over 2022–2026, positive in at least 4 of those 5 years, and positive in 2026.
- 2016–2021 is reported separately, as it was for QQQ (where it was about zero).
- Placebo: random side on the same days, 20 runs; the rule must beat 19.

**If it passes** I propose a paper SPY shares bot, with your approval. **If it fails**, no bot.
