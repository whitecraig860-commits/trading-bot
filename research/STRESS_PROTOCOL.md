# Study 11: stress tests for the best picking rule, and a "his clone" bot. Pre-registered protocol

**Status:** committed on 2026-11-18, after Study 10's results and before any of the tests below were run. Backtest only.

**Why:** Study 10's ALL rule (EMA9/EMA20 agree, strong candle, before 12:00, not a weak cross) cut the loss from −$38 to
−$12 a day. But it keeps only 10% of the signals, and its loss per trade (about −$3.40) is close to the live bot's
(about −$3.96), so most of the gain may come simply from trading less. The user asked for harder, varied tests, and for a
bot as close to his as the data allows.

## Rules tested

| Code | Entries | Exits |
|---|---|---|
| BASE | the live bot's signals | +2.5% / −6% / 10 min |
| ALL | Study 10 ALL | +2.5% / −6% / 10 min |
| CLONE | Study 10 ALL | his exits from his 83 posted trades: +3.5% target (his median win), −10% stop (his losers were −10% to −14%), 6-minute limit (his winners were all sold within 5½ minutes) |

All with "stop after 2 losses in a row", signals from 09:45, nearest strike, real option bars, Mar 2024 to Oct 2026.

## Tests (each rule against BASE unless stated)

| # | Test | Passes when |
|---|---|---|
| T1 | Year by year (2024, 2025, 2026) | better than BASE in every year |
| T2 | Placebo: 20 runs that keep a random set of signals of the same size as the rule | better per day than at least 19 of the 20 |
| T3 | Higher costs: 3 and 5 cents a side | better than BASE at both |
| T4 | Late fill: every entry one minute later | better than BASE |
| T5 | Settings wobbled (ALL entries): EMA 8/21; candle 50% and 70%; cut-off 11:30 and 12:30; weak cross $0.05 and $0.15 | every variant better than BASE |
| T6 | 1,000 resamples of the days in blocks of 5 | better than BASE in at least 95% |
| T7 | Calm vs busy days (split at the median daily range); up vs down days | better than BASE in all four groups |

**Robust** = passes all seven. **Profitable** = positive per day with t ≥ 2.0 at 1 cent, positive at 2 cents, and positive
in every year. Only a robust rule is considered for the main bot, and only with the user's say-so. Any rule passing T2 and
T6 runs as a comparison paper bot.

## Amendments

(none)
