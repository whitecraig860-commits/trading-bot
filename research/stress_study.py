"""
Study 11 (research/STRESS_PROTOCOL.md): seven stress tests for Study 10's ALL rule and a "his clone" rule.
Read-only market data; no orders.   python research/stress_study.py [--synthetic]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import his_filter_study as s9
import qqq_triggers_study as s5

EXITS = {"BASE": (0.025, 0.06, 10), "ALL": (0.025, 0.06, 10), "CLONE": (0.035, 0.10, 6)}


def keep_mask(q, sig, fast=9, slow=20, frac=0.6, cutoff="12:00", weak=0.10) -> np.ndarray:
    ef = q.close.ewm(span=fast, adjust=False).mean()
    es = q.close.ewm(span=slow, adjust=False).mean()
    body = (q.close - q.open).reindex(sig.bar).to_numpy()
    rng = (q.high - q.low).reindex(sig.bar).to_numpy()
    d = (ef - es).reindex(sig.bar).to_numpy()
    up = (sig.side == "C").to_numpy()
    m1 = (up & (d > 0)) | (~up & (d < 0))
    m2 = (up & (body > frac * rng)) | (~up & (-body > frac * rng))
    m3 = (sig.t.dt.strftime("%H:%M") < cutoff).to_numpy()
    strong = (sig.dist >= weak).to_numpy()
    return m1 & m2 & m3 & strong


def simulate(q, sig, opts, cents, keep=None, target=0.025, stop=0.06, hold=10, delay=0, maxrun=2):
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    rng = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    trades, free_at, run, run_day = [], pd.Timestamp("1900-01-01"), 0, None
    for i, r in enumerate(sig.itertuples()):
        d = r.t.normalize()
        if d != run_day:
            run, run_day = 0, d
        if keep is not None and not keep[i]:
            continue
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt:
            continue
        b = opts.day(d, nxt[d], rng.lo[d], rng.hi[d]).get((r.side, int(round(r.px))))
        if b is None:
            continue
        t_in = r.t + pd.Timedelta(minutes=delay)
        b = b[(b.index >= t_in) & (b.index <= d + pd.Timedelta(hours=15, minutes=55))]
        if b.empty or b.index[0] > t_in + pd.Timedelta(minutes=3):
            continue
        entry = float(b.open.iloc[0])
        if entry < 0.5:
            continue
        tgt, stp, t0 = entry * (1 + target), entry * (1 - stop), b.index[0]
        px = xt = None
        for j, bar in enumerate(b.itertuples()):
            if j > 0 and bar.open <= stp:
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
        run = run + 1 if pnl < 0 else 0
    tr = pd.DataFrame(trades, columns=["day", "pnl"])
    return tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0), len(tr)


def main() -> int:
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2024-11-04", "2026-02-27")
                                for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + 0.08, "low": c - 0.08, "close": c, "volume": 1000.0},
                         index=idx)
        s5.say("*** SYNTHETIC DATA: results are meaningless ***")
    else:
        q = s5.load_qqq()
    sig = s9.signals2(q, "09:45")
    opts = s5.Options(syn, q)
    k_all = keep_mask(q, sig)
    say = s5.say
    say(f"Study 11. {len(set(q.index.normalize()))} days, {len(sig):,} signals; ALL/CLONE keep {k_all.mean():.1%}.")

    def run(rule, cents=1, keep="rule", delay=0):
        t, st, h = EXITS[rule]
        kp = None if rule == "BASE" else (k_all if isinstance(keep, str) else keep)
        return simulate(q, sig, opts, cents, kp, t, st, h, delay)

    res = {(r, c): run(r, c) for r in EXITS for c in (1, 2, 3, 5)}
    base = res[("BASE", 1)][0]
    days = base.index
    verdict = {"ALL": {}, "CLONE": {}}

    say("\nPer day (number of trades) at 1 / 2 / 3 / 5 cents a side:")
    for r in EXITS:
        say(f"  {r:6s} " + "  ".join(f"{res[(r, c)][0].mean():+7.2f} ({res[(r, c)][1]})" for c in (1, 2, 3, 5))
            + f"   own t at 1c {s5.nw_t(res[(r, 1)][0].to_numpy()):+.2f}")
    for r in ("ALL", "CLONE"):
        d = res[(r, 1)][0]
        diff = d - base
        say(f"\n===== {r} vs BASE (1 cent): {diff.mean():+.2f} a day, paired t {s5.nw_t(diff.to_numpy()):+.2f}; "
            f"per trade {d.sum() / max(res[(r, 1)][1], 1):+.2f} vs BASE {base.sum() / res[('BASE', 1)][1]:+.2f}")
        # T1
        yrs = sorted(set(days.year))
        t1 = {y: (d[days.year == y].mean(), base[days.year == y].mean()) for y in yrs}
        verdict[r]["T1 every year"] = all(a > b for a, b in t1.values())
        say("T1 years: " + ", ".join(f"{y} {a:+.2f} vs {b:+.2f}" for y, (a, b) in t1.items()))
        # T2
        rng = np.random.default_rng(11)
        plac = []
        for _ in range(20):
            pk = rng.random(len(sig)) < k_all.mean()
            plac.append(run(r, 1, keep=pk)[0].mean())
        beaten = sum(d.mean() > p for p in plac)
        verdict[r]["T2 placebo 19/20"] = beaten >= 19
        say(f"T2 placebo (random {k_all.mean():.0%} of signals, same exits): rule {d.mean():+.2f}; placebos "
            f"median {np.median(plac):+.2f}, best {max(plac):+.2f}; rule beats {beaten}/20")
        # T3
        t3 = {c: res[(r, c)][0].mean() - res[("BASE", c)][0].mean() for c in (3, 5)}
        verdict[r]["T3 costs"] = all(v > 0 for v in t3.values())
        say("T3 vs BASE at 3c / 5c: " + " / ".join(f"{v:+.2f}" for v in t3.values()))
        # T4
        late_r, late_b = run(r, 1, delay=1)[0].mean(), run("BASE", 1, delay=1)[0].mean()
        verdict[r]["T4 late fill"] = late_r > late_b
        say(f"T4 one minute late: {late_r:+.2f} vs BASE {late_b:+.2f}")
        # T5
        if r == "ALL":
            vs = {"EMA 8/21": dict(fast=8, slow=21), "candle 50%": dict(frac=0.5), "candle 70%": dict(frac=0.7),
                  "cut-off 11:30": dict(cutoff="11:30"), "cut-off 12:30": dict(cutoff="12:30"),
                  "weak $0.05": dict(weak=0.05), "weak $0.15": dict(weak=0.15)}
            t5 = {n: run(r, 1, keep=keep_mask(q, sig, **kw))[0].mean() for n, kw in vs.items()}
            verdict[r]["T5 wobble"] = all(v > base.mean() for v in t5.values())
            say("T5 wobble: " + ", ".join(f"{n} {v:+.2f}" for n, v in t5.items()) + f" (BASE {base.mean():+.2f})")
        # T6
        arr = diff.to_numpy()
        nb = len(arr) // 5
        blocks = arr[: nb * 5].reshape(nb, 5)
        brng = np.random.default_rng(6)
        boot = np.array([blocks[brng.integers(0, nb, nb)].mean() for _ in range(1000)])
        verdict[r]["T6 bootstrap 95%"] = (boot > 0).mean() >= 0.95
        say(f"T6 bootstrap: better than BASE in {(boot > 0).mean():.1%} of 1,000 resamples")
        # T7
        rngd = (q.high.groupby(q.index.normalize()).max() - q.low.groupby(q.index.normalize()).min()).reindex(days)
        dirn = (q.close.groupby(q.index.normalize()).last() - q.open.groupby(q.index.normalize()).first()).reindex(days)
        groups = {"calm": rngd <= rngd.median(), "busy": rngd > rngd.median(), "up days": dirn > 0, "down days": dirn <= 0}
        t7 = {n: (d[g].mean(), base[g].mean()) for n, g in groups.items()}
        verdict[r]["T7 regimes"] = all(a > b for a, b in t7.values())
        say("T7: " + ", ".join(f"{n} {a:+.2f} vs {b:+.2f}" for n, (a, b) in t7.items()))
        # profitable?
        prof = d.mean() > 0 and s5.nw_t(d.to_numpy()) >= 2 and res[(r, 2)][0].mean() > 0 and all(a > 0 for a, _ in t1.values())
        verdict[r]["PROFITABLE"] = prof

    say("\n===== VERDICT")
    for r, v in verdict.items():
        robust = all(ok for k, ok in v.items() if k.startswith("T"))
        say(f"{r}: " + ", ".join(f"{k} {'PASS' if ok else 'fail'}" for k, ok in v.items())
            + f"  ->  {'ROBUST' if robust else 'not robust'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
