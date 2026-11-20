"""
Study 12 tests 2 and 3 and part C (research/BRAKES_PROTOCOL.md): replay the real paper-bot code on our own recorded
5-second quotes, and apply the brakes to his posted trades. Reads files only; no market data requests; no orders.
python research/brakes_replay.py   (run from the repository root, with origin/main and origin/live-data fetched)
"""

from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))
import qqqbot  # noqa: E402

NY = ZoneInfo("America/New_York")
RULES = {"BASE": {}, "PB50": {"profit_brake": 50}, "PB100": {"profit_brake": 100}, "LB100": {"loss_brake": 100},
         "PB50LB": {"profit_brake": 50, "loss_brake": 100}, "G1 spread>5%": {"max_spread": 0.05},
         "G2 3 min after a gap": {"resume_wait": 3}}


def git(*a, binary=False):
    out = subprocess.run(["git", *a], capture_output=True)
    return out.stdout if binary else out.stdout.decode()


def day_bars(day: str):
    """The last live.json of that day on the live-data branch (full candles from 18 Nov; 17 Nov has them too)."""
    shas = git("log", "origin/live-data", "--format=%H", f"--until={day}T23:59:00Z", f"--since={day}T00:00:00Z").split()
    for sha in shas:
        try:
            d = json.loads(git("show", f"{sha}:live.json"))
        except ValueError:
            continue
        if d.get("updated", "").startswith(day) and d.get("bars") and len(d["bars"][0]) == 6 and d.get("prev"):
            mk = lambda rows: pd.DataFrame([r[1:] for r in rows], columns=["open", "high", "low", "close", "volume"],
                                           index=pd.DatetimeIndex([r[0] for r in rows]))
            return mk(d["bars"]), mk(d["prev"]), d
    return None, None, None


def replay(day: str):
    files = [f for f in git("ls-tree", "-r", "--name-only", "origin/main", "state/quotes").split() if day in f]
    if not files:
        return None
    q = pd.concat(pd.read_csv(io.BytesIO(gzip.decompress(git("show", f"origin/main:{f}", binary=True))),
                              dtype={"expiry": str}) for f in files)
    bars, prev, live = day_bars(day)
    if bars is None:
        return None
    bf = lambda now, back=0: prev if back else bars[bars.index < pd.Timestamp(now.replace(tzinfo=None)).floor("min")]
    t0 = datetime.fromisoformat(day + " 09:30").replace(tzinfo=NY)
    bots = {k: qqqbot.PaperBot(bf, t0, say=lambda t: True, state_dir=Path(tempfile.mkdtemp()), trade_messages=False,
                               **kw) for k, kw in RULES.items()}
    for pt, g in q.groupby("poll_time", sort=True):
        t = datetime.fromisoformat(pt).replace(tzinfo=NY)
        rows = g.to_dict("records")
        for b in bots.values():
            b.on_poll(t, rows)
    actual = None
    try:
        actual = json.loads(git("show", f"origin/main:state/qqqbot/{day}.json"))["trades"]
    except ValueError:
        actual = (live.get("options") or {}).get("trades")
    first = q.poll_time.min()[11:16]
    return {k: b.s["trades"] for k, b in bots.items()}, actual, first


def main() -> int:
    print("===== TEST 2: replay on our own recorded live prices =====")
    tot = {k: 0.0 for k in RULES}
    for day in ("2026-11-17", "2026-11-18", "2026-11-19"):
        r = replay(day)
        if r is None:
            print(f"{day}: no recorded quotes or candles")
            continue
        res, actual, first = r
        base = res["BASE"]
        same = actual is not None and [(t["t"], t["exit_t"], t["pnl"]) for t in base] == \
            [(t["t"], t["exit_t"], t["pnl"]) for t in actual][:len(base)]
        print(f"\n{day} (quotes from {first}): replay matches the live bot's real trades: {same} "
              f"({len(base)} replayed vs {len(actual or [])} real)")
        for k, tr in res.items():
            tot[k] += sum(t["pnl"] for t in tr)
            blocked = [t for t in base if t["t"] not in {x["t"] for x in tr}]
            print(f"  {k:22s} {len(tr):3d} trades  {sum(t['pnl'] for t in tr):+8.2f}"
                  + (f"   blocked vs BASE: " + ", ".join(f"{t['t'][11:16]} {t['pnl']:+.0f}" for t in blocked) if k != "BASE" and blocked else ""))
    print("\nTotal over these days: " + ", ".join(f"{k} {v:+.0f}" for k, v in tot.items()))

    print("\n===== TEST 3: the brakes applied to his posted trades (per contract, each account separately) =====")
    his = pd.read_csv(Path(__file__).resolve().parent.parent / "state" / "discord_trades.csv").dropna(subset=["trader"])
    his["pc"] = (his.sell - his.buy) * 100
    his["bt"] = his.date + " " + his.buy_time
    out = []
    for (day, acct), g in his.sort_values("bt").groupby(["date", "trader"]):
        res = {}
        for name, pb, lb in (("none", 0, 0), ("PB50", 50, 0), ("PB100", 100, 0), ("LB100", 0, 100), ("PB50LB", 50, 100)):
            cum = 0.0
            for v in g.pc:
                if (pb and cum >= pb) or (lb and cum <= -lb):
                    break
                cum += v
            res[name] = cum
        out.append({"day": day, "account": int(acct), **res})
    o = pd.DataFrame(out)
    print(o.round(0).to_string(index=False))
    print("Totals: " + ", ".join(f"{c} {o[c].sum():+.0f}" for c in o.columns[2:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
