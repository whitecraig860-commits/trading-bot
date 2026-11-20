"""
Audit baseline (audit/README.md): every bot's strategy on history, with metrics, market regimes, named stress events,
out-of-sample results, execution stress, parameter wobble and 5,000-run Monte Carlo. Measures only; changes nothing.
Read-only market data; no orders.   python research/audit_baseline.py [--synthetic]
Writes audit/baseline_<bot>.md and audit/baseline_summary.md.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

import his_filter_study as s9
import new_entries_study as s13
import one_a_day_study as s6
import qqq_triggers_study as s5
import stress_study as s11

OUT = os.path.join(os.path.dirname(__file__), "..", "audit")
HOLDOUT = pd.Timestamp("2026-01-01")
ACCOUNTS = (2000, 5000, 25000)
EVENTS = {"Aug 2024 volatility spike (5 Aug)": ("2024-08-01", "2024-08-09"),
          "Apr 2025 tariff crash and rebound": ("2025-04-02", "2025-04-11"),
          "Dec 2024 Fed sell-off (18 Dec)": ("2024-12-17", "2024-12-20")}


def sim(q, sig, opts, cents=1, keep=None, target=0.025, stop=0.06, hold=10, trail=0.0, maxrun=2, pb=0, lb=0,
        delay=0, itm=False, reject=0.0, outage=False, seed=0):
    """One contract, next-day expiry, real option trade bars. Returns a trade list with costs separated."""
    rng = np.random.default_rng(seed)
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    lohi = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    out_hour = {d: int(rng.integers(10, 15)) for d in days} if outage else {}
    trades, free_at, run, run_day, dpnl = [], pd.Timestamp("1900-01-01"), 0, None, 0.0
    for i, r in enumerate(sig.itertuples()):
        d = r.t.normalize()
        if d != run_day:
            run, run_day, dpnl = 0, d, 0.0
        if keep is not None and not keep[i]:
            continue
        if r.t < free_at or (maxrun and run >= maxrun) or d not in nxt or (pb and dpnl >= pb) or (lb and dpnl <= -lb):
            continue
        if outage and r.t.hour == out_hour[d]:
            continue
        if reject and rng.random() < reject:
            continue
        k = (int(np.floor(r.px)) if r.side == "C" else int(np.ceil(r.px))) if itm else int(round(r.px))
        b = opts.day(d, nxt[d], lohi.lo[d], lohi.hi[d]).get((r.side, k))
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
        best = None
        blind = False
        for j, bar in enumerate(b.itertuples()):
            if outage and bar.Index.hour == out_hour[d]:
                blind = True  # connection down: the bot cannot act; it resumes at the first bar after the hour
                continue
            if blind:
                blind = False
                lvl = best * (1 - trail) if best is not None else stp
                if bar.open <= lvl or bar.open >= tgt and not trail:
                    px, why = bar.open, "after outage"
            if px is None and best is not None:
                lvl = best * (1 - trail)
                if bar.open <= lvl:
                    px, why = bar.open, "trail"
                elif bar.low <= lvl:
                    px, why = lvl, "trail"
                elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                    px, why = bar.close, "time"
                else:
                    best = max(best, bar.high)
            elif px is None:
                if j > 0 and bar.open <= stp:
                    px, why = bar.open, "stop (gap)"
                elif bar.low <= stp:
                    px, why = stp, "stop"
                elif bar.high >= tgt:
                    if trail:
                        best = bar.high
                        if bar.close <= best * (1 - trail):
                            px, why = bar.close, "trail"
                    else:
                        px, why = tgt, "target"
                elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                    px, why = bar.close, "time"
            if px is not None:
                xt = bar.Index
                break
        if px is None:
            px, xt, why = float(b.close.iloc[-1]), b.index[-1], "end of day"
        gross = (px - entry) * 100
        cost = 2 * cents + 2 * s5.FEE
        pnl = gross - cost
        trades.append({"day": d, "t": t0, "side": r.side, "entry": entry, "exit": float(px), "why": why,
                       "gross": gross, "cost": cost, "pnl": pnl, "mins": (xt - t0).total_seconds() / 60})
        free_at = xt + pd.Timedelta(minutes=1)
        run = run + 1 if pnl < 0 else 0
        dpnl += pnl
    return pd.DataFrame(trades, columns=["day", "t", "side", "entry", "exit", "why", "gross", "cost", "pnl", "mins"]), days


def daily(tr, days):
    return tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0) if len(tr) else pd.Series(0.0, index=days)


def metrics(tr, days) -> dict:
    d = daily(tr, days)
    w, l = tr.pnl[tr.pnl > 0], tr.pnl[tr.pnl <= 0]
    eq = d.cumsum()
    dd = (eq - eq.cummax()).min()
    streak = best = 0
    for v in tr.pnl:
        streak = streak + 1 if v <= 0 else 0
        best = max(best, streak)
    top5 = tr.pnl.nlargest(5).sum() if len(tr) else 0
    sd = d.std()
    down = d[d < 0].std()
    return {"trades": len(tr), "wins": len(w), "losses": len(l), "win%": len(w) / max(len(tr), 1),
            "net": tr.pnl.sum(), "per day": d.mean(), "t": s5.nw_t(d.to_numpy()) if len(d) > 10 else float("nan"),
            "PF": w.sum() / -l.sum() if l.sum() else float("inf"), "avg win": w.mean() if len(w) else 0.0,
            "avg loss": l.mean() if len(l) else 0.0,
            "R:R": (w.mean() / -l.mean()) if len(w) and len(l) and l.mean() else float("nan"),
            "expectancy": tr.pnl.mean() if len(tr) else 0.0, "maxDD$": dd,
            "sharpe": d.mean() / sd * np.sqrt(252) if sd else float("nan"),
            "sortino": d.mean() / down * np.sqrt(252) if down and down == down else float("nan"),
            "max losses in a row": best, "costs": tr.cost.sum() if "cost" in tr else float("nan"),
            "top5 share": top5 / tr.pnl.sum() if tr.pnl.sum() > 0 else float("nan"),
            "net without top 5": tr.pnl.sum() - top5}


def regimes(q, days):
    dc = q.close.groupby(q.index.normalize()).last()
    do = q.open.groupby(q.index.normalize()).first()
    ma50 = dc.rolling(50).mean()
    ret = dc.pct_change()
    vol20 = ret.rolling(20).std()
    trend20 = (dc / dc.shift(20) - 1).abs() / (vol20 * np.sqrt(20))
    rng = (q.high.groupby(q.index.normalize()).max() - q.low.groupby(q.index.normalize()).min()) / do
    g = pd.DataFrame({"bull (above 50-day avg)": dc > ma50, "bear (below 50-day avg)": dc <= ma50,
                      "high volatility (top third)": vol20 > vol20.quantile(2 / 3),
                      "low volatility (bottom third)": vol20 < vol20.quantile(1 / 3),
                      "trending month": trend20 > 1.0, "choppy month": trend20 < 0.5,
                      "big-range day (top 10%)": rng > rng.quantile(0.9),
                      "gap open over 1%": (do / dc.shift(1) - 1).abs() > 0.01}).reindex(days).fillna(False)
    return g


def monte_carlo(tr, days, n=5000, seed=42) -> dict:
    """Resample a year of trades (random order, with replacement) and add random extra slippage per trade."""
    rng = np.random.default_rng(seed)
    pnl = tr.pnl.to_numpy()
    if len(pnl) < 10:
        return {}
    per_year = max(1, int(round(len(pnl) / (len(days) / 252))))
    finals, dds = np.empty(n), np.empty(n)
    for i in range(n):
        x = rng.choice(pnl, per_year) - np.abs(rng.normal(0, 1.0, per_year)) * 2  # 0-~4 cents extra a round trip
        eq = np.cumsum(x)
        finals[i] = eq[-1]
        dds[i] = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    res = {"trades a year": per_year, "pcts": {p: np.percentile(finals, p) for p in (1, 5, 25, 50, 75, 95, 99)},
           "dd pcts": {p: np.percentile(dds, p) for p in (50, 5, 1)}, "p(loss)": (finals < 0).mean()}
    for acct in ACCOUNTS:
        res[acct] = {f"DD>={k}%": (dds <= -acct * k / 100).mean() for k in (10, 20, 30, 50)}
        res[acct]["ruin (lose half)"] = (finals <= -acct / 2).mean()
    return res


def report(name, desc, tr, days, q, stress: dict, wobble: dict, paper: str = "see audit/paper_results.md") -> str:
    m = metrics(tr, days)
    g = regimes(q, days)
    d = daily(tr, days)
    L = [f"# {name}: baseline audit", "", desc, "",
         "All figures: one contract (options) or as stated, after costs (1 cent a side + fees unless stated). History only; "
         "paper-trading results are in `audit/paper_results.md`.", "", "## Metrics (full period)", "", "| Metric | Value |",
         "|---|---|"]
    fmt = {"win%": "{:.0%}", "top5 share": "{:.0%}", "t": "{:+.2f}", "PF": "{:.2f}", "R:R": "{:.2f}", "sharpe": "{:+.2f}",
           "sortino": "{:+.2f}"}
    for k, v in m.items():
        L.append(f"| {k} | " + (fmt.get(k, "{:,.2f}").format(v) if isinstance(v, (float, np.floating)) else f"{v:,}") + " |")
    oos = tr[tr.day >= HOLDOUT]
    mo = metrics(oos, [x for x in days if x >= HOLDOUT])
    L += ["", f"**Out of sample (2026, not used to design the rules):** {mo['trades']} trades, {mo['win%']:.0%} won, "
          f"{mo['per day']:+.2f} a day, PF {mo['PF']:.2f}, max drawdown {mo['maxDD$']:,.0f}.", "",
          "## Market conditions (per day)", "", "| Condition | Days | Per day |", "|---|---|---|"]
    for c in g.columns:
        sel = g[c].to_numpy()
        L.append(f"| {c} | {sel.sum()} | {d[sel].mean():+.2f} |")
    L += ["", "| Year | Per day |", "|---|---|"] + [f"| {y} | {d[d.index.year == y].mean():+.2f} |" for y in sorted(set(d.index.year))]
    L += ["", "## Named stress events", ""]
    for ev, (a, b) in EVENTS.items():
        sel = (d.index >= a) & (d.index <= b)
        L.append(f"- {ev}: {sel.sum()} days, total {d[sel].sum():+,.0f}, worst day {d[sel].min() if sel.any() else 0:+,.0f}")
    L += ["", "## Execution stress (per day; each changes one thing)", "", "| Scenario | Per day | Trades |", "|---|---|---|"]
    for k, (v, n) in stress.items():
        L.append(f"| {k} | {v:+.2f} | {n:,} |")
    if wobble:
        L += ["", "## Settings wobbled (per day)", "", "| Variant | Per day |", "|---|---|"] + \
             [f"| {k} | {v:+.2f} |" for k, v in wobble.items()]
    mc = monte_carlo(tr, days)
    if mc:
        L += ["", f"## Monte Carlo: 5,000 simulated years ({mc['trades a year']} trades each, random order, extra slippage)", "",
              "| Percentile | Year's result | Max drawdown |", "|---|---|---|"]
        for p in (1, 5, 25, 50, 75, 95, 99):
            L.append(f"| {p}% | {mc['pcts'][p]:+,.0f} | " + (f"{mc['dd pcts'][p]:,.0f}" if p in mc["dd pcts"] else "") + " |")
        L += ["", f"Chance of a losing year: {mc['p(loss)']:.0%}", "", "| Account | DD ≥10% | ≥20% | ≥30% | ≥50% | Ruin (lose half in a year) |",
              "|---|---|---|---|---|---|"]
        for a in ACCOUNTS:
            r = mc[a]
            L.append(f"| ${a:,} | {r['DD>=10%']:.0%} | {r['DD>=20%']:.0%} | {r['DD>=30%']:.0%} | {r['DD>=50%']:.0%} | {r['ruin (lose half)']:.0%} |")
    if len(tr) and "why" in tr:
        L += ["", "## Where the money goes (by exit reason)", "", "| Exit | Trades | Average | Total |", "|---|---|---|---|"]
        for k, gg in tr.groupby("why"):
            L.append(f"| {k} | {len(gg):,} | {gg.pnl.mean():+.2f} | {gg.pnl.sum():+,.0f} |")
    return "\n".join(L) + "\n"


class _NoOpt:
    def bars(self, *a, **k):
        return pd.DataFrame(columns=["open", "high", "low", "close"])


def shares_long(say) -> str:
    """The shares bot back to 2016 (no option prices needed): covers the 2018 sell-off, the 2020 crash, the 2022 bear."""
    s5.START, s5.END = "2016-01-01", "2026-11-01"
    q = s5.load_qqq()
    r = s6.run(q, s6.prepare(q), _NoOpt(), dte=1, itm=0.0)
    t = r[r.traded.astype(bool)].copy()
    t["gross"] = (t.exit - t.entry) * np.where(t.side == "C", 1, -1) * 100
    t["cost"] = 2.0
    t["pnl"] = t.gross - t.cost
    tr = t[["day", "gross", "cost", "pnl", "why"]].copy()
    days = sorted(set(q.index.normalize()))
    global EVENTS
    EVENTS = {**EVENTS, "Dec 2018 sell-off": ("2018-12-03", "2018-12-24"), "Feb-Mar 2020 COVID crash": ("2020-02-20", "2020-03-23"),
              "2022 bear market (full year)": ("2022-01-03", "2022-12-30"), "Mar 2020 rebound": ("2020-03-24", "2020-04-30")}
    stress = {f"costs {c} cents a share a side": (daily(tr.assign(pnl=tr.gross - 2 * c), days).mean(), len(tr)) for c in (2, 5, 10)}
    txt = report("shares_oneaday_2016", "Shares one-a-day, 100 QQQ shares, 2016 to 2026 (longest data available)", tr, days, q, stress, {})
    open(os.path.join(OUT, "baseline_shares_oneaday_2016.md"), "w").write(txt)
    m = metrics(tr, days)
    mo = metrics(tr[tr.day >= HOLDOUT], [x for x in days if x >= HOLDOUT])
    mc = monte_carlo(tr, days)
    line = (f"| shares_oneaday 2016-2026 | {m['trades']:,} | {m['win%']:.0%} | {m['per day']:+.2f} | {m['t']:+.2f} | {m['PF']:.2f} | "
            f"{m['maxDD$']:,.0f} | {mo['per day']:+.2f} | {stress['costs 5 cents a share a side'][0]:+.2f} | {mc.get('p(loss)', float('nan')):.0%} |")
    say(line)
    return line


def main() -> int:
    syn = "--synthetic" in sys.argv
    say = s5.say
    os.makedirs(OUT, exist_ok=True)
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2025-06-02", "2026-02-27")
                                for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + 0.08, "low": c - 0.08, "close": c, "volume": 1000.0},
                         index=idx)
    else:
        q = s5.load_qqq()
    opts = s5.Options(syn, q)
    late, early = s9.signals2(q, "09:45"), s9.signals2(q, "09:31")
    k_pick = s11.keep_mask(q, late)
    k_weak = ~late.F3.to_numpy()
    k_trend = ~late.F4.to_numpy()
    k_combo = ~early.F3.to_numpy()
    five, open30 = s13.signals_five(q), s13.signals_open30(q)
    X = {"target": 0.025, "stop": 0.06, "hold": 10}
    bots = {
        "options_stop2": ("Main options bot: 1-minute VWAP/EMA50 crosses + 15-min range break, +2.5%/-6%/10 min, stop after 2 losses", late, {}),
        "original": ("Original: same as main, no stop after losses", late, {"maxrun": 0}),
        "trail": ("Trailing exit: main + keep winners from +2.5%, sell 1.5% below best, 15-min limit", late, {"trail": 0.015, "hold": 15}),
        "trailtrend": ("Trailing exit + trend: as trail, calls only above the open, puts only below", late, {"trail": 0.015, "hold": 15, "keep": k_trend}),
        "his": ("His style: trail + 12% stop", late, {"trail": 0.015, "hold": 15, "stop": 0.12}),
        "skipweak": ("Skip weak crosses: main, skipping closes less than $0.10 past the line", late, {"keep": k_weak}),
        "combo": ("Combo: skip weak + signals from 09:31 + strike in the money", early, {"keep": k_combo, "itm": True}),
        "picks": ("Picks like him: EMA9/20 agree + strong candle + before 12:00 + not weak", late, {"keep": k_pick}),
        "clone": ("His clone: picks like him + +3.5%/-10%/6 min", late, {"keep": k_pick, "target": 0.035, "stop": 0.10, "hold": 6}),
        "brakes": ("Brakes: main + stop for the day at +$50 or -$100", late, {"pb": 50, "lb": 100}),
        "five": ("5-minute crosses: +5%/-10%/30 min, stop after 2 losses", five, {"target": 0.05, "stop": 0.10, "hold": 30}),
        "open30": ("Opening move at 10:00: +10%/-10%/60 min, one a day", open30, {"target": 0.10, "stop": 0.10, "hold": 60}),
    }
    summary = ["| Bot | Trades | Win% | Per day | t | PF | Max DD | 2026 per day | 5c per day | MC losing year |", "|---|---|---|---|---|---|---|---|---|---|"]
    for name, (desc, sig, kw) in bots.items():
        base_kw = {**X, **kw}
        tr, days = sim(q, sig, opts, 1, **base_kw)
        stress = {}
        for c in (2, 3, 5, 10):
            t2, _ = sim(q, sig, opts, c, **base_kw)
            stress[f"costs {c} cents a side"] = (daily(t2, days).mean(), len(t2))
        for dl in (1, 2):
            t2, _ = sim(q, sig, opts, 1, delay=dl, **base_kw)
            stress[f"orders filled {dl} min late"] = (daily(t2, days).mean(), len(t2))
        t2, _ = sim(q, sig, opts, 1, reject=0.10, **base_kw)
        stress["10% of orders rejected"] = (daily(t2, days).mean(), len(t2))
        t2, _ = sim(q, sig, opts, 1, outage=True, **base_kw)
        stress["one-hour connection outage every day"] = (daily(t2, days).mean(), len(t2))
        wob = {}
        for lab, ch in (("target x0.8", {"target": base_kw["target"] * 0.8}), ("target x1.2", {"target": base_kw["target"] * 1.2}),
                        ("stop x0.8", {"stop": base_kw["stop"] * 0.8}), ("stop x1.2", {"stop": base_kw["stop"] * 1.2})):
            t2, _ = sim(q, sig, opts, 1, **{**base_kw, **ch})
            wob[lab] = daily(t2, days).mean()
        txt = report(name, desc, tr, days, q, stress, wob)
        open(os.path.join(OUT, f"baseline_{name}.md"), "w").write(txt)
        m = metrics(tr, days)
        mo = metrics(tr[tr.day >= HOLDOUT], [x for x in days if x >= HOLDOUT])
        mc = monte_carlo(tr, days)
        summary.append(f"| {name} | {m['trades']:,} | {m['win%']:.0%} | {m['per day']:+.2f} | {m['t']:+.2f} | {m['PF']:.2f} | "
                       f"{m['maxDD$']:,.0f} | {mo['per day']:+.2f} | {stress['costs 5 cents a side'][0]:+.2f} | "
                       f"{mc.get('p(loss)', float('nan')):.0%} |")
        say(summary[-1])

    # ONEADAY options and the shares bot (Study 6 engine)
    prep = s6.prepare(q)
    opt = s6.Opt(syn, q)
    r = s6.run(q, prep, opt, dte=1, itm=0.0)
    days = sorted(set(q.index.normalize()))
    for name, desc, col in (("oneaday", "One-a-day breakout on next-day at-the-money options (follows the shares bot)", "opt"),
                            ("shares_oneaday", "Shares one-a-day: 100 QQQ shares on the same breakout (the live bot trades about $1,000)", "shares")):
        t = r[r.traded.astype(bool)].copy()
        if col == "opt":
            t = t.dropna(subset=["o_in"])
            t["gross"] = (t.o_out - t.o_in) * 100
            t["cost"] = 2 * 1 + 2 * s5.FEE
        else:
            t["gross"] = (t.exit - t.entry) * np.where(t.side == "C", 1, -1) * 100
            t["cost"] = 2.0
        t["pnl"] = t.gross - t.cost
        tr = t[["day", "gross", "cost", "pnl", "why"]].copy()
        stress = {}
        for c in (2, 3, 5, 10):
            stress[f"costs {c} cents a side"] = (daily(tr.assign(pnl=tr.gross - 2 * c - (2 * s5.FEE if col == 'opt' else 0)), days).mean(), len(tr))
        txt = report(name, desc, tr, days, q, stress, {})
        open(os.path.join(OUT, f"baseline_{name}.md"), "w").write(txt)
        m = metrics(tr, days)
        mo = metrics(tr[tr.day >= HOLDOUT], [x for x in days if x >= HOLDOUT])
        mc = monte_carlo(tr, days)
        summary.append(f"| {name} | {m['trades']:,} | {m['win%']:.0%} | {m['per day']:+.2f} | {m['t']:+.2f} | {m['PF']:.2f} | "
                       f"{m['maxDD$']:,.0f} | {mo['per day']:+.2f} | {stress['costs 5 cents a side'][0]:+.2f} | "
                       f"{mc.get('p(loss)', float('nan')):.0%} |")
        say(summary[-1])
    if not syn:
        summary.append(shares_long(say))
    open(os.path.join(OUT, "baseline_summary.md"), "w").write(
        "# Baseline summary (history, Mar 2024 to Oct 2026, one contract / 100 shares, 1 cent a side)\n\n" + "\n".join(summary) + "\n")
    say("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
