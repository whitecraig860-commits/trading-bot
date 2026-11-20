"""How many paper trades were bought or sold on a quote older than 60 seconds, and their P&L. Files only; no orders."""
from __future__ import annotations
import gzip, io, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import paper_results as pr  # noqa: E402

trades = pr.load_trades()
files = pr.git("ls-tree", "-r", "--name-only", "origin/main", "state/quotes").split()
cache, rows = {}, []
for bot, ts in trades.items():
    if bot == "shares":
        continue
    for t in ts:
        day = t["day"]
        if day not in cache:
            fs = [f for f in files if day in f]
            cache[day] = pd.concat(pd.read_csv(io.BytesIO(gzip.decompress(pr.git("show", f"origin/main:{f}", binary=True))),
                                               dtype={"expiry": str}) for f in fs) if fs else None
        q = cache[day]
        if q is None:
            continue
        g = q[(q.type == t["type"]) & (q.strike == float(t["strike"])) & (q.expiry == t["expiry"])]
        ages = []
        for col in ("t", "exit_t"):
            row = g[g.poll_time <= t[col]].tail(1)
            ages.append((pd.Timestamp(row.poll_time.iloc[0]) - pd.Timestamp(row.quote_time.iloc[0])).total_seconds() if len(row) else None)
        rows.append({"bot": bot, "day": day, "pnl": t["pnl"], "age_in": ages[0], "age_out": ages[1]})
d = pd.DataFrame(rows)
d["stale"] = (d.age_in > 60) | (d.age_out > 60)
L = ["# Paper trades made on stale (frozen) option quotes", "",
     f"{len(d)} paper option trades checked. A quote counts as stale if it was stamped more than 60 seconds before it was used.", "",
     f"**{d.stale.sum()} trades ({d.stale.mean():.0%}) used a stale quote at entry or exit**, with a total P&L of "
     f"{d[d.stale].pnl.sum():+,.0f} (all trades: {d.pnl.sum():+,.0f}). Their recorded results are not reliable in either direction.", "",
     "| Bot | Trades | Stale trades | P&L of stale trades | P&L of the rest |", "|---|---|---|---|---|"]
for b, g in d.groupby("bot"):
    L.append(f"| {b} | {len(g)} | {g.stale.sum()} | {g[g.stale].pnl.sum():+,.0f} | {g[~g.stale].pnl.sum():+,.0f} |")
L += ["", "| Day | Stale trades | Their P&L |", "|---|---|---|"]
for day, g in d.groupby("day"):
    L.append(f"| {day} | {g.stale.sum()} | {g[g.stale].pnl.sum():+,.0f} |")
L += ["", "Fix: CC-001 (only trade on quotes stamped within 60 seconds), pending the user's approval in PR #39."]
open(os.path.join(pr.ROOT, "audit", "stale_quotes.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
