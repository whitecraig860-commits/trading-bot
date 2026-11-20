# Experiment log: Shares one-a-day (`shares_oneaday`)

**Rules now:** Study 6 breakout: 09:30-09:45 range; checks 10:00-14:00 every 10 min; enters past range +/- 0.3 ATR(5-min), beyond VWAP and the noise band; trail at 4 ATR giving back half; 10 ATR safety stop; out 15:45. About GBP 1,000 notional, fractional shares.

Every change is recorded here before it is made: problem, evidence, change, expected effect, possible side effects, tests, result.

| Date | Change | Evidence / tests | Result / decision |
|---|---|---|---|
| 2026-11-14 | Created from Study 6 (ONE_A_DAY_PROTOCOL.md). | Study 6: 100 shares +$36.56/day, t 2.72, positive every year. | Paper bot running. |
| 2026-11-20 | Audit baseline measured (no change). | `audit/baseline_shares_oneaday.md` | Rated B (PROMISING). See audit/README.md. |
| 2026-11-20 | Audit part 2: forensic and stress tests (no change). | `audit/AUDIT2_REPORT.md` section 3: per-trade return ~0 or negative 2016-2021, +0.08-0.14% 2022-2026; pre-registered ex-ante filter failed both ways; stress tests pass; GBP 1,000 expected ~GBP 67-170 a year. | Stays B (PROMISING, regime-dependent). Not for real money. |
