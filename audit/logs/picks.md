# Experiment log: Picks like him (`picks`)

**Rules now:** EMA9/EMA20 agree + strong candle + before 12:00 + not weak.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-18 | Created (Study 10 ALL). | History -$12/day; Study 11 placebo: random 10% of signals does as well. | Comparison bot. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_picks.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
