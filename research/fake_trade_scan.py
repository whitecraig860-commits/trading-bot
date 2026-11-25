"""
Checks every stored options paper trade against the option prices we recorded at that moment (state/quotes).
A trade is FLAGGED when its entry (ask) or exit (bid) cannot be matched to a FRESH recorded quote (stamped within 60 s,
CC-001) at that time. Read-only: the bots' state files are not changed. Output: audit/flagged_trades.json and .md
Run: python research/fake_trade_scan.py
"""
from __future__ import annotations

import glob
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
Q: dict = {}


def quotes(day):
    if day not in Q:
        fs = sorted(glob.glob(str(ROOT / f"state/quotes/{day}*.csv.gz")))
        Q[day] = pd.concat([pd.read_csv(gzip.open(f), dtype={"expiry": str}) for f in fs]) if fs else None
        if Q[day] is not None:
            q = Q[day]
            q["pt"] = pd.to_datetime(q.poll_time)
            q["age"] = (q.pt - pd.to_datetime(q.quote_time)).dt.total_seconds()
    return Q[day]


def check(tr, when, price, field):
    q = quotes(when[:10])
    if q is None:
        return "no recorded quotes that day"
    t = pd.Timestamp(when)
    g = q[(q.expiry == tr["expiry"]) & (q.type == tr["type"]) & (q.strike == float(tr["strike"])) &
          (q.pt >= t - pd.Timedelta(seconds=6)) & (q.pt <= t + pd.Timedelta(seconds=1))]
    if g.empty:
        return f"no recorded quote for this contract at {when[11:19]}"
    m = g[(g[field] - price).abs() < 0.005]
    if m.empty:
        return f"recorded {field} at {when[11:19]} was {g[field].iloc[-1]} not {price}"
    if (m.age > 60).all():
        return f"{field} {price} came from a quote {int(m.age.min())} s old (frozen/stale)"
    return None


def main():
    out = []
    n = 0
    for f in sorted(glob.glob(str(ROOT / "state/qqqbot*/20??-??-??.json"))):
        key = Path(f).parent.name.replace("qqqbot_", "").replace("qqqbot", "options")
        if key == "ctx":
            key = "options_ctx"
        st = json.loads(Path(f).read_text())
        for tr in st.get("trades", []):
            n += 1
            probs = [p for p in (check(tr, tr["t"], tr["entry"], "ask"),
                                 check(tr, tr["exit_t"], tr["exit"], "bid") if tr.get("exit_t") else None) if p]
            if probs:
                out.append({"bot": key, "t": tr["t"], "exit_t": tr.get("exit_t"), "pnl": tr["pnl"], "why": tr.get("why"),
                            "problems": probs})
    (ROOT / "audit/flagged_trades.json").write_text(json.dumps(out, indent=1))
    lines = [f"# Trades checked against recorded quotes\n\n{n} stored options trades checked; {len(out)} flagged "
             f"(entry or exit not matched to a fresh recorded quote). Flagged trades are excluded from the live page's "
             f"totals and shown with a warning. Bot state files are unchanged.\n",
             "| Bot | Entry | Exit | P&L | Problem |", "|---|---|---|---|---|"]
    lines += [f"| {x['bot']} | {x['t']} | {x['exit_t']} | {x['pnl']:+.2f} | {'; '.join(x['problems'])} |" for x in out]
    (ROOT / "audit/flagged_trades.md").write_text("\n".join(lines) + "\n")
    print(n, "checked;", len(out), "flagged;", round(sum(x["pnl"] for x in out), 2), "USD")
    for x in out[:40]:
        print(x["bot"], x["t"], x["pnl"], x["problems"])


if __name__ == "__main__":
    main()
