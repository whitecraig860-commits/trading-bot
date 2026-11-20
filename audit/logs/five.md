# Experiment log: 5-minute crosses (`five`)

**Rules now:** VWAP / EMA50 crosses on 5-minute candles; +5% / -10% / 30 min; stop after 2 losses.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-19 | Created (Study 13 FIVE). | History -$16/day; signal 49-50% right (coin flip). | Pending merge (PR #39). |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_five.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
