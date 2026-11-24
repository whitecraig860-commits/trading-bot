# Experiment log: His style (`his`)

**Rules now:** Trailing exit + 12% stop (from his posted trades).

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-17 | Created (Study 8 WT). | History -$19.48/day; the 12% stop costs about $9/day vs TRAIL. | Comparison bot. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_his.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
| 2026-11-24 | Retired (CC-006), at the user's request. Code, state files and reports kept. | `audit/CHANGE_CONTROL.md` CC-006 | Stops running when the pull request is merged. |
