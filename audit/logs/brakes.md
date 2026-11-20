# Experiment log: Brakes (`brakes`)

**Rules now:** Main bot + stop for the day at +$50 or -$100.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-19 | Created (Study 12 PB50LB). | History -$35/day (+$2.85 vs main, 5/6 stress tests). | Pending merge (PR #39). |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_brakes.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
