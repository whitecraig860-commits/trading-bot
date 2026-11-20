"""
Paper-trading record for every bot, from the state files the live bots saved (origin/main) plus today's live page data
(origin/live-data). Also measures what each paper trade actually paid in spread, from the recorded quotes.
Reads files only; no orders.   python research/paper_results.py   ->  audit/paper_results.md
"""

from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
FOLDERS = {"options": "qqqbot", "original": "qqqbot_original", "trail": "qqqbot_trail", "trailtrend": "qqqbot_trailtrend",
           "his": "qqqbot_his", "skipweak": "qqqbot_skipweak", "combo": "qqqbot_combo", "picks": "qqqbot_picks",
           "clone": "qqqbot_clone", "brakes": "qqqbot_brakes", "five": "qqqbot_five", "open30": "qqqbot_open30",
           "oneaday": "qqqbot_oneaday"}


def git(*a, binary=False):
    out = subprocess.run(["git", "-C", ROOT, *a], capture_output=True)
    return out.stdout if binary else out.stdout.decode()


def load_trades() -> dict:
    out = {k: [] for k in FOLDERS}
    out["shares"] = []
    for key, folder in list(FOLDERS.items()) + [("shares", "sharesbot")]:
        for f in git("ls-tree", "--name-only", "origin/main", f"state/{folder}/").split():
            if not f.endswith(".json") or "20" not in f:
                continue
            try:
                st = json.loads(git("show", f"origin/main:{f}"))
            except ValueError:
                continue
            day = os.path.basename(f)[:10]
            if key == "shares":
                t = st.get("trade")
                if t and t.get("exit") is not None:
                    out[key].append({"day": day, "pnl": float(t["pnl_usd"]), "t": t["t"], "why": t.get("why")})
            else:
                out[key] += [dict(x, day=day) for x in st.get("trades", [])]
    try:  # today's trades from the live page, if the day is not saved on main yet
        live = json.loads(git("show", "origin/live-data:live.json"))
        today = live["updated"][:10]
        for key in FOLDERS:
            if live.get(key) and not any(x["day"] == today for x in out[key]):
                out[key] += [dict(x, day=today) for x in live[key].get("trades", [])]
    except (ValueError, KeyError):
        pass
    return out


def spread_paid(trades: list) -> tuple[float, int]:
    """For trades whose quotes were recorded: half the bid-ask spread at entry plus half at exit, per contract."""
    files = git("ls-tree", "-r", "--name-only", "origin/main", "state/quotes").split()
    cache, costs = {}, []
    for t in trades:
        day = t["day"]
        if day not in cache:
            fs = [f for f in files if day in f]
            cache[day] = pd.concat(pd.read_csv(io.BytesIO(gzip.decompress(git("show", f"origin/main:{f}", binary=True))),
                                               dtype={"expiry": str}) for f in fs) if fs else None
        q = cache[day]
        if q is None or "strike" not in t:
            continue
        g = q[(q.type == t["type"]) & (q.strike == float(t["strike"])) & (q.expiry == t["expiry"])]
        c = 0.0
        ok = True
        for col in ("t", "exit_t"):
            row = g[g.poll_time <= t[col]].tail(1)
            if row.empty:
                ok = False
                break
            c += (float(row.ask.iloc[0]) - float(row.bid.iloc[0])) / 2 * 100
        if ok:
            costs.append(c)
    return (float(np.mean(costs)) if costs else float("nan")), len(costs)


def main() -> int:
    tr = load_trades()
    L = ["# Paper-trading record (real-time paper trades, bought at the recorded ask, sold at the recorded bid)", "",
         "Each bot started on a different day; few days are not enough to judge any bot.", "",
         "| Bot | Days | Trades | Win% | Net | Per day | PF | Avg win | Avg loss | Max losses in a row | Spread paid per trade (half-spread in + out) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    per_day = {}
    for k, ts in tr.items():
        if not ts:
            L.append(f"| {k} | 0 | 0 | | | | | | | | |")
            continue
        d = pd.DataFrame(ts)
        pnl = d.pnl.astype(float)
        days = sorted(d.day.unique())
        w, l = pnl[pnl > 0], pnl[pnl <= 0]
        streak = best = 0
        for v in pnl:
            streak = streak + 1 if v <= 0 else 0
            best = max(best, streak)
        sp, n = spread_paid(ts) if k != "shares" else (float("nan"), 0)
        per_day[k] = d.groupby("day").pnl.sum()
        L.append(f"| {k} | {len(days)} | {len(d)} | {len(w) / len(d):.0%} | {pnl.sum():+,.0f} | {pnl.sum() / len(days):+.0f} | "
                 f"{(w.sum() / -l.sum()) if l.sum() else float('inf'):.2f} | {w.mean() if len(w) else 0:+.0f} | "
                 f"{l.mean() if len(l) else 0:+.0f} | {best} | " + (f"${sp:.2f} ({n} trades measured)" if n else "-") + " |")
    L += ["", "## Day by day", ""]
    allp = pd.DataFrame(per_day).sort_index()
    L.append("| Day | " + " | ".join(allp.columns) + " |")
    L.append("|---|" + "---|" * len(allp.columns))
    for day, row in allp.iterrows():
        L.append(f"| {day} | " + " | ".join("–" if pd.isna(v) else f"{v:+.0f}" for v in row) + " |")
    os.makedirs(os.path.join(ROOT, "audit"), exist_ok=True)
    open(os.path.join(ROOT, "audit", "paper_results.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
