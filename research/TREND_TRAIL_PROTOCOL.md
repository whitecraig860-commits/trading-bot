# Study 8: wider stop, trailing exit and trend-only entries for the QQQ options bot. Pre-registered protocol

**Status:** committed on 2026-11-17, before any code for this study was written or any result seen. Backtest only; no orders.

**Why:** on 17 Nov 2026 the paper bot and his posted QQQ Trader bots bought at almost the same second (10:06, 11:02, 11:05, 11:13),
but ours sold two of those at our −6% stop within a minute, while he held through the dip and sold +3.6% to +6%. His two losing
trades that day were −12.3% and −13.6%, which suggests a stop near 12%. His winners ranged +2% to +7% (held 15 seconds to
13 minutes), which suggests a small trailing exit. The user also asked for trend-only entries. These settings were read off one
day, so they are tested on 2.7 years of history before anyone trusts them. A paper bot with all three (`TREND_TRAIL` in
`tracker/qqqbot.py`) runs alongside from 18 Nov for comparison; it does not replace anything.

## Rules compared (Study 5 engine and data; all include the live "stop after 2 losses in a row" rule)

| Code | Rule |
|---|---|
| BASE | the live bot: +2.5% target, −6% stop, 10-minute limit |
| WIDE | as BASE but −12% stop |
| TRAIL | on reaching +2.5% keep the trade; sell when the price falls 1.5% below its best since; 15-minute limit |
| TREND | as BASE, but calls only when QQQ is above today's 09:30 opening price, puts only when below |
| ALL | WIDE + TRAIL + TREND together (the new paper bot) |

One-minute bars cannot show the order of prices inside a minute, so: the stop is checked before the target in the same bar; the
trail starts in the bar that touches +2.5%, with "best" = that bar's high, and in that bar it sells only if the bar closes 1.5% or
more below that high, at the close; in later bars it sells at the trail level, or at the open if the bar opens below it.

## Data and costs

- As Study 5: 2024-03-01 to 2026-10-31, real option trade bars from Alpaca. Holdout from 2026-01-01.
- Costs: 1 cent per share per side (base) and 2 cents; $0.03 fee per contract per side.

## Decision lines

**A. Better than the live bot?** A rule goes into the main paper bot only if **all** hold (as Study 7):
1. Daily profit improves on BASE over the full period, paired Newey-West t ≥ 2.0 at 1 cent.
2. It also improves on BASE in the 2026 holdout.
3. It also improves on BASE at 2 cents.
If several pass, the one with the highest t is adopted.

**B. Makes money on its own?** A rule is called "profitable in the history test" only if its own daily profit is above zero with
Newey-West t ≥ 2.0 over the full period at 1 cent, and above zero in the holdout and at 2 cents. Only a rule that passes B would
ever be discussed for real money, and even then only after weeks of matching paper results.

## Amendments

(none)
