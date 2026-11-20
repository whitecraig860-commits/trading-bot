# Data-integrity audit

Every recorded quote file (`state/quotes/`) and every paper trade saved by the options bots and the shares bot,
checked from the files themselves. Times are New York time throughout (the recorder writes NY time; the US clocks changed
on 1 Nov 2026, before the first recorded day, so no recorded day spans a clock change).

## 1. Recorded quotes

| File | Rows | Poll span (NY) | Longest gap between polls | Duplicate rows | Bid > ask | Zero/blank bid or ask | Quote stamped after poll | Quote older than 60 s | Quote from an earlier day |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-12-am.csv.gz | 17,216 | 09:30:01-13:04:02 | 61 s | 0 | 0 | 3 | 0 | 5 (0.0%) | 5 |
| 2026-11-13-0946.csv.gz | 115,284 | 09:46:32-13:06:28 | 6 s | 0 | 0 | 0 | 0 | 0 (0.0%) | 0 |
| 2026-11-13-1307.csv.gz | 111,216 | 13:07:08-16:19:58 | 5 s | 0 | 0 | 991 | 442 | 2,332 (2.1%) | 0 |
| 2026-11-16-0930.csv.gz | 115,272 | 09:30:01-12:49:56 | 5 s | 0 | 0 | 0 | 0 | 0 (0.0%) | 0 |
| 2026-11-16-1250.csv.gz | 115,280 | 12:50:36-16:10:31 | 5 s | 0 | 0 | 301 | 0 | 0 (0.0%) | 0 |
| 2026-11-17-0930.csv.gz | 115,316 | 09:30:01-12:49:57 | 6 s | 0 | 0 | 0 | 103 | 0 (0.0%) | 0 |
| 2026-11-17-1250.csv.gz | 115,208 | 12:50:37-16:10:33 | 6 s | 0 | 0 | 0 | 0 | 0 (0.0%) | 0 |
| 2026-11-18-0930.csv.gz | 115,336 | 09:30:01-12:49:57 | 6 s | 0 | 0 | 0 | 0 | 0 (0.0%) | 0 |
| 2026-11-18-1250.csv.gz | 115,408 | 12:50:35-16:10:31 | 6 s | 0 | 0 | 242 | 0 | 0 (0.0%) | 0 |
| 2026-11-19-1031.csv.gz | 115,296 | 10:31:21-13:51:16 | 5 s | 0 | 0 | 0 | 0 | 850 (0.7%) | 764 |
| 2026-11-19-1351.csv.gz | 85,288 | 13:51:54-16:19:57 | 10 s | 0 | 0 | 310 | 85 | 2,308 (2.7%) | 0 |
| 2026-11-20-0930.csv.gz | 115,292 | 09:30:01-12:49:56 | 5 s | 0 | 0 | 1 | 0 | 4,364 (3.8%) | 0 |
| 2026-11-20-1250.csv.gz | 115,256 | 12:50:30-16:10:28 | 8 s | 0 | 0 | 0 | 244 | 86 (0.1%) | 0 |

Quotes older than 60 s are normal for quiet strikes far from the price; the problem is only when a bot trades on one (section 3).

## 2. Paper-trade accounting checks

| Bot | Trades | P&L recomputed = recorded | Exit after entry | Inside 09:30-16:00 | Contract multiplier 100 | Duplicate trades | Still open in a saved file |
|---|---|---|---|---|---|---|---|
| options | 76 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| original | 161 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| trail | 20 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| trailtrend | 11 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| his | 28 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| skipweak | 8 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| combo | 11 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| picks | 9 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| clone | 4 | yes | yes | yes | yes (code: (bid-entry) x 100) | 0 | see below |
| shares | 5 | (P&L = (exit-entry) x side x qty; checked below) | | | n/a | | |

Open positions left in saved files: none.
Accounting problems found: none (every recorded P&L equals (exit - entry) x 100 - $0.06 for options, and (exit - entry) x side x quantity for shares).

## 3. Trades made on stale quotes (all 316 option trades checked)

| Bot | Entry time | Option | Entry | Quote used at entry (stamped) | Exit | Exit time | Quote used at exit (stamped) | Recorded P&L | Should it have executed? | Corrected P&L |
|---|---|---|---|---|---|---|---|---|---|---|
| options | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| options | 2026-11-20 10:19:06 | 634P 2026-11-23 | 7.03 | 7.01/7.03 (11-20 10:14:04, 302 s old) | 10.24 | 10:24:01 | 10.24/10.37 (11-20 10:24:00, 1 s old) | +320.94 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| original | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| original | 2026-11-20 10:19:06 | 634P 2026-11-23 | 7.03 | 7.01/7.03 (11-20 10:14:04, 302 s old) | 10.24 | 10:24:01 | 10.24/10.37 (11-20 10:24:00, 1 s old) | +320.94 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| trail | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| trail | 2026-11-20 10:19:06 | 634P 2026-11-23 | 7.03 | 7.01/7.03 (11-20 10:14:04, 302 s old) | 10.25 | 10:24:41 | 10.25/10.6 (11-20 10:24:41, 0 s old) | +321.94 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| trailtrend | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| his | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| his | 2026-11-20 10:19:06 | 634P 2026-11-23 | 7.03 | 7.01/7.03 (11-20 10:14:04, 302 s old) | 10.25 | 10:24:41 | 10.25/10.6 (11-20 10:24:41, 0 s old) | +321.94 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| skipweak | 2026-11-19 10:32:36 | 662P 2026-11-20 | 9.68 | 9.51/9.68 (11-18 16:14:59, 65857 s old) | 8.21 | 10:32:41 | 8.21/8.26 (11-19 10:32:40, 1 s old) | -147.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |
| combo | 2026-11-19 10:32:36 | 663P 2026-11-20 | 10.08 | 9.83/10.08 (11-18 16:14:59, 65857 s old) | 8.81 | 10:32:41 | 8.81/8.88 (11-19 10:32:40, 1 s old) | -127.06 | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |

11 trades affected. Corrected day ledgers (replay of the real bot code on the recorded quotes with the fresh-quote guard):
main bot 20 Nov −$142.42 (recorded +$178.52), original 20 Nov −$64.08 (recorded +$256.86); see `audit/LEDGER_RECONCILIATION.md`.
These trades affected only the paper record and the audit's paper tables. No history backtest uses paper trades (the backtests use
Alpaca's historical option trade bars), so no backtest result changes.

## 4. Checks that cannot be fully done from our files
- Historical option bars (Alpaca) are trade prints, not bid/ask: the backtests cannot see stale quotes or spreads; costs are added as an assumption (see `audit/cost_breakdown.md`).
- Missing one-minute QQQ candles in the history: the backtest engines skip a check if its candle is missing; not counted per day.
- Commissions: the paper bots charge $0.03 a contract a side. A real broker may charge more (e.g. about $0.65 a contract at some brokers); not included.
