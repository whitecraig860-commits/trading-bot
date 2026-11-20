# Experiment log: Opening move (`open30`)

**Rules now:** At 10:00, call if QQQ up 0.25%+ from the open, put if down; +10% / -10% / 60 min; one a day.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-19 | Created (Study 13 OPEN30). | History -$2.46/day; 54% right at 30 min. | Pending merge (PR #39). |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_open30.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
