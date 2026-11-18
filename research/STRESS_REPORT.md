# Study 11 results: the stress tests, and what they say about every filter so far

Protocol: `research/STRESS_PROTOCOL.md` (committed before running). Script: `research/stress_study.py`.
Output: `research/study11_output.txt`. 670 days, real option bars, all with "stop after 2 losses".

## Results

| Test | "Picks like him" (ALL) | "His clone" (CLONE) |
|---|---|---|
| Per day at 1 / 2 / 3 / 5 cents a side | −$11.69 / −$18.47 / −$21.97 / −$25.23 | −$11.15 / −$17.94 / −$24.64 / −$30.46 |
| Live bot at the same costs | −$38.25 / −$55.86 / −$57.23 / −$44.03 | same |
| T1 better than the live bot in every year | PASS | PASS |
| **T2 better than picking 10% of signals at random** | **FAIL: random −$11.44 (median), beats 9 of 20** | **FAIL: random −$11.65, beats 12 of 20** |
| T3 higher costs | PASS | PASS |
| T4 one minute late | PASS | PASS |
| T5 settings wobbled | PASS (all −$10 to −$13) | — |
| T6 1,000 resamples | PASS (100%) | PASS (100%) |
| T7 calm / busy / up / down days | PASS | PASS |
| Profitable | no | no |

## What this means

**T2 is the decisive one.** Keeping a *random* 10% of the signals does just as well as keeping the 10% that look like his
picks. So the improvement from −$38 to −$12 a day comes from **trading less**, not from choosing better trades. Every
version loses about $3.30 to $4.00 per trade (live bot −$3.96, picks −$3.44, clone −$3.28).

This also explains Studies 9 and 10: the filters that "passed" all cut the number of trades, and fewer trades means
smaller losses when each trade loses on average.

**Why each trade loses:** a one-minute VWAP or EMA cross does not predict the next few minutes well enough to beat the
cost of buying at the ask and selling at the bid. Changing the exits (Studies 8, 11) or the filters (9, 10, 11) does not fix
that: the entries themselves have no edge over 2.7 years.

## Decisions

- Neither rule is robust (both fail T2), so neither goes into the main bot.
- The two comparison bots stay (Study 10's rule passed its own test, and the user asked for a bot as close to his as
  possible), labelled with this result, so their live record can be compared with his.
