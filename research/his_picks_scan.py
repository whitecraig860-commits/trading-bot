"""
Descriptive scan (no rule is adopted from this): among OUR signals on his trading days, how do the ones he took differ
from the ones he skipped? Compares the two groups on measurable features at the signal bar.
Read-only market data; no orders.   python research/his_picks_scan.py
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

sig = s9.signals2(q, "09:31")
sig = sig[sig.day.isin(days)].copy()
sig["taken"] = [bool(((his.bt >= r.t) & (his.bt <= r.t + pd.Timedelta(seconds=60)) & (his.type == r.side)).any())
                for r in sig.itertuples()]

day = q.index.normalize()
tp = (q.high + q.low + q.close) / 3
vwap = (tp * q.volume).groupby(day).cumsum() / q.volume.groupby(day).cumsum()
e9, e20, e50 = (q.close.ewm(span=n, adjust=False).mean() for n in (9, 20, 50))
body = q.close - q.open
d = q.close.diff()
rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
atr = (q.high - q.low).rolling(14).mean()
sgn = np.where(sig.side == "C", 1, -1)
b = sig.bar
f = pd.DataFrame({
    "cross size $": sig.dist.to_numpy(),
    "candle size in its direction $": body.reindex(b).to_numpy() * sgn,
    "candle size / avg range": body.reindex(b).to_numpy() * sgn / atr.reindex(b).to_numpy(),
    "minutes since previous signal": sig.gap.to_numpy(),
    "price vs EMA9 in its direction $": (q.close - e9).reindex(b).to_numpy() * sgn,
    "EMA9 vs EMA20 in its direction $": (e9 - e20).reindex(b).to_numpy() * sgn,
    "price vs VWAP in its direction $": (q.close - vwap).reindex(b).to_numpy() * sgn,
    "RSI (calls) / 100-RSI (puts)": np.where(sgn > 0, rsi.reindex(b).to_numpy(), 100 - rsi.reindex(b).to_numpy()),
    "move over last 5 min in its direction $": (q.close - q.close.shift(5)).reindex(b).to_numpy() * sgn,
    "volume / 20-bar average": (q.volume / q.volume.rolling(20).mean()).reindex(b).to_numpy(),
    "minutes after 09:30": ((sig.bar - sig.day).dt.total_seconds() / 60 - 570).to_numpy(),
}, index=sig.index)
f["taken"] = sig.taken.to_numpy()
pd.set_option("display.width", 250)
print(f"Our signals on his {len(days)} days: {len(f)}; he took {int(f.taken.sum())}.\n")
print("Median of each feature: signals he TOOK vs signals he SKIPPED (and how well it separates them: 0.5 = not at all)")
out = []
for col in f.columns.drop("taken"):
    a, s_ = f.loc[f.taken, col].dropna(), f.loc[~f.taken, col].dropna()
    # probability that a random taken signal has a higher value than a random skipped one (AUC)
    auc = (np.searchsorted(np.sort(s_.to_numpy()), a.to_numpy(), side="left").sum()
           + 0.5 * sum(int((s_ == v).sum()) for v in a)) / (len(a) * len(s_)) if len(a) and len(s_) else np.nan
    out.append((col, round(a.median(), 2), round(s_.median(), 2), round(auc, 2)))
print(pd.DataFrame(out, columns=["feature", "took (median)", "skipped (median)", "separation (AUC)"])
      .sort_values("separation (AUC)", key=lambda v: -abs(v - 0.5)).to_string(index=False))
print("\nBy trigger (took / all): " + ", ".join(f"{k} {int(g.taken.sum())}/{len(g)}" for k, g in sig.groupby("trigger")))
print("By side (took / all): " + ", ".join(f"{k} {int(g.taken.sum())}/{len(g)}" for k, g in sig.groupby("side")))
print("\nEvery signal he took:")
print(pd.concat([sig.loc[f.taken, ["t", "side", "trigger"]], f.loc[f.taken].drop(columns="taken").round(2)], axis=1)
      .to_string(index=False))
sys.exit(0)
