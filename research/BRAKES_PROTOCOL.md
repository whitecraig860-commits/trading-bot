# Study 12: his brakes, a bad-price guard, and a full check-up of our bot. Pre-registered protocol

**Status:** committed on 2026-11-19, before any code for this study was written or any result seen. No orders.

**Why:** his 19 Nov summary showed a **profit brake** (a bot stops for the day once it is up enough) and a **loss brake**
(it stops once it is down too much). The same day, both his bots and ours were hurt by stale prices after a data outage.
The user asked what is wrong with our bot and for every way of testing each part, not just the history test.

## Part A: what is wrong with ours (diagnosis of the live bot on 2.7 years, no new rule)

Reported for the live bot (+2.5% / −6% / 10 min, stop after 2 losses): wins and losses by exit reason (target, stop,
time); average win and loss in dollars; the share of each trade's cost that is the bid-ask spread and fees; how often a
trade that hit the stop would have reached +2.5% later within 10 minutes (was the stop shaken out?); how often a trade that
hit +2.5% went on to +5% and +10% within 10 minutes (are we selling winners too early?); and how big a move in QQQ
follows a signal on average in the next 1, 3, 5 and 10 minutes, in the signal's direction (does the signal predict anything?).

## Part B: brake rules (all on top of the live bot)

| Code | Rule |
|---|---|
| BASE | the live bot |
| PB50 | profit brake: stop for the day once the day's result reaches +$50 |
| PB100 | profit brake at +$100 |
| LB100 | loss brake: stop for the day once the day's result reaches −$100 (as well as after 2 losses in a row) |
| PB50LB | PB50 and LB100 together |

### Test 1: history (Mar 2024 to Oct 2026, real option bars), the full Study 11 battery
T1 every year; T2 placebo (stop the day after a random number of trades with the same average count; 20 runs);
T3 costs 3 and 5 cents; T4 entries one minute late; T6 1,000 block resamples; T7 calm / busy / up / down days;
plus the decision lines A and B from Studies 8 to 10.

### Test 2: our own recorded live prices (5-second bid and ask, 17, 18 and 19 Nov 2026)
Each rule replayed through the real paper-bot code on the recorded quotes and that day's candles (checked first: the
replay must reproduce the live bot's actual trades). Too few days to decide anything; reported as a reality check.

### Test 3: his days
For each of his posted days, whether the rule would have stopped him earlier or later and what his day would have been
at his own trades (profit brake applied to his posted sequence, per account).

## Part C: bad-price guard (only testable on recorded quotes: the history bars have no bid and ask)

| Code | Don't buy when |
|---|---|
| G1 | the ask is more than 5% above the bid |
| G2 | it is within 3 minutes of the first fresh quote after a gap of 2 minutes or more |

Tested on all recorded quote days (13 to 19 Nov) with the replay: trades blocked, and their results.

## What gets added

- A brake rule that passes A and at least five of the six history stress tests runs as a new comparison bot.
- The guard, if it blocks only trades made at abnormal prices, is offered to the user for all bots (it changes existing
  bots, so only with their say-so).
- Nothing is called profitable unless it passes B.

## Amendments

(none)
