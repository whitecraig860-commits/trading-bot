"""
Audit part 2 (research/AUDIT2_PROTOCOL.md). Measures only; changes no bot. Read-only market data; no orders.
python research/audit2.py [--synthetic]     -> prints every section; the workflow saves the output as audit/audit2_output.txt
"""

from __future__ import annotations

import sys
from statistics import NormalDist

import numpy as np
import pandas as pd

import audit_baseline as ab
import his_filter_study as s9
import one_a_day_study as s6
import qqq_triggers_study as s5

say = s5.say
FX = 1.27  # USD per GBP (approximate)
ACCOUNT_USD = 1000 * FX


def day_features(q: pd.DataFrame) -> pd.DataFrame:
    D = q.index.normalize()
    dc, do = q.close.groupby(D).last(), q.open.groupby(D).first()
    dh, dl = q.high.groupby(D).max(), q.low.groupby(D).min()
    ret = dc.pct_change()
    vol20 = ret.rolling(20).std().shift(1)
    f = pd.DataFrame(index=dc.index)
    f["vol20"] = vol20
    f["vol_rank"] = vol20.rolling(250, min_periods=60).rank(pct=True)
    f["trend20"] = ((dc.shift(1) / dc.shift(21) - 1) / (vol20 * np.sqrt(20)))
    f["gap%"] = (do / dc.shift(1) - 1) * 100
    rng = (dh - dl) / do * 100
    f["dayrange%"] = rng
    f["range20%"] = rng.rolling(20).mean().shift(1)
    first15 = q[(q.index.hour == 9) & (q.index.minute < 45)]
    o15 = (first15.high.groupby(first15.index.normalize()).max() - first15.low.groupby(first15.index.normalize()).min())
    f["orb15"] = o15.reindex(f.index)
    f["orb15_ratio"] = f.orb15 / o15.rolling(20).mean().shift(1).reindex(f.index)
    first30 = q[(q.index.hour == 9) | ((q.index.hour == 10) & (q.index.minute == 0))]
    v30 = first30.volume.groupby(first30.index.normalize()).sum()
    f["relvol30"] = (v30 / v30.rolling(20).mean().shift(1)).reindex(f.index)
    f["prev_high"], f["prev_low"] = dh.shift(1), dl.shift(1)
    f["day_dir"] = np.sign(dc - do)
    return f


def run2(q, prep, opt, dte=1, itm=0.0, trail=4.0, buffer=0.3, stop_atr=10.0, noise_mult=1.0, delay=0, reject=0.0,
         outage=False, seed=0, price=True):
    """Study 6 one-a-day engine with stress options. One trade a day at most."""
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
            up = c > hi + buffer * a and c > vw and c > o * (1 + noise_mult * sg)
            dn = c < lo - buffer * a and c < vw and c < o * (1 - noise_mult * sg)
            if up or dn:
                trade = (t, 1 if up else -1, a)
                break
        if not trade:
            continue
        t, side, a = trade
        if reject and rng.random() < reject:
            out.append({"day": d, "rejected": True})
            continue
        t_fill = t + pd.Timedelta(minutes=delay)
        if t_fill not in g.index:
            continue
        entry = g.close[t_fill]
        rest = g[g.index > t_fill]
        blind_h = int(rng.integers(10, 16)) if outage else -1
        best, why, xt, xp = 0.0, "time", None, None
        for bar in rest.itertuples():
            if bar.Index.hour == blind_h:
                continue  # connection down: no exit checks this hour
            fav = (bar.close - entry) * side
            best = max(best, fav)
            if fav <= -stop_atr * a:
                why, xt, xp = "safety stop", bar.Index, bar.close
                break
            if best >= trail * a and fav <= best / 2:
                why, xt, xp = "trail", bar.Index, bar.close
                break
            if bar.Index >= d + pd.Timedelta(hours=15, minutes=44):
                xt, xp = bar.Index, bar.close
                break
        if xt is None:
            xt, xp = rest.index[-1], rest.close.iloc[-1]
        rec = {"day": d, "rejected": False, "t": t_fill, "side": side, "entry": entry, "exit": xp, "why": why, "atr": a,
               "best_atr": best / a, "mins": (xt - t_fill).total_seconds() / 60,
               "ret%": (xp - entry) * side / entry * 100}
        if price:
            typ = "C" if side > 0 else "P"
            strike = round(entry - itm * side)
            ob = opt.bars(d, days[i + dte], typ, strike)
            o_in = o_out = None
            if len(ob):
                e = ob[(ob.index > t_fill) & (ob.index <= t_fill + pd.Timedelta(minutes=5))]
                x = ob[(ob.index <= xt) & (ob.index >= xt - pd.Timedelta(minutes=10)) & (ob.index > t_fill)]
                if len(e) and len(x) and x.index[-1] > e.index[0]:
                    o_in, o_out = float(e.open.iloc[0]), float(x.close.iloc[-1])
            rec.update(o_in=o_in, o_out=o_out)
        out.append(rec)
    r = pd.DataFrame(out)
    return r[~r.rejected] if len(r) else r


def opt_pnl(r, cents=1.0):
    t = r.dropna(subset=["o_in"]) if "o_in" in r else r.iloc[:0]
    return t.assign(pnl=(t.o_out - t.o_in) * 100 - 2 * cents - 2 * s5.FEE)


def shr_pnl(r, cents=1.0, shares=100):
    return r.assign(pnl=(r.exit - r.entry) * r.side * shares - 2 * cents / 100 * shares)


def perday(tr, ndays):
    return tr.pnl.sum() / ndays


def tstat(tr, days):
    d = tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0)
    return s5.nw_t(d.to_numpy())


def streaks(pnl):
    best = cur = 0
    end = 0
    for i, v in enumerate(pnl):
        cur = cur + 1 if v <= 0 else 0
        if cur > best:
            best, end = cur, i
    return best, end


def section_fast(q, opts):
    say("\n" + "=" * 100 + "\nSECTION 1: can a pre-defined market-condition filter rescue the fast bots' entry?\n" + "=" * 100)
    sig = s9.signals2(q, "09:45")
    f = day_features(q)
    dfe = f.reindex(sig.t.dt.normalize()).reset_index(drop=True)
    side = np.where(sig.side == "C", 1, -1)
    masks = {"none (main bot)": np.ones(len(sig), bool),
             "R1 high-volatility regime": (dfe.vol_rank >= 2 / 3).to_numpy(),
             "R2 wide opening range": (dfe.orb15_ratio >= 1.5).to_numpy(),
             "R3 trend regime, with the trend": ((dfe.trend20.abs() > 1) & (np.sign(dfe.trend20) == side)).to_numpy()}
    later = q.close.reindex(sig.t - pd.Timedelta(minutes=1) + pd.Timedelta(minutes=10)).to_numpy()
    right = (later - sig.px.to_numpy()) * side > 0
    ins = (sig.t < ab.HOLDOUT).to_numpy()
    for name, m in masks.items():
        m = np.nan_to_num(m.astype(float)).astype(bool)
        res = {}
        for lab, part in (("2024-25", ins), ("2026", ~ins)):
            mm = m & part
            keep = mm
            for c in (1, 5):
                tr, days = ab.sim(q, sig, opts, c, keep=keep, target=0.025, stop=0.06, hold=10)
                dsub = [x for x in days if (x < ab.HOLDOUT) == (lab == "2024-25")]
                res[(lab, c)] = (tr.pnl.mean() if len(tr) else float("nan"), len(tr), tstat(tr, dsub) if len(tr) else float("nan"))
            res[(lab, "right")] = right[mm].mean() if mm.any() else float("nan")
        rescue = all(res[(lab, "right")] > 0.52 and res[(lab, 5)][0] > 0 and res[(lab, 5)][2] >= 2.4 for lab in ("2024-25", "2026"))
        say(f"{name:36s} | " + " | ".join(
            f"{lab}: right after 10 min {res[(lab, 'right')]:.1%}, per trade 1c {res[(lab, 1)][0]:+.2f} / 5c {res[(lab, 5)][0]:+.2f} "
            f"({res[(lab, 5)][1]} trades, t {res[(lab, 5)][2]:+.2f})" for lab in ("2024-25", "2026")) + f" | RESCUE: {'YES' if rescue else 'no'}")


def section_options(q, prep, opt):
    say("\n" + "=" * 100 + "\nSECTION 2: one-a-day options forensic\n" + "=" * 100)
    days = sorted(set(q.index.normalize()))
    nd = len(days)
    f = day_features(q)
    r = run2(q, prep, opt)
    tr = opt_pnl(r, 1).reset_index(drop=True)
    tr = tr.join(f.reindex(tr.day).reset_index(drop=True)[["vol_rank", "trend20", "dayrange%", "gap%", "relvol30"]])
    say(f"Trades {len(tr)}, per day {perday(tr, nd):+.2f}, t {tstat(tr, days):+.2f}, total {tr.pnl.sum():+,.0f}")
    top = tr.nlargest(5, "pnl")
    say("\nThe five biggest winners:")
    say(top[["day", "t", "side", "why", "mins", "best_atr", "o_in", "o_out", "pnl", "dayrange%", "vol_rank", "trend20", "gap%"]]
        .round(2).to_string(index=False))
    say(f"Median trade for comparison: day range {tr['dayrange%'].median():.2f}%, vol rank {tr.vol_rank.median():.2f}, "
        f"best move {tr.best_atr.median():.2f} ATR, held {tr.mins.median():.0f} min")
    rest = tr.drop(top.index)
    say(f"\nWithout the five: total {rest.pnl.sum():+,.0f}, per day {perday(rest, nd):+.2f}, t {tstat(rest, days):+.2f}")
    for cut in (0.25, 0.5, 0.75):
        adj = tr.pnl.copy()
        adj.loc[top.index] = adj.loc[top.index] * (1 - cut)
        tt = tr.assign(pnl=adj)
        say(f"Top five cut by {cut:.0%}: total {tt.pnl.sum():+,.0f}, per day {perday(tt, nd):+.2f}, t {tstat(tt, days):+.2f}")
    unf = tr[(tr.vol_rank < 1 / 3) | (tr.trend20.abs() > 1) | (tr["dayrange%"] < tr["dayrange%"].median())]
    rng = np.random.default_rng(20)
    sims = np.array([rng.choice(unf.pnl.to_numpy(), 20).sum() for _ in range(5000)])
    say(f"\nNext 20 trades all on unfavourable days (calm, trending or below-median range; pool of {len(unf)} trades, 5,000 runs): "
        f"median {np.median(sims):+,.0f}, 5% {np.percentile(sims, 5):+,.0f}, 95% {np.percentile(sims, 95):+,.0f}, "
        f"chance of a loss {(sims < 0).mean():.0%}")
    n, end = streaks(tr.pnl.to_numpy())
    st = tr.iloc[end - n + 1:end + 1]
    say(f"\nLongest losing streak: {n} trades, {st.day.iloc[0].date()} to {st.day.iloc[-1].date()}, total {st.pnl.sum():+,.0f}; "
        f"median day range in the streak {st['dayrange%'].median():.2f}% (all trades {tr['dayrange%'].median():.2f}%), "
        f"exits {st.why.value_counts().to_dict()}, sides {st.side.value_counts().to_dict()}")
    per_year = int(round(len(tr) / (nd / 252)))
    ms = [streaks(rng.choice(tr.pnl.to_numpy(), per_year))[0] for _ in range(5000)]
    say(f"Longest losing streak in a simulated year ({per_year} trades, 5,000 runs): median {np.median(ms):.0f}, "
        f"95% {np.percentile(ms, 95):.0f}, 99% {np.percentile(ms, 99):.0f}")
    say("\nBy market condition (per day on those days):")
    dsr = tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0)
    ff = f.reindex(days)
    conds = {"calm (vol rank < 1/3)": ff.vol_rank < 1 / 3, "volatile (vol rank > 2/3)": ff.vol_rank > 2 / 3,
             "trending (|trend20| > 1)": ff.trend20.abs() > 1, "sideways (|trend20| < 0.5)": ff.trend20.abs() < 0.5}
    for k, m in conds.items():
        m = m.fillna(False).to_numpy()
        say(f"  {k:28s} {m.sum():4d} days  {dsr[m].mean():+8.2f}")
    say("\nCosts (per round trip assumed in the test: 2 x cents + $0.06):")
    for c in (1, 3, 5, 7, 10):
        t2 = opt_pnl(r, c)
        say(f"  {c:2d} cents a side (${2 * c + 0.06:.2f} a trade): per day {perday(t2, nd):+.2f}, t {tstat(t2, days):+.2f}")
    k = 30
    z = NormalDist().inv_cdf(1 - 0.05 / (2 * k))
    say(f"\nMultiple testing: about {k} strategy variants were tested in Studies 5-13. Bonferroni line (two-sided 5%): t >= {z:.2f}. "
        f"This bot's t: {tstat(tr, days):+.2f} -> {'significant' if tstat(tr, days) >= z else 'NOT significant after correction'}.")
    return r, tr


def stress(label, q, prep, opt, pnlf, price, days):
    nd = len(days)
    base = run2(q, prep, opt, price=price)
    b = pnlf(base)
    rows = [("baseline", b)]
    for dl in (1, 2):
        rows.append((f"entry {dl} min late", pnlf(run2(q, prep, opt, delay=dl, price=price))))
    rows.append(("10% of orders rejected", pnlf(run2(q, prep, opt, reject=0.10, seed=3, price=price))))
    rows.append(("1-hour outage daily (blind)", pnlf(run2(q, prep, opt, outage=True, seed=4, price=price))))
    for nm, kw in (("range buffer 0.24", {"buffer": 0.24}), ("range buffer 0.36", {"buffer": 0.36}),
                   ("trail 3.2 ATR", {"trail": 3.2}), ("trail 4.8 ATR", {"trail": 4.8}),
                   ("stop 8 ATR", {"stop_atr": 8}), ("stop 12 ATR", {"stop_atr": 12}),
                   ("noise band x0.8", {"noise_mult": 0.8}), ("noise band x1.2", {"noise_mult": 1.2})):
        rows.append((nm, pnlf(run2(q, prep, opt, price=price, **kw))))
    say(f"\n--- {label}: stress tests (each changes one thing) ---")
    say(f"{'scenario':34s} {'trades':>6s} {'win%':>5s} {'per day':>8s} {'t':>6s} {'longest losing streak':>22s}")
    for nm, t in rows:
        say(f"{nm:34s} {len(t):6d} {(t.pnl > 0).mean():5.0%} {perday(t, nd):+8.2f} {tstat(t, days):+6.2f} {streaks(t.pnl.to_numpy())[0]:22d}")
    f = day_features(q).reindex(days)
    for nm, m in (("volatile days only (vol rank > 2/3)", f.vol_rank > 2 / 3), ("calm days only (vol rank < 1/3)", f.vol_rank < 1 / 3)):
        sel = set(np.array(days)[m.fillna(False).to_numpy()])
        t = b[b.day.isin(sel)]
        say(f"{nm:34s} {len(t):6d} {(t.pnl > 0).mean() if len(t) else 0:5.0%} {t.pnl.sum() / max(len(sel), 1):+8.2f}")
    return b


def section_shares(ql, prep_l, say_title=True):
    say("\n" + "=" * 100 + "\nSECTION 3: shares one-a-day 2016-2026 forensic\n" + "=" * 100)
    days = sorted(set(ql.index.normalize()))
    r = run2(ql, prep_l, None, price=False)
    tr = shr_pnl(r).reset_index(drop=True)
    f = day_features(ql)
    tr = tr.join(f.reindex(tr.day).reset_index(drop=True))
    tr["year"] = tr.day.dt.year
    tr["ret_net%"] = tr["ret%"] - 2 * 0.01 / tr.entry * 100
    tr["with_trend"] = np.sign(tr.trend20) == tr.side
    tr["entry_hhmm"] = tr.t.dt.hour * 60 + tr.t.dt.minute
    tr["dist_prev_extreme_atr"] = np.where(tr.side > 0, (tr.prev_high - tr.entry), (tr.entry - tr.prev_low)) / tr.atr
    tr["price"] = tr.entry
    say("By year (return as % of price, after 1 cent a share a side; dollar figures on 100 shares):")
    say(f"{'year':6s} {'trades':>6s} {'win%':>5s} {'avg ret%':>9s} {'sum ret%':>9s} {'$ on 100 sh':>12s} {'QQQ price':>9s} {'vol20%':>7s} "
        f"{'range20%':>8s} {'trail exits':>11s}")
    for y, g in tr.groupby("year"):
        say(f"{y:<6d} {len(g):6d} {(g.pnl > 0).mean():5.0%} {g['ret_net%'].mean():+9.3f} {g['ret_net%'].sum():+9.2f} {g.pnl.sum():+12,.0f} "
            f"{g.price.median():9.0f} {g.vol20.median() * 100:7.2f} {g['range20%'].median():8.2f} {(g.why == 'trail').mean():11.0%}")
    grp = {"losing years 2016, 2017, 2020": tr.year.isin([2016, 2017, 2020]), "flat years 2018, 2019, 2021": tr.year.isin([2018, 2019, 2021]),
           "winning years 2022-2026": tr.year >= 2022, "winning trades (all years)": tr.pnl > 0, "losing trades (all years)": tr.pnl <= 0}
    cols = {"vol20": "volatility (20-day, %)", "trend20": "trend strength (signed)", "gap%": "opening gap %", "dayrange%": "day range %",
            "range20%": "avg range last 20 days %", "relvol30": "volume first 30 min vs normal", "entry_hhmm": "entry time (min after midnight)",
            "dist_prev_extreme_atr": "distance to prev-day high/low (ATR)", "mins": "minutes held", "best_atr": "best move (ATR)",
            "ret_net%": "return %"}
    say("\nMedians by group:")
    hdr = f"{'feature':38s}" + "".join(f"{k[:22]:>24s}" for k in grp)
    say(hdr)
    for c, lab in cols.items():
        vals = []
        for k, m in grp.items():
            v = tr.loc[m, c].median()
            vals.append(v * 100 if c == "vol20" else v)
        say(f"{lab:38s}" + "".join(f"{v:24.3f}" for v in vals))
    for k, m in grp.items():
        g = tr[m]
        say(f"{k}: with-trend share {g.with_trend.mean():.0%}, calls {(g.side > 0).mean():.0%}, exits {g.why.value_counts(normalize=True).round(2).to_dict()}")
    say("\nEx-ante test: avg range of the last 20 days (known before entry), threshold = median of the TRAINING period's trades:")
    for train, test in (((2016, 2021), (2022, 2026)), ((2022, 2026), (2016, 2021))):
        trn = tr[(tr.year >= train[0]) & (tr.year <= train[1])]
        tst = tr[(tr.year >= test[0]) & (tr.year <= test[1])]
        thr = trn["range20%"].median()
        kept = tst[tst["range20%"] >= thr]
        dropped = tst[tst["range20%"] < thr]
        say(f"  train {train}, test {test}: threshold {thr:.2f}%. Test trades kept {len(kept)}: avg ret {kept['ret_net%'].mean():+.3f}% "
            f"(win {(kept.pnl > 0).mean():.0%}); dropped {len(dropped)}: avg ret {dropped['ret_net%'].mean():+.3f}% "
            f"(win {(dropped.pnl > 0).mean():.0%}); all {len(tst)}: {tst['ret_net%'].mean():+.3f}%")
    return r, tr


def section_sizing(opt_tr, shr_tr, nd_opt, nd_shr):
    say("\n" + "=" * 100 + f"\nSECTION 5: a GBP 1,000 account (about ${ACCOUNT_USD:,.0f})\n" + "=" * 100)
    prem = opt_tr.o_in * 100
    say(f"OPTIONS (one-a-day): premium per contract median ${prem.median():,.0f}, 90% ${prem.quantile(0.9):,.0f}, max ${prem.max():,.0f} "
        f"= {prem.median() / ACCOUNT_USD:.0%} / {prem.quantile(0.9) / ACCOUNT_USD:.0%} / {prem.max() / ACCOUNT_USD:.0%} of the account. "
        f"Minimum size is ONE contract (100 x premium).")
    say(f"  worst single trade {opt_tr.pnl.min():+,.0f} ({opt_tr.pnl.min() / ACCOUNT_USD:.0%} of account); average loss {opt_tr.pnl[opt_tr.pnl <= 0].mean():+,.0f}; "
        f"maximum possible loss = the whole premium (median ${prem.median():,.0f})")
    rng = np.random.default_rng(7)
    per_year = int(round(len(opt_tr) / (nd_opt / 252)))
    ruin = dd50 = 0
    for _ in range(5000):
        bal = ACCOUNT_USD
        peak = bal
        hit = False
        for v in rng.choice(opt_tr.pnl.to_numpy(), per_year):
            if bal < prem.median():
                ruin += 1
                hit = True
                break
            bal += v
            peak = max(peak, bal)
            if bal <= peak * 0.5:
                hit = True
        dd50 += hit
    say(f"  5,000 simulated years at one contract on ${ACCOUNT_USD:,.0f}: can no longer afford a contract {ruin / 5000:.0%}; "
        f"a 50% drawdown (or worse) at some point {dd50 / 5000:.0%}")
    for risk in (0.02, 0.05):
        need = -opt_tr.pnl.quantile(0.05) / risk
        say(f"  capital so that a bad trade (5th percentile loss {opt_tr.pnl.quantile(0.05):+,.0f}) is {risk:.0%} of the account: about ${need:,.0f}")
    say(f"\nSHARES (one-a-day) at ${ACCOUNT_USD:,.0f} per trade (fractional shares, no leverage):")
    rp = shr_tr["ret_net%"] / 100 * ACCOUNT_USD
    wk = pd.Series(rp.to_numpy(), index=shr_tr.day).groupby(pd.Grouper(freq="W")).sum()
    dy = pd.Series(rp.to_numpy(), index=shr_tr.day).groupby(level=0).sum()
    eq = dy.cumsum()
    say(f"  per trade: average {rp.mean():+.2f}, worst {rp.min():+.2f} ({rp.min() / ACCOUNT_USD:.1%}), best {rp.max():+.2f}; worst day {dy.min():+.2f}; "
        f"worst week {wk.min():+.2f}; max drawdown {(eq - eq.cummax()).min():+.2f} ({(eq - eq.cummax()).min() / ACCOUNT_USD:.1%}); "
        f"average a year {rp.sum() / (nd_shr / 252):+.2f}")
    say(f"  costs: about 2 shares at QQQ ~$600; a 1-cent spread each way is about $0.04 a trade ({0.04 / ACCOUNT_USD:.3%} of the account)")
    n, _ = streaks(shr_tr.pnl.to_numpy())
    say(f"  longest losing streak in 2016-2026: {n} trades; average loss {rp[rp <= 0].mean():+.2f} -> such a streak costs about "
        f"{n * rp[rp <= 0].mean():+.2f} ({n * rp[rp <= 0].mean() / ACCOUNT_USD:.1%})")


def main() -> int:
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2024-06-03", "2026-02-27") for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + 0.08, "low": c - 0.08, "close": c, "volume": 1000.0}, index=idx)
        ql = q
    else:
        q = s5.load_qqq()
    opts = s5.Options(syn, q)
    section_fast(q, opts)
    prep = s6.prepare(q)
    opt = s6.Opt(syn, q)
    r, otr = section_options(q, prep, opt)
    days = sorted(set(q.index.normalize()))
    stress("ONE-A-DAY OPTIONS (1 contract, 1 cent a side)", q, prep, opt, lambda x: opt_pnl(x, 1), True, days)
    say("\nOptions at higher costs: see Section 2.")
    if not syn:
        s5.START, s5.END = "2016-01-01", "2026-11-01"
        ql = s5.load_qqq()
    prep_l = s6.prepare(ql)
    _, str_ = section_shares(ql, prep_l)
    days_l = sorted(set(ql.index.normalize()))
    stress("SHARES ONE-A-DAY 2016-2026 (100 shares, 1 cent a share a side)", ql, prep_l, None, lambda x: shr_pnl(x, 1), False, days_l)
    for c in (2, 5, 10):
        t = shr_pnl(run2(ql, prep_l, None, price=False), c)
        say(f"shares at {c} cents a share a side: per day {perday(t, len(days_l)):+.2f}, t {tstat(t, days_l):+.2f}")
    section_sizing(otr, str_, len(days), len(days_l))
    return 0


if __name__ == "__main__":
    sys.exit(main())
