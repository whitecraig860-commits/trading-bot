"""
Study 10 (research/MOMENTUM_PICK_PROTOCOL.md): momentum-based picking of signals, on 2.7 years of real option bars.
Read-only market data; no orders.   python research/momentum_pick_study.py
"""

from __future__ import annotations

import sys

import pandas as pd

import his_filter_study as s9
import qqq_triggers_study as s5

HOLDOUT = pd.Timestamp("2026-01-01")


def add_features(q: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    e9 = q.close.ewm(span=9, adjust=False).mean()
    e20 = q.close.ewm(span=20, adjust=False).mean()
    body = q.close - q.open
    rng = (q.high - q.low)
    b = sig.bar
    up = (sig.side == "C").to_numpy()
    d920 = (e9 - e20).reindex(b).to_numpy()
    bd = body.reindex(b).to_numpy()
    rg = rng.reindex(b).to_numpy()
    sig = sig.copy()
    # these are SKIP flags: True means the rule would not take the signal
    sig["noM1"] = ~((up & (d920 > 0)) | (~up & (d920 < 0)))
    sig["noM2"] = ~((up & (bd > 0.6 * rg)) | (~up & (-bd > 0.6 * rg)))
    sig["noM3"] = (sig.t.dt.strftime("%H:%M") >= "12:00").to_numpy()
    sig["noM4"] = sig.noM1 | sig.noM2
    sig["noALL"] = sig.noM1 | sig.noM2 | sig.noM3 | sig.F3
    return sig


def main() -> int:
    q = s5.load_qqq()
    sig = add_features(q, s9.signals2(q, "09:45"))
    opts = s5.Options(False, q)
    rules = {"BASE": None, "M1": "noM1", "M2": "noM2", "M3": "noM3", "M4": "noM4", "ALL": "noALL"}
    s5.say(f"Study 10. {len(set(q.index.normalize()))} days, {len(sig):,} signals. "
           + ", ".join(f"{k} keeps {(~sig[v]).mean():.0%}" for k, v in rules.items() if v))
    res = {(k, c): s9.simulate(q, sig, opts, c, skip=v) for c in (1, 2) for k, v in rules.items()}
    s5.say(f"\n{'rule':6s} {'cents':>5s} {'trades':>7s} {'win%':>5s} {'per day':>9s} {'own t':>7s} {'holdout/day':>12s} "
           f"{'vs BASE/day':>12s} {'paired t':>9s}")
    passA, passB = {}, []
    for k in rules:
        okA = okB = True
        tA = float("nan")
        for c in (1, 2):
            d, n, w = res[(k, c)]
            diff = d - res[("BASE", c)][0]
            tp = s5.nw_t(diff.to_numpy()) if k != "BASE" else float("nan")
            to = s5.nw_t(d.to_numpy())
            h = d[d.index >= HOLDOUT].mean()
            s5.say(f"{k:6s} {c:5d} {n:7d} {w:5.0%} {d.mean():+9.2f} {to:+7.2f} {h:+12.2f} {diff.mean():+12.2f} {tp:+9.2f}")
            if c == 1:
                tA = tp
                okA = okA and tp >= 2.0 and diff[diff.index >= HOLDOUT].mean() > 0
                okB = okB and d.mean() > 0 and to >= 2.0 and h > 0
            else:
                okA = okA and diff.mean() > 0
                okB = okB and d.mean() > 0
        if k != "BASE":
            passA[k] = (tA, okA)
        if okB:
            passB.append(k)
    s5.say("\nA (better than the live bot): " + ", ".join(f"{k} {'PASS' if ok else 'fail'} (t {t:+.2f})" for k, (t, ok) in passA.items()))
    s5.say("B (profitable on its own): " + (", ".join(passB) if passB else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
