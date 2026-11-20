# Experiment log: Stop after 2 + trailing exit + trend (`trailtrend`)

**Rules now:** Trail bot, calls only above the 09:30 open, puts only below.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-17 | Created (Study 8 parts combined; this mix not run as one rule). | Not tested as one rule in Study 8. | Comparison bot. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_trailtrend.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
