"""
Audit part 3 (research/AUDIT3_PROTOCOL.md). Measures only; changes no bot. Read-only market data; no orders.
python research/audit3.py [--synthetic]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import audit2 as a2
import one_a_day_study as s6
import qqq_triggers_study as s5

say = s5.say


def run3(q, prep, opt, exit_delay=0, exit_fail=0.0, stop_slip=1.0, seed=0, price=False, dte=1):
    """One-a-day engine with exit stress and extra features per trade."""
    opens, sigma, vwap, atr = prep
    rng = np.random.default_rng(seed)
    days = sorted(set(q.index.normalize()))
    out = []
    for i, d in enumerate(days):
        if i + dte >= len(days) or d not in sigma.index or sigma.loc[d].isna().all():
            continue
        g = q[q.index.normalize() == d]
        if len(g) < 300:
            continue
        orb = g.iloc[:15]
        hi, lo, o = orb.high.max(), orb.low.min(), opens[d]
        trade = None
        for hh in range(10 * 60, 14 * 60 + 1, 10):
            t = d + pd.Timedelta(minutes=hh - 1)
            if t not in g.index:
                continue
            a = atr.get(d + pd.Timedelta(minutes=hh - 5))
            sg = sigma.loc[d].get(hh - 1)
            if a is None or a != a or sg != sg:
                continue
            c, vw = g.close[t], vwap[t]
            up = c > hi + 0.3 * a and c > vw and c > o * (1 + sg)
            dn = c < lo - 0.3 * a and c < vw and c < o * (1 - sg)
            if up or dn:
                trade = (t, 1 if up else -1, a, sg)
                break
        if not trade:
            continue
        t, side, a, sg = trade
        entry = g.close[t]
        rest = g[g.index > t]
        bars_ = list(rest.itertuples())
        best, why, xt, xp = 0.0, "time", None, None
        j = 0
        while j < len(bars_):
            bar = bars_[j]
            fav = (bar.close - entry) * side
            best = max(best, fav)
            sig = None
            if fav <= -10 * a:
                sig = "safety stop"
            elif best >= 4 * a and fav <= best / 2:
                sig = "trail"
            elif bar.Index >= d + pd.Timedelta(hours=15, minutes=44):
                sig = "time"
            if sig:
                if exit_fail and sig != "time" and rng.random() < exit_fail:
                    j += 1  # the exit order failed; the bot re-checks on the next bar
                    continue
                k = min(j + exit_delay, len(bars_) - 1)
                xb = bars_[k]
                xp = xb.close
                if sig == "safety stop" and stop_slip > 1:
                    xp = entry - side * 10 * a * stop_slip  # the stop filled at a multiple of its distance
                why, xt = sig, xb.Index
                break
            j += 1
        if xt is None:
            xt, xp = rest.index[-1], rest.close.iloc[-1]
        p1500 = rest.close.asof(d + pd.Timedelta(hours=15)) if (rest.index <= d + pd.Timedelta(hours=15)).any() else np.nan
        first30 = g.close.asof(d + pd.Timedelta(hours=9, minutes=59)) / o - 1
        rec = {"day": d, "t": t, "side": side, "entry": entry, "exit": xp, "why": why, "atr": a, "sg": sg, "open": o,
               "mins": (xt - t).total_seconds() / 60, "best_atr": best / a, "ret%": (xp - entry) * side / entry * 100,
               "first30": first30, "late_drift%": ((xp - p1500) * side / entry * 100) if p1500 == p1500 and xt > d + pd.Timedelta(hours=15) else np.nan}
        if price:
            typ = "C" if side > 0 else "P"
            ob = opt.bars(d, days[i + dte], typ, round(entry))
            o_in = o_out = None
            if len(ob):
                e = ob[(ob.index > t) & (ob.index <= t + pd.Timedelta(minutes=5))]
                x = ob[(ob.index <= xt) & (ob.index >= xt - pd.Timedelta(minutes=10)) & (ob.index > t)]
                if len(e) and len(x) and x.index[-1] > e.index[0]:
                    o_in, o_out = float(e.open.iloc[0]), float(x.close.iloc[-1])
            rec.update(o_in=o_in, o_out=o_out)
        out.append(rec)
    return pd.DataFrame(out)


def mc_table(rets_frac, per_year, balances, label, cost_frac=0.0, n=5000, seed=11):
    """rets_frac: per-trade return as a fraction of the position; the position = the whole balance (no leverage)."""
    rng = np.random.default_rng(seed)
    say(f"\n{label}: 5,000 simulated years of {per_year} trades (resampled real trades; NOT historical years)")
    say(f"{'balance':>10s} {'median':>10s} {'5%':>10s} {'95%':>10s} {'P(loss)':>8s} {'P(DD>=10%)':>10s} {'P(DD>=20%)':>10s} "
        f"{'P(DD>=30%)':>10s} {'P(lose half)':>12s} {'losing streak 50%/95%':>22s}")
    r = np.asarray(rets_frac) - cost_frac
    for bal in balances:
        fin, dd, st = np.empty(n), np.empty(n), np.empty(n)
        for i in range(n):
            x = rng.choice(r, per_year)
            eq = bal * np.cumprod(1 + x)
            peak = np.maximum.accumulate(np.r_[bal, eq])[1:]
            dd[i] = ((eq - peak) / peak).min()
            fin[i] = eq[-1] - bal
            s = best = 0
            for v in x:
                s = s + 1 if v <= 0 else 0
                best = max(best, s)
            st[i] = best
        say(f"{bal:>10,.0f} {np.median(fin):>+10,.0f} {np.percentile(fin, 5):>+10,.0f} {np.percentile(fin, 95):>+10,.0f} "
            f"{(fin < 0).mean():>8.0%} {(dd <= -0.10).mean():>10.0%} {(dd <= -0.20).mean():>10.0%} {(dd <= -0.30).mean():>10.0%} "
            f"{(fin <= -bal / 2).mean():>12.0%} {np.median(st):>11.0f} / {np.percentile(st, 95):.0f}")


def main() -> int:
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2019-01-02", "2026-02-27") for m in range(390)])
        c = 300 + np.cumsum(rng.normal(0, 0.08, len(idx)))
        ql = pd.DataFrame({"open": np.r_[300, c[:-1]], "high": c + 0.05, "low": c - 0.05, "close": c, "volume": 1000.0}, index=idx)
    else:
        s5.START, s5.END = "2016-01-01", "2026-11-01"
        ql = s5.load_qqq()
    prep = s6.prepare(ql)
    f = a2.day_features(ql)
    tr = run3(ql, prep, None).reset_index(drop=True)
    tr = tr.join(f.reindex(tr.day).reset_index(drop=True)[["prev_high", "prev_low", "trend20", "vol20"]])
    tr["net%"] = tr["ret%"] - 2 * 0.01 / tr.entry * 100
    tr["year"] = tr.day.dt.year
    early, late = tr.year <= 2021, tr.year >= 2022

    say("=" * 100 + "\nA. Pre-registered pre-entry filters (shares one-a-day, return per trade % after 1 cent a share a side)\n" + "=" * 100)
    inside = np.where(tr.side > 0, tr.prev_high - tr.entry, tr.entry - tr.prev_low) / tr.atr
    moved = (tr.entry - tr.open).abs() / tr.open / tr.sg
    skip = {"FA room to yesterday's extreme > 0.5 ATR": inside > 0.5,
            "FB already moved > 2 noise bands": moved > 2,
            "FC first 30 min against the trade": np.sign(tr.first30) == -tr.side}
    say(f"{'filter':42s} {'period':10s} {'kept':>5s} {'kept avg%':>10s} {'skipped':>8s} {'skipped avg%':>12s} {'all avg%':>9s}")
    for name, sk in skip.items():
        sk = np.asarray(sk, bool)
        impr = []
        for lab, m in (("2016-2021", early), ("2022-2026", late)):
            m = np.asarray(m, bool)
            kept, drop = tr[m & ~sk], tr[m & sk]
            impr.append(kept["net%"].mean() - tr[m]["net%"].mean())
            say(f"{name:42s} {lab:10s} {len(kept):5d} {kept['net%'].mean():+10.3f} {len(drop):8d} {drop['net%'].mean():+12.3f} {tr[m]['net%'].mean():+9.3f}")
        d_all = tr["net%"].where(~sk, 0.0) - tr["net%"]  # change per trade from skipping
        t_impr = d_all.mean() / (d_all.std() / np.sqrt(len(d_all))) if d_all.std() > 0 else 0
        useful = all(v > 0 for v in impr) and t_impr >= 2.4
        say(f"{'':42s} improvement t over all years {t_impr:+.2f} -> {'USEFUL' if useful else 'rejected'}")

    say("\n" + "=" * 100 + "\nB. Can it tell when its edge has gone? (trailing average of its own past signals)\n" + "=" * 100)
    for n in (120, 60):
        trail_avg = tr["net%"].shift(1).rolling(n).mean()
        on = trail_avg > 0
        say(f"RD{n}: share of trades taken {on.mean():.0%}")
        say(f"{'year':6s} {'always: sum%':>13s} {'RD: sum%':>9s} {'RD trades':>9s}")
        for y, g in tr.groupby("year"):
            say(f"{y:<6d} {g['net%'].sum():+13.2f} {g['net%'][on[g.index]].sum():+9.2f} {int(on[g.index].sum()):9d}")
        say(f"total  {tr['net%'].sum():+13.2f} {tr['net%'][on].sum():+9.2f}")

    say("\n" + "=" * 100 + "\nC. The 2022 market-structure hypothesis (evidence, not proof)\n" + "=" * 100)
    for lab, m in (("2016-2021", early), ("2022-2026", late), ("2023-2026 (excludes the 2022 bear year)", tr.year >= 2023)):
        g = tr[np.asarray(m, bool)]
        se = g["net%"].std() / np.sqrt(len(g))
        say(f"{lab:42s} trades {len(g):5d}  avg {g['net%'].mean():+.3f}%  (t {g['net%'].mean() / se:+.2f})  late drift 15:00->exit "
            f"{g['late_drift%'].mean():+.3f}%  win {(g['net%'] > 0).mean():.0%}")
    bull = tr["trend20"] > 0
    for lab, m in (("bull-trend days 2016-2021", early & bull), ("bull-trend days 2022-2026", late & bull),
                   ("bear-trend days 2016-2021", early & ~bull), ("bear-trend days 2022-2026", late & ~bull)):
        g = tr[np.asarray(m, bool)]
        say(f"{lab:42s} trades {len(g):5d}  avg {g['net%'].mean():+.3f}%")

    say("\n" + "=" * 100 + "\nD. Remaining stress tests (shares 2016-2026, avg return per trade %, after 1 cent a share a side)\n" + "=" * 100)
    for lab, kw in (("baseline", {}), ("exits 1 min late", {"exit_delay": 1}), ("exits 5 min late", {"exit_delay": 5}),
                    ("10% of exit signals fail", {"exit_fail": 0.10, "seed": 5}), ("safety stop filled at 2x distance", {"stop_slip": 2.0})):
        t2 = run3(ql, prep, None, **kw)
        t2["net%"] = t2["ret%"] - 2 * 0.01 / t2.entry * 100
        say(f"{lab:36s} trades {len(t2):5d}  avg {t2['net%'].mean():+.3f}%  sum {t2['net%'].sum():+.1f}%  worst trade {t2['net%'].min():+.2f}%")
    per_year = int(round(len(tr) / (len(set(ql.index.normalize())) / 252)))
    mc_table(tr["net%"] / 100, per_year, (1270, 6350, 31750), "SHARES, all 2016-2026 trades, whole balance per trade")
    mc_table(tr.loc[late, "net%"] / 100, per_year, (1270,), "SHARES, 2022-2026 trades only")
    mc_table(tr.loc[early, "net%"] / 100, per_year, (1270,), "SHARES, 2016-2021 trades only")

    say("\n--- One-a-day options: exit stress and balances (Mar 2024 - Oct 2026) ---")
    if not syn:
        s5.START, s5.END = "2024-03-01", "2026-11-01"
        q = s5.load_qqq()
    else:
        q = ql[ql.index >= "2024-06-01"]
    prep_o = s6.prepare(q)
    opt = s6.Opt(syn, q)
    nd = len(set(q.index.normalize()))
    for lab, kw in (("baseline", {}), ("exits 1 min late", {"exit_delay": 1}), ("exits 5 min late", {"exit_delay": 5}),
                    ("10% of exit signals fail", {"exit_fail": 0.10, "seed": 5})):
        t2 = run3(q, prep_o, opt, price=True, **kw).dropna(subset=["o_in"])
        pnl = (t2.o_out - t2.o_in) * 100 - 2.06
        say(f"{lab:36s} trades {len(t2):4d}  per day {pnl.sum() / nd:+.2f}  per trade {pnl.mean():+.2f}")
    t2 = run3(q, prep_o, opt, price=True).dropna(subset=["o_in"])
    pnl = ((t2.o_out - t2.o_in) * 100 - 10.06).to_numpy()  # measured-cost level (about 5 cents a side)
    rng = np.random.default_rng(9)
    per_year_o = int(round(len(t2) / (nd / 252)))
    say(f"\nOPTIONS one contract, measured costs ($10.06 a round trip), 5,000 simulated years of {per_year_o} trades (NOT historical years):")
    say(f"{'balance':>10s} {'median':>10s} {'5%':>10s} {'95%':>10s} {'P(loss)':>8s} {'P(DD>=20%)':>10s} {'P(DD>=50%)':>10s} {'P(cannot afford a contract)':>27s}")
    prem = float(np.median(t2.o_in) * 100)
    for bal in (1270, 6350, 31750):
        fin, dd20, dd50, broke = [], 0, 0, 0
        for _ in range(5000):
            b, peak, h20, h50, br = bal, bal, False, False, False
            for v in rng.choice(pnl, per_year_o):
                if b < prem:
                    br = True
                    break
                b += v
                peak = max(peak, b)
                h20 |= b <= peak * 0.8
                h50 |= b <= peak * 0.5
            fin.append(b - bal)
            dd20 += h20
            dd50 += h50
            broke += br
        fin = np.array(fin)
        say(f"{bal:>10,.0f} {np.median(fin):>+10,.0f} {np.percentile(fin, 5):>+10,.0f} {np.percentile(fin, 95):>+10,.0f} {(fin < 0).mean():>8.0%} "
            f"{dd20 / 5000:>10.0%} {dd50 / 5000:>10.0%} {broke / 5000:>27.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
