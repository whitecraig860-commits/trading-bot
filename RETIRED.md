# Retired strategies (11 Nov 2026)

These strategies failed properly controlled, pre-registered tests (see `research/REPORT.md` and PR #20). Their code,
results and research are kept for reference. They're switched off as money-making systems, reversibly, and guarded so
that scheduled automation can't switch them back on by accident.

| Strategy | Evidence | How it's switched off | To undo (only after a NEW validated study) |
|---|---|---|---|
| Intraday options scalper (`scalper.py`) | Signal lost on the share itself: −0.23R over 3,318 trades (t = −10.6); option versions lost more | `[scalper] retired = true` (refuses to trade whatever `enabled` says); `[pulse] start_scalper = false` | Remove `retired`, set `start_scalper = true` |
| Short-term QQQ trend worker (`trendworker.py`, PR #19) | Same study as above; every market negative with real option prices | Never merged; PR #19 stays open and unmerged | n/a |
| Swing breakout (`bot.py`, setup `breakout`) | Point-in-time S&P 500 holdout 2024-26: −0.027R over 2,938 trades at 0.25%/side, no better than random entries; failed 7 of 8 checks | `[scan] retired_setups = ["breakout"]`: never alerts or paper-trades | Remove "breakout" from `retired_setups` |

Still running, unchanged: the pullback and insider-copy swing setups (not yet independently tested), the pulse market
reading, Trump and news alerts, the morning briefing and the watchdog. All paper; nothing can place a real-money order
(`scalper.py` hard-codes `paper=True`; the swing account is a file).
