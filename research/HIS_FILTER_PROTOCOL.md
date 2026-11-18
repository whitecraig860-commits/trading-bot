# Study 9: his skip rule, an earlier start and an in-the-money strike. Pre-registered protocol

**Status:** committed on 2026-11-18, before any code for this study was written or any result seen. Backtest only; no orders.

**Why:** on 18 Nov 2026 all of his posted entries lined up with signals our bots also produced, but he took about 16 of
the roughly 50 signals and skipped the rest; his first trade came at 09:34 (ours start at 09:45); and at 10:26 he bought the
658 call (just in the money) where we bought the 659 (nearest) and lost. Re-priced at the real bid and ask we recorded,
his 42 matched trades on 17-18 Nov still made money (+$963 and +$2,716), so slippage does not explain the gap.

## Stage 1: what separates the signals he took from the ones he skipped (his trades only)

- Days: the four days of his trades in `state/discord_trades.csv` (11, 12, 17, 18 Nov 2026). QQQ one-minute bars from Alpaca.
- Our signals on those days are computed from 09:31 (VWAP and 50 EMA crosses; the 15-minute range break from 09:45).
- A signal counts as **taken** if any of his accounts bought the same side within 60 seconds after the signal's bar closed.
- Candidate skip rules, fixed now:

| Code | Skip a signal when |
|---|---|
| F1 | an opposite-side signal came in the previous 2 minutes (a flip-flop) |
| F2 | any other signal came in the previous 2 minutes |
| F3 | the close is less than $0.10 beyond the line it crossed (a weak cross) |
| F4 | it is against the day's direction (call below the 09:30 open, put above it) |
| F5 | the previous signal was less than 5 minutes ago |

- **Choice, fixed now:** for each rule, keep = share of his taken signals the rule keeps, and skip-power = share of the signals
  he skipped that the rule also skips. The rule with the highest keep + skip-power − 1 is chosen as **FILTER**, provided it
  keeps at least 70% of his taken signals. If none keeps 70%, there is no FILTER. Stage 1 uses no option prices and no results.

## Stage 2: history test (Study 5 engine, Mar 2024 to Oct 2026, real option bars, holdout from 2026-01-01)

All rules use the live bot's exits (+2.5% target, −6% stop, 10-minute limit) and "stop after 2 losses in a row".

| Code | Rule |
|---|---|
| BASE | the live bot (signals from 09:45, nearest strike) |
| EARLY | VWAP and 50 EMA signals from 09:31 instead of 09:45 |
| ITM | strike one step in the money: calls at the strike just below the price, puts just above |
| FILTER | BASE with the Stage 1 skip rule (if there is one) |
| COMBO | EARLY + ITM + FILTER |

Costs: 1 cent a side (base) and 2 cents; $0.03 fee per contract a side. Decision lines exactly as Study 8:
**A** (better than the live bot: paired Newey-West t ≥ 2.0 at 1 cent, better in the holdout, better at 2 cents) and
**B** (profitable on its own: t ≥ 2.0, positive in the holdout and at 2 cents).

Any rule passing A is added as a new comparison paper bot; existing bots are not changed (the user's standing request).

## Amendments

(none)
