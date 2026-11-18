"""
Descriptive scan (no rule is adopted from this): what was happening on the one-minute QQQ chart at each of his entries?
For every minute on his trading days it records which events happened on the bar that had just closed, then reports, per
event, how many of his entries it lines up with (coverage) and how often it happens at all (precision = his entries / events).
Read-only market data; no orders.   python research/his_entries_scan.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

import his_filter_study as s9

q = s9.load_recent()
his = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "state", "discord_trades.csv"))
his["bt"] = pd.to_datetime(his.date + " " + his.buy_time)
days = sorted(pd.to_datetime(his.date.unique()))

day = q.index.normalize()
tp = (q.high + q.low + q.close) / 3
L = {"VWAP": (tp * q.volume).groupby(day).cumsum() / q.volume.groupby(day).cumsum()}
for n in (9, 20, 50):
    L[f"EMA{n}"] = q.close.ewm(span=n, adjust=False).mean()
c, pc = q.close, q.close.shift(1)
same = pd.Series(day, index=q.index).eq(pd.Series(day, index=q.index).shift(1))
ev = {}  # event name -> (up series, down series): "up" means a call setup, "down" a put setup
for n, line in L.items():
    ev[f"close crosses {n}"] = (same & (pc <= line.shift(1)) & (c > line), same & (pc >= line.shift(1)) & (c < line))
ev["EMA9 crosses EMA20"] = (same & (L["EMA9"].shift(1) <= L["EMA20"].shift(1)) & (L["EMA9"] > L["EMA20"]),
                            same & (L["EMA9"].shift(1) >= L["EMA20"].shift(1)) & (L["EMA9"] < L["EMA20"]))
ev["EMA20 crosses EMA50"] = (same & (L["EMA20"].shift(1) <= L["EMA50"].shift(1)) & (L["EMA20"] > L["EMA50"]),
                             same & (L["EMA20"].shift(1) >= L["EMA50"].shift(1)) & (L["EMA20"] < L["EMA50"]))
hi5, lo5 = q.high.rolling(5).max().shift(1), q.low.rolling(5).min().shift(1)
ev["close beyond last 5 bars' high/low"] = (same & (c > hi5), same & (c < lo5))
body = c - q.open
rng_ = (q.high - q.low).replace(0, np.nan)
ev["strong candle (body > 60% of range) in that direction"] = (body > 0.6 * rng_, -body > 0.6 * rng_)
ev["2 candles in a row that way"] = ((body > 0) & (body.shift(1) > 0), (body < 0) & (body.shift(1) < 0))
ev["reversal candle (opposite to the previous one)"] = ((body > 0) & (body.shift(1) < 0), (body < 0) & (body.shift(1) > 0))
d_rsi = c.diff()
rsi = 100 - 100 / (1 + d_rsi.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d_rsi.clip(upper=0)).ewm(alpha=1 / 14).mean())
ev["RSI(14) crosses 50"] = (same & (rsi.shift(1) <= 50) & (rsi > 50), same & (rsi.shift(1) >= 50) & (rsi < 50))
ev["price above all 4 lines (call) / below all (put)"] = (
    pd.Series(np.logical_and.reduce([c > L[k] for k in L]), index=q.index),
    pd.Series(np.logical_and.reduce([c < L[k] for k in L]), index=q.index))

# his distinct entries: one per (minute, side)
e = his.assign(m=his.bt.dt.floor("min")).drop_duplicates(["m", "type"])
rows = []
for r in e.itertuples():
    bar = r.m - pd.Timedelta(minutes=1)  # the bar that closed at his entry minute
    if bar not in q.index:
        continue
    k = 0 if r.type == "C" else 1
    hits = [n for n, s in ev.items() if bool(s[k].get(bar, False))]
    ours = any(bool(ev[f"close crosses {n}"][k].get(bar, False)) for n in ("VWAP", "EMA50"))
    rows.append({"date": r.date, "time": r.m.strftime("%H:%M"), "side": "CALL" if r.type == "C" else "PUT",
                 "our signal": ours, "events": hits,
                 "QQQ": round(float(c[bar]), 2), "vs VWAP": round(float(c[bar] - L["VWAP"][bar]), 2),
                 "vs EMA9": round(float(c[bar] - L["EMA9"][bar]), 2), "candle": round(float(body[bar]), 2),
                 "RSI": round(float(rsi[bar]), 0)})
x = pd.DataFrame(rows)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 200)
print(f"His distinct entries on {len(days)} days: {len(x)}; on one of our signals (VWAP/EMA50 cross on that bar): "
      f"{int(x['our signal'].sum())}; not: {int((~x['our signal']).sum())}\n")
print("=== Entries that are NOT our signals ===")
print(x[~x["our signal"]].drop(columns=["our signal"]).to_string(index=False))
print("\n=== Event table over his days (09:31-15:30). coverage = share of his entries on that event (same direction);"
      " occurs = minutes it happened; precision = his entries / occurrences ===")
mins = q.index[(day.isin(days)) & (q.index.strftime("%H:%M") >= "09:30") & (q.index.strftime("%H:%M") <= "15:29")]
out = []
for n, (u, d_) in ev.items():
    occ = int(u.reindex(mins).fillna(False).sum() + d_.reindex(mins).fillna(False).sum())
    cov_all = x.events.apply(lambda h: n in h).mean()
    cov_not = x[~x["our signal"]].events.apply(lambda h: n in h).mean() if (~x["our signal"]).any() else 0
    hits = int(x.events.apply(lambda h: n in h).sum())
    out.append((n, f"{cov_all:.0%}", f"{cov_not:.0%}", occ, f"{hits / occ:.0%}" if occ else "-"))
print(pd.DataFrame(out, columns=["event", "coverage (all his)", "coverage (his not ours)", "occurs", "precision"]).to_string(index=False))
sys.exit(0)
