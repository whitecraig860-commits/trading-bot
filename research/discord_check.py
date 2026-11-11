"""
Do a Discord group's posted QQQ option trades match real market prices?
=======================================================================
Takes the trades exactly as posted (read off screenshots), finds the real option contract on Alpaca, and checks
whether each claimed fill price actually traded during that minute (inside the 1-minute bar's low..high).
The posts don't say the expiry, so 11/11, 11/12, 11/13 and 11/16 are all tried; the expiry that fits best is kept.
Read-only market data. Nothing is traded.
"""
import os

import pandas as pd
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import OptionBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

NY = "America/New_York"
DAY = "2026-11-11"
# (trader, qty, strike, side, buy price, buy time ET, sell price, sell time ET or None, posted P&L)
TRADES = [
    ("#2", 5, 686, "C", 4.21, "10:02:01", 4.30, "10:02:13", 45),
    ("#3", 14, 686, "C", 4.34, "10:02:12", 4.47, "10:07:16", 182),
    ("#1", 15, 686, "C", 4.47, "10:03:11", None, None, None),
    ("#2", 6, 686, "P", 4.13, "10:04:01", 4.22, "10:04:28", 54),
    ("?", 19, 693, "C", None, None, 4.06, "12:14:44", 171),
    ("?", 18, 693, "C", 4.12, "12:17:01", 4.22, "12:19:46", 180),
    ("#2", 18, 694, "C", 4.16, "12:23:01", 4.18, "12:23:24", 36),
    ("#2", 20, 694, "C", 3.97, "12:31:01", 4.02, "12:33:11", 94),
    ("#2", 20, 694, "P", 3.81, "13:02:01", 3.89, "13:06:26", 160),
    ("#2", 20, 695, "C", 3.74, "13:42:01", 3.87, "13:45:17", 260),
    ("#2", 20, 695, "C", 3.74, "13:51:01", 3.57, "13:54:41", -340),
    ("#2", 20, 695, "P", 3.60, "13:57:01", 3.67, "14:00:05", 140),
]
EXPIRIES = ["2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16"]

oc = OptionHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
sc = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
t0 = pd.Timestamp(f"{DAY} 09:30", tz=NY)
t1 = pd.Timestamp(f"{DAY} 16:00", tz=NY)
cache = {}


def bars(sym):
    if sym not in cache:
        try:
            df = oc.get_option_bars(OptionBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                                                      start=t0.tz_convert("UTC").to_pydatetime(),
                                                      end=t1.tz_convert("UTC").to_pydatetime())).df
            if df is not None and len(df):
                df = df.xs(sym, level=0) if isinstance(df.index, pd.MultiIndex) else df
                df.index = pd.DatetimeIndex(df.index).tz_convert(NY)
            else:
                df = pd.DataFrame()
        except Exception as exc:
            print(f"{sym}: {type(exc).__name__}: {str(exc)[:120]}")
            df = pd.DataFrame()
        cache[sym] = df
    return cache[sym]


def check(df, price, hhmmss):
    """Where the claimed price sits vs the real trades in that minute (and the minutes either side)."""
    if price is None or hhmmss is None:
        return None, "n/a"
    t = pd.Timestamp(f"{DAY} {hhmmss}", tz=NY).floor("min")
    if df.empty:
        return None, "no data"
    b = df[(df.index >= t - pd.Timedelta(minutes=1)) & (df.index <= t + pd.Timedelta(minutes=1))]
    if b.empty:
        return None, "no trades that minute"
    lo, hi = float(b["low"].min()), float(b["high"].max())
    exact = df[df.index == t]
    tag = f"real {lo:.2f}-{hi:.2f}"
    if len(exact):
        tag += f" (that minute {float(exact['low'].iloc[0]):.2f}-{float(exact['high'].iloc[0]):.2f}, " \
               f"vol {int(exact['volume'].iloc[0])})"
    dist = 0.0 if lo <= price <= hi else min(abs(price - lo), abs(price - hi))
    return dist, tag


q = sc.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute,
                                       start=t0.tz_convert("UTC").to_pydatetime(),
                                       end=t1.tz_convert("UTC").to_pydatetime())).df
q = q.xs("QQQ", level=0)
q.index = pd.DatetimeIndex(q.index).tz_convert(NY)
print(f"QQQ on {DAY}: open {q['open'].iloc[0]:.2f}, high {q['high'].max():.2f}, low {q['low'].min():.2f}, "
      f"close {q['close'].iloc[-1]:.2f}\n")

for tr in TRADES:
    who, qty, k, side, bp, bt, sp, st, pnl = tr
    best = None
    for exp in EXPIRIES:
        sym = f"QQQ{pd.Timestamp(exp):%y%m%d}{side}{k * 1000:08d}"
        df = bars(sym)
        db, tb = check(df, bp, bt)
        ds, ts = check(df, sp, st)
        score = sum(x for x in (db, ds) if x is not None) + 10 * sum(x is None for x in (db, ds) if True)
        if best is None or score < best[0]:
            best = (score, sym, db, tb, ds, ts)
    _, sym, db, tb, ds, ts = best
    under = q[q.index <= pd.Timestamp(f"{DAY} {bt or st}", tz=NY).floor("min")]["close"]
    print(f"Trader {who} {qty}x {sym}  (QQQ then {float(under.iloc[-1]):.2f})")
    for lab, p, t, d, tag in (("BUY ", bp, bt, db, tb), ("SELL", sp, st, ds, ts)):
        if p is None:
            continue
        verdict = "n/a" if d is None else ("MATCHES a real price" if d == 0 else f"OFF by ${d:.2f} - never traded there")
        print(f"   {lab} {p:.2f} at {t}: {tag} -> {verdict}")
    if bp and sp:
        print(f"   held {(pd.Timestamp(f'{DAY} {st}') - pd.Timestamp(f'{DAY} {bt}')).seconds}s, "
              f"move ${sp - bp:+.2f} per share = {(sp - bp) / bp:+.1%}; posted P&L ${pnl}")
    print()
