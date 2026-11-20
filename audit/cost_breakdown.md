# Where the real cost of each paper trade comes from

316 paper option trades with recorded bid/ask at both entry and exit. Cost = half the bid-ask spread at entry (we buy at the ask, half a spread above the middle) + half at exit (we sell at the bid) + $0.06 fees, per contract.

**Average $9.41 per round trip** (median $8.56); entry half-spread $4.06, exit half-spread $5.29. The history tests assumed $2.06. Average spread at entry 1.14% of the option price, at exit 1.48%.

## By bot

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| clone | 4.0 | $8.31 | $3.88 | $4.38 | 0.96% |
| combo | 11.0 | $14.92 | $6.41 | $8.45 | 1.38% |
| his | 27.0 | $12.75 | $4.30 | $8.39 | 1.14% |
| options | 76.0 | $7.78 | $3.62 | $4.10 | 1.15% |
| original | 150.0 | $8.26 | $3.86 | $4.34 | 1.11% |
| picks | 9.0 | $7.39 | $3.22 | $4.11 | 0.84% |
| skipweak | 8.0 | $13.75 | $6.56 | $7.13 | 1.49% |
| trail | 20.0 | $14.59 | $4.85 | $9.68 | 1.20% |
| trailtrend | 11.0 | $12.06 | $4.50 | $7.50 | 1.17% |

## By time of day (New York)

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| 09:00 | 61.0 | $11.58 | $4.30 | $7.22 | 1.09% |
| 10:00 | 49.0 | $10.48 | $5.13 | $5.29 | 1.31% |
| 11:00 | 84.0 | $9.68 | $4.10 | $5.52 | 1.14% |
| 12:00 | 42.0 | $9.06 | $4.14 | $4.86 | 1.25% |
| 13:00 | 31.0 | $7.95 | $3.81 | $4.08 | 1.23% |
| 14:00 | 32.0 | $6.12 | $2.75 | $3.31 | 0.86% |
| 15:00 | 17.0 | $6.91 | $2.71 | $4.15 | 0.92% |

## By exit reason

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| stop | 129.0 | $11.43 | $4.58 | $6.79 | 1.25% |
| target | 151.0 | $6.63 | $3.62 | $2.95 | 1.07% |
| time | 1.0 | $6.06 | $3.00 | $3.00 | 0.69% |
| trail | 35.0 | $14.04 | $4.07 | $9.90 | 1.08% |

## By how fast QQQ was moving in the 10 minutes before entry

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| calm (bottom third) | 106.0 | $7.34 | $3.49 | $3.79 | 1.07% |
| middle | 105.0 | $9.94 | $4.89 | $4.99 | 1.40% |
| fast (top third) | 105.0 | $10.97 | $3.81 | $7.09 | 0.95% |

## By instrument (call / put)

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| C | 161.0 | $8.89 | $3.61 | $5.22 | 1.04% |
| P | 155.0 | $9.94 | $4.53 | $5.35 | 1.25% |

## By day

| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |
|---|---|---|---|---|---|
| 2026-11-13 | 33.0 | $6.86 | $3.24 | $3.56 | 1.21% |
| 2026-11-16 | 44.0 | $5.65 | $3.15 | $2.44 | 1.07% |
| 2026-11-17 | 51.0 | $8.90 | $3.59 | $5.25 | 1.01% |
| 2026-11-18 | 86.0 | $10.56 | $3.89 | $6.61 | 1.12% |
| 2026-11-19 | 50.0 | $8.89 | $4.49 | $4.34 | 1.16% |
| 2026-11-20 | 52.0 | $13.29 | $5.69 | $7.54 | 1.30% |

## Effect on each bot's history (per day, one contract)

Using the measured average cost instead of the assumed $2.06, per trade, times the bot's history trades per day:

| Bot | History per day at $2.06 | Trades per day | Extra cost per day | History per day at measured cost |
|---|---|---|---|---|
| options | -38.25 | 9.7 | -71.04 | -109.29 |
| original | -95.19 | 27.2 | -199.62 | -294.81 |
| trail | -10.07 | 5.5 | -40.45 | -50.52 |
| trailtrend | -6.42 | 5.4 | -39.37 | -45.79 |
| his | -19.48 | 7.3 | -53.35 | -72.83 |
| skipweak | -31.57 | 8.3 | -60.80 | -92.37 |
| combo | -34.58 | 8.6 | -63.07 | -97.65 |
| picks | -11.69 | 3.4 | -24.97 | -36.66 |
| clone | -11.15 | 3.4 | -24.97 | -36.12 |
| brakes | -35.39 | 9.3 | -68.05 | -103.44 |
| five | -16.46 | 5.4 | -39.83 | -56.29 |
| open30 | -2.46 | 0.5 | -3.70 | -6.16 |
| oneaday | +14.12 | 0.7 | -5.26 | +8.86 |

Caveat 1: the history tests priced trades at actual trade prices (option trade bars), which are often already
inside the bid-ask spread, plus 1 cent. The paper cost above is measured from the middle of the spread. So adding the whole
difference to the history probably overstates the effect: the true figure lies between the $2.06 column and the last column.
Either way, every fast bot loses more, and none turns positive.
Caveat 2: the one-a-day options bot buys a slightly in-the-money or at-the-money option once a day and holds for hours;
its cost was not measured live yet (not deployed). The fast bots' measured spreads are used as the estimate.
Shares: QQQ's spread is about 1 cent a share; at about 2 shares (GBP 1,000) that is about $0.04 a round trip.
