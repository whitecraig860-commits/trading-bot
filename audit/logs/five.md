# Experiment log: 5-minute crosses (`five`)

**Rules now:** VWAP / EMA50 crosses on 5-minute candles; +5% / -10% / 30 min; stop after 2 losses.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-19 | Created (Study 13 FIVE). | History -$16/day; signal 49-50% right (coin flip). | Pending merge (PR #39). |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_five.md`, `audit/paper_results.md` | See `audit/README.md` for the rating. |
