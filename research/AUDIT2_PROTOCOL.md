# Audit part 2: pre-registered tests (committed before any code or result)

Date: 2026-11-20. Follows the user's follow-up instructions. Measures; changes no bot.

## 1. Can a market-condition filter rescue the fast bots' entry? (fixed in advance, no tuning)

Three filters, each known **before** the signal, each with a reason:

| Code | Trade the main bot's signals only when | Reason |
|---|---|---|
| R1 | the last 20 days' QQQ volatility is in the top third of the previous 250 days | moves are bigger, so a small edge has more room than the spread |
| R2 | the first 15 minutes' range is at least 1.5 times its 20-day average | a wide opening range signals an active day |
| R3 | the last 20 days trended (|return| / (vol x sqrt 20) > 1), and only in that trend's direction | crosses in the direction of a clear trend are more likely to continue |

Judged at a realistic cost (5 cents a side) and at 1 cent. A filter "rescues" the entry only if, on 2024-2025 **and** separately
on 2026, the share of signals where QQQ moved the right way after 10 minutes is above 52% **and** the per-trade result at
5 cents is positive, with t ≥ 2.4 (Bonferroni for three filters). Otherwise the fast bots are retired permanently.

## 2. One-a-day options: forensic tests

Top-5 trades in detail; result without them; top-5 cut by 25 / 50 / 75%; 5,000 runs of "the next 20 trades" drawn only from
unfavourable days (calm, trending, low-volatility); the 11-loss streak in detail; the distribution of the longest losing streak
in a year (5,000 runs); calm / volatile / trending / sideways; costs at the measured paper level; and a multiple-testing check:
about 30 strategy variants were tested in Studies 5-13, so the Bonferroni line is t ≈ 3.0.

## 3. Shares one-a-day 2016-2026: forensic tests

Trade-level features compared between losing years (2016, 2017, 2020), flat years (2018, 2019, 2021) and winning years
(2022-2026), and between winning and losing trades: volatility, trend strength, gap, intraday range, relative volume, entry
time, distance from the previous day's high/low, market direction, duration, exit reason, and return as a % of price
(dollar results on 100 shares are not comparable across years because QQQ's price rose about six-fold).

Ex-ante test: one pre-entry measure with a stated reason (the last 20 days' average intraday range as % of price; a breakout
needs room to move), threshold fixed as the median of the **2016-2021** trades only, then tested on 2022-2026; and the reverse
(threshold from 2022-2026, tested on 2016-2021). A filter is only proposed if it helps in **both** directions.

## 4. Stress tests for both promising bots (each changes one thing)

Entries 1 and 2 minutes late; 10% of orders rejected; a one-hour outage every day (blind, then acts at the first bar after);
settings ±20% (range buffer 0.3 ATR, trail 4 ATR, stop 10 ATR, noise band); costs 2, 5, 10 cents; volatile days only;
calm days only; longest losing streak; position size.

## 5. £1,000 account

Affordable size, risk per trade, daily and weekly loss, total drawdown, survivable losing streak, costs vs account, minimum
sensible capital, for each bot, from the trade lists. Option contract multiplier 100; minimum one contract.
