# Study 13: three different kinds of entry. Pre-registered protocol

**Status:** committed on 2026-11-19, before any code for this study was written or any result seen. No orders.

**Why:** Study 12 showed the one-minute VWAP / 50 EMA cross is a coin flip (QQQ moved the signal's way 49% of the time), so
no exit, brake or filter can make it profitable. Only a different entry can. The user asked to test them all, add them as
bots, and analyse every bot every day.

## Entries

| Code | Entry | Exits | Per day |
|---|---|---|---|
| FIVE | the same VWAP / 50 EMA crosses, on **5-minute** candles (5-minute VWAP and 50 EMA), 09:45-15:30 | +5% target, −10% stop, 30-minute limit | many; stop after 2 losses |
| OPEN30 | the **opening move**: at 10:00, if QQQ is up 0.25% or more from the 09:30 open, buy a call; down 0.25% or more, a put | +10% target, −10% stop, 60-minute limit | one |
| ONEADAY | the **one-a-day breakout** of Study 6 (the shares bot's signal), traded with the at-the-money option expiring the next trading day (Study 6 flagged this choice as better but untested) | the shares bot's exit (safety stop, trail, 15:44) | at most one |

All: one contract, next-day expiry, real option bars, Mar 2024 to Oct 2026, 1 cent a side plus fees (base).

## Tests for each entry

| # | Test |
|---|---|
| P | Does the entry predict anything? QQQ's move after the signal (5, 15, 30, 60 minutes) in its direction: share right and average |
| H | History per day at 1, 2, 3 and 5 cents a side; own Newey-West t |
| T1 | Every year (2024, 2025, 2026) |
| T2 | Placebo, 20 runs: FIVE and OPEN30 against random entry times (same number per day, random side, same exits); ONEADAY against the same entry times with a random side |
| T4 | FIVE and OPEN30: entries one minute late |
| T6 | 1,000 block resamples of the days: share with a positive result |
| T7 | Calm / busy / up / down days |
| R | FIVE and OPEN30: replay of the real paper-bot code on our own recorded live prices (17-19 Nov) |

**Profitable** = positive per day with t ≥ 2.0 at 1 cent, positive at 2 cents, positive in every year, beats at least 19
of 20 placebos, and positive in at least 95% of resamples. Nothing that falls short is called profitable.

All three run as comparison paper bots whatever the result (the user's request), labelled with the result.

## Amendments

(none)
