# Reconciliation of the reported figures (20 Nov 2026 and the paper record)

Authoritative source: the saved state files on `main` (`state/<bot>/<day>.json`, written by the live bots and committed by
the recorder after each run), checked against the recorded quotes (`state/quotes/`). Live-page and Telegram figures during
the day are **interim snapshots** and are superseded by the saved files.

## The four different figures for "the QQQ paper bot" on 20 Nov

| Figure reported | What it actually was |
|---|---|
| **8 trades, +$178.52** | Final, realised: the **main bot** ("stop after 2 losses"). It stopped for the day after its 2nd loss in a row at 11:16:16. |
| **17 trades, +$257** | Interim snapshot at 15:12 NY of the **original bot** (no loss stop), from the live page. |
| **19 trades, +$256.86** | Final, realised: the **original bot**. It kept trading until 15:23. |
| "8 trades +$179" vs "19 trades +$257" in the morning summaries | Two different bots, not two versions of one result. |

Both final ledgers contain the same frozen-price trade: 10:19:06 634 put, bought at 7.03 on a quote stamped 10:14:04 (302 s
old), sold at 10:24:01 at 10.24 on the first fresh quote: **+$320.94 that could not have been executed.**

| Bot, 20 Nov | Recorded (realised, as saved) | Corrected (real bot code replayed on the recorded quotes, fresh quotes only) |
|---|---|---|
| Main (stop after 2) | 8 trades, +$178.52 | **7 trades, −$142.42** |
| Original | 19 trades, +$256.86 | **18 trades, −$64.08** |

Proof that the difference is only the frozen price: replaying the same code with the fresh-quote guard switched off
reproduces both real ledgers trade for trade (8/8 and 19/19, same times and P&L).

Main bot ledger, 20 Nov (as recorded): 09:47 637C +39.94 · 09:51 636P −69.06 · 09:52 637C +39.94 · 09:55 640C −76.06 ·
10:13 637P +42.94 · **10:19 634P +320.94 (frozen quote: void)** · 11:13 630C −56.06 · 11:16 629P −64.06 → stopped.

## The main bot's paper record: +$55 vs −$118

The recorded record on 13-20 Nov was +$55 (76 trades). Two of its trades used frozen quotes: 19 Nov 10:32:36 662P (−$147.06,
bought on a quote from the previous afternoon) and 20 Nov 10:19:06 634P (+$320.94). Removing those two leaves −$118. The
fully corrected record (replaying 19 and 20 Nov with fresh quotes only, which also changes later trades those days) is in
`audit/paper_results.md` after correction; the day-level corrected figures above are the authoritative ones.

## "An earlier comparison reported different results for the same exit strategies"

On 17 Nov I replayed the morning (09:30-12:50) of that day through the new comparison bots (trail −$104, trail+trend −$99,
his style −$196), while the live comparison bots only started in the afternoon after the merge (their live figures that day
were afternoon-only: trail −$110, trail+trend −$66, his style +$11). Different periods of the same day; neither is a full day.

## The QQQ share buy-back: 2.0819 shares at $609.59, +£35.49

This belongs to the **shares one-a-day bot** (separate paper account of about £1,000, fractional QQQ shares). It is not an
options result and is not included in any options total.

20 Nov: short 2.0819 shares at $632.02 at 10:30:06 (breakout below the 09:30-09:45 range); bought back at $609.59 at 15:45:07
(the 15:45 time exit). Result: (632.02 − 609.59) × 2.0819 = **+$46.70 = £35.49** (at £1 = $1.316). The best point was +$22.81
a share.

**Price check against the live QQQ price recorded at the same second:** the shares bot books its fills at the close of the
last completed one-minute candle (plus 1 cent), not at the live price. On 20 Nov the live price was $631.44 at entry and
$610.23 at exit, so at live prices the trade made +$44.16 instead of +$46.70. Over all five shares trades the difference
nets to almost nothing (recorded +$67.59, at live prices +$67.62) and goes both ways (from −$1.40 to +$2.54 a trade). The
history test uses the same candle-close convention, so live and history are consistent, but a real order fills at the live
price plus the spread: this is recorded as an execution difference to measure during validation.

Shares bot paper record to date (5 trades, all short sales): 16 Nov +$8.07, 17 Nov +$1.06, 18 Nov −$9.19, 19 Nov +$20.95,
20 Nov +$46.70; total **+$67.59 (about £51)** on about £1,000. All five exits were the 15:45 time exit. Five trades prove nothing yet.
