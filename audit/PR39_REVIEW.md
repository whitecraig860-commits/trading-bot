# Review of PR #39 (do not merge without the user's explicit approval)

Full code diff against `main`: `audit/PR39_code_diff.txt`. Tests: `tests/test_fixes.py` (14 tests, all pass:
`python -m unittest tests/test_fixes.py -v`). Change records: `audit/CHANGE_CONTROL.md` (CC-001 to CC-003).

## What PR #39 contains

| Part | Files | Changes trading behaviour of live bots? |
|---|---|---|
| CC-001 fresh-quote guard | `tracker/qqqbot.py` (`FRESH_QUOTES_ONLY`, `FRESH_SECONDS`, `_fresh`, two call sites) | **Yes, for every options bot, on purpose** (see below) |
| CC-002 holiday check | `tracker/recorder.py` (`holiday_decision`) | Only on days when the option feed is stale at the open |
| CC-003 follow-bot carry-over | `tracker/qqqbot.py` (`finish`) | No: only the new one-a-day options bot (not live yet) |
| New comparison bots: brakes, 5-minute, opening move, one-a-day options | `tracker/qqqbot.py` (new options, all off by default; `EXTRA_BOTS` entries), `tracker/recorder.py` (feeds the shares bot's trade to the one-a-day options bot), `docs/live/index.html` (labels) | No: new bots only |
| Daily Telegram check | `tracker/weekly.py` (`--daily`), `.github/workflows/daily.yml` | No: reads files only |
| Research and audit files | `research/`, `audit/`, `tests/` | No |
| Temporary research runner | `.github/workflows/zz-research.yml` | No; **must be deleted before merging** (I will remove it) |

## CC-001: the original bug and the fix

- **Bug:** bots used whatever bid/ask the data feed returned, even if the quote was minutes or a day old. On 19 Nov the main
  bot bought at a quote stamped the previous afternoon (fake −$147). Measured on all 316 paper option trades: **11 used a
  stale quote** (all on 19-20 Nov), with recorded P&L of −$1,009 on 19 Nov and **+$1,286 on 20 Nov**. Example 20 Nov: the
  634 put's quote was frozen at 7.01/7.03 from 10:14 to 10:24 while QQQ fell; the bot "bought" at 7.03 and "sold" at 10.24
  (+$320). That win was not real. Details: `audit/stale_quotes.md`.
- **Fix:** a quote is used only if stamped within 60 seconds of now; otherwise the bot neither buys nor sells on it.
- **Tests:** stale quote blocks an entry; fresh quote allows it; a stale bid does not trigger an exit and the next fresh one
  does; switching it off restores the old behaviour (all pass).
- **Effect on real recorded days (replay of the real paper-bot code on our recorded prices):** 17 Nov and 18 Nov identical
  to what the live bot did (6/6, 8/8 trades). 19 Nov and 20 Nov **change**, because those days had stale quotes: the main
  bot's 20 Nov becomes −$142 instead of the recorded +$179 (which included the fake +$320). With the guard switched off the
  replay matches all 8 real trades exactly, which shows the difference is the guard and nothing else.
- **New risks:** if a contract's quote is legitimately quiet for over a minute, a bot may skip an entry or delay an exit
  until a fresh quote arrives (bounded by the 10-minute limit and the 15:55 flat time). Accepted as far smaller than trading
  on prices that do not exist.

## CC-002: the original bug and the fix

- **Bug:** if no option quote dated today arrived within 30 minutes, the recorder assumed a holiday and stopped. On 19 Nov
  the feed was stale until 10:30 and the recorder stopped twice; all bots missed 09:30-10:30.
- **Fix:** `holiday_decision()`: after 30 minutes, check every 5 minutes whether QQQ shares are trading today; stop only if
  not; keep waiting if they are or if the check fails.
- **Tests:** first 30 minutes → go; fresh quotes → go; stale + QQQ trading → wait; real holiday → stop; check fails → wait;
  only checks every 5 minutes (all pass).
- **New risks:** none to trading (the bots still only trade on fresh quotes, CC-001). On a real holiday the run lasts until
  its time limit instead of stopping (harmless).

## CC-003: found in this review

- **Bug:** the recorder restarts about every 200 minutes and `finish()` closed every open option. The one-a-day options bot
  holds for hours, so it would have been sold around 12:50 and not re-bought.
- **Fix and tests:** a follow-mode bot keeps its option through a restart; the next run resumes it and sells when the shares
  bot exits; it still closes after 15:55; it never opens a second position; other bots still close at a restart (all pass).

## Unrelated strategies unchanged

- 8 replayed test days: the main and original bots make identical trades with the old (main) and new code.
- 6 replayed test days: all seven comparison bots live on main today (trail, trail+trend, his, skip weak, combo, picks,
  clone) make identical trades with the old and new code (synthetic quotes carry no time stamp, so CC-001 does not act;
  its effect on real data is shown above).

## Execution-risk review (duplicates, missed exits, not stopping)

| Risk | Finding |
|---|---|
| Duplicate positions | Each options bot has one position slot (`s["open"]`); the shares bot sets `done` after its one trade; the one-a-day options bot marks `follow` once per day. Tested: no second entry. |
| Missed exit at a restart | Options bots (except follow mode) close at a restart (they hold ≤ 15 minutes); the shares bot and, with CC-003, the one-a-day options bot carry over. The gap between runs is about 1-2 minutes of start-up (measured from run logs). |
| Missed exit during a feed freeze | With CC-001 a bot will not sell on a frozen bid; it sells on the next fresh quote, at 15:55 at the latest. |
| Continuing to trade after its stop rule | Stop after 2 losses and the brakes are checked every minute before any entry (tested in earlier replays). |
| Real broker behaviour (rejections, partial fills, reconnection, order acknowledgement) | **Cannot be tested**: the bots keep paper ledgers and send no orders; no broker paper account is connected. |
