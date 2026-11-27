# Change control

Every change to any bot is recorded here **before** it is made, with the eight fields below, and then completed with the
results. Strategy changes also need a pre-registered protocol in `research/`. A change is only called "fixed" when the
listed tests pass. No setting is changed repeatedly to improve historical profit.

Template:

| Field | |
|---|---|
| 1. Problem | |
| 2. Evidence | |
| 3. Proposed change | |
| 4. Expected improvement | |
| 5. Possible negative effects | |
| 6. Tests | |
| 7. Results | |
| 8. Decision | accepted / rejected / pending the user's approval |

---

## CC-001: bots traded on stale option quotes (all options bots)

| Field | |
|---|---|
| 1. Problem | On 19 Nov the data feed served the previous afternoon's option quotes until 10:30 NY. At 10:32:36 the main bot bought a 662 put at 9.68, a quote stamped 2026-11-18 16:14:59; the real quote (bid 8.21) arrived 5 seconds later, recorded as a −$147 loss that never happened at that price. |
| 2. Evidence | `state/quotes/2026-11-19-1031.csv.gz`, 662P rows 10:31:51-10:33:06: quote_time 2026-11-18 16:14:59 until 10:32:36, then 10:32:40. |
| 3. Proposed change | `tracker/qqqbot.py`: new `_fresh(q, now)`; a quote counts only if stamped within the last 60 s (`FRESH_SECONDS`). Used for the entry ask and the exit bid. Switch: `FRESH_QUOTES_ONLY`. |
| 4. Expected improvement | No trades or exits on prices that are not current. |
| 5. Possible negative effects | If the feed's time stamps lag on quiet contracts, a bot could skip a valid entry or delay an exit until a fresh quote arrives (bounded by the 10-minute limit and the 15:55 flat time). If a quote has no time stamp, behaviour is unchanged. |
| 6. Tests | (a) `tests/test_fixes.py`: a stale quote blocks the entry, a fresh one allows it; a stale bid does not trigger an exit. (b) Replay of the real recorded prices for 17 and 18 Nov: identical trades to the live bot. (c) 19 Nov replay: the 10:32 stale trade is no longer taken. |
| 7. Results | (a) pass. (b) 17 and 18 Nov identical (6/6, 8/8 trades). (c) 19 Nov stale trade blocked. **Side effect found and investigated:** 20 Nov also changes (+$179 recorded becomes −$142 in the replay); with the guard off the replay matches all 8 real trades, and the difference is a +$320 trade bought on a quote frozen for 5 minutes, i.e. a fake win. 11 of 316 paper trades used stale quotes (`audit/stale_quotes.md`). The side effect is the intended behaviour. |
| 8. Decision | Pending the user's approval (PR #39). |

## CC-002: the recorder stopped itself on a trading day (all bots)

| Field | |
|---|---|
| 1. Problem | On 19 Nov the recorder stopped twice with "No quotes dated today after 30 minutes (market holiday?)" while the market was open, because the option quotes were stale. All bots missed 09:30-10:30. |
| 2. Evidence | Recorder run logs 44549813350 and 44540052811; first trade of the day at 10:32. |
| 3. Proposed change | `tracker/recorder.py`: after 30 minutes of stale quotes, stop only if QQQ shares have no bars today (a real holiday); otherwise keep waiting, re-checking every 5 minutes. The decision is a small function, `holiday_decision`, so it can be tested. |
| 4. Expected improvement | No lost trading time when the option feed is late. |
| 5. Possible negative effects | On a real holiday the share-bar request is made every 5 minutes for the rest of the run (harmless). If the share-bar request fails, it keeps waiting rather than stopping (safer than missing a day). |
| 6. Tests | `tests/test_fixes.py`: stale quotes + QQQ trading -> wait; stale quotes + no QQQ bars -> stop; fresh quotes -> go; before 30 minutes -> go. |
| 7. Results | Pass (see `audit/PR39_REVIEW.md`). |
| 8. Decision | Pending the user's approval (PR #39). |

## CC-003: the one-a-day options bot would be force-sold at every recorder restart

| Field | |
|---|---|
| 1. Problem | The recorder restarts about every 200 minutes. `PaperBot.finish()` closes any open option at a restart ("recorder restart"). The one-a-day options bot holds for hours (median 5.5 h in history), so its trade would be sold around 12:50 NY and never re-bought: live results would not match its tested rules. The shares bot already carries its trade over. |
| 2. Evidence | `tracker/qqqbot.py` `finish()`; `tracker/sharesbot.py` `finish()` keeps the trade; history median hold for this strategy 5.5 hours (Study 6). |
| 3. Proposed change | In `finish()`, a bot in "follow" mode keeps its open option (saved in its state file) and the next run resumes managing it; it is still closed at 15:55 or when the shares bot exits. No other bot changes. |
| 4. Expected improvement | Live one-a-day options trades follow the tested exit rules. |
| 5. Possible negative effects | During the 1-2 minutes between runs the option is not watched (measured gaps: up to about 2 minutes of start-up). If a run fails to start, the position stays open until the next run (the watchdog restarts the recorder). |
| 6. Tests | `tests/test_fixes.py`: a follow-mode bot with an open option keeps it through `finish()` before 15:55; a new bot instance on the same day resumes it and sells it when the shares bot exits; other modes still close at a restart (unchanged). |
| 7. Results | Pass (see `audit/PR39_REVIEW.md`). |
| 8. Decision | Pending the user's approval (PR #39). The bot is not live yet, so no live behaviour changes. |

## CC-004: daily automatic validation of the two promising bots (no trading change)

| Field | |
|---|---|
| 1. Problem | There is no daily check that the live shares bot and one-a-day options bot do what their tested rules say, and no running record towards the 60-day / 40-trade validation. |
| 2. Evidence | The audit's paper record is 4 days; live and history engines are separate code (`tracker/sharesbot.py` vs `research/one_a_day_study.py`). |
| 3. Proposed change | `research/validate_daily.py`: after the close, re-run the history engine on that day's bars (same IEX data the live bot uses) and compare with what the live bots did: side, entry time and price, exit time, price and reason, result; for the options bot also the spread paid and stale quotes. One row per bot per day is appended to `audit/validation_log.csv`. The daily workflow runs it and commits the log; the Telegram daily check shows the validation count and any deviation. |
| 4. Expected improvement | Deviations between live and tested behaviour are caught the same day; validation progress is measured, not guessed. |
| 5. Possible negative effects | The daily workflow needs write access to commit the log, and the Alpaca keys (read-only market data). If the check fails it reports the failure; it never touches the bots. |
| 6. Tests | Offline test with synthetic bars and a fake bot state: matching day -> "match"; different side or time -> "deviation". |
| 7. Results | Offline test with synthetic bars: identical trade → match; opposite side → DEVIATION; 10 minutes late → DEVIATION ("entry time differs by more than 2 minutes"); no trade on both sides → match; engine traded but live did not → DEVIATION. Daily message shows the count (tested with a sample log). The live run needs the merge and the Alpaca keys in the daily workflow. |
| 8. Decision | Pending the user's approval (PR #39). |

## CC-005 (proposal only, not implemented): retire the 12 fast bots from active paper trading and the live page

| Field | |
|---|---|
| 1. Problem | 12 fast strategies (main, original, trail, trail+trend, his style, skip weak, combo, picks, his clone, brakes, 5-minute, opening move) have no measurable edge. |
| 2. Evidence | Entry right 49-51% of the time (Study 12, audit part 2 section 1); every one negative in every year, out of sample and at realistic costs; three pre-registered market-condition filters failed (`audit/AUDIT2_REPORT.md`). |
| 3. Proposed change | Remove all except main and original from `EXTRA_BOTS` / the recorder and the live page; keep main and original as benchmarks; keep all code, state files, reports and logs; add a guard so a retired bot can only be re-enabled together with a new pre-registered study reference. |
| 4. Expected improvement | Less noise; attention on the one candidate; no accidental use. |
| 5. Possible negative effects | Less live data on strategies already shown to fail (acceptable). |
| 6. Tests | Recorder runs with the reduced bot list; main and original produce identical trades before and after (replay). |
| 7. Results | Not run: proposal only. |
| 8. Decision | **Waiting for the user's approval.** |

## CC-006: retire four bots (user-approved 24 Nov 2026)

| Field | |
|---|---|
| 1. Problem | Four live comparison bots are among the worst performers. |
| 2. Evidence | Paper (recorded, 13-20 Nov): original −$770 (−$1,009 incl. 20 Nov corrected), trail −$171, trail + trend −$446, his style −$170; history per day −$95.19 / −$10.07 / −$6.42 / −$19.48; all rated E (`audit/FINAL_REPORT.md`). |
| 3. Proposed change | Stop running `original`, `trail`, `trailtrend` and `his` and remove them from the live page, the calendar and the daily/weekly Telegram checks. Their code (moved to `RETIRED_BOTS` in `tracker/qqqbot.py`), saved state files, reports and logs are kept. `ORIGINAL_ENABLED = False` in `tracker/recorder.py`. |
| 4. Expected improvement | Less noise; the user's request ("get rid of the worst bots"). |
| 5. Possible negative effects | The original bot was the benchmark for "stop after 2 losses" (the audit recommended keeping it); that comparison stops. Reversible by moving a line back. |
| 6. Tests | Recorder imports with the reduced list; remaining bots make identical trades (replay); live page renders without the four boxes; daily message lists only active bots. |
| 7. Results | 14 tests pass; main + the 8 remaining options bots make identical trades on 6 replayed test days (old main code vs new code); daily message lists only active bots; the live page's bot list no longer contains the four. |
| 8. Decision | Approved by the user in chat; goes live only when the user merges the pull request. |

## CC-007: dashboard stage 2 (decision log, pause switch, live option value, "+context" twins), 25 Nov 2026
- **Problem.** The owner wants to see why each bot does or doesn't trade, be able to pause bots, and have bots that use
  the dashboard's information.
- **Change.**
  - **Decision log:** every bot records one decision a minute (no signal / entered / rejected with the reason / holding)
    plus each exit, with the shared indicators it saw.
  - **Pause switch:** `tracker/controls.py` plus the "Bot controls" workflow. It is checked before every entry.
    - If the switch is unreadable, the bot does not trade.
    - A failed read keeps the last known state.
  - **Live value of an open option:** the bid at each 5-second check, shown on the page.
  - **Twins:** a "+context" twin of every bot (research/CONTEXT_TWINS_PROTOCOL.md).
- **Effect on the original bots.** Their entry and exit rules are unchanged. The only new way an original can skip a
  trade is the pause switch, which is the owner's control.
- **Tests.**
  - `tests/test_stage2.py` (11 tests) covers:
    - decisions logged with inputs;
    - no-signal minutes;
    - exits logged;
    - the open trade valued;
    - the pause blocks trading and says why;
    - an unreadable switch means no trade;
    - the gate rules;
    - a twin blocked by context;
    - the original ignores context;
    - every bot has a twin.
  - `tests/test_fixes.py` (14 tests) still passes.
- **Decision.** Approved by the owner in chat on 25 Nov 2026; the owner merges the pull request.

## CC-008: fake-trade check, alerts and reports (dashboard stage 4), 26 Nov 2026
- **Problem.** The owner asked to make sure no fake trades remain.
- **Evidence.** `research/fake_trade_scan.py` checked all 553 stored options trades against our recorded quotes:
  - 11 could not be matched to a fresh quote, all on 19–20 Nov, before CC-001;
  - none since;
  - details in `audit/flagged_trades.md`.
- **Change.**
  - The live page leaves flagged trades out of every total and lists them under Alerts with the reason.
  - The check now runs after every recorder session.
  - The bots' state files are unchanged.
  - Stage 4 page (display only): an alerts centre with severities, acknowledgement and thresholds; daily reports per bot
    and for the portfolio; a weekly comparison.
- **Effect.** Totals change on 19 and 20 Nov:
  - "Stop after 2" goes from −$200.12 to −$53.06 on 19 Nov, and from +$178.52 to −$142.42 on 20 Nov;
  - net effect on that bot −$173.88.
- **Decision.** Owner request in chat on 26 Nov 2026; the owner merges the pull request.

## CC-009: 25 Nov frozen run, watchdog heartbeat, recovered trades, live page corrections, 26 Nov 2026
- **Problem.**
  - The 25 Nov recorder run's machine stopped at 12:32 NY, but GitHub kept showing it as "running" for a day.
  - So the watchdog never restarted it, and the run's save step never ran: no state files and no quotes for 25 Nov.
  - The page showed a stale £ rate, and some labels were wrong.
- **Change.**
  - **Run cancelled** (it was dead).
  - **Watchdog:** it now also checks the live page heartbeat between 10:00 and 16:00 NY. If there is no update for
    20+ minutes on a run older than 25 minutes, it cancels the run, restarts it and sends a Telegram message.
  - **25 Nov trades** rebuilt from live.json, the bots' own records up to 12:32. Every rebuilt file is marked
  - **Fake-trade scan:** days without saved quotes are listed as "unverified", not flagged.
  - **£ rate** is fetched by the recorder (Frankfurter/ECB, falling back to open.er-api) and published; the browser
    tries the same sources if needed.
  - **Page corrections:**
    - the shares bots start at £1,000 (≈$1,316), not $1,000;
    - the Trend card uses the bots' own shared context when available;
    - the Errors column shows failed polls;
    - US holidays and 13:00 early closes are in the clock;
    - "Losing over $50" names the session date when the market is closed;
    - the bottom note no longer says every options bot uses +2.5% / −6% / 10 min.
- **Decision.** The owner asked for missing or wrong information to be fixed (26 Nov 2026); the owner merges.

## CC-010: fresh start, every bot's account at £1,000 from 27 Nov 2026 (26 Nov 2026)
- **Request.** "Reset all the bots to £1000 … leave everything else", then "all £1000 except the one share a day bot, keep him the same": the shares one-a-day bot is not reset and keeps its full record.
- **Change.** Live page only.
  - Every bot's account (originals and twins, options and shares) starts at £1,000 on 27 Nov 2026.
  - Dollar figures are £1,000 at the live rate plus the bot's dollar P&L.
  - Balances, leaderboard, analytics, calendar, reports and alerts count trades from 27 Nov 2026 only.
  - Earlier trades remain in the repo, the state files and the trade history; there is a checkbox to include them,
    and they are marked "before fresh start".
  - Bot rules, sizing and logs are unchanged.
- **Decision.** Owner request in chat; the owner merges.

## CC-011: daily Telegram check failing, 26 Nov 2026
- **Problem.** The "Daily check of the paper bots" job failed on 24 and 26 Nov, and the owner got failure emails.
- **Evidence.** The report built fine, but it is now 6,500 characters (more bots, plus twins). Telegram refuses
  messages over 4,096 characters, so the send step returned an error.
- **Change.** `send_telegram` splits long messages at blank lines into parts under 3,900 characters, numbered
  (1/2) and (2/2). It also prints Telegram's own refusal reason (never the token).
- **Tests.** Two new tests (long messages split under the limit with HTML tags balanced; short messages unchanged).
  All tests pass.
- **Decision.** The owner asked for it to be fixed; the owner merges.

## CC-012: news bot, daily-target versions, bot families on the page, ship map widget (27 Nov 2026)
- **Request (owner, 27 Nov).**
  - A news bot using a free word scorer.
  - £30/£40/£50/£60 daily-target copies of every bot and twin.
  - A neater page that collapses each bot with its versions inside.
  - Try another ship map.
  - Studies 16 (SPY) and 17 (meme coins).
- **Change.**
  - **News bot:** a NEW paper bot (`news`, `tracker/newsscore.py`, `tracker/newsfeed.py`, `PaperBot` mode
    "news"); rules pre-registered in `research/NEWS_BOT_PROTOCOL.md`. No other bot's rules change: the new mode only
    runs for this bot, and the existing tests still pass.
  - **Daily targets:** 56 versions (7 options bots and their twins × 4 targets), worked out on the page from the real
    bots' trades (exact, because a target version trades identically until it stops). No extra bots run. The
    one-trade-a-day bots are excluded (a target cannot change them).
  - **Page:**
    - one collapsed row per bot, with its versions and full details on click;
    - the chart and calendar pickers become grouped drop-downs;
    - views Originals / twins / targets / everything.
  - **Ship map:** MyShipTracking's free widget, with the VesselFinder button kept.
- **Tests.**
  - 4 new news-bot tests: the scorer; good news plus a bullish chart buys a call; bad news against the chart does not
    trade; no headlines means no trade.
  - All 35 bot tests and 19 copytrader tests pass.
  - The page was rendered with simulated 27 Nov data: no errors, no sideways scroll on a phone.
- **Decision.** Owner's request; the owner merges. The live bots running today are not touched (code changes only take
  effect at the next recorder start after the merge).

## CC-013: SPY one-a-day paper bot, Dogecoin dip-buy paper bot (27 Nov 2026)
- **Evidence.** audit/STUDIES_15_17_REPORT.md: Study 16 passed; DOGE M3 "promising, not proven".
- **Request.** The owner asked to try the SPY one-a-day bot ("number one… try that") and the DOGE dip-buy on paper
  ("Yeah, I try the Dogecoin on paper"). No other coins.
- **Change.**
  - **`shares_spy`:** the existing SharesBot class with symbol "SPY", its own state folder and no Telegram. The bar
    fetchers gained a symbol argument whose default is QQQ, so existing callers are unchanged.
  - **`tracker/dogebot.py` + `.github/workflows/doge.yml`:** every 15 minutes, the ledger in doge.json on the
    live-data branch (not on main), Telegram messages on buy and sell.
- **Tests.** 3 DOGE ledger tests (target, stop, no double-processing); all 38 bot tests pass.
- **Original bots.** Unchanged.

## CC-014: extra Telegram notifications (27 Nov 2026)
- **Request.** The owner asked for these on Telegram: news bot trades, SPY bot trades, "target reached", critical alerts.
- **Change (messages only; no trading rule changes).**
  - The news bot's buys and sells are tagged "📰 News bot", and each buy includes the headlines behind it.
  - The SPY bot's buys and sells are sent.
  - `tracker/notify_extra.py` sends, once a day each:
    - when an original options bot's day first reaches +£30/£40/£50/£60;
    - critical alerts: a bot down $100 today, the emergency pause on, the pause switch unreadable, 20+ failed polls.
- **Tests.** A notifier test (sent once; the right targets; loss alert). All tests pass.
