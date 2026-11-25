"""Study 14 (research/HIS_EXITS_PROTOCOL.md). Read-only data; no orders.  python research/his_exits_study.py [--synthetic]"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
import his_filter_study as s9
import qqq_triggers_study as s5
import stress_study as s11

def sim_hx(q, sig, opts, cents, keep=None, maxrun=2, atr_n=14):
    f = q.resample("5min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc = f.close.shift(1)
    atr = pd.concat([f.high - f.low, (f.high - pc).abs(), (f.low - pc).abs()], axis=1).max(axis=1).rolling(atr_n).mean()
    days = sorted(set(q.index.normalize())); nxt = dict(zip(days[:-1], days[1:]))
    lohi = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    tr, free_at, run, rday = [], pd.Timestamp("1900"), 0, None
    for i, r in enumerate(sig.itertuples()):
        d = r.t.normalize()
        if d != rday: run, rday = 0, d
        if keep is not None and not keep[i]: continue
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt: continue
        b = opts.day(d, nxt[d], lohi.lo[d], lohi.hi[d]).get((r.side, int(round(r.px))))
        if b is None: continue
        b = b[(b.index >= r.t) & (b.index <= d + pd.Timedelta(hours=15, minutes=55))]
        if b.empty or b.index[0] > r.t + pd.Timedelta(minutes=3): continue
        entry = float(b.open.iloc[0])
        a = atr.asof(r.t - pd.Timedelta(minutes=5))
        if entry < 0.5 or not a == a: continue
        side = 1 if r.side == "C" else -1
        q0 = r.px; best_q = 0.0; locked = False; px = xt = why = None
        for bar in b.itertuples():
            qc = q.close.asof(bar.Index)
            fav = (qc - q0) * side
            best_q = max(best_q, fav)
            if fav <= -2.0 * a: px, why = bar.close, "stop (QQQ 2 ATR)"
            elif bar.high >= entry * 1.25: px, why = entry * 1.25, "take profit +25%"
            elif best_q >= 1.5 * a and fav <= best_q / 2: px, why = bar.close, "trail"
            else:
                if bar.high >= entry * 1.035: locked = True
                if locked and bar.low <= entry * 1.02: px, why = entry * 1.02, "lock +2%"
            if px is not None: xt = bar.Index; break
        if px is None: px, xt, why = float(b.close.iloc[-1]), b.index[-1], "end of day"
        pnl = (px - entry) * 100 - 2 * cents - 2 * s5.FEE
        tr.append({"day": d, "pnl": pnl, "why": why}); free_at = xt + pd.Timedelta(minutes=1); run = run + 1 if pnl < 0 else 0
    t = pd.DataFrame(tr, columns=["day", "pnl", "why"])
    return t, t.pnl.groupby(t.day).sum().reindex(days, fill_value=0.0)

def line(lab, t, d):
    w, l = t.pnl[t.pnl > 0], t.pnl[t.pnl <= 0]
    yrs = " ".join(f"{y}:{d[d.index.year == y].mean():+.1f}" for y in sorted(set(d.index.year)))
    s5.say(f"{lab:34s} trades {len(t):5d} win {len(w)/max(len(t),1):4.0%} avg win {w.mean() if len(w) else 0:+7.1f} avg loss {l.mean() if len(l) else 0:+7.1f} "
           f"worst {t.pnl.min() if len(t) else 0:+7.0f} per day {d.mean():+7.2f} t {s5.nw_t(d.to_numpy()):+5.2f} 2026 {d[d.index >= '2026-01-01'].mean():+6.2f} | {yrs}")

def main():
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([x + pd.Timedelta(minutes=570 + m) for x in pd.bdate_range("2025-06-02", "2026-02-27") for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, .12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + .08, "low": c - .08, "close": c, "volume": 1000.0}, index=idx)
    else:
        q = s5.load_qqq()
    opts = s5.Options(syn, q); sig = s9.signals2(q, "09:45"); kp = s11.keep_mask(q, sig)
    for cents in (1, 5):
        s5.say(f"\n=== {cents} cent(s) a side ===")
        for lab, keep in (("HX exits, all signals", None), ("HX exits, picks like him", kp)):
            t, d = sim_hx(q, sig, opts, cents, keep); line(lab, t, d)
            if cents == 1: s5.say("   exits: " + str(t.why.value_counts().to_dict()))
        for lab, keep in (("main-bot exits, all signals", None), ("main-bot exits, picks like him", kp)):
            d, n = s11.simulate(q, sig, opts, cents, keep); s5.say(f"{lab:34s} trades {n:5d} per day {d.mean():+7.2f}")
    rng = np.random.default_rng(14); base = sim_hx(q, sig, opts, 1, kp)[1].mean()
    pl = [sim_hx(q, sig, opts, 1, rng.random(len(sig)) < kp.mean())[1].mean() for _ in range(20)]
    s5.say(f"\nPlacebo (random {kp.mean():.0%} of signals, HX exits): picks {base:+.2f} vs placebo median {np.median(pl):+.2f}, best {max(pl):+.2f}; beats {sum(base > p for p in pl)}/20")
if __name__ == "__main__":
    main()
