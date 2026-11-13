"""
Study 7: pause-after-loss rules on the Study 5 engine (research/LOSS_PAUSE_PROTOCOL.md). Read-only data; no orders.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import qqq_triggers_study as s5

HOLDOUT = pd.Timestamp("2026-01-01")
RULES = {"BASE": {}, "W10": {"cool": 10}, "W20": {"cool": 20}, "S2": {"maxrun": 2}, "S3": {"maxrun": 3}}


def simulate(q, sig, opts, cents, cool=0, maxrun=0, target=0.025, stop=0.06, hold=10):
    """Study 5's simulate, plus: after a loss wait `cool` minutes; stop for the day after `maxrun` losses in a row."""
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    rng = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    trades, free_at, run, run_day = [], pd.Timestamp("1900-01-01"), 0, None
    for r in sig.itertuples():
        d = r.t.normalize()
        if d != run_day:
            run, run_day = 0, d
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt:
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
        for i, bar in enumerate(b.itertuples()):
            if i > 0 and bar.open <= stp:
                px = bar.open
            elif bar.low <= stp:
                px = stp
            elif bar.high >= tgt:
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
        if pnl < 0:
            run += 1
            free_at = max(free_at, xt + pd.Timedelta(minutes=cool))
        else:
            run = 0
    tr = pd.DataFrame(trades)
    return tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0), len(tr)


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
    s5.say(f"Study 7. {len(set(q.index.normalize()))} days, {len(sig):,} signals. Protocol: research/LOSS_PAUSE_PROTOCOL.md")
    res = {}
    for cents in (1, 2):
        for k, kw in RULES.items():
            res[(k, cents)] = simulate(q, sig, opts, cents, **kw)
    s5.say(f"\n{'rule':6s} {'cents':>5s} {'trades':>7s} {'per day':>9s} {'holdout/day':>12s} {'vs BASE/day':>12s} {'paired t':>9s}")
    verdict = {}
    for k in RULES:
        ok = True
        for cents in (1, 2):
            d, n = res[(k, cents)]
            b, _ = res[("BASE", cents)]
            diff = d - b
            t = s5.nw_t(diff.to_numpy()) if k != "BASE" else float("nan")
            h = diff[diff.index >= HOLDOUT].mean()
            s5.say(f"{k:6s} {cents:5d} {n:7d} {d.mean():+9.2f} {d[d.index >= HOLDOUT].mean():+12.2f} {diff.mean():+12.2f} {t:+9.2f}")
            if k != "BASE":
                if cents == 1:
                    ok = ok and t >= 2.0 and h > 0
                    verdict[k] = t
                else:
                    ok = ok and diff.mean() > 0
        if k != "BASE":
            verdict[k] = (verdict[k], ok)
    passed = {k: v[0] for k, v in verdict.items() if v[1]}
    s5.say("\nADOPTION (§ adoption line): " + (f"{max(passed, key=passed.get)} passes and is adopted" if passed else
                                                 "no rule passes; the live bot is not changed"))
    for k, (t, ok) in verdict.items():
        s5.say(f"   {k}: {'PASS' if ok else 'fail'} (paired t {t:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
