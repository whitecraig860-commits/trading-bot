# Study 14: his exit structure from his 24 Nov screenshot. Pre-registered (24 Nov 2026, before code or results)

What his panel showed (Trader #2, 636 put, entry 7.48): stop on QQQ's price about 2 ATR away (anchor 635.87, stop 637.98,
ATR 1.058), take profit 9.35 (+25%), a "% lock" that arms when the bid reaches +3.5%, a trail that arms after a 1.5 ATR move,
"TREND" label, and 9 of 57 signals taken.

## Exit rule HX (fixed now)
1. Stop: QQQ closes 2.0 ATR (5-minute ATR, 14) against the trade from the entry price.
2. Take profit: option reaches +25%.
3. Lock: once the option has reached +3.5%, sell if it falls back to +2%.
4. Trail: once QQQ has moved 1.5 ATR in favour, sell if QQQ gives back half of its best move.
5. Otherwise out at 15:55. Stop after 2 losses in a row (as the live bots).

## Entries
E1 all signals (main bot); E2 "picks like him" (Study 10, keeps ~10%); E3 placebo: random 10% of signals (20 runs).

## Judged
Per day at 1 cent and at 5 cents a side (measured cost level), each year, 2026 out of sample, win rate, average win and
loss, worst trade; vs the main bot's exits on the same entries; HX+E2 must beat 19 of 20 placebos to count as skill.
Profitable only if positive at 5 cents with t >= 2 and positive every year.
