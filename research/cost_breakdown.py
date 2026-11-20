"""
Where the real trading cost comes from: every paper options trade, its recorded bid/ask at entry and at exit.
Reads files only (origin/main state + quotes, origin/live-data for today). No orders.
python research/cost_breakdown.py  -> audit/cost_breakdown.md
"""

from __future__ import annotations

import gzip
import io
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import paper_results as pr  # noqa: E402


def main() -> int:
    trades = pr.load_trades()
    files = pr.git("ls-tree", "-r", "--name-only", "origin/main", "state/quotes").split()
    qcache, rows = {}, []
    for bot, ts in trades.items():
        if bot == "shares":
            continue
        for t in ts:
            day = t["day"]
            if day not in qcache:
                fs = [f for f in files if day in f]
                qcache[day] = pd.concat(pd.read_csv(io.BytesIO(gzip.decompress(pr.git("show", f"origin/main:{f}", binary=True))),
                                                    dtype={"expiry": str}) for f in fs) if fs else None
            q = qcache[day]
            if q is None:
                continue
            g = q[(q.type == t["type"]) & (q.strike == float(t["strike"])) & (q.expiry == t["expiry"])]
            rec = {"bot": bot, "day": day, "t": t["t"], "type": t["type"], "entry": t["entry"], "exit": t["exit"],
                   "why": t.get("why"), "pnl": t["pnl"]}
            ok = True
            for leg, col in (("in", "t"), ("out", "exit_t")):
                row = g[g.poll_time <= t[col]].tail(1)
                if row.empty:
                    ok = False
                    break
                bid, ask = float(row.bid.iloc[0]), float(row.ask.iloc[0])
                rec[f"half_{leg}"] = (ask - bid) / 2 * 100
                rec[f"spread%_{leg}"] = (ask - bid) / ((ask + bid) / 2) * 100
                rec[f"qqq_{leg}"] = float(row.qqq.iloc[0]) if "qqq" in row else np.nan
            if not ok:
                continue
            # QQQ's movement over the 10 minutes before entry: a simple "fast market" measure
            hist = q[(q.poll_time <= t["t"]) & (q.poll_time >= (pd.Timestamp(t["t"]) - pd.Timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"))]
            rec["qqq_move_10m"] = float(hist.qqq.max() - hist.qqq.min()) if len(hist) else np.nan
            rows.append(rec)
    d = pd.DataFrame(rows)
    d["cost"] = d.half_in + d.half_out + 0.06
    d["hour"] = pd.to_datetime(d.t).dt.strftime("%H:00")
    d["moneyness"] = np.where(d.type == "C", d.qqq_in - d.entry * 0 - 0, 0)
    L = ["# Where the real cost of each paper trade comes from", "",
         f"{len(d)} paper option trades with recorded bid/ask at both entry and exit. Cost = half the bid-ask spread at entry "
         "(we buy at the ask, half a spread above the middle) + half at exit (we sell at the bid) + $0.06 fees, per contract.", "",
         f"**Average ${d.cost.mean():.2f} per round trip** (median ${d.cost.median():.2f}); entry half-spread ${d.half_in.mean():.2f}, "
         f"exit half-spread ${d.half_out.mean():.2f}. The history tests assumed $2.06. Average spread at entry "
         f"{d['spread%_in'].mean():.2f}% of the option price, at exit {d['spread%_out'].mean():.2f}%.", ""]

    def tab(by, title):
        g = d.groupby(by).agg(trades=("cost", "size"), cost=("cost", "mean"), half_in=("half_in", "mean"), half_out=("half_out", "mean"),
                              pct_in=("spread%_in", "mean"))
        out = [f"## By {title}", "", "| | Trades | Cost per round trip | Entry half-spread | Exit half-spread | Spread % at entry |", "|---|---|---|---|---|---|"]
        out += [f"| {k} | {r.trades} | ${r.cost:.2f} | ${r.half_in:.2f} | ${r.half_out:.2f} | {r.pct_in:.2f}% |" for k, r in g.iterrows()]
        return out + [""]

    L += tab("bot", "bot")
    L += tab("hour", "time of day (New York)")
    L += tab("why", "exit reason")
    d["fast"] = pd.qcut(d.qqq_move_10m.rank(method="first"), 3, labels=["calm (bottom third)", "middle", "fast (top third)"])
    L += tab("fast", "how fast QQQ was moving in the 10 minutes before entry")
    L += tab("type", "instrument (call / put)")
    L += tab("day", "day")
    L += ["## Effect on each bot's history (per day, one contract)", "",
          "Using the measured average cost instead of the assumed $2.06, per trade, times the bot's history trades per day:", "",
          "| Bot | History per day at $2.06 | Trades per day | Extra cost per day | History per day at measured cost |", "|---|---|---|---|---|"]
    base = {"options": (-38.25, 6477), "original": (-95.19, 18201), "trail": (-10.07, 3688), "trailtrend": (-6.42, 3590),
            "his": (-19.48, 4864), "skipweak": (-31.57, 5544), "combo": (-34.58, 5751), "picks": (-11.69, 2277),
            "clone": (-11.15, 2277), "brakes": (-35.39, 6205), "five": (-16.46, 3632), "open30": (-2.46, 337), "oneaday": (+14.12, 480)}
    extra = d.cost.mean() - 2.06
    for b, (pd_, n) in base.items():
        per = n / 670
        L.append(f"| {b} | {pd_:+.2f} | {per:.1f} | {-extra * per:+.2f} | {pd_ - extra * per:+.2f} |")
    L += ["", "Caveat 1: the history tests priced trades at actual trade prices (option trade bars), which are often already",
          "inside the bid-ask spread, plus 1 cent. The paper cost above is measured from the middle of the spread. So adding the whole",
          "difference to the history probably overstates the effect: the true figure lies between the $2.06 column and the last column.",
          "Either way, every fast bot loses more, and none turns positive.",
          "Caveat 2: the one-a-day options bot buys a slightly in-the-money or at-the-money option once a day and holds for hours;",
          "its cost was not measured live yet (not deployed). The fast bots' measured spreads are used as the estimate.",
          "Shares: QQQ's spread is about 1 cent a share; at about 2 shares (GBP 1,000) that is about $0.04 a round trip."]
    os.makedirs(os.path.join(pr.ROOT, "audit"), exist_ok=True)
    open(os.path.join(pr.ROOT, "audit", "cost_breakdown.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
