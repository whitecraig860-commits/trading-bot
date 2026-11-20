# Experiment log: Skip weak crosses (`skipweak`)

**Rules now:** Main bot, skipping signals whose close is less than $0.10 past the line.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-18 | Created (Study 9 FILTER=F3). | History -$32/day (t +5.9 vs main); Study 11: gain comes from trading less. | Comparison bot. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_skipweak.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
