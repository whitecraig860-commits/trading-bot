# Final consolidated audit report (20 Nov 2026)

Rules followed: no production change has been made since the instruction to stop; nothing has been merged or deployed;
every test listed here was actually run (outputs in `audit/`); anything not run is listed in section M.

Supporting files: `BOTS.md` (register), `LEDGER_RECONCILIATION.md`, `DATA_INTEGRITY.md`, `stale_quotes.md`,
`cost_breakdown.md`, `baseline_*.md` and `baseline_summary.md`, `AUDIT2_REPORT.md` + `audit2_output.txt`,
`audit3_output.txt`, `PR39_REVIEW.md` + `PR39_code_diff.txt`, `CHANGE_CONTROL.md`, `CHANGES.md`, `logs/`.

## A. Bots and status

14 strategies, but only **three independent ideas**: one-minute crosses (11 bots share the signal code), the opening move,
and the one-a-day breakout (shares bot and its options copy). 9 run on paper now; 4 are waiting in PR #39; none trades real
money. Full register: `BOTS.md`.

## B. Reconciled performance

- **20 Nov:** main bot 8 trades +$178.52 (final); original bot 19 trades +$256.86 (final); "17 trades +$257" was a 15:12
  snapshot of the original. Both include a +$320.94 trade bought on a quote frozen for 302 seconds. **Corrected: main −$142.42,
  original −$64.08** (real bot code replayed on the recorded quotes; with the guard off, the replay reproduces both real ledgers
  exactly).
- **Main bot record 13-20 Nov:** +$55 recorded; −$118 without its two frozen-price trades.
- **Shares bot:** 5 trades, +$67.59 (about £51). The 20 Nov buy-back (2.0819 shares at $609.59, +£35.49) is this bot; not an
  options result.
- History, out-of-sample and paper figures for every bot: `baseline_summary.md`, `paper_results.md`.

## C. Problems found (confirmed / suspected / not established)

| Problem | Status | Impact measured |
|---|---|---|
| Fast bots' entry has no edge (QQQ moves the signal's way 49-51%) | **confirmed** (6,477+ trades, every year, out of sample, three filters tried) | all 12 lose in every year |
| Small target vs large stop (win $5.85 vs loss $21.02 average) | confirmed (fast bots) | combined with the coin-flip entry: −$3.96 a trade |
| Real costs 4-5x the assumed | confirmed: $9.41 a round trip measured on 316 trades vs $2.06 assumed | fast bots lose $40-200 a day more; one-a-day options t falls from 1.73 to about 1 |
| Trading on frozen quotes | confirmed: 11 of 316 paper trades | −$1,009 fake (19 Nov) and +$1,286 fake (20 Nov) recorded P&L |
| Recorder stopped on a trading day | confirmed (19 Nov, 09:30-10:30 missed) | one hour of all bots |
| One-a-day options would be sold at restarts | confirmed in code review (bot not live) | would have broken its exit rule |
| Shares bot books fills at the candle close, not the live price | confirmed | nets to ~$0 over 5 trades (−$1.40 to +$2.54 each) |
| Shares edge depends on the market regime (none 2016-2021) | **confirmed** | per trade −0.019% (2016-21) vs +0.101% (2022-26) |
| Cause of that regime change (daily-expiring options) | **suspected only** | supporting evidence, not proof (section F) |
| One-a-day options profit depends on a few extreme days | confirmed | without top 5: +$3.35/day, t 0.51 |
| Multiple-testing bias | confirmed risk | ~30 variants tested; Bonferroni line t ≥ 3.14 |
| Data leakage via published rules | suspected | the shares rules come from published research (2024) that saw part of our test period |
| Missing commissions | confirmed (paper charges $0.03 a contract a side; a real broker may charge more) | not included |
| Duplicate orders, missed exits, not stopping | not found in code review and tests | — |
| Real broker behaviour (rejections, partial fills, reconnection) | **not testable** (no broker connected) | — |

## D. Why each strategy wins or loses

- **Fast bots (12):** the entry does not predict the next minutes; the exits take +2.5% and accept −6%, and spreads are large
  relative to the target. Filters only reduce the number of trades (Study 11: a random 10% of signals did as well). Stop exits
  are the most expensive (spread $11.43). Evidence: Study 12 diagnosis, `AUDIT2_REPORT.md` section 1.
- **One-a-day options:** profits come from rare days with very large moves (best five: 9-18 ATR moves vs 2.2 typical); on
  ordinary days it loses slowly to time decay and spread (11 losses in a row in Aug-Sep 2026, all closed at 15:44 without a
  move). Evidence: `AUDIT2_REPORT.md` section 2.
- **Shares one-a-day:** profits come from days that keep moving after the breakout (best move 3.5 ATR on winners vs 0.8 on
  losers); since 2022 the price has kept drifting in the trade's direction into the close (+0.047% from 15:00 to the exit,
  vs −0.009% before 2022). Evidence: `audit3_output.txt` C.

## E. Stress tests (each changes one thing; full tables in `AUDIT2_REPORT.md` and `audit3_output.txt`)

| Scenario | One-a-day options (per day) | Shares 2016-26 (per trade) |
|---|---|---|
| Baseline | +$14.12 | +0.035% |
| Entry 1 / 2 min late | +$13.13 / +$10.72 | +0.031% / +0.028% (approx., per day 12.51 / 11.48 on 100 sh) |
| Exits 1 / 5 min late | +$13.25 / +$10.72 | +0.031% / +0.035% |
| 10% of entries rejected / 10% of exits fail | +$13.84 / +$13.73 | unchanged / unchanged |
| 1-hour outage daily | +$10.55 | unchanged |
| Settings ±20% | +$12.20 to +$14.59 | unchanged within ±0.002% |
| Safety stop filled at 2× distance | n/a | +0.013% (sum +27% vs +72%) |
| Costs: assumed / measured / adverse / severe | +$14.12 / +$8.39 / +$5.52 / +$1.23 (1 / 5 / 7 / 10 cents) | 100 sh: +$13.46 / +$7.42 (5c) / −$0.14 (10c); at £1,000 size costs are negligible |
| Recorder restart | carried over after CC-003 (tested) | carried over (code) |
| Monte Carlo (5,000 simulated years; not historical) | at $1,270: P(loss) 59%, 50% drawdown 85%, cannot afford a contract 58%; at $31,750: P(loss) 28%, 50% drawdown 0% | at £1,000: median +$83, 5% −$163, 95% +$369, P(loss) 30%, P(DD ≥ 20%) 5%, ruin 0%; losing streak median 6, 95% 9 |

## F. Shares strategy and 2016-2021

- **Per trade:** 2016-2021 −0.019% (t −0.81, 1,123 trades); 2022-2026 +0.101% (t +3.36, 934 trades); 2023-2026 (excluding
  the 2022 bear year) +0.089% (t +3.03). Post-2022 it works on both bull-trend days (+0.078%) and bear-trend days (+0.138%),
  so it is not just the 2022 bear market.
- **Pre-registered filters (fixed thresholds, each period out of sample for the other): all three rejected.** Room to
  yesterday's high/low helped 2016-2021 (+0.021% kept vs −0.061% skipped) but not 2022-2026 (improvement t −0.17 overall).
  "Already moved" and "first-30-minute momentum" also failed. So **no pre-entry filter identified the bad conditions.**
- **Can it detect that its edge has gone?** A rule using only its own past signals (trade only when the last 120 signals
  averaged above zero) would have skipped most of 2016 and 2020 (2020: −6.0% instead of −19.8%) and kept 2023-2026 in full;
  total +79.5% vs +72.5% always on; but it also gave up part of 2021-2022. It is a candidate safety switch, not yet a
  validated one (it was compared, not tested with an adoption line).
- **2022 hypothesis:** the late-day drift in the trade's direction appeared after 2022 (+0.047% vs −0.009%), which is what
  dealer hedging of daily-expiring options would produce. That is consistent with the hypothesis, **not proof**: the split
  date was chosen after seeing the results, and other changes happened in 2022.
- **Statistical caution:** 2016-2026 t 2.96 is just below the Bonferroni line (3.14) if all ~30 variants count; the rules come
  from research published in 2024 that saw part of our period. The cleanest out-of-sample evidence is after publication
  (2025: +13.3%, 2026: +13.2% per trade-sum), which is positive but short.

## G. One-a-day options: statistical validity (independent re-check of the B → C downgrade)

Re-check confirms C. Without the five best trades: +$2,245 over 2.7 years (t 0.51). Top five cut by 25/50/75%: +$11.43 /
+$8.74 / +$6.04 a day. 9 Apr 2025 (+$2,207): the tariff-pause day (12.6% range); a call bought at $7.53 was worth $29.62 at
15:44. Such days happen a few times a year at most and cannot be predicted. 11 losses in a row: unlucky but normal (95th
percentile 11). Calm/volatile/trending/sideways: no stable pattern. At measured costs t ≈ 1.0. After correction for ~30
tests: not significant (t 1.73 vs 3.14). Exits late/failing: robust. **No edge established.**

## H. Trading costs

$9.41 per round trip per contract = half the spread at entry ($4.06) + half at exit ($5.29) + $0.06 fees, measured from the
recorded bid/ask on 316 trades. No separate slippage beyond the spread (paper fills at the quoted ask/bid); commissions beyond
$0.03 a side not included. Opening hour $11.58; after 14:00 $6.12; fast markets $10.97 vs calm $7.34; stop exits $11.43,
target exits $6.63. Every bot at four cost levels: `baseline_*.md` "Execution stress" tables (1, 2, 3, 5, 10 cents).
Profit factor, expectancy and drawdown at the higher cost levels were **not** recomputed for every bot (per-day results only).

## I. £1,000 account

- **Options: not appropriate.** Minimum one contract = $312 median to $925 (25-73% of the account); the whole premium can be
  lost; worst historical trade −$629. At measured costs: 58% chance of being unable to afford a contract within a simulated
  year. Sensible minimum: about $14,000 (a bad trade = 2% of the account).
- **Shares:** about 2 shares; costs ≈ $0.04 a trade. Simulated year at £1,000: median **+$83 (~£65)**, 5% −$163, 95% +$369;
  chance of a losing year 30%; 20% drawdown 5%; losing streak typically 6, up to 9. On 2022-2026 trades only: median +$262
  (~£205), chance of a loss 7%. Worst historical trade −7% of the position; historical maximum drawdown −43% (2016-2020).
  Suggested limits if it were ever traded: one position at a time, the 10 ATR stop always on, stop for the week after a −5%
  week, stop the strategy at −15% from its peak pending review.
- **Is it worth it?** At about £65-205 a year on £1,000, the risk is modest but so is the reward; the main value of trading
  it small would be measuring real fills, not income.

## J. UK broker and instrument

- Many UK brokers cannot sell US-domiciled ETFs such as QQQ to retail clients because they lack a UK/EU key information
  document; existing holders can usually only sell. Some platforms allow "sophisticated" clients. **Must be confirmed with
  the chosen broker.** ([justETF](https://www.justetf.com/uk/news/etf/us-domiciled-etfs.html),
  [Interactive Brokers](https://www.interactivebrokers.com/support/faq/content/1136192471))
- London-listed Nasdaq-100 UCITS ETFs trade in London hours (about 08:00-16:30 UK = 03:00-11:30 New York): the strategy's
  10:00-15:45 NY window is mostly outside them. **Not suitable without a full re-test, and probably not suitable at all.**
- A spread bet on the Nasdaq-100 trades during US hours, is commission-free (the cost is in the spread), and profits are
  generally free of capital gains tax for UK residents (individual circumstances vary). But it is leveraged (IG lists a 5%
  margin and a minimum of 0.10 per point on its US Tech 100), and FCA figures cited by providers say about 80% of retail
  accounts lose money. ([IG US Tech 100](https://www.ig.com/uk/ig-indices/us-tech-100),
  [CMC Markets](https://www.cmcmarkets.com/en-gb/spread-betting/what-is-spread-betting))
- **The strategy has not been tested on the Nasdaq-100 index or on any spread-bet price.** Before using a substitute, the
  whole strategy must be re-run on that instrument's own minute data and costs (not available in our data feed).

## K. PR #39

Full review: `PR39_REVIEW.md`; diff: `PR39_code_diff.txt`; records: `CHANGE_CONTROL.md` CC-001 to CC-004. 14 tests pass.
17-18 Nov replay identical; 19-20 Nov change only because of the stale-quote guard (with it off, the real ledgers reproduce
exactly). Bots live on main today make identical trades with the new code. Remaining risk: a bot may wait for a fresh quote
before selling. **Not merged; needs explicit approval.** The temporary research runner will be removed before any merge.

## L. What has been changed

See `CHANGES.md`. In short: the only trading-rule change that ever went live on an existing bot is the main bot's "stop
after 2 losses" (14 Nov). Everything else live is new comparison bots, display, messages and reports. A trailing exit was
applied to the main bot on 17 Nov and reverted before it went live. Four items are pending in PR #39. Unrecorded changes are
now recorded there.

## M. Not tested

Real broker order handling (rejections, partial fills, acknowledgements, reconnection); option prices before 2024 (no data);
the Nasdaq-100 index or spread-bet prices; the shares bot's real fills (it books candle closes); a validated "edge has gone"
switch; profit factor and drawdown at every cost level for every bot; the 2022 hypothesis by any test other than price data;
named news events beyond the price facts.

## N. Before any real money

1. 60 trading days and 40 completed trades of the shares bot on paper, with the daily validation log showing no unexplained
   deviation (CC-004, needs PR #39).
2. Corrected P&L only (fresh quotes; CC-001).
3. A pre-registered test of the "edge has gone" switch, and a written rule for stopping the strategy.
4. The tradeable UK instrument identified with a broker, and the strategy re-tested on that instrument's data and costs.
5. A broker paper account connected and tested: orders, rejections, partial fills, reconnection, kill switch.
6. Account-level limits in code: one position, daily and weekly loss stops, drawdown stop, emergency stop that halts all
   trading when data or execution is unreliable.

## O. Final ratings

| Bot | Rating |
|---|---|
| Main, original | E (kept only as research benchmarks) |
| Trail, trail+trend, his style, skip weak, combo, picks like him, his clone, brakes, 5-minute, opening move | E: discontinue |
| One-a-day options | C: weak, paper observation only; not for a £1,000 account in any case |
| Shares one-a-day | B: promising but regime-dependent and unproven going forward; not ready for real money |

## P. Recommended next steps, in order

1. **Approve or reject PR #39** (fixes the data faults that corrupt the paper record; adds the daily validation). Evidence:
   CC-001/CC-002 incidents and tests.
2. **Approve or reject CC-005** (retire the 10 non-benchmark fast bots). Evidence: section C, `AUDIT2_REPORT.md` section 1.
3. **Run the shares bot's 60-day / 40-trade validation** without changing it. Evidence needed: forward results.
4. **Pre-register and test the "edge has gone" switch** (section F). Evidence so far: it would have cut 2020's loss by 70%.
5. **Ask a UK broker** whether QQQ is available to you; if not, obtain Nasdaq-100 minute data and re-test the strategy on it.
6. Only then consider a broker paper account and, much later, a very small live test.
