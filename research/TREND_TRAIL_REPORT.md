# Study 8 results: wider stop, trailing exit, trend-only entries

Protocol: `research/TREND_TRAIL_PROTOCOL.md` (committed before any code or result; one amendment, WT, added before any
result was seen). Script: `research/trend_trail_study.py`. Full output: `research/study8_output.txt`.
Data: 670 trading days (Mar 2024 to Oct 2026), 26,516 signals, real one-minute option trade bars, one contract a trade,
1 cent a side plus fees. Every rule includes the live "stop for the day after 2 losses in a row".

## Results (1 cent a side)

| Rule | Trades | Won | Per day | 2026 holdout per day | vs live bot per day | paired t |
|---|---|---|---|---|---|---|
| BASE (live bot: +2.5% / −6% / 10 min) | 6,477 | 64% | −$38.25 | −$42.52 | | |
| WIDE (−12% stop) | 9,466 | 75% | −$59.52 | −$64.35 | −$21.27 | −10.58 |
| **TRAIL (keep winners, sell 1.5% below best)** | 3,688 | 47% | **−$10.07** | −$10.86 | **+$28.18** | **+16.01** |
| TREND (with the day's direction only) | 5,651 | 65% | −$30.97 | −$35.50 | +$7.28 | +5.85 |
| WT (his style: −12% stop + trail) | 4,864 | 57% | −$19.48 | −$23.85 | +$18.77 | +8.14 |
| ALL (WIDE + TRAIL + TREND) | 4,517 | 58% | −$11.30 | −$15.78 | +$26.95 | +11.73 |

At 2 cents a side every rule loses more, and the order is the same. See the output file.

## Decisions (as the protocol says)

- **A. Better than the live bot:** TRAIL, TREND, WT and ALL pass; TRAIL has the highest t, so **TRAIL is adopted** in the
  main paper bot (`MAIN_TRAIL = True` in `tracker/qqqbot.py`; set it to False to undo).
- **WT (his style) is better than the live bot but worse than TRAIL alone:** the 12% stop costs about $9 a day.
- **WIDE fails badly.** A 12% stop wins more often (75%) but the losses are twice as big, and it loses $21 a day more.
- **B. Profitable on its own: none.** The best version still loses about $10 a day per contract. It is not a money-maker,
  and nothing here supports real money.

## What this says about his results

- Our entries fire at the same seconds as his on 17 Nov (10:06, 11:02, 11:05, 11:13), so the entry signal is the same family.
- His 57 posted trades (11–17 Nov, `state/discord_trades.csv`) won 91%, with an average win of +4.8% and loss of −10.5%,
  so he needs 69% wins to break even. On these same entries over 2.7 years, a 12% stop wins 75% of the time and still loses,
  because the bigger losses outweigh the extra wins.
- So his wide stop is not the reason he wins. The 4 days we have of his are days he chose to post, and 2.7 years show what
  the same rules do on every day. His "his style" copy runs on paper next to the others so this can be checked forward.
