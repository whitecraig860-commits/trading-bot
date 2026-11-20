# Experiment log: One-a-day breakout on options (`oneaday`)

**Rules now:** Follows the shares bot's entry/exit with the at-the-money option expiring the next trading day.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-19 | Created (Study 13 ONEADAY). | History +$14.44/day, positive every year, beats 20/20 placebos, t 1.73. | Pending merge (PR #39). Same rules as his new one-a-day bot (his post 20 Nov), which uses ~$2 in-the-money, 1-3 day expiry. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_oneaday.md` | Rated B (PROMISING). See audit/README.md. |
