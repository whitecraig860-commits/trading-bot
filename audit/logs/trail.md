# Experiment log: Stop after 2 + trailing exit (`trail`)

**Rules now:** Main bot, but from +2.5% keep the trade and sell 1.5% below its best; 15-minute limit.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-17 | Created (Study 8 TRAIL). | History -$10/day vs -$38 (paired t +16). Live replay 17 Nov: 1.5% trail shaken out by quote flicker. | Comparison bot; live behaviour worse than history. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_trail.md` | Rated E (DISCONTINUE): no edge. See audit/README.md. |
| 2026-11-20 | Audit part 2: three pre-registered market-condition filters (no change). | `audit/AUDIT2_REPORT.md` section 1: no filter lifts the entry above ~51% right; all negative at realistic cost. | Recommend permanent retirement from trading (code and reports kept). |
