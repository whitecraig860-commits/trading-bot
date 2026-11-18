# Study 10: does picking signals the way he does make the bot profitable? Pre-registered protocol

**Status:** committed on 2026-11-18, after the descriptive scans of his entries (`research/his_scans_output.txt`) and
before any history test of these rules. Backtest only; no orders.

**Where the rules come from (his 4 days only, not the history data):** among our signals, the ones he took had short-term
momentum already pointing his way: EMA9 on the right side of EMA20 (median +$0.18 vs −$0.04 for the ones he skipped),
a bigger candle in his direction ($0.50 vs $0.30), and they came earlier in the day (median 68 vs 190 minutes after the
open). Of his entries that were not our signals, 69% came on a strong candle in his direction.

## Rules (Study 5 engine; live exits +2.5% / −6% / 10 min; stop after 2 losses; signals from 09:45)

| Code | Take a signal only when |
|---|---|
| BASE | always (the live bot) |
| M1 | EMA9 is above EMA20 for a call, below for a put, on the signal bar |
| M2 | the signal bar is a strong candle in the trade's direction (body more than 60% of its high-low range) |
| M3 | the signal comes before 12:00 New York time |
| M4 | M1 and M2 |
| ALL | M1, M2, M3, and not a weak cross (Study 9's F3) |

Data, costs and decision lines A and B exactly as Studies 8 and 9 (670 days, real option bars, 1 and 2 cents a side,
holdout from 2026-01-01). Any rule passing A becomes a new comparison paper bot; existing bots are not changed.

## Amendments

(none)
