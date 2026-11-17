"""
Study 8: wider stop, trailing exit, trend-only entries on the Study 5 engine (research/TREND_TRAIL_PROTOCOL.md).
Read-only data; no orders.   python research/trend_trail_study.py [--synthetic]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import qqq_triggers_study as s5

HOLDOUT = pd.Timestamp("2026-01-01")
RULES = {"BASE": {}, "WIDE": {"stop": 0.12}, "TRAIL": {"trail": 0.015, "hold": 15}, "TREND": {"trend": True},
         "WT": {"stop": 0.12, "trail": 0.015, "hold": 15},
         "ALL": {"stop": 0.12, "trail": 0.015, "hold": 15, "trend": True}}


def simulate(q, sig, opts, cents, target=0.025, stop=0.06, hold=10, trail=0.0, trend=False, maxrun=2):
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    rng = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    day_open = q.open.groupby(q.index.normalize()).first()
    trades, free_at, run, run_day = [], pd.Timestamp("1900-01-01"), 0, None
    for r in sig.itertuples():
        d = r.t.normalize()
        if d != run_day:
            run, run_day = 0, d
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt:
            continue
        if trend and ((r.side == "C" and r.px <= day_open[d]) or (r.side == "P" and r.px >= day_open[d])):
            continue
        b = opts.day(d, nxt[d], rng.lo[d], rng.hi[d]).get((r.side, int(round(r.px))))
        if b is None:
            continue
        b = b[(b.index >= r.t) & (b.index <= d + pd.Timedelta(hours=15, minutes=55))]
        if b.empty or b.index[0] > r.t + pd.Timedelta(minutes=3):
            continue
        entry = float(b.open.iloc[0])
        if entry < 0.5:
            continue
        tgt, stp, t0 = entry * (1 + target), entry * (1 - stop), b.index[0]
        px = xt = None
        best = None
        for i, bar in enumerate(b.itertuples()):
            if best is not None:  # trailing
                lvl = best * (1 - trail)
                if bar.open <= lvl:
                    px = bar.open
                elif bar.low <= lvl:
                    px = lvl
                elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                    px = bar.close
                best = max(best, bar.high) if px is None else best
            elif i > 0 and bar.open <= stp:
                px = bar.open
            elif bar.low <= stp:
                px = stp
            elif bar.high >= tgt:
                if trail:
                    best = bar.high
                    if bar.close <= best * (1 - trail):
                        px = bar.close
                else:
                    px = tgt
            elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                px = bar.close
            if px is not None:
                xt = bar.Index
                break
        if px is None:
            px, xt = float(b.close.iloc[-1]), b.index[-1]
        pnl = (px - entry - 2 * cents / 100) * 100 - 2 * s5.FEE
        trades.append({"day": d, "pnl": pnl})
        free_at = xt + pd.Timedelta(minutes=1)
        run = run + 1 if pnl < 0 else 0
    tr = pd.DataFrame(trades)
    wins = float((tr.pnl > 0).mean()) if len(tr) else 0.0
    return tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0), len(tr), wins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    if a.synthetic:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2025-11-03", "2026-02-27")
                                for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.12, len(idx)))
        q = pd.DataFrame({"open": c, "high": c + 0.08, "low": c - 0.08, "close": c + rng.normal(0, 0.03, len(idx)),
                          "volume": 1000.0}, index=idx)
        s5.say("*** SYNTHETIC DATA: results are meaningless ***")
    else:
        q = s5.load_qqq()
    sig = s5.signals(q)
    opts = s5.Options(a.synthetic, q)
    s5.say(f"Study 8. {len(set(q.index.normalize()))} days, {len(sig):,} signals. Protocol: research/TREND_TRAIL_PROTOCOL.md")
    res = {(k, c): simulate(q, sig, opts, c, **kw) for c in (1, 2) for k, kw in RULES.items()}
    s5.say(f"\n{'rule':6s} {'cents':>5s} {'trades':>7s} {'win%':>5s} {'per day':>9s} {'own t':>7s} {'holdout/day':>12s} "
           f"{'vs BASE/day':>12s} {'paired t':>9s}")
    a_pass, b_pass = {}, []
    for k in RULES:
        okA = okB = True
        for c in (1, 2):
            d, n, w = res[(k, c)]
            base = res[("BASE", c)][0]
            diff = d - base
            tp = s5.nw_t(diff.to_numpy()) if k != "BASE" else float("nan")
            to = s5.nw_t(d.to_numpy())
            hold = d[d.index >= HOLDOUT].mean()
            s5.say(f"{k:6s} {c:5d} {n:7d} {w:5.0%} {d.mean():+9.2f} {to:+7.2f} {hold:+12.2f} {diff.mean():+12.2f} {tp:+9.2f}")
            if c == 1:
                okA = okA and tp >= 2.0 and diff[diff.index >= HOLDOUT].mean() > 0
                okB = okB and d.mean() > 0 and to >= 2.0 and hold > 0
                if k != "BASE":
                    a_pass[k] = (tp, None)
            else:
                okA = okA and diff.mean() > 0
                okB = okB and d.mean() > 0
        if k != "BASE":
            a_pass[k] = (a_pass[k][0], okA)
        if okB:
            b_pass.append(k)
    passed = {k: v[0] for k, v in a_pass.items() if v[1]}
    s5.say("\nA (better than the live bot): " + (f"{max(passed, key=passed.get)} passes and is adopted" if passed else
                                                 "no rule passes; the main paper bot is not changed"))
    for k, (t, ok) in a_pass.items():
        s5.say(f"   {k}: {'PASS' if ok else 'fail'} (paired t {t:+.2f})")
    s5.say("B (profitable on its own): " + (", ".join(b_pass) if b_pass else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
