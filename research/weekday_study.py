"""Descriptive only: Study 8 daily results split by weekday (no rule is chosen from this). Read-only data; no orders."""
import sys

import pandas as pd

import qqq_triggers_study as s5
import trend_trail_study as s8

q = s5.load_qqq()
sig = s5.signals(q)
opts = s5.Options(False, q)
names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
for k in ("BASE", "TRAIL", "TREND", "WT"):
    d, n, w = s8.simulate(q, sig, opts, 1, **s8.RULES[k])
    s5.say(f"\n{k} (1 cent): weekday   days  avg/day  up-days  best  worst  total")
    for i, g in d.groupby(d.index.dayofweek):
        s5.say(f"   {names[i]:9s} {len(g):5d} {g.mean():+8.2f} {(g > 0).mean():6.0%} {g.max():+6.0f} {g.min():+6.0f} {g.sum():+8.0f}")
sys.exit(0)
