"""Study 16 (research/SPY_ONEADAY_PROTOCOL.md): the shares one-a-day rule, unchanged, on SPY 2016-2026. Read-only."""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

import one_a_day_study as s6
import qqq_triggers_study as s5


class NoOpt:
    def bars(self, *a):
        return pd.DataFrame(columns=["open", "close"])


def load(sym, start="2016-01-01", end="2026-11-01"):
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    parts = []
    m = pd.date_range(start, end, freq="MS")
    for a, b in zip(m, m[1:]):
        df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                                                 start=a.tz_localize(s5.NY).tz_convert("UTC").to_pydatetime(),
                                                 end=b.tz_localize(s5.NY).tz_convert("UTC").to_pydatetime(), feed=DataFeed.SIP)).df
        if df is not None and len(df):
            parts.append(df.xs(sym, level=0))
    q = pd.concat(parts)
    q.index = pd.DatetimeIndex(q.index).tz_convert(s5.NY).tz_localize(None)
    q = q.between_time("09:30", "15:59")[["open", "high", "low", "close", "volume"]].astype(float)
    return q[~q.index.duplicated()]


def main():
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(3)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2024-01-01", "2026-06-30") for m in range(390)])
        c = 500 + np.cumsum(rng.normal(0, .12, len(idx)))
        q = pd.DataFrame({"open": c, "high": c + .08, "low": c - .08, "close": c, "volume": 1000.0}, index=idx)
        s5.say("*** SYNTHETIC: meaningless ***")
    else:
        q = load("SPY")
    prep = s6.prepare(q)
    r = s6.run(q, prep, NoOpt())
    days = sorted(set(r.day))
    tr = r[r.traded.astype(bool)]
    d = tr.shares.groupby(tr.day).sum().reindex(days, fill_value=0.0)
    s5.say(f"Study 16 SPY one-a-day (100 shares, $2 a round trip): {len(days)} days, {len(tr)} trades")
    for y in sorted(set(d.index.year)):
        g = d[d.index.year == y]
        s5.say(f"  {y}: {g.mean():+.2f}/day  t {s5.nw_t(g.to_numpy()):+.2f}  trades {int((tr.day.dt.year == y).sum())}")
    rec = d[d.index >= "2022-01-01"]
    old = d[d.index < "2022-01-01"]
    t = s5.nw_t(rec.to_numpy())
    pos_years = sum(rec[rec.index.year == y].mean() > 0 for y in range(2022, 2027))
    s5.say(f"2022-2026: {rec.mean():+.2f}/day t {t:+.2f}; positive years {pos_years}/5; 2026 {d[d.index >= '2026-01-01'].mean():+.2f}")
    s5.say(f"2016-2021 (reported): {old.mean():+.2f}/day t {s5.nw_t(old.to_numpy()) if len(old) > 10 else float('nan'):+.2f}")
    rng = np.random.default_rng(16)
    pl = []
    for _ in range(20):
        rr = s6.run(q[q.index >= "2022-01-01"], s6.prepare(q[q.index >= "2022-01-01"]), NoOpt(), rand_side=rng)
        t2 = rr[rr.traded.astype(bool)]
        pl.append(t2.shares.groupby(t2.day).sum().reindex(sorted(set(rr.day)), fill_value=0.0).mean())
    beats = sum(rec.mean() > p for p in pl)
    s5.say(f"Placebo random side (2022-2026): rule {rec.mean():+.2f} vs median {np.median(pl):+.2f}, best {max(pl):+.2f}; beats {beats}/20")
    ok = rec.mean() > 0 and t >= 2 and pos_years >= 4 and d[d.index >= "2026-01-01"].mean() > 0 and beats >= 19
    s5.say(f"VERDICT: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
