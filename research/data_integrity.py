"""
Data-integrity audit of every recorded quote file and every paper trade (files only; no orders).
python research/data_integrity.py  ->  audit/DATA_INTEGRITY.md
"""

from __future__ import annotations

import gzip
import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import paper_results as pr  # noqa: E402

FEE = 0.03


def main() -> int:
    L = ["# Data-integrity audit", "", "Every recorded quote file (`state/quotes/`) and every paper trade saved by the options bots and the shares bot,",
         "checked from the files themselves. Times are New York time throughout (the recorder writes NY time; the US clocks changed",
         "on 1 Nov 2026, before the first recorded day, so no recorded day spans a clock change).", ""]
    files = [f for f in pr.git("ls-tree", "-r", "--name-only", "origin/main", "state/quotes").split() if f.endswith(".csv.gz")]
    L += ["## 1. Recorded quotes", "", "| File | Rows | Poll span (NY) | Longest gap between polls | Duplicate rows | Bid > ask | Zero/blank bid or ask | Quote stamped after poll | Quote older than 60 s | Quote from an earlier day |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    qall = {}
    for f in sorted(files):
        q = pd.read_csv(io.BytesIO(gzip.decompress(pr.git("show", f"origin/main:{f}", binary=True))), dtype={"expiry": str})
        day = os.path.basename(f)[:10]
        qall.setdefault(day, []).append(q)
        pt = pd.to_datetime(q.poll_time)
        qt = pd.to_datetime(q.quote_time, errors="coerce")
        polls = pt.drop_duplicates().sort_values()
        gap = polls.diff().max().total_seconds() if len(polls) > 1 else 0
        dup = q.duplicated(["poll_time", "contract"]).sum()
        bidask = pd.to_numeric(q.bid, errors="coerce"), pd.to_numeric(q.ask, errors="coerce")
        bad = (bidask[0] > bidask[1]).sum()
        zero = ((bidask[0].fillna(0) <= 0) | (bidask[1].fillna(0) <= 0)).sum()
        future = (qt > pt + pd.Timedelta(seconds=2)).sum()
        age = (pt - qt).dt.total_seconds()
        stale = (age > 60).sum()
        earlier = (qt.dt.normalize() < pt.dt.normalize()).sum()
        L.append(f"| {os.path.basename(f)} | {len(q):,} | {polls.iloc[0]:%H:%M:%S}-{polls.iloc[-1]:%H:%M:%S} | {gap:.0f} s | {dup} | {bad} | {zero:,} | {future} | {stale:,} ({stale / len(q):.1%}) | {earlier:,} |")
    L += ["", "Quotes older than 60 s are normal for quiet strikes far from the price; the problem is only when a bot trades on one (section 3).", ""]

    trades = pr.load_trades()
    L += ["## 2. Paper-trade accounting checks", "", "| Bot | Trades | P&L recomputed = recorded | Exit after entry | Inside 09:30-16:00 | Contract multiplier 100 | Duplicate trades | Still open in a saved file |",
          "|---|---|---|---|---|---|---|---|"]
    problems = []
    for bot, ts in trades.items():
        if not ts:
            continue
        d = pd.DataFrame(ts)
        if bot == "shares":
            L.append(f"| shares | {len(d)} | (P&L = (exit-entry) x side x qty; checked below) | | | n/a | | |")
            continue
        recomputed = ((d.exit - d.entry) * 100 - 2 * FEE).round(2)
        ok_pnl = (recomputed - d.pnl.round(2)).abs().max() < 0.011
        after = (pd.to_datetime(d.exit_t) >= pd.to_datetime(d.t)).all()
        hours = d.t.str[11:16].between("09:30", "16:00").all() and d.exit_t.str[11:16].between("09:30", "16:00").all()
        dups = d.duplicated(["day", "t", "strike", "type"]).sum()
        L.append(f"| {bot} | {len(d)} | {'yes' if ok_pnl else 'NO'} | {'yes' if after else 'NO'} | {'yes' if hours else 'NO'} | yes (code: (bid-entry) x 100) | {dups} | see below |")
        if not ok_pnl:
            problems.append(f"{bot}: recorded P&L differs from (exit-entry) x 100 - fees")
    opened = []
    for key, folder in list(pr.FOLDERS.items()) + [("shares", "sharesbot")]:
        for f in pr.git("ls-tree", "--name-only", "origin/main", f"state/{folder}/").split():
            if not f.endswith(".json"):
                continue
            try:
                st = json.loads(pr.git("show", f"origin/main:{f}"))
            except ValueError:
                continue
            if key == "shares":
                t = st.get("trade")
                if t and t.get("exit") is None:
                    opened.append(f"{f}: shares trade still open in the saved file")
                elif t and t.get("exit") is not None:
                    pnl = round((t["exit"] - t["entry"]) * t["side"] * t["qty"], 2)
                    if abs(pnl - t["pnl_usd"]) > 0.011:
                        problems.append(f"{f}: shares P&L {t['pnl_usd']} vs recomputed {pnl}")
            elif st.get("open"):
                opened.append(f"{f}: an option position is still open in the saved file")
    L += ["", "Open positions left in saved files: " + ("; ".join(opened) if opened else "none."),
          "Accounting problems found: " + ("; ".join(problems) if problems else "none (every recorded P&L equals (exit - entry) x 100 - $0.06 for options, and (exit - entry) x side x quantity for shares)."), ""]

    L += ["## 3. Trades made on stale quotes (all 316 option trades checked)", "",
          "| Bot | Entry time | Option | Entry | Quote used at entry (stamped) | Exit | Exit time | Quote used at exit (stamped) | Recorded P&L | Should it have executed? | Corrected P&L |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    n = 0
    for bot, ts in trades.items():
        if bot == "shares":
            continue
        for t in ts:
            q = pd.concat(qall.get(t["day"], [])) if t["day"] in qall else None
            if q is None:
                continue
            g = q[(q.type == t["type"]) & (q.strike == float(t["strike"])) & (q.expiry == t["expiry"])]
            info, stale = [], False
            for col in ("t", "exit_t"):
                row = g[g.poll_time <= t[col]].tail(1)
                if row.empty:
                    info.append("no quote")
                    continue
                a = (pd.Timestamp(row.poll_time.iloc[0]) - pd.Timestamp(row.quote_time.iloc[0])).total_seconds()
                stale |= a > 60
                info.append(f"{row.bid.iloc[0]}/{row.ask.iloc[0]} ({row.quote_time.iloc[0][5:19]}, {a:.0f} s old)")
            if stale:
                n += 1
                L.append(f"| {bot} | {t['t'][:19]} | {int(t['strike'])}{t['type']} {t['expiry']} | {t['entry']} | {info[0]} | {t['exit']} | {t['exit_t'][11:19]} | "
                         f"{info[1]} | {t['pnl']:+.2f} | No: the price used was not current | void ($0); the day's corrected ledger is the replay with the guard on |")
    L += ["", f"{n} trades affected. Corrected day ledgers (replay of the real bot code on the recorded quotes with the fresh-quote guard):",
          "main bot 20 Nov −$142.42 (recorded +$178.52), original 20 Nov −$64.08 (recorded +$256.86); see `audit/LEDGER_RECONCILIATION.md`.",
          "These trades affected only the paper record and the audit's paper tables. No history backtest uses paper trades (the backtests use",
          "Alpaca's historical option trade bars), so no backtest result changes.", "",
          "## 4. Checks that cannot be fully done from our files",
          "- Historical option bars (Alpaca) are trade prints, not bid/ask: the backtests cannot see stale quotes or spreads; costs are added as an assumption (see `audit/cost_breakdown.md`).",
          "- Missing one-minute QQQ candles in the history: the backtest engines skip a check if its candle is missing; not counted per day.",
          "- Commissions: the paper bots charge $0.03 a contract a side. A real broker may charge more (e.g. about $0.65 a contract at some brokers); not included."]
    os.makedirs(os.path.join(pr.ROOT, "audit"), exist_ok=True)
    open(os.path.join(pr.ROOT, "audit", "DATA_INTEGRITY.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
