"""
Study 12 (research/BRAKES_PROTOCOL.md), history parts: A (diagnosis of the live bot) and B test 1 (brakes, stress battery).
Read-only market data; no orders.   python research/brakes_study.py [--synthetic]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import his_filter_study as s9
import qqq_triggers_study as s5

RULES = {"BASE": {}, "PB50": {"pb": 50}, "PB100": {"pb": 100}, "LB100": {"lb": 100}, "PB50LB": {"pb": 50, "lb": 100}}


def simulate(q, sig, opts, cents=1, pb=0, lb=0, cap=None, delay=0, target=0.025, stop=0.06, hold=10, maxrun=2,
             detail=False):
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    rng = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    trades, free_at, run, run_day, dpnl, n_day = [], pd.Timestamp("1900-01-01"), 0, None, 0.0, 0
    for r in sig.itertuples():
        d = r.t.normalize()
        if d != run_day:
            run, run_day, dpnl, n_day = 0, d, 0.0, 0
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt:
            continue
        if (pb and dpnl >= pb) or (lb and dpnl <= -lb) or (cap is not None and n_day >= cap.get(d, 99)):
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
        px = xt = why = None
        for j, bar in enumerate(b.itertuples()):
            if j > 0 and bar.open <= stp:
                px, why = bar.open, "stop"
            elif bar.low <= stp:
                px, why = stp, "stop"
            elif bar.high >= tgt:
                px, why = tgt, "target"
            elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                px, why = bar.close, "time"
            if px is not None:
                xt = bar.Index
                break
        if px is None:
            px, xt, why = float(b.close.iloc[-1]), b.index[-1], "end"
        gross = (px - entry) * 100
        pnl = gross - 2 * cents - 2 * s5.FEE
        rec = {"day": d, "pnl": pnl}
        if detail:
            w10 = b[b.index <= t0 + pd.Timedelta(minutes=hold)]
            after = w10[w10.index > xt]
            rec.update(why=why, gross=gross, entry=entry,
                       stop_then_target=bool(why == "stop" and len(after) and (after.high >= tgt).any()),
                       max10=float(w10.high.max() / entry - 1))
        trades.append(rec)
        free_at = xt + pd.Timedelta(minutes=1)
        run = run + 1 if pnl < 0 else 0
        dpnl += pnl
        n_day += 1
    tr = pd.DataFrame(trades)
    daily = tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0) if len(tr) else pd.Series(0.0, index=days)
    return daily, tr


def diagnose(q, sig, opts):
    say = s5.say
    _, tr = simulate(q, sig, opts, detail=True)
    n = len(tr)
    say(f"\n===== PART A: what is wrong with the live bot ({n:,} trades) =====")
    say(f"Win rate {(tr.pnl > 0).mean():.0%}. Average win ${tr.pnl[tr.pnl > 0].mean():+.2f}, average loss "
        f"${tr.pnl[tr.pnl <= 0].mean():+.2f}, per trade ${tr.pnl.mean():+.2f}.")
    say(f"Average option price ${tr.entry.mean():.2f}: +2.5% is about ${tr.entry.mean() * 2.5:.0f} a contract, "
        f"-6% about ${tr.entry.mean() * 6:.0f}. Costs per round trip in the test: $2.06 (1 cent a side + fees).")
    for why, g in tr.groupby("why"):
        say(f"  exit by {why:6s}: {len(g):6,} trades ({len(g) / n:4.0%}), average ${g.pnl.mean():+7.2f}, total ${g.pnl.sum():+10,.0f}")
    st = tr[tr.why == "stop"]
    say(f"Stopped trades that reached +2.5% later in the same 10 minutes: {st.stop_then_target.mean():.0%} of {len(st):,}")
    tg = tr[tr.why == "target"]
    say(f"Target trades that went on to +5% within 10 minutes: {(tg.max10 >= 0.05).mean():.0%}; to +10%: "
        f"{(tg.max10 >= 0.10).mean():.0%} (of {len(tg):,})")
    say(f"Gross result before costs, per trade: ${tr.gross.mean():+.2f}; costs take ${tr.gross.mean() - tr.pnl.mean():.2f}")
    sgn = np.where(sig.side == "C", 1, -1)
    base_px = q.close.reindex(sig.bar).to_numpy()
    say("QQQ move after a signal, in the signal's direction (average $ / share of signals where it went the right way):")
    for m in (1, 3, 5, 10):
        later = q.close.reindex(sig.bar + pd.Timedelta(minutes=m)).to_numpy()
        mv = (later - base_px) * sgn
        ok = ~np.isnan(mv)
        say(f"  after {m:2d} min: {np.nanmean(mv):+.3f} $  right way {np.mean(mv[ok] > 0):.0%}")


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
    say = s5.say
    diagnose(q, sig, opts)

    say("\n===== PART B, test 1: brakes on 2.7 years =====")
    res = {(k, c): simulate(q, sig, opts, c, **kw) for c in (1, 2, 3, 5) for k, kw in RULES.items()}
    base = res[("BASE", 1)][0]
    days = base.index
    say("Per day at 1 / 2 / 3 / 5 cents (trades at 1 cent):")
    for k in RULES:
        say(f"  {k:7s} " + "  ".join(f"{res[(k, c)][0].mean():+7.2f}" for c in (1, 2, 3, 5)) + f"   ({len(res[(k, 1)][1]):,} trades)")
    for k in list(RULES)[1:]:
        d, tr = res[(k, 1)]
        diff = d - base
        tA = s5.nw_t(diff.to_numpy())
        hold = diff[days >= pd.Timestamp("2026-01-01")].mean()
        A = tA >= 2.0 and hold > 0 and res[(k, 2)][0].mean() > res[("BASE", 2)][0].mean()
        B = d.mean() > 0 and s5.nw_t(d.to_numpy()) >= 2.0 and res[(k, 2)][0].mean() > 0
        say(f"\n--- {k} vs BASE: {diff.mean():+.2f} a day, paired t {tA:+.2f}, holdout {hold:+.2f}  ->  A {'PASS' if A else 'fail'}, "
            f"B {'PASS' if B else 'fail'}")
        t1 = {y: (d[days.year == y].mean(), base[days.year == y].mean()) for y in sorted(set(days.year))}
        tests = {"T1": all(a > b for a, b in t1.values())}
        say("T1 years: " + ", ".join(f"{y} {a:+.2f} vs {b:+.2f}" for y, (a, b) in t1.items()))
        counts = tr.groupby("day").size().reindex(days, fill_value=0).to_numpy()
        prng = np.random.default_rng(12)
        plac = [simulate(q, sig, opts, 1, cap=dict(zip(days, prng.permutation(counts))))[0].mean() for _ in range(20)]
        beaten = sum(d.mean() > p for p in plac)
        tests["T2"] = beaten >= 19
        say(f"T2 placebo (same trade counts, random days): rule {d.mean():+.2f}, placebo median {np.median(plac):+.2f}; beats {beaten}/20")
        t3 = [res[(k, c)][0].mean() - res[("BASE", c)][0].mean() for c in (3, 5)]
        tests["T3"] = all(v > 0 for v in t3)
        say(f"T3 vs BASE at 3c / 5c: {t3[0]:+.2f} / {t3[1]:+.2f}")
        late = simulate(q, sig, opts, 1, delay=1, **RULES[k])[0].mean() - simulate(q, sig, opts, 1, delay=1)[0].mean()
        tests["T4"] = late > 0
        say(f"T4 one minute late vs BASE late: {late:+.2f}")
        arr = diff.to_numpy()
        nb = len(arr) // 5
        blocks = arr[: nb * 5].reshape(nb, 5)
        brng = np.random.default_rng(6)
        boot = np.array([blocks[brng.integers(0, nb, nb)].mean() for _ in range(1000)])
        tests["T6"] = (boot > 0).mean() >= 0.95
        say(f"T6 bootstrap: better in {(boot > 0).mean():.1%}")
        rngd = (q.high.groupby(q.index.normalize()).max() - q.low.groupby(q.index.normalize()).min()).reindex(days)
        dirn = (q.close.groupby(q.index.normalize()).last() - q.open.groupby(q.index.normalize()).first()).reindex(days)
        groups = {"calm": rngd <= rngd.median(), "busy": rngd > rngd.median(), "up": dirn > 0, "down": dirn <= 0}
        t7 = {n: (d[g].mean(), base[g].mean()) for n, g in groups.items()}
        tests["T7"] = all(a > b for a, b in t7.values())
        say("T7: " + ", ".join(f"{n} {a:+.2f} vs {b:+.2f}" for n, (a, b) in t7.items()))
        say(f"VERDICT {k}: " + ", ".join(f"{t} {'PASS' if v else 'fail'}" for t, v in tests.items())
            + f" ({sum(tests.values())}/6) | A {'PASS' if A else 'fail'} | B {'PASS' if B else 'fail'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
