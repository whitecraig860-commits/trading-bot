# Trading system audit and research report (11 Nov 2026)

Author: Claude (acting as researcher/auditor). Everything here is backtest or paper; nothing places real-money trades.
Pre-registered protocol: [`research/PROTOCOL.md`](PROTOCOL.md) (committed before the results, `be757ee`).

## Executive summary

**There is no evidence of a trading edge anywhere in the system yet.** Both pre-registered studies failed:

| Study | What was tested | Result | Verdict |
|---|---|---|---|
| 1. Intraday trend signal (the QQQ "trend worker") | Same signal and exits, on the SHARE, six markets, Mar 2024 to Nov 2026 | **−0.231R per trade over 3,318 trades (t = −10.6)**; negative on every market and both periods | No edge; the signal is worse than random |
| 2. 55-day swing breakout | Point-in-time S&P 500 (583 shares incl. 79 later removed), 2016 to Nov 2026, rules unchanged | Holdout 2024-26: **−0.027R per trade over 2,938 trades** at 0.25%/side; random entries with the same exits did +0.034R | Fails 7 of 8 pre-set checks |

The options were never the root cause: the intraday signal loses money on the share itself, and options add time decay
and spread on top. The breakout's earlier "+0.55R" came from a hand-picked list of past winners (NVDA, META, AMZN and
so on), which is hindsight selection.

**Can £30 a day be reached?** Not with anything in this repository. With an evidence-based strategy, it's a question
of capital, not cleverness: at a realistic 8–12% a year, £30 a trading day (~£7,500 a year) needs roughly £60,000–£95,000
of capital (section 7). Increasing risk on £1,000 to reach it would very likely end in ruin.

## 1. What the system is (audit summary)

Full component inventory: the audit doc ("Trading Bot System Audit", 7 Nov) and `README.md`. Key facts checked today:

- `main` = PR #18 merged plus state commits. PR #19 (QQQ trend worker as the only trader) is **open and not merged**;
  it was not touched. This research is on a separate branch (`claude/research-breakout`).
- Live-money safeguard: `scalper.py:564` hard-codes `TradingClient(..., paper=True)`. The swing account is a JSON file.
  Nothing in the repository can place a real-money order.
- **No AI makes trading decisions.** There is no language model, ML model or trained classifier in the code. "Brain",
  "confidence", "learning" are rule-based scores and t-statistic filters written in Python. So the requested
  "AI-only vs indicator-only vs AI-assisted" comparison has nothing to compare yet: every decision is indicator-based.
- Data: Yahoo (daily, 5-minute), Alpaca IEX live 1-minute, Alpaca SIP history (research), Alpaca real 1-minute option
  trade bars (since 2024; no historical bid/ask quotes), SEC EDGAR, RSS news, trumpstruth.org.
- State lives in JSON/CSV files committed to a public GitHub repository.

### Where money is being lost
| Component | Evidence | Cause |
|---|---|---|
| Options scalper (all versions) | Old rules −£19,023 (model); later rules −£2,496 (model) and ~break-even with real prices over 22 months | Entry signals without edge + option spread + time decay |
| QQQ trend worker | Real option prices: −£2,515 (QQQ) and every other market negative | Study 1: the entry signal itself has negative expectancy |
| Swing breakout | Point-in-time test: no edge after costs out of sample | Study 2: entries no better than random; result driven by 2016–17, 2020 |
| Intraday pulse | Never qualified a signal | Correctly found nothing |
| Insider copier | Never opened a trade; no backtest exists | Unknown; no historical filings stored |

### Can the existing backtests be trusted?
- **Old swing backtest: no.** Fixed hand-picked watchlist (survivorship + selection bias), no true holdout (settings
  chosen after seeing the full 10 years), 0.1% costs only.
- **Old scalper share-price backtest: no.** Ignored option costs and decay; tuned on one month.
- **Option model backtest (`optionbt.py`): partly.** Black-Scholes prices were ~35% off real prices (`optioncheck.py`);
  even then, the variants were chosen using 2026 data, so its +£163 / +£790 are in-sample.
- **This report's studies: much better, not perfect.** Point-in-time universe, three cost levels, random-entry null,
  untouched holdout. Residual issues are listed in section 6.

## 2. Study 1: why the intraday trend bot loses

Script: [`research/trend_signal_check.py`](trend_signal_check.py). Signal and exits identical to PR #19's
`trendworker.py` (copied unchanged to `research/trend_snapshot.py`); traded on the share with 0.02%/side (ETFs) or
0.05%/side (NVDA, TSLA) cost. Alpaca SIP 1-minute bars, Mar 2024 to Nov 2026.

| Market | Trades | Won | Avg win | Avg loss | Expectancy | t | 2024-25 | 2026 |
|---|---|---|---|---|---|---|---|---|
| QQQ | 509 | 36% | +1.30R | −1.06R | −0.208R | −3.7 | −0.255R | −0.120R |
| SPY | 290 | 35% | +1.29R | −1.11R | −0.267R | −3.5 | −0.280R | −0.237R |
| IWM | 606 | 33% | +1.33R | −1.05R | −0.273R | −5.4 | −0.262R | −0.299R |
| GLD | 292 | 33% | +1.30R | −1.18R | −0.373R | −4.9 | −0.341R | −0.408R |
| NVDA | 823 | 37% | +1.25R | −1.02R | −0.170R | −3.9 | −0.210R | −0.081R |
| TSLA | 798 | 34% | +1.29R | −1.00R | −0.213R | −4.9 | −0.222R | −0.193R |
| **All** | **3,318** | **35%** | | | **−0.231R** | **−10.6** | | |

**Diagnosis.**
1. *Insufficient edge (cause A): confirmed.* Forward returns after an entry are no better, and usually worse, than
   the trend filter alone (QQQ 60-minute: signals −0.4 bp vs trend filter +1.4 bp; TSLA 30-minute −2.8 bp vs +1.5 bp).
   The trigger ("strong candle at a new high", "pullback held") tends to fire at short-term exhaustion.
2. *Intraday trend persistence is tiny.* Even the trend filter alone is worth +0.3 to +2.8 bp over 60 minutes,
   smaller than the round-trip cost of an option and similar to the cost of trading the share.
3. *Options (cause B) make it worse but aren't the root cause.* Spread and theta add to a negative base.
4. *Exits clip winners.* Average win is only +1.3R against a 2R target because the break-even/trail rules exit
   early; that's a design choice, not the main problem.

This matches the research: retail 0DTE option buyers lost heavily, mostly to transaction costs
([Beckmeyer, Branger & Gayda 2023](https://www.cfr-cologne.de/download/workingpaper/cfr-25-09.pdf)), and 97% of
people who day-traded for more than 300 days lost money
([Chague, De-Losso & Giovannetti 2019](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)).

**Recommendation:** retire the intraday trend worker and the options scalper as money-making strategies. Do not
merge PR #19 for trading purposes.

## 3. Study 2: the swing breakout, tested properly

Script: [`research/breakout_study.py`](breakout_study.py). Rules from `bot.py` unchanged (55-day high above the
200-day, score ≥ 50, next-open entry, 2 ATR stop, trail under the 20-day low). Universe: S&P 500 members as of each
signal date from the [fja05680/sp500](https://github.com/fja05680/sp500) dataset; 583 of 584 tickers that were members
since 2016 have Alpaca SIP data, including 79 of the 80 later removed. Eligibility at the signal: member, price ≥ $5,
20-day average turnover ≥ $10m.

| Period | Trades | Won | Avg win | Avg loss | PF | Expectancy (0.10% / 0.25% / 0.50% per side) |
|---|---|---|---|---|---|---|
| Development 2016-21 | 6,389 | 35% | +2.24R | −0.98R | 1.22 | +0.217 / **+0.139** / +0.008 |
| Validation 2022-23 | 1,783 | 29% | +2.03R | −0.97R | 0.87 | −0.024 / **−0.090** / −0.200 |
| **Holdout 2024-26** | **2,938** | 30% | +2.27R | −1.00R | 0.96 | +0.041 / **−0.027** / −0.142 |

By year at 0.25%: 2016 +0.72R, 2017 +0.53R, **2018 −0.46R**, 2019 +0.09R, 2020 +0.26R, 2021 +0.09R,
**2022 −0.46R**, 2023 +0.18R, 2024 +0.12R, 2025 +0.03R, **2026 −0.29R**. By regime: SPY above its 200-day +0.068R,
below −0.069R. Average hold 24–29 days. Longest losing run 18–24 trades.

Robustness (holdout, 0.25%): without the 10 best trades −0.084R; without the 10 best shares −0.092R.
**Random-entry null** (same shares, same exits, same number of entries, 3 seeds): development +0.191R, validation
−0.033R, holdout +0.034R. Real signals: +0.139R, −0.090R, −0.027R. **The breakout entry adds nothing over a random
entry**; what positive result exists comes from the trailing exit plus the market's rise (SPY +64.5% over the
holdout, versus a £1,000 cash-limited replay of the strategy falling to £472, worst fall 53%).

**Pre-registered verdict: FAIL** (7 of 8 checks failed: expectancy, profit factor, robustness to removing winners
and best shares, beating random entries, consistency across periods, drawdown).

Why it fails, in plain terms: buying S&P 500 shares at a 55-day high is one of the most widely known signals there is.
Any edge it had in individual large-cap shares is small, and it doesn't survive realistic costs. Momentum works far
better as a *portfolio* (cross-sectional ranking, monthly rebalancing) and across asset classes than as single-stock
breakout entries (section 5).

## 4. AI: what it can and can't do here

- The system has no AI decision-maker today; that's fine. Gu, Kelly & Xiu
  ([2020](https://nber.org/papers/w25398)) show tree models and neural networks can improve return forecasts, but on
  large panels (tens of thousands of shares, decades of data) and the gains come mostly from the same known signals
  (momentum, liquidity, volatility). With one person's data budget, a complex model mostly finds noise.
- Backtest overfitting is the main hazard. Bailey, Borwein, López de Prado & Zhu
  ([2017](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting))
  show that hold-out testing alone is unreliable when many variants are tried; Harvey, Liu & Zhu
  ([2016](https://nber.org/papers/w20592)) argue new findings need t > 3, not 2. This project has tried 50+ variants
  of the scalper and trend worker on the same data, which is exactly the situation they warn about.
- Where AI could genuinely help later: (1) regime classification as a *filter* on a strategy that already has an edge,
  validated out of sample; (2) news/earnings text classification to avoid event risk. Both only after a base edge exists.

## 5. Quantitative research summary (what has credible evidence)

| Approach | Evidence | Fit for this project |
|---|---|---|
| Time-series momentum (trend following across asset classes) | Positive 12-month TSMOM in all 58 futures markets studied ([Moskowitz, Ooi & Pedersen 2012](https://papers.ssrn.com/abstract=2089463)); profitable in every decade since 1880 across 67 markets ([Hurst, Ooi & Pedersen 2017](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)) | **Best candidate.** Works at monthly horizons on diversified ETFs (equity, bond, gold, commodity). Holding periods are months, not minutes. |
| Cross-sectional momentum (buy recent winners, avoid losers, monthly) | One of the most replicated anomalies (Jegadeesh & Titman 1993 and many follow-ups); crashes after bear markets | Candidate for a share portfolio; needs a point-in-time universe (now built) |
| Pairs/statistical arbitrage | ~11% a year 1962–2002 but declining since ([Gatev, Goetzmann & Rouwenhorst 2006](https://econpapers.repec.org/RePEc:oup:rfinst:v:19:y:2006:i:3:p:797-827)) | Low priority: crowded, needs shorting, fast execution |
| Volatility selling (variance risk premium) | Implied volatility usually exceeds realised ([Carr & Wu 2009](https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:3:p:1311-1341)) | The edge is on the *seller's* side, with crash risk; not suitable for £1,000 or buying options |
| Buying short-dated options | Retail buyers lose mostly to costs (Beckmeyer et al. 2023) | **Stop** |
| Intraday day trading | 97% of persistent day traders lost money (Chague et al. 2019) | **Stop** |

## 6. Limitations of this report

- The S&P 500 universe still misses 1 of 80 removed members; companies that went bankrupt *before* 2016 aren't relevant.
- Costs are modelled as a percentage per side; there are no historical bid/ask quotes for shares or options in the data.
- Stops fill at the stop price unless the day opens beyond it (intraday gaps through stops are partly understated).
- Study 1 covers 2.7 years (Alpaca 1-minute history); Study 2 covers ~10 years.
- Both studies test the *existing* rules only; they say nothing about other strategies (section 8).

## 7. The £30-a-day target: capital, not cleverness

£30 × ~250 trading days ≈ £7,500 a year. Required capital at a given *net* annual return, and what a realistic
diversified trend strategy also brings (illustrative, based on the long-run studies in section 5: volatility ~10–15%
a year, worst falls ~20–30%, some losing years):

| Net return a year | Capital needed for ~£7,500 a year | Typical worst fall at that capital (−25%) | £1,000 would make a year |
|---|---|---|---|
| 5% | £150,000 | −£37,500 | £50 |
| 8% | £94,000 | −£23,500 | £80 |
| 12% | £62,500 | −£15,600 | £120 |
| 20% (top-decile, rarely sustained) | £37,500 | −£9,400 | £200 |

UK tax: gains outside an ISA/SIPP are subject to Capital Gains Tax above the annual exempt amount; trading through
an ISA avoids it (check current HMRC rules). GBP to USD conversion typically costs 0.15–0.5% each way at retail
brokers, which matters for frequent trading. Raising risk per trade to force £30 a day from £1,000 means risking ruin:
in Study 2 the longest losing run was 22 trades, which at 10% risk a trade is a near-total loss.

## 8. Recommended architecture and plan

The five-worker design you described is sound **as a structure**, but building it around strategies with no edge
would only add complexity. Proposed order (each step must pass its own pre-registered test before the next):

| Priority | Item | Type | Status |
|---|---|---|---|
| 1 | Keep the research harness (point-in-time universe, cost levels, random null, holdout, pre-registration) as the standard test for every idea | Essential | **Built** (`research/`) |
| 2 | Retire intraday trend worker and options scalper as money-making strategies; leave the code in place, off | Essential | Recommendation (needs your approval; PR #19 left untouched) |
| 3 | Test diversified time-series momentum on liquid ETFs (SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, DBC, VNQ...), monthly rebalance, volatility-scaled, pre-registered thresholds, holdout | Essential next research | Not started |
| 4 | Test cross-sectional momentum on the point-in-time S&P 500 (top decile by 12-1 month return, monthly) with the same protocol | Next research | Not started |
| 5 | Worker 4 (risk engine) + Worker 5 (paper execution ledger with expected vs actual fill) + dashboard, built around whichever strategy passes | Build after 3/4 | Not started |
| 6 | Worker 1 (regime) and Worker 3 (validator) as filters, each proven to add value out of sample | Optional, later | Not started |
| 7 | Privacy: move state out of the public repo | Essential before real money | Not started |

Deliverables 6 and 7 (paper-trading system and dashboard) are deliberately **not** built yet: there's no validated
strategy for them to trade. Building them now would produce a dashboard of a losing system.
