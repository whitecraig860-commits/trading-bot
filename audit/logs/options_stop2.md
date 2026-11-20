# Experiment log: Main options bot ("stop after 2 losses") (`options_stop2`)

**Rules now:** 1-minute VWAP / EMA50 crosses + first 15-minute range break, 09:45-15:30; nearest strike, next-day expiry, 1 contract; +2.5% target, -6% stop, 10-minute limit; stop for the day after 2 losses in a row.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-11 | Created from Study 5 rules (QQQ_TRIGGERS_PROTOCOL.md). | Study 5: -$95/day on history (all signals, no loss stop). | Kept as baseline. |
| 2026-11-13 | Added: stop for the day after 2 losses in a row. | Study 7 (LOSS_PAUSE): paired t +20.1 vs no stop; -$95 -> -$38/day. | Adopted. Still unprofitable. |
| 2026-11-19 | Fresh-quote guard (only trade on quotes < 60 s old) - data-error fix, all bots. | 19 Nov fake -$147 trade on an 18 Nov quote; replay of 17-18 Nov unchanged. | Pending merge (PR #39). |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_options_stop2.md`, `audit/paper_results.md` | See `audit/README.md` for the rating. |
