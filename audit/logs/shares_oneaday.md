# Experiment log: Shares one-a-day (`shares_oneaday`)

**Rules now:** Study 6 breakout: 09:30-09:45 range; checks 10:00-14:00 every 10 min; enters past range +/- 0.3 ATR(5-min), beyond VWAP and the noise band; trail at 4 ATR giving back half; 10 ATR safety stop; out 15:45. About GBP 1,000 notional, fractional shares.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-14 | Created from Study 6 (ONE_A_DAY_PROTOCOL.md). | Study 6: 100 shares +$36.56/day, t 2.72, positive every year. | Paper bot running. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_shares_oneaday.md` | Rated B (PROMISING). See audit/README.md. |
