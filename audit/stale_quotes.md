# Paper trades made on stale (frozen) option quotes

316 paper option trades checked. A quote counts as stale if it was stamped more than 60 seconds before it was used.

**11 trades (3%) used a stale quote at entry or exit**, with a total P&L of +276 (all trades: -2,251). Their recorded results are not reliable in either direction.

| Bot | Trades | Stale trades | P&L of stale trades | P&L of the rest |
|---|---|---|---|---|
| clone | 4 | 0 | +0 | -207 |
| combo | 11 | 1 | -127 | -148 |
| his | 27 | 2 | +175 | -345 |
| options | 76 | 2 | +174 | -118 |
| original | 150 | 2 | +174 | -944 |
| picks | 9 | 0 | +0 | +5 |
| skipweak | 8 | 1 | -147 | -126 |
| trail | 20 | 2 | +175 | -346 |
| trailtrend | 11 | 1 | -147 | -299 |

| Day | Stale trades | Their P&L |
|---|---|---|
| 2026-11-13 | 0 | +0 |
| 2026-11-16 | 0 | +0 |
| 2026-11-17 | 0 | +0 |
| 2026-11-18 | 0 | +0 |
| 2026-11-19 | 7 | -1,009 |
| 2026-11-20 | 4 | +1,286 |

Fix: CC-001 (only trade on quotes stamped within 60 seconds), pending the user's approval in PR #39.
