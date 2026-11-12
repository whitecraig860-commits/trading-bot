"""
Study 4: trend following for a UK investor, in pounds, run exactly as research/UK_TREND_PROTOCOL.md says
=========================================================================================================
Reuses Study 3's tested engine (trend_following_study.py) for signals, sizing, execution, metrics and statistics;
only the price series, cash rate and costs change (§4, §5). Downloads public data, simulates, prints. No orders.

  python research/uk_trend_study.py               real data
  python research/uk_trend_study.py --synthetic   fake data, to check the code runs (results meaningless)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import trend_following_study as s3

TICKERS, K = s3.TICKERS, len(s3.TICKERS)
SEED = s3.SEED
RULES = ["A", "B6", "B12"]
HOLDOUT = s3.HOLDOUT
HALF = {**{t: 0.0005 for t in ["SPY", "QQQ", "IWM", "EFA", "IEF", "TLT", "LQD", "GLD"]},
        **{t: 0.0010 for t in ["EEM", "TIP", "VNQ", "SLV"]}, "DBC": 0.0015}
COST = {"gross": np.zeros(K), "net": np.array([HALF[t] + 0.0005 for t in TICKERS]),
        "stress": np.array([3 * (HALF[t] + 0.0005) for t in TICKERS])}
HEDGE_COST, HEDGE_COST_STRESS = 0.0015, 0.0030
N_TRIALS = 21
UCITS = {"VUSA.L": ("SPY", "U"), "IGUS.L": ("SPY", "H"), "EQQQ.L": ("QQQ", "U"), "SGLN.L": ("GLD", "U")}
say, hdr = s3.say, s3.hdr


def monthly_to_daily(s: pd.Series, cal: pd.DatetimeIndex) -> tuple[np.ndarray, int]:
    per = s.groupby(s.index.to_period("M")).last()
    v = pd.Series(cal.to_period("M").map(per).astype(float), index=cal)
    missing = int(v.isna().sum())
    return v.ffill().bfill().to_numpy(), missing


def build(m, fx, fx_prev, uk, us, mode: str, hedge_cost: float = HEDGE_COST):
    """§4: a copy of the market in GBP, unhedged ('U') or hedged ('H'), with UK cash."""
    g = s3.Mkt()
    for k in ("cal", "me", "me_dates", "elig", "s0", "spy0", "first"):
        setattr(g, k, getattr(m, k))
    if mode == "U":
        g.close = m.close / fx[:, None]
        g.open = m.open / fx_prev[:, None]
    else:
        r = m.close[1:] / m.close[:-1] - 1 + ((uk[:-1] - us[:-1]) / 252 - hedge_cost / 252)[:, None]
        r = np.vstack([np.full((1, K), np.nan), r])
        close = np.full_like(m.close, np.nan)
        for k in range(K):
            first = np.flatnonzero(~np.isnan(m.close[:, k]))[0]
            rr = np.nan_to_num(r[first + 1:, k])
            close[first, k] = m.close[first, k]
            close[first + 1:, k] = m.close[first, k] * np.cumprod(1 + rr)
        g.close = close
        g.open = np.vstack([np.full((1, K), np.nan), close[:-1] * (m.open[1:] / m.close[:-1])])
        g.open[np.isnan(g.open)] = m.open[np.isnan(g.open)]  # each ETF's first day
    daily = np.maximum(np.r_[uk[0], uk[:-1]] - s3.CASH_HAIRCUT, 0) / 252
    g.ci = np.cumprod(1 + daily)
    return g


def capital(name, run, cash_m, reps):
    x = run.mret.to_numpy()
    yrs = (1 + run.mret).groupby(run.mret.index.year).prod() - 1
    yrs = yrs[(yrs.index > run.mret.index[0].year)]
    idx = s3.sb_idx(len(x), 240, reps, np.random.default_rng(SEED))
    R = x[idx]
    wd = 630 * 1.025 ** (np.arange(240) // 12)
    cagr = s3.metrics(run, cash_m)["CAGR"]
    say(f"\n[{name}] historical: CAGR {cagr:.1%}; losing calendar years {(yrs < 0).sum()}/{len(yrs)}; "
        f"worst year {yrs.min():+.1%} ({yrs.idxmin()})")
    out = {}
    for cap in (50_000, 100_000, 150_000, 250_000):
        pot = np.full(reps, float(cap))
        dead = np.zeros(reps, bool)
        for t in range(240):
            pot = pot * (1 + R[:, t]) - wd[t]
            dead |= pot <= 0
            pot = np.where(dead, 0, pot)
        out[cap] = (float(dead.mean()), float(np.median(pot)), float(np.percentile(pot, 10)))
        say(f"   ISA, start £{cap:>7,}: runs out {dead.mean():.0%}, median after 20y £{np.median(pot):,.0f}, "
            f"bad case (10%) £{np.percentile(pot, 10):,.0f}, worst year ≈ £{yrs.min() * cap:,.0f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--placebos", type=int, default=1000)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--cache", default="/tmp/trend_study_data.pkl")
    a = ap.parse_args()
    end = pd.Timestamp.now(tz="America/New_York").to_period("M").start_time.strftime("%Y-%m-%d")
    say(f"Study 4, UK investor trend following in GBP. Protocol: research/UK_TREND_PROTOCOL.md. Data to {end} (excl)."
        + ("  *** SYNTHETIC DATA: results are meaningless ***" if a.synthetic else ""))
    data = s3.load_synthetic(end) if a.synthetic else s3.load_real(end, Path(a.cache))
    m = s3.prepare(data, end)
    cal = m.cal

    # ------------------------------------------------------------------ §3, §10: FX and rates
    hdr("GBP DATA (§3, §10)")
    if a.synthetic:
        rng = np.random.default_rng(3)
        fx = 1.6 * np.exp(np.cumsum(rng.normal(0, 0.005, len(cal))))
        uk_m = pd.Series(3.0, index=cal)
    else:
        dex = s3.fred("DEXUSUK")
        uk_m = s3.fred("IR3TIB01GBM156N")
        if dex is None or uk_m is None:
            raise SystemExit("STOP: FRED exchange rate or UK interest rate not available (§3)")
        fxs = dex.reindex(cal.union(dex.index)).sort_index()
        gaps = int(fxs.reindex(cal).isna().sum())
        fx = fxs.ffill().reindex(cal).to_numpy()
        say(f"USD per GBP: FRED DEXUSUK {dex.index[0].date()} to {dex.index[-1].date()}, {gaps} NYSE days carried forward")
        yg = data["gbp"].reindex(cal).ffill()
        both = pd.concat([pd.Series(fx, index=cal), yg], axis=1).dropna()
        both = both[both.index >= "2004-01-01"]
        mad = float((both.iloc[:, 0] / both.iloc[:, 1] - 1).abs().median() * 100)
        fx_label = "FX confirmed" if mad < 0.5 else "FX unconfirmed"
        say(f"FRED vs Yahoo GBPUSD from 2004: median |difference| {mad:.3f}% -> {fx_label}")
    uk, miss = monthly_to_daily(uk_m, cal)
    uk = uk / 100
    us = pd.Series(np.r_[np.diff(np.log(m.ci)), 0], index=cal).to_numpy() * 252 + s3.CASH_HAIRCUT  # back out ^IRX
    us = np.maximum(us, 0)
    say(f"UK 3-month rate: {miss} NYSE days with no monthly value yet (carried from the last month); "
        f"median {np.median(uk) * 100:.2f}%, US median {np.median(us) * 100:.2f}%")
    if np.isnan(fx[m.me[m.s0] - 300:]).any():
        raise SystemExit("STOP: exchange rate missing inside the evaluation window")
    fx_prev = np.r_[fx[0], fx[:-1]]

    mk = {"U": build(m, fx, fx_prev, uk, us, "U"), "H": build(m, fx, fx_prev, uk, us, "H"),
          "H-stress": build(m, fx, fx_prev, uk, us, "H", HEDGE_COST_STRESS)}
    ex = {v: s3.signals(g) for v, g in mk.items()}
    cash_run = s3.simulate(mk["U"], np.zeros((len(m.me), K)), COST["net"])
    cash_m = cash_run.mret

    W, runs = {}, {c: {} for c in COST}
    for v in ("U", "H"):
        for r in RULES:
            W[f"{r}-{v}"] = s3.weights(mk[v], ex[v][r], r)
        elig = m.elig.astype(float)
        spy = np.zeros((len(m.me), K)); spy[:, TICKERS.index("SPY")] = 1
        ief = np.zeros((len(m.me), K)); ief[:, TICKERS.index("IEF")] = 1
        W[f"BH-DIV-{v}"] = elig / elig.sum(1, keepdims=True).clip(1)
        W[f"60/40-{v}"] = 0.6 * spy + 0.4 * ief
        W[f"SPY-{v}"] = spy
    W["CASH-UK"] = np.zeros((len(m.me), K))
    for name, w in W.items():
        v = "U" if name.endswith("-U") or name == "CASH-UK" else "H"
        for c in COST:
            g = mk["H-stress"] if (c == "stress" and v == "H") else mk[v]
            ww = w
            if c == "stress" and v == "H" and name.split("-")[0] in RULES:
                ww = s3.weights(g, ex["H-stress"][name.split("-")[0]], name.split("-")[0])
            runs[c][name] = s3.simulate(g, ww, COST[c])
    net = runs["net"]
    CONF = [f"{r}-{v}" for v in ("U", "H") for r in RULES]
    BENCH = [k for k in W if k not in CONF]

    # ------------------------------------------------------------------ results
    start, last = m.me_dates[m.s0], m.me_dates[-1]
    hdr(f"RESULTS IN GBP, {start.date()} to {last.date()}. Configurations: {' '.join(CONF)}")
    for c, label in (("net", "NET (UK costs, §5)"), ("gross", "GROSS"), ("stress", "STRESS (3x costs, 0.30% hedge)")):
        say(f"\n--- {label}")
        s3.show({k: s3.metrics(runs[c][k], cash_m) for k in CONF + BENCH})
    say("\n--- Pre-holdout / holdout, net")
    for lab, lo, hi in (("PRE", None, HOLDOUT - pd.Timedelta(days=1)), ("HOLDOUT", HOLDOUT, None)):
        say(f"[{lab}]")
        s3.show({k: s3.metrics(net[k], cash_m, lo, hi) for k in CONF + BENCH if k != "CASH-UK"},
                cols=("CAGR", "Vol", "Sharpe", "MaxDD", "Calmar", "Worst12m"))

    hdr("STATISTICAL TESTS (§7, §8)")
    xs = {k: (net[k].mret - cash_m.reindex(net[k].mret.index)).to_numpy() for k in CONF + BENCH}
    nw = {k: s3.newey_west(xs[k]) for k in CONF}
    hp = s3.holm({k: nw[k][2] for k in CONF})
    trial = np.array([xs[k].mean() / xs[k].std(ddof=1) for k in CONF])
    v_sr = np.var(trial, ddof=1)
    pb = s3.pbo(np.column_stack([xs[k] for k in CONF]))
    say(f"PBO across the 6 configurations (information only, §8.1): {pb:.2f}")
    stats = {}
    for k in CONF:
        bench = "BH-DIV-" + k[-1]
        b = s3.boot_sharpe(xs[k], xs[bench], a.boot)
        # DSR with N = 21 trials and the variance of the 6 configurations (§8.2)
        x = xs[k]
        sr = x.mean() / x.std(ddof=1)
        gmm = 0.5772156649
        sr0 = math.sqrt(v_sr) * ((1 - gmm) * s3.ND.inv_cdf(1 - 1 / N_TRIALS) + gmm * s3.ND.inv_cdf(1 - 1 / (N_TRIALS * math.e)))
        sk, ku = float(pd.Series(x).skew()), float(pd.Series(x).kurt()) + 3
        dsr = s3.ND.cdf((sr - sr0) * math.sqrt(len(x) - 1) / math.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12)))
        stats[k] = {"t": nw[k][1], "p": nw[k][2], "p_holm": hp[k], "sharpe_ci": b["ci"], "diff_ci": b["diff_ci"],
                    "diff_p": b["diff_p"], "dsr": dsr}
        say(f"{k:6s} mean excess {nw[k][0] * 100:+.2f}%/mo  NW t {nw[k][1]:5.2f}  p {nw[k][2]:.4f}  Holm p {hp[k]:.4f}  "
            f"Sharpe CI [{b['ci'][0]:.2f}, {b['ci'][1]:.2f}]  vs {bench} diff CI [{b['diff_ci'][0]:+.2f}, "
            f"{b['diff_ci'][1]:+.2f}] p {b['diff_p']:.3f}  DSR(N=21) {dsr:.3f}")

    say(f"\nRandom-timing null: {a.placebos} placebos per configuration")
    rng = np.random.default_rng(SEED)
    plc = {}
    for k in CONF:
        rule, v = k.split("-")
        g = mk[v]
        e = np.nan_to_num(ex[v][rule])
        shs = []
        t0 = time.time()
        for _ in range(a.placebos):
            e2 = e.copy()
            for j in range(K):
                rows = np.flatnonzero(m.elig[:, j])
                rows = rows[rows >= m.s0]
                if len(rows) < 2:
                    continue
                chunks = [rows[i:i + 3] for i in range(0, len(rows), 3)]
                order = rng.permutation(len(chunks))
                e2[rows, j] = np.concatenate([e[chunks[o], j] for o in order])
            rr = s3.simulate(g, s3.weights(g, np.where(m.elig, e2, np.nan), rule), COST["net"], detail=False)
            shs.append(s3.sharpe((rr.mret - cash_m.reindex(rr.mret.index)).to_numpy()))
        real = s3.sharpe(xs[k])
        plc[k] = float(np.mean(np.array(shs) < real))
        say(f"{k:6s} real Sharpe {real:.2f} vs placebo median {np.median(shs):.2f}, 95th {np.percentile(shs, 95):.2f} "
            f"-> percentile {plc[k]:.1%} ({time.time() - t0:.0f}s)")

    hdr("PASS / FAIL (§9)")
    verdict = {}
    for k in CONF:
        bench = "BH-DIV-" + k[-1]
        f, bd = s3.metrics(net[k], cash_m), s3.metrics(net[bench], cash_m)
        h, bh = s3.metrics(net[k], cash_m, HOLDOUT), s3.metrics(net[bench], cash_m, HOLDOUT)
        st = s3.metrics(runs["stress"][k], cash_m)
        subs = [s3.metrics(net[k], cash_m, pd.Timestamp(lo) if lo else None, pd.Timestamp(hi) if hi else None)["CAGR"]
                for lo, hi in ((None, "2009-12-31"), ("2010-01-01", "2017-12-31"), ("2018-01-01", None))]
        prof = float(net[k].nav.iloc[-1] - 1)
        share = float(net[k].contrib.max() / prof) if prof > 0 else float("inf")
        c = {"1 significance (Holm p<0.05)": stats[k]["p_holm"] < 0.05,
             f"2 Sharpe>={bench} and DD<=0.75x": f["Sharpe"] >= bd["Sharpe"] and abs(f["MaxDD"]) <= 0.75 * abs(bd["MaxDD"]),
             "3 holdout Sharpe>0 and DD<=benchmark": h["Sharpe"] > 0 and abs(h["MaxDD"]) <= abs(bh["MaxDD"]),
             "4 beats 95% of random timing": plc[k] >= 0.95,
             "5 deflated Sharpe (N=21) >= 0.95": stats[k]["dsr"] >= 0.95,
             "6 positive in >=2 of 3 sub-periods": sum(x > 0 for x in subs) >= 2,
             "7 Sharpe>0 at stress costs": st["Sharpe"] > 0,
             "8 no ETF >50% of profit": share <= 0.50}
        if all(c.values()):
            vd = "VALIDATED"
        elif all(c[x] for x in c if x[0] in "23678"):
            vd = "PROMISING (not built)"
        else:
            vd = "FAILED"
        verdict[k] = {"verdict": vd, "n_pass": sum(c.values()), "criteria": {n: bool(b) for n, b in c.items()},
                      "full": f, "holdout": h, "bench_full": bd, "bench_holdout": bh, "subs": subs, "share": share,
                      "stress_sharpe": st["Sharpe"]}
        say(f"\n{k}: {vd} ({sum(c.values())}/8)")
        for n, ok in c.items():
            say(f"   {'PASS' if ok else 'fail'}  {n}")
        say(f"   detail: Sharpe {f['Sharpe']:.2f} vs {bd['Sharpe']:.2f}; max DD {f['MaxDD']:.1%} vs line "
            f"{-0.75 * abs(bd['MaxDD']):.1%}; holdout Sharpe {h['Sharpe']:.2f}, DD {h['MaxDD']:.1%} vs {bh['MaxDD']:.1%}; "
            f"sub-periods {', '.join(f'{x:+.1%}' for x in subs)}; stress Sharpe {st['Sharpe']:.2f}; top ETF {share:.0%}")

    # ------------------------------------------------------------------ descriptive (§11)
    hdr("HEDGED vs UNHEDGED (§11)")
    for r in RULES + ["BH-DIV", "60/40", "SPY"]:
        u, h = s3.metrics(net[f"{r}-U"], cash_m), s3.metrics(net[f"{r}-H"], cash_m)
        say(f"   {r:7s} unhedged: CAGR {u['CAGR']:.1%} Sharpe {u['Sharpe']:.2f} maxDD {u['MaxDD']:.1%} | hedged: CAGR "
            f"{h['CAGR']:.1%} Sharpe {h['Sharpe']:.2f} maxDD {h['MaxDD']:.1%}")

    hdr("BY CALENDAR YEAR, net, GBP")
    cols = CONF + ["BH-DIV-U", "BH-DIV-H", "SPY-U", "SPY-H", "CASH-UK"]
    say(f"{'year':6s}" + "".join(f"{c:>9s}" for c in cols))
    yr = {c: (1 + net[c].mret).groupby(net[c].mret.index.year).prod() - 1 for c in cols}
    for y in sorted(yr[CONF[0]].index):
        say(f"{y:<6d}" + "".join(f"{yr[c].get(y, float('nan')):>9.1%}" for c in cols))

    hdr("CRISIS WINDOWS, GBP: return / worst drawdown inside")
    cc = CONF + ["BH-DIV-U", "BH-DIV-H", "SPY-U", "SPY-H"]
    say(f"{'':20s}" + "".join(f"{c:>15s}" for c in cc))
    for name, (lo, hi) in s3.CRISES.items():
        lo_t, hi_t = pd.Period(lo, "M").start_time, pd.Period(hi, "M").end_time
        cells = []
        for c in cc:
            mr = net[c].mret[(net[c].mret.index >= lo_t) & (net[c].mret.index <= hi_t)]
            nv = net[c].nav[(net[c].nav.index >= lo_t - pd.Timedelta(days=4)) & (net[c].nav.index <= hi_t)]
            cells.append(f"{np.prod(1 + mr) - 1:>+7.1%}/{s3.maxdd(nv):>+6.1%}" if len(mr) else f"{'n/a':>15s}")
        say(f"{name:20s}" + " ".join(cells))

    hdr("CORRELATION / BETA TO S&P 500 (same currency treatment): all | down months | worst 10%")
    for k in CONF + ["BH-DIV-U", "BH-DIV-H"]:
        x = net[k].mret
        s = net["SPY-" + k[-1]].mret.reindex(x.index)
        out = []
        for msk in (s.notna(), s < 0, s <= s.quantile(0.10)):
            xx, ss = x[msk], s[msk]
            out.append(f"{xx.corr(ss):+.2f} / {np.cov(xx, ss)[0, 1] / ss.var():+.2f}")
        say(f"   {k:9s} " + " | ".join(out))

    hdr("REAL LONDON-LISTED FUNDS vs the series built in §4 (§10.3, descriptive)")
    if not a.synthetic:
        for tk, (src, v) in UCITS.items():
            try:
                d = s3.yf_one(tk, "2005-01-01", end)["Close"]
            except Exception as exc:
                say(f"   {tk}: not available ({str(exc)[:80]})")
                continue
            rm = d.groupby(d.index.to_period("M")).last().pct_change().dropna()
            jumps = rm[rm.abs() > 0.5]
            g = mk[v]
            sm = pd.Series(g.close[:, TICKERS.index(src)], index=cal)
            sm = sm.groupby(sm.index.to_period("M")).last().pct_change()
            both = pd.concat([rm, sm], axis=1, join="inner").dropna()
            both = both[~both.index.isin(jumps.index)]
            if len(both) < 12:
                say(f"   {tk}: too little overlap")
                continue
            diff = both.iloc[:, 0] - both.iloc[:, 1]
            say(f"   {tk} vs {src}-{v}: {len(both)} months from {both.index[0]}, correlation {both.corr().iloc[0, 1]:.3f}, "
                f"median |monthly difference| {diff.abs().median() * 100:.2f} pp, average yearly gap "
                f"{diff.mean() * 12 * 100:+.2f}%" + (f"; {len(jumps)} broken month(s) skipped: "
                                                    f"{[str(p) for p in jumps.index]}" if len(jumps) else ""))

    hdr("CAPITAL AND £30 A DAY (§11), ISA, £630/month rising 2.5%/yr, 20 years")
    best = max(CONF, key=lambda k: (verdict[k]["n_pass"], verdict[k]["full"]["Sharpe"]))
    say(f"Best-scoring configuration: {best} ({verdict[best]['verdict']})")
    cap = {k: capital(k, net[k], cash_m, a.boot) for k in (best, "BH-DIV-U", "BH-DIV-H", "60/40-U")}

    hdr("SUMMARY")
    for k in CONF:
        f = verdict[k]["full"]
        say(f"{k:6s} {verdict[k]['verdict']:24s} {verdict[k]['n_pass']}/8  Sharpe {f['Sharpe']:.2f}  CAGR {f['CAGR']:.1%}  "
            f"max DD {f['MaxDD']:.1%}  (benchmark Sharpe {verdict[k]['bench_full']['Sharpe']:.2f}, "
            f"max DD {verdict[k]['bench_full']['MaxDD']:.1%})")
    say(f"PBO (information only) {pb:.2f}; data: {m.dq_label if hasattr(m, 'dq_label') else 'see above'}")
    Path("research_uk_summary.json").write_text(json.dumps({"verdict": verdict, "stats": stats, "placebo": plc,
                                                            "pbo": pb, "capital": cap}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
