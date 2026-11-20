# Audit part 2: report (20 Nov 2026)

Pre-registered tests: `research/AUDIT2_PROTOCOL.md`. Full output: `audit/audit2_output.txt`. Costs: `audit/cost_breakdown.md`.
Stale quotes: `audit/stale_quotes.md`. PR #39: `audit/PR39_REVIEW.md`. Change records: `audit/CHANGE_CONTROL.md`.

## Section 1. The 12 fast bots: can an independent market-condition filter rescue the entry?

Three filters fixed in advance (no tuning), each known before the signal. Share of signals where QQQ moved the right way
after 10 minutes, and per-trade result at 5 cents a side:

| Filter | 2024-25: right | per trade (5c) | 2026: right | per trade (5c) | Rescue? |
|---|---|---|---|---|---|
| none (main bot) | 49.2% | −$12.07 | 49.6% | −$13.39 | no |
| R1 high-volatility regime | 49.3% | −$12.38 | 50.9% | −$11.88 | no |
| R2 wide opening range | 49.9% | −$12.69 | 48.6% | −$14.51 | no |
| R3 trend regime, with the trend | 51.2% | −$12.39 | 51.4% | −$11.69 | no |

**Conclusion:** no filter lifts the entry meaningfully above a coin flip, in any condition. There is no statistically
defensible edge to recover. **Recommendation: retire all 12 permanently from trading**; keep their code, results and reports.

## Section 2 (report C). One-a-day options: forensic

| Test | Result |
|---|---|
| Baseline | 480 trades, +$14.12/day, t 1.73, total +$9,461 |
| **Without the 5 biggest winners** | **+$2,245 total, +$3.35/day, t 0.51** |
| Top 5 cut by 25% / 50% / 75% | +$11.43 / +$8.74 / +$6.04 a day (t 1.53 / 1.26 / 0.91) |
| What made the top 5 | huge days: 9 Apr 2025 (tariff-pause day, 12.6% range, +$2,207), 20 Nov 2025, 10 Oct 2025, 5 and 9 Jun 2026; best move 9-18 ATR vs 2.2 for a median trade; options bought at $3-7 rose to $15-30 |
| Next 20 trades all on unfavourable days (5,000 runs) | median −$136, 5% −$1,403, 95% +$2,013; **56% chance of a loss** |
| The 11-loss streak | 5 Aug to 2 Sep 2026, −$1,025, quiet days (median range 1.09% vs 1.37%), every one closed at 15:44 without a big move |
| Expected longest losing streak in a year | median 7, 95% 11, 99% 14: the 11 was unlucky but normal |
| Calm / volatile / trending / sideways days | +$22.51 / +$12.42 / +$19.94 / +$21.41 a day (no stable pattern) |
| At realistic costs (measured ~$9.41 a round trip ≈ 5 cents a side) | +$8.39/day, t 1.03; at 7 cents +$5.52; at 10 cents +$1.23 |
| **Multiple testing** (~30 variants tested in Studies 5-13) | Bonferroni line t ≥ 3.14; **t 1.73 is NOT significant** |
| Stress (each one thing) | 1 min late +$13.13, 2 min late +$10.72, 10% rejected +$13.84, daily 1-hour outage +$10.55, settings ±20% between +$12.20 and +$14.59 |

**Conclusion:** the stress tests do not break it, but its profit rests on a handful of extreme days, it is not significant
after correcting for the number of strategies tested, and at realistic costs t falls to about 1. **Rating lowered from B to
C (WEAK): no convincing evidence of an edge yet.** Keep it on paper only as an observation.

## Section 3 (report B). Shares one-a-day 2016-2026: forensic

**First correction to my own earlier report:** dollar results on 100 shares are not comparable across years (QQQ rose from
~$111 to ~$699). As a % of price per trade, after 1 cent a share a side:

| Year | Trades | Win% | Avg return per trade | Sum for the year | QQQ volatility (20-day) |
|---|---|---|---|---|---|
| 2016 | 176 | 47% | −0.033% | −5.9% | 0.81% |
| 2017 | 187 | 47% | −0.017% | −3.1% | 0.57% |
| 2018 | 192 | 54% | +0.013% | +2.5% | 1.03% |
| 2019 | 176 | 53% | +0.006% | +1.0% | 0.90% |
| 2020 | 196 | 51% | −0.101% | **−19.8%** | 1.55% |
| 2021 | 196 | 59% | +0.017% | +3.4% | 1.00% |
| 2022 | 209 | 57% | +0.144% | +30.1% | 1.97% |
| 2023 | 195 | 57% | +0.106% | +20.6% | 1.09% |
| 2024 | 188 | 60% | +0.092% | +17.3% | 0.99% |
| 2025 | 177 | 58% | +0.075% | +13.3% | 1.15% |
| 2026 | 165 | 57% | +0.080% | +13.2% | 1.10% |

So: **2016-2021 roughly zero to negative (2020 badly negative), 2022-2026 consistently positive.** This is a clear break,
not noise.

What differs (medians):

| | Losing years (2016, 17, 20) | Flat (2018, 19, 21) | Winning (2022-26) | Winning trades | Losing trades |
|---|---|---|---|---|---|
| Volatility 20-day | 0.85% | 0.97% | 1.18% | 1.08% | 1.05% |
| Prior 20-day trend strength | 0.71 | 0.48 | 0.31 | 0.41 | 0.52 |
| Day range | 1.13% | 1.33% | 1.53% | 1.54% | 1.15% |
| Opening gap | 0.08% | 0.10% | 0.07% | 0.10% | 0.06% |
| Volume first 30 min vs normal | 0.92 | 0.98 | 0.98 | 0.95 | 0.97 |
| Entry time | 10:19 | 10:19 | 10:19 | 10:19 | 10:19 |
| Room to the previous day's high/low (ATR) | 0.41 | 0.51 | 0.54 | **0.17** | **0.89** |
| Minutes held | 315 | 315 | 325 | 315 | 325 |
| Exits at 15:44 / trail / safety stop | 88/11/2% | 87/12/2% | 91/8/1% | 82/18/0% | 97/0/3% |

- Winning trades are the ones where the day keeps moving (best move 3.5 ATR vs 0.8). Losing trades entered further inside the
  previous day's range (0.89 ATR from yesterday's high/low): they ran into yesterday's extremes, i.e. resistance/support.
  This is an observation made after the fact, not yet a tested rule.
- Volume, entry time and gaps barely differ. Direction (calls vs puts, with or against the trend) barely differs.
- 2020 was the most volatile year and the worst, so "more volatility = better" does not hold.

**Could it have seen the bad periods coming?** The pre-registered test (average range of the last 20 days, threshold set on
one period, tested on the other) **failed in both directions**: on 2022-26 the trades it would have dropped did as well as
the ones kept, and on 2016-21 the trades it kept did worse. So, with the measures tested, **no: the strategy could not
have identified the unsuitable conditions before entering.**

**My best explanation (a hypothesis, not proven):** the break coincides with the arrival of daily-expiring (0DTE) index and
QQQ options in 2022, whose dealer hedging is widely reported to push prices further in the direction of the day's move.
If that is the cause, the edge depends on a market structure that could change again. I cannot prove this with price data
alone. It means the 2022-2026 record should not be assumed to continue.

## Section 4 (report A). Stress tests for the two promising bots (each changes one thing)

| Scenario | One-a-day options (per day, t) | Shares 2016-26 (per day on 100 shares, t) |
|---|---|---|
| Baseline | +$14.12, 1.73 | +$13.46, 2.96 |
| Entry 1 min late | +$13.13, 1.61 | +$12.51, 2.75 |
| Entry 2 min late | +$10.72, 1.47 | +$11.48, 2.60 |
| 10% of orders rejected | +$13.84, 1.84 | +$13.58, 3.15 |
| 1-hour outage every day (blind) | +$10.55, 1.45 | +$13.56, 2.91 |
| Range buffer 0.24 / 0.36 | +$12.20 / +$14.59 | +$13.59 / +$13.67 |
| Trail 3.2 / 4.8 ATR | +$13.59 / +$13.15 | +$13.18 / +$13.18 |
| Stop 8 / 12 ATR | +$14.01 / +$14.06 | +$13.26 / +$13.18 |
| Noise band ×0.8 / ×1.2 | +$13.95 / +$13.35 | +$13.04 / +$12.92 |
| Costs 2 / 5 / 10 cents | see Section 2 | +$11.95 / +$7.42 / −$0.14 |
| Volatile days only / calm days only | +$12.42 / +$22.51 | +$1.12 / +$20.57 |
| Longest losing streak | 11 (expected 95%: 11) | 9 |

Both are insensitive to the settings (no sign of over-fitting to the exact numbers) and survive late fills, rejected
orders and outages. Duplicate positions, missed exits and not stopping: see `audit/PR39_REVIEW.md` (one flaw found and
fixed: CC-003). Broker behaviour cannot be tested without a connected broker paper account.

## Section 5 (report D). A £1,000 account (about $1,270)

**One-a-day options: NOT affordable safely.**
- One contract (the minimum) costs a median $312, up to $925 (25% / 73% of the account). The most you can lose on a trade
  is the whole premium. The worst historical trade lost $629 (half the account).
- 5,000 simulated years at one contract on $1,270: **47% chance of being unable to afford a contract within a year; 77%
  chance of a 50% drawdown.**
- Capital for a bad trade (5th percentile, −$284) to be 2% of the account: about **$14,200**; to be 5%: about $5,700.

**Shares one-a-day: affordable, but the money is small and the drawdowns are long.**
- £1,000 buys about 2 QQQ shares (fractional). Costs: about $0.04 a trade (negligible).
- Per trade on $1,270, 2016-2026: average +$0.45, worst −$88 (−7%), worst week −$111; **maximum drawdown −$546 (−43%)**,
  mostly 2016-2020; longest losing streak 9 trades (about −$70).
- **Expected about +$85 a year (~£67) on £1,000**, if the 2016-2026 average holds; about +£110-170 a year if only the
  2022-2026 rate holds. Nowhere near £30 a day.
- Risk per trade is set by the 10 ATR safety stop: in practice up to about 7% of the position on the worst day.
- **Can UK retail buy QQQ?** Most UK brokers do not offer US-listed ETFs such as QQQ to retail clients (they lack the
  required UK/EU key information document). The alternatives (a London-listed Nasdaq-100 fund, which trades in London hours;
  or a spread bet / CFD on the Nasdaq-100, which has different costs and leverage) are not the instrument that was tested.
  This must be checked with a specific broker before anything else.

## Section 6 (report E). The real cost of trading

- 316 paper option trades: **average $9.41 per round trip** (median $8.56): half-spread $4.06 at entry, $5.29 at exit.
  Highest at the open (09:00 hour $11.58) and lowest after 14:00 ($6.12); higher in fast markets ($10.97 vs $7.34 calm);
  **stop exits cost the most ($11.43; trail exits $14.04)** because spreads widen when price is moving against you; target
  exits $6.63. Puts a little dearer than calls.
- Effect on history (one contract): every fast bot loses $40-200 more a day. The one-a-day options bot at ~5 cents a side:
  +$8.39/day (t 1.03). The shares bot at £1,000 size: negligible (about $0.04 a trade).
- Caveat: the history's 1-cent prices were trade prints, already partly inside the spread, so the true effect lies between
  the 1-cent and the measured figures.
- 11 of the 316 paper trades used frozen quotes; recorded P&L of those is unreliable (CC-001).

## Section 7 (report F). PR #39

See `audit/PR39_REVIEW.md`: three fixes (CC-001 stale quotes, CC-002 holiday check, CC-003 one-a-day options carried over a
restart) plus CC-004 (daily validation). 14 tests pass. Existing strategies verified unchanged on synthetic replays; on
real recorded days, 17-18 Nov identical, 19-20 Nov changed only by the stale-quote guard (shown by switching it off).
**Not merged: waiting for the user's explicit approval.**

## Section 8 (report G). Plan for the two remaining candidates

1. **Shares one-a-day (B, PROMISING, regime-dependent):** 60 trading days and 40 trades on paper with the daily validation
   log (CC-004); a pre-registered test of the "room to yesterday's high/low" observation on 2016-2021 vs 2022-2026; a
   pre-registered test of the 0DTE-era hypothesis (does the edge appear when QQQ daily expiries started?); confirm what
   instrument a UK account can actually trade and re-test on that instrument's prices and costs.
2. **One-a-day options (C, WEAK):** keep on paper only to observe; no further development unless the paper record and a
   fresh out-of-sample period (2027) show the effect independently.
3. **Retire the 12 fast bots** from the live page (keep code and reports). Needs the user's agreement.

## Section 9 (report H). What still prevents real money

1. No bot has a meaningful paper record (shares: 4 days; options: none). Requirement: 60 trading days and 40 trades, matched
   daily against the tested rules.
2. The shares edge is regime-dependent (nothing from 2016 to 2021) and the cause is not established.
3. The one-a-day options result is not statistically significant once the number of tests is accounted for, and depends on a
   few extreme days.
4. A £1,000 account cannot safely hold one option contract. In shares, the expected return is about £67-170 a year, with
   drawdowns of up to ~40% seen in history.
5. The tested instrument (QQQ) is probably not available to a UK retail account; the substitute must be tested.
6. No broker is connected: order rejection, partial fills, reconnection and real fills are untested.
7. The data feed can freeze individual option quotes for minutes (fix pending in PR #39).

**Honest bottom line: neither bot is ready for real money.**
