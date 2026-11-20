"""
Study 13 (research/NEW_ENTRIES_PROTOCOL.md): 5-minute crosses (FIVE), the opening move (OPEN30) and the one-a-day breakout
on next-day at-the-money options (ONEADAY). Read-only market data; no orders.  python research/new_entries_study.py [--synthetic]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import one_a_day_study as s6
import qqq_triggers_study as s5
import stress_study as s11

EXITS = {"FIVE": (0.05, 0.10, 30), "OPEN30": (0.10, 0.10, 60)}


def signals_five(q: pd.DataFrame) -> pd.DataFrame:
    f = q.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    day = f.index.normalize()
    tp = (f.high + f.low + f.close) / 3
    vwap = (tp * f.volume).groupby(day).cumsum() / f.volume.groupby(day).cumsum()
    ema = f.close.ewm(span=50, adjust=False).mean()
    same = pd.Series(day, index=f.index).eq(pd.Series(day, index=f.index).shift(1))
    rows = []
    for name, line in (("VWAP5", vwap), ("EMA50_5", ema)):
        pc, pl = f.close.shift(1), line.shift(1)
        up = same & (pc <= pl) & (f.close > line)
        dn = same & (pc >= pl) & (f.close < line)
        rows += [(t, "C", name) for t in f.index[up]] + [(t, "P", name) for t in f.index[dn]]
    s = pd.DataFrame(rows, columns=["bar", "side", "trigger"]).sort_values(["bar", "trigger"]).drop_duplicates("bar")
    s["t"] = s.bar + pd.Timedelta(minutes=5)
    s["px"] = f.close.reindex(s.bar).to_numpy()
    tod = s.t.dt.strftime("%H:%M")
    return s[(tod >= "09:45") & (tod <= "15:30")].reset_index(drop=True)


def signals_open30(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for d, g in q.groupby(q.index.normalize()):
        b = d + pd.Timedelta(hours=9, minutes=59)
        if b not in g.index or len(g) < 30:
            continue
        mv = g.close[b] / g.open.iloc[0] - 1
        if abs(mv) >= 0.0025:
            rows.append((b, "C" if mv > 0 else "P", "OPEN30", d + pd.Timedelta(hours=10), g.close[b]))
    return pd.DataFrame(rows, columns=["bar", "side", "trigger", "t", "px"])


def placebo(q, sig, rng) -> pd.DataFrame:
    """Same number of entries per day as `sig`, at random minutes 09:45-15:30, with a random side."""
    rows = []
    for d, g in sig.groupby(sig.t.dt.normalize()):
        mins = rng.choice(np.arange(9 * 60 + 45, 15 * 60 + 31), size=len(g), replace=False)
        for m in sorted(mins):
            t = d + pd.Timedelta(minutes=int(m))
            b = t - pd.Timedelta(minutes=1)
            if b in q.index:
                rows.append((b, rng.choice(["C", "P"]), "RANDOM", t, q.close[b]))
    return pd.DataFrame(rows, columns=["bar", "side", "trigger", "t", "px"])


def predict(q, sig, say):
    sgn = np.where(sig.side == "C", 1, -1)
    p0 = sig.px.to_numpy()
    parts = []
    for m in (5, 15, 30, 60):
        later = q.close.reindex(sig.t - pd.Timedelta(minutes=1) + pd.Timedelta(minutes=m)).to_numpy()
        mv = (later - p0) * sgn
        ok = ~np.isnan(mv)
        parts.append(f"{m} min: right {np.mean(mv[ok] > 0):.0%}, avg {np.nanmean(mv):+.3f}$")
    say("P  QQQ after the signal: " + " | ".join(parts))


def battery(name, d, base_daily_by_cents, q, say, placebo_means, extra=None):
    days = d.index
    t_own = s5.nw_t(d.to_numpy())
    yrs = {y: d[days.year == y].mean() for y in sorted(set(days.year))}
    beaten = sum(d.mean() > p for p in placebo_means)
    arr = d.to_numpy()
    nb = len(arr) // 5
    blocks = arr[: nb * 5].reshape(nb, 5)
    brng = np.random.default_rng(6)
    boot = np.array([blocks[brng.integers(0, nb, nb)].mean() for _ in range(1000)])
    rngd = (q.high.groupby(q.index.normalize()).max() - q.low.groupby(q.index.normalize()).min()).reindex(days)
    dirn = (q.close.groupby(q.index.normalize()).last() - q.open.groupby(q.index.normalize()).first()).reindex(days)
    groups = {"calm": rngd <= rngd.median(), "busy": rngd > rngd.median(), "up": dirn > 0, "down": dirn <= 0}
    say(f"H  per day at 1/2/3/5 cents: " + " / ".join(f"{v:+.2f}" for v in base_daily_by_cents) + f"; own t {t_own:+.2f}")
    say("T1 years: " + ", ".join(f"{y} {v:+.2f}" for y, v in yrs.items()))
    say(f"T2 placebo: rule {d.mean():+.2f}; placebos median {np.median(placebo_means):+.2f}, best {max(placebo_means):+.2f}; "
        f"rule beats {beaten}/20")
    if extra:
        say(extra)
    say(f"T6 resamples positive: {(boot > 0).mean():.1%}")
    say("T7: " + ", ".join(f"{n} {d[g].mean():+.2f}" for n, g in groups.items()))
    prof = (d.mean() > 0 and t_own >= 2 and base_daily_by_cents[1] > 0 and all(v > 0 for v in yrs.values())
            and beaten >= 19 and (boot > 0).mean() >= 0.95)
    say(f"VERDICT {name}: {'PROFITABLE' if prof else 'not profitable'}")


def main() -> int:
    syn = "--synthetic" in sys.argv
    say = s5.say
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2024-11-04", "2026-02-27")
                                for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + 0.08, "low": c - 0.08, "close": c,
                          "volume": 1000.0}, index=idx)
        say("*** SYNTHETIC DATA: results are meaningless ***")
    else:
        q = s5.load_qqq()
    opts = s5.Options(syn, q)
    say(f"Study 13. {len(set(q.index.normalize()))} days.")

    for name, sig in (("FIVE", signals_five(q)), ("OPEN30", signals_open30(q))):
        tgt, stp, hold = EXITS[name]
        say(f"\n===== {name}: {len(sig):,} signals ({len(sig) / len(set(q.index.normalize())):.1f} a day) =====")
        predict(q, sig, say)
        res = {c: s11.simulate(q, sig, opts, c, None, tgt, stp, hold) for c in (1, 2, 3, 5)}
        d, n = res[1]
        say(f"   trades {n:,}")
        prng = np.random.default_rng(13)
        plac = [s11.simulate(q, placebo(q, sig, prng), opts, 1, None, tgt, stp, hold)[0].mean() for _ in range(20)]
        late = s11.simulate(q, sig, opts, 1, None, tgt, stp, hold, delay=1)[0].mean()
        battery(name, d, [res[c][0].mean() for c in (1, 2, 3, 5)], q, say, plac, extra=f"T4 one minute late: {late:+.2f}")

    say("\n===== ONEADAY: Study 6 breakout on next-day at-the-money options =====")
    prep = s6.prepare(q)
    opt = s6.Opt(syn, q)
    r = s6.run(q, prep, opt, dte=1, itm=0.0)
    tr = r[r.traded.astype(bool)].dropna(subset=["o_in"])
    days = pd.DatetimeIndex(sorted(set(r.day)))
    say(f"   days {len(days)}, trades with option prices {len(tr)}")

    def daily(trd, cents):
        pnl = (trd.o_out - trd.o_in - 2 * cents / 100) * 100 - 2 * s5.FEE
        return pnl.groupby(trd.day).sum().reindex(days, fill_value=0.0)

    sig1 = r[r.traded.astype(bool)]
    s1 = pd.DataFrame({"t": pd.to_datetime(sig1.t) + pd.Timedelta(minutes=1),
                       "side": sig1.side.to_numpy(), "px": sig1.entry.to_numpy()})
    predict(q, s1, say)
    prng = np.random.default_rng(13)
    plac = []
    for _ in range(20):
        rr = s6.run(q, prep, opt, dte=1, itm=0.0, rand_side=prng)
        plac.append(daily(rr[rr.traded.astype(bool)].dropna(subset=["o_in"]), 1).mean())
    battery("ONEADAY", daily(tr, 1), [daily(tr, c).mean() for c in (1, 2, 3, 5)], q, say, plac)
    return 0


if __name__ == "__main__":
    sys.exit(main())
