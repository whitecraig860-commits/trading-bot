# Study 12 results: what is wrong with our bot, his brakes, and the bad-price guard

Protocol: `research/BRAKES_PROTOCOL.md` (committed before code or results). Scripts: `research/brakes_study.py` (history),
`research/brakes_replay.py` (our recorded live prices, his trades). Output: `research/study12_output.txt`,
`research/study12_replay_output.txt`.

## Part A: what is wrong with ours (6,477 trades over 2.7 years)

1. **The entry signal predicts nothing.** After a signal, QQQ moved the signal's way 49% of the time at 1, 3, 5 and 10
   minutes, and by about $0.00 on average. It is a coin flip.
2. **The wins are small and the losses big.** Win rate 64%, but the average win is +$5.85 and the average loss −$21.02
   (the average option cost $3.16: +2.5% is about $8, −6% about $19).
3. **Even before costs it loses** (−$1.90 a trade); costs take another $2.06.
4. **The stop shakes trades out:** 39% of stopped trades would have reached the +2.5% target within the same 10 minutes.
5. **Winners are sold early:** 84% of trades that hit +2.5% went on to +5%, and 55% to +10%. (But letting them run, Study 8,
   and wider stops, Study 8, did not make it profitable, because with a coin-flip entry the extra wins are matched by
   extra losses.)

Conclusion: **no exit, brake or filter can make a coin-flip entry profitable.** Only a different entry can.

## Part B: his brakes

| Rule | History per day (1c) | vs live bot | paired t | Stress tests passed | A | B |
|---|---|---|---|---|---|---|
| BASE | −$38.25 | | | | | |
| PB50 (stop at +$50) | −$35.68 | +$2.57 | +3.59 | 5/6 (T2 fail) | PASS | fail |
| PB100 | −$37.32 | +$0.93 | +1.56 | 2/6 | fail | fail |
| LB100 (stop at −$100) | −$37.96 | +$0.28 | +1.16 | 2/6 | fail | fail |
| **PB50LB (both)** | **−$35.39** | **+$2.85** | **+3.28** | **5/6 (T2 fail)** | **PASS** | fail |

- Test 2, our recorded live prices (17-19 Nov; the replay reproduced the live bot's real trades on 17 and 18 Nov):
  BASE −$100, PB50 −$34, PB100 +$90, LB100 −$45, PB50LB +$20. Three days only.
- Test 3, his own trades (per contract, per account, 11-19 Nov): no brake +$1,427; PB50 +$623; PB100 +$906;
  LB100 +$1,582. His profit brake must be set much higher than $50 per contract, and his loss brake is what saves him.
- T2 fail: cutting the same number of trades on random days helps more, so the brake is a small help, not an edge.

**Decision:** PB50LB passes A and 5 of 6 stress tests, so it runs as a new comparison bot ("brakes").

## Part C: bad-price guard

- G1 (wide spread) and G2 (3 minutes after a quote gap) blocked nothing on the recorded days.
- The real fault on 19 Nov was different: the 10:32:36 trade bought at a quote stamped **18 Nov 16:14** (9.68); the real price
  (8.21) came 5 seconds later, so the −$147 was not a real trade. Fix for every bot: only buy or sell on quotes stamped within
  the last 60 seconds (`FRESH_QUOTES_ONLY` in `tracker/qqqbot.py`). On 17 and 18 Nov it changes nothing (verified by replay).
