# Study 9 results: his skip rule, an earlier start and an in-the-money strike

Protocol: `research/HIS_FILTER_PROTOCOL.md` (committed before code or results). Script: `research/his_filter_study.py`.
Output: `research/study9_output.txt`.

## First: is his profit just "no slippage"?

No. His 42 trades on 17-18 Nov that match our recorded quotes, re-priced at the real ask (buy) and bid (sell) exactly as
our bots are, still made +$963 and +$2,716 (his posted figures: +$1,092 and +$3,677). His posted prices are a few cents
better than the real quotes, which explains roughly 10-25% of his profit, not the gap between his results and ours.

## Stage 1: which of our signals did he take? (11, 12, 17, 18 Nov)

- 187 of our signals on those days; he took 27 of them. 55 of his 83 entries matched one of our signals within 60 seconds,
  so about a third of his entries come from something our bots do not produce.
- By the hour: 09h 6/17, 10h 9/42, 11h 6/24, 12h 4/34, 13h 2/21, 14h 0/26, 15h 0/23. **He hardly trades after 1pm.**
  (In our history test every time of day loses about the same per trade, so stopping early would only mean fewer trades.)
- The pre-set choice rule picked **F3: skip weak crosses** (close less than $0.10 past the line): it keeps 89% of the
  signals he took and skips 26% of the ones he skipped.

## Stage 2: 2.7 years of real option prices (1 cent a side; all with stop after 2 losses)

| Rule | Per day | Holdout per day | vs live bot | paired t | A |
|---|---|---|---|---|---|
| BASE (live bot) | −$38.25 | −$42.52 | | | |
| EARLY (from 09:31) | −$38.73 | −$43.46 | −$0.48 | −0.73 | fail |
| ITM (strike just in the money) | −$39.24 | −$44.39 | −$0.99 | −1.38 | fail |
| **FILTER (skip weak crosses)** | **−$31.57** | −$35.85 | **+$6.68** | **+5.89** | **PASS** |
| COMBO (all three) | −$34.58 | −$39.26 | +$3.67 | +2.85 | PASS |

**B (profitable on its own): none.**

## Decisions

- FILTER and COMBO pass A, so each runs as a new comparison paper bot (`skipweak`, `combo` in `EXTRA_BOTS`). The existing
  bots are unchanged (verified: identical trades with the new code).
- An earlier start and an in-the-money strike do not help on their own.
- The skip rule explains a little of how he chooses; most of his edge is still unexplained: a third of his entries are not
  our signals at all, and he picks among the rest in a way these five rules only partly capture.
