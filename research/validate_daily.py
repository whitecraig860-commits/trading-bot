"""
CC-004 daily validation (audit/CHANGE_CONTROL.md). After the close: re-run the tested one-a-day engine on the day's bars and
compare with what the live shares bot and one-a-day options bot did. Appends to audit/validation_log.csv. No orders.
python research/validate_daily.py [YYYY-MM-DD]
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import one_a_day_study as s6  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
LOG = os.path.join(ROOT, "audit", "validation_log.csv")
FIELDS = ["date", "bot", "status", "exp_side", "live_side", "exp_entry_t", "live_entry_t", "exp_entry", "live_entry",
          "exp_exit_t", "live_exit_t", "exp_why", "live_why", "exp_ret%", "live_ret%", "live_pnl", "spread_paid",
          "stale_quotes", "note"]


class _NoOpt:
    def bars(self, *a, **k):
        return pd.DataFrame(columns=["open", "high", "low", "close"])


def load_bars(day: date) -> pd.DataFrame:
    """The same IEX one-minute bars the live bots use, for the 40 calendar days up to `day`."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    a = pd.Timestamp(day - timedelta(days=40)).tz_localize("America/New_York")
    b = pd.Timestamp(day + timedelta(days=1)).tz_localize("America/New_York")
    df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute, start=a.to_pydatetime(),
                                             end=b.to_pydatetime(), feed=DataFeed.IEX)).df.xs("QQQ", level=0)
    df.index = pd.DatetimeIndex(df.index).tz_convert("America/New_York").tz_localize(None)
    q = df.between_time("09:30", "15:59")[["open", "high", "low", "close", "volume"]].astype(float)
    return q[~q.index.duplicated()]


def expected(q: pd.DataFrame, day: date) -> dict | None:
    r = s6.run(q, s6.prepare(q), _NoOpt(), dte=0, itm=0.0)
    if not len(r):
        return None
    r = r[r.day == pd.Timestamp(day)]
    if not len(r) or not bool(r.traded.iloc[0]):
        return {"side": 0}
    x = r.iloc[0]
    side = 1 if x.side == "C" else -1
    exit_t = pd.Timestamp(x.t) + pd.Timedelta(minutes=float(x.mins))
    return {"side": side, "t": pd.Timestamp(x.t) + pd.Timedelta(minutes=1), "entry": float(x.entry), "exit_t": exit_t,
            "why": x.why, "ret%": (float(x.exit) - float(x.entry)) * side / float(x.entry) * 100}


def compare_shares(exp: dict | None, live: dict | None) -> dict:
    row = {}
    if exp is None:
        return {"status": "no data", "note": "engine could not run (not enough history?)"}
    ls = (live or {}).get("side", 0) or 0
    row.update(exp_side=exp["side"], live_side=ls)
    if exp["side"] == 0 and ls == 0:
        return {**row, "status": "match", "note": "no trade, as expected"}
    if exp["side"] != ls:
        return {**row, "status": "DEVIATION", "note": "different side or one traded and the other did not"}
    lt = pd.Timestamp(live["t"])
    row.update(exp_entry_t=exp["t"].strftime("%H:%M"), live_entry_t=lt.strftime("%H:%M"), exp_entry=round(exp["entry"], 2),
               live_entry=round(float(live["entry"]), 2), exp_why=exp["why"], live_why=live.get("why"),
               exp_exit_t=exp["exit_t"].strftime("%H:%M"),
               live_exit_t=pd.Timestamp(live["exit_t"]).strftime("%H:%M") if live.get("exit_t") else "",
               **{"exp_ret%": round(exp["ret%"], 3)})
    if live.get("exit") is not None:
        row["live_ret%"] = round((float(live["exit"]) - float(live["entry"])) * ls / float(live["entry"]) * 100, 3)
        row["live_pnl"] = live.get("pnl_usd")
    bad = []
    if abs((lt - exp["t"]).total_seconds()) > 120:
        bad.append("entry time differs by more than 2 minutes")
    if abs(float(live["entry"]) - exp["entry"]) / exp["entry"] > 0.001:
        bad.append("entry price differs by more than 0.1%")
    if live.get("why") and live.get("why") != exp["why"]:
        bad.append(f"exit reason {live.get('why')} vs {exp['why']}")
    return {**row, "status": "DEVIATION" if bad else "match", "note": "; ".join(bad)}


def git(*a, binary=False):
    out = subprocess.run(["git", "-C", ROOT, *a], capture_output=True)
    return out.stdout if binary else out.stdout.decode()


def options_row(day: str, shares_live: dict | None) -> dict:
    f = os.path.join(ROOT, "state", "qqqbot_oneaday", f"{day}.json")
    if not os.path.exists(f):
        return {"status": "not running", "note": "no state file (bot not deployed or no trade)"}
    st = json.load(open(f))
    tr = st.get("trades", [])
    ls = (shares_live or {}).get("side", 0) or 0
    if not tr:
        return {"status": "match" if not ls else "DEVIATION", "live_side": 0, "exp_side": ls,
                "note": "no option trade" + ("" if not ls else " although the shares bot traded")}
    t = tr[0]
    row = {"exp_side": ls, "live_side": 1 if t["type"] == "C" else -1, "live_entry_t": t["t"][11:16],
           "live_exit_t": t["exit_t"][11:16], "live_entry": t["entry"], "live_why": t["why"], "live_pnl": t["pnl"]}
    bad = []
    if row["live_side"] != ls:
        bad.append("option side differs from the shares bot")
    if shares_live and abs((pd.Timestamp(t["t"]) - pd.Timestamp(shares_live["t"])).total_seconds()) > 120:
        bad.append("option bought more than 2 minutes after the shares entry")
    if len(tr) > 1:
        bad.append(f"{len(tr)} option trades (expected 1)")
    files = [p for p in git("ls-tree", "-r", "--name-only", "HEAD", "state/quotes").split() if day in p]
    if files:
        q = pd.concat(pd.read_csv(io.BytesIO(gzip.decompress(open(os.path.join(ROOT, p), "rb").read())), dtype={"expiry": str})
                      for p in files)
        g = q[(q.type == t["type"]) & (q.strike == float(t["strike"])) & (q.expiry == t["expiry"])]
        paid, stale = 0.0, 0
        for col in ("t", "exit_t"):
            rr = g[g.poll_time <= t[col]].tail(1)
            if len(rr):
                paid += (float(rr.ask.iloc[0]) - float(rr.bid.iloc[0])) / 2 * 100
                stale += (pd.Timestamp(rr.poll_time.iloc[0]) - pd.Timestamp(rr.quote_time.iloc[0])).total_seconds() > 60
        row.update(spread_paid=round(paid + 0.06, 2), stale_quotes=stale)
        if stale:
            bad.append("traded on a stale quote")
    return {**row, "status": "DEVIATION" if bad else "match", "note": "; ".join(bad)}


def main() -> int:
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    if day.weekday() >= 5:
        return 0
    ds = day.isoformat()
    sf = os.path.join(ROOT, "state", "sharesbot", f"{ds}.json")
    shares_live = (json.load(open(sf)).get("trade") if os.path.exists(sf) else None)
    try:
        exp = expected(load_bars(day), day)
    except Exception as exc:
        exp = None
        print(f"engine: {type(exc).__name__}: {str(exc)[:120]}")
    rows = [{"date": ds, "bot": "shares_oneaday", **compare_shares(exp, shares_live)},
            {"date": ds, "bot": "oneaday_options", **options_row(ds, shares_live)}]
    new = not os.path.exists(LOG)
    old = open(LOG).read() if not new else ""
    with open(LOG, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            if f"{ds},{r['bot']}," not in old:
                w.writerow({k: r.get(k, "") for k in FIELDS})
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
