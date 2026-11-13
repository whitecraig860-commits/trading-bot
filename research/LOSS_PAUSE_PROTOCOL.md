# Study 7: does pausing after a loss help the live QQQ paper bot? Pre-registered protocol

**Status:** committed on 2026-11-13, before any code for this study was written or any result seen. Backtest only; no orders.

**Why:** on 13 Nov 2026 the live paper bot (the Study 5 rules) lost two strings of 4 to 5 trades in a row in a flat afternoon, flipping between calls and puts every minute. The rules below were chosen after seeing that one day. That is why they are tested here on 2.7 years of history, not judged on that day.

## Rules compared (all on the Study 5 engine, base settings: +2.5% target, −6% stop, 10-minute limit, all three triggers, conservative ordering)

| Code | Rule |
|---|---|
| BASE | as the live bot runs now |
| W10 | after any losing trade, no new trade for 10 minutes |
| W20 | after any losing trade, no new trade for 20 minutes |
| S2 | stop for the day after 2 losing trades in a row |
| S3 | stop for the day after 3 losing trades in a row |

## Data and costs

- As Study 5: 2024-03-01 to 2026-10-31, real option trade bars.
- Costs: 1 cent per share per side (base) and 2 cents. Holdout from 2026-01-01.

## Adoption line (each rule, judged on the difference from BASE, day by day)

A rule goes into the live bot only if **all** hold:
1. Daily profit improves on BASE over the full period, with a paired Newey-West t ≥ 2.0 at 1 cent.
2. It also improves on BASE in the 2026 holdout.
3. It also improves on BASE at 2 cents.

If more than one rule passes, the one with the highest full-period t is used. If none passes, the live bot is not changed.

**This does not make the bot "validated"** (Study 5 still fails). It only decides whether the pause is an improvement worth adding to the paper bot.

## Amendments

(none)
