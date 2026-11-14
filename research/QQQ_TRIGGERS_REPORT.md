# Study 5: the three one-minute QQQ triggers. Results

**Run:** 2026-11-12, on data from 2024-03-01 to 2026-10-30 (670 trading days). Rules: `research/QQQ_TRIGGERS_PROTOCOL.md`, committed (bb027d3) before any code. Full output: `research/study5_output.txt`. No orders were placed.

## Verdict: FAILS all three pass lines

| Cost per side | Trades | Win rate | Average win | Average loss | Per day, one contract |
|---|---|---|---|---|---|
| 0 cents | 18,201 | 65% | $7.5 | −$18.1 | −$41 (−£31) |
| **1 cent (base)** | 18,201 | 65% | $5.5 | −$20.0 | **−$95 (−£72)** |
| 2 cents | 18,201 | 61% | $3.7 | −$20.0 | −$150 (−£114) |

- It lost on 93% of days at 1 cent per side, and it lost even with zero costs.
- Every trigger, both sides, every year, every time of day and every sensitivity setting was negative.

## Why it loses

- A +2.5% target against a −6% stop needs about a 71% win rate to break even before costs. The plain triggers won 65%.
- The triggers fire about 40 times a day. Price crosses the 50 EMA and VWAP constantly in sideways markets, and most of those crosses mean nothing.

## What this does and does not show

- **It shows** that the three triggers as described in the video, taken on every signal with simple exits, are not profitable.
- **It does not show** that the owner's bot loses. His bot trades about 17 times a day across three QQQ bots, not 27 for one, so it filters out most signals. His posted day won 86% of trades. Those filters, and his real fills, are what we cannot see.

## Limitations

1. The exits are my reconstruction, not his.
2. One-minute bars cannot show the order of events inside a minute. The "optimistic" ordering was still negative (−$83 a day).
3. Option trade prices are not bid/ask quotes.

## Next step

The scorecard in `tracker/` re-prices his actual posted trades at recorded bid/ask prices, starting 2026-11-12. That is the direct test of whether his results survive real fills.
