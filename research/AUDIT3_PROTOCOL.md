# Audit part 3: shares strategy deep tests and remaining stress tests. Pre-registered

Committed 2026-11-20, before any code or result. Measures only; no bot is changed (the user has not authorised changes).

## A. Pre-entry filters for the shares one-a-day strategy (thresholds fixed now, not fitted)

| Code | Skip the trade when | Reason |
|---|---|---|
| FA | the entry is more than 0.5 ATR inside the previous day's range on the breakout side (long: yesterday's high is more than 0.5 ATR above the entry; short: yesterday's low more than 0.5 ATR below) | yesterday's extreme acts as resistance/support; audit part 2 saw losing trades further inside yesterday's range (observation, now tested) |
| FB | at entry, price is already more than 2 noise bands away from the open | most of the move has already happened |
| FC | the 09:30-10:00 return points the other way from the trade | intraday momentum disagrees |

Judged separately on 2016-2021 and 2022-2026 (each is out of sample for the other; nothing was fitted on either). A filter is
called useful only if it raises the average return per trade in **both** periods and the improvement over all years has
t ≥ 2.4 (Bonferroni for three filters). Otherwise it is rejected.

## B. Can the strategy tell when its edge has gone? (uses only its own past signals)

RD120: trade only if the average return of the strategy's last 120 signals (taken or not, so it keeps measuring while
switched off) is above zero. RD60: the same with 60 signals (sensitivity only). Compared with always trading, by year.

## C. The 2022 market-structure hypothesis (evidence for or against, not proof)

1. Average return per trade before and after 1 Jan 2022, and the same split excluding 2022 itself (the bear year).
2. If dealer hedging of daily-expiring options pushes prices along the day's move, the drift after entry should be stronger
   late in the day after 2022: average favourable move from 15:00 to the 15:44 exit, before vs after 2022.
3. Bull years only (2023-2026 vs 2016-2021 bull periods): does the post-2022 edge survive outside the 2022 bear market?

## D. Remaining stress tests (both candidates; each changes one thing)

Exits decided 1 and 5 minutes late; 10% of exit signals fail (retried at the next check); the safety stop filled at twice its
distance (flash move); position sizes and starting balances (shares: £1,000 / £5,000 / £25,000 fully invested;
options: one contract on £1,000 / £5,000 / £25,000), 5,000 simulated years each: median, 5th and 95th percentile, chance of
a losing year, chance of a 10 / 20 / 30% drawdown, chance of losing half (ruin), longest losing streak.
Simulated years are resamples of real trades; they are not historical years.
