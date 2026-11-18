"""
Study 9 (research/HIS_FILTER_PROTOCOL.md): Stage 1 finds which of our signals he took; Stage 2 tests EARLY, ITM, FILTER
and COMBO on 2.7 years of real option bars. Read-only market data; no orders.   python research/his_filter_study.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

import qqq_triggers_study as s5

HOLDOUT = pd.Timestamp("2026-01-01")
NY = s5.NY


def signals2(q: pd.DataFrame, first: str = "09:45") -> pd.DataFrame:
    """Study 5's signals, optionally from an earlier time, with the size of each cross and the day's open."""
    day = q.index.normalize()
    tp = (q.high + q.low + q.close) / 3
    vwap = (tp * q.volume).groupby(day).cumsum() / q.volume.groupby(day).cumsum()
    ema = q.close.ewm(span=50, adjust=False).mean()
    same_day = day == pd.Series(day, index=q.index).shift(1).to_numpy()
    rows = []
    for name, line in (("VWAP", vwap), ("EMA50", ema)):
        pc, pl = q.close.shift(1), line.shift(1)
        up = same_day & (pc <= pl) & (q.close > line)
        dn = same_day & (pc >= pl) & (q.close < line)
        dist = (q.close - line).abs()
        rows += [(t, "C", name, dist[t]) for t in q.index[up]] + [(t, "P", name, dist[t]) for t in q.index[dn]]
    for d, g in q.groupby(day):
        if len(g) < 30:
            continue
        hi, lo = g.iloc[:15].high.max(), g.iloc[:15].low.min()
        rest = g.iloc[15:]
        a, b = rest.index[rest.close > hi], rest.index[rest.close < lo]
        if len(a):
            rows.append((a[0], "C", "RANGE", rest.close[a[0]] - hi))
        if len(b):
            rows.append((b[0], "P", "RANGE", lo - rest.close[b[0]]))
    s = pd.DataFrame(rows, columns=["bar", "side", "trigger", "dist"]).sort_values(["bar", "trigger"])
    s["t"] = s.bar + pd.Timedelta(minutes=1)
    s["px"] = q.close.reindex(s.bar).to_numpy()
    s["open"] = q.open.groupby(day).transform("first").reindex(s.bar).to_numpy()
    tod = s.t.dt.strftime("%H:%M")
    s = s[(tod >= first) & (tod <= "15:30")].drop_duplicates("bar").reset_index(drop=True)
    # features for the skip rules (computed over all signals, whether or not a bot would be free to take them)
    s["day"] = s.t.dt.normalize()
    prev_t = s.groupby("day").t.shift(1)
    prev_side = s.groupby("day").side.shift(1)
    s["gap"] = (s.t - prev_t).dt.total_seconds() / 60
    s["F1"] = (s.gap <= 2) & (prev_side != s.side)
    s["F2"] = s.gap <= 2
    s["F3"] = s.dist < 0.10
    s["F4"] = ((s.side == "C") & (s.px <= s.open)) | ((s.side == "P") & (s.px >= s.open))
    s["F5"] = s.gap < 5
    for f in ("F1", "F2", "F3", "F4", "F5"):
        s[f] = s[f].fillna(False).astype(bool)
    return s


def load_recent() -> pd.DataFrame:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute,
                                             start=pd.Timestamp("2026-11-02").tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                                             end=pd.Timestamp("2026-11-19").tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                                             feed=DataFeed.IEX)).df.xs("QQQ", level=0)
    df.index = pd.DatetimeIndex(df.index).tz_convert(NY).tz_localize(None)
    q = df.between_time("09:30", "15:59")[["open", "high", "low", "close", "volume"]].astype(float)
    return q[~q.index.duplicated()]


def stage1() -> str | None:
    his = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "state", "discord_trades.csv"))
    his["bt"] = pd.to_datetime(his.date + " " + his.buy_time)
    q = load_recent()
    sig = signals2(q, "09:31")
    days = sorted(pd.to_datetime(his.date.unique()))
    sig = sig[sig.day.isin(days)].copy()
    sig["taken"] = [bool(((his.bt >= r.t) & (his.bt <= r.t + pd.Timedelta(seconds=60)) & (his.type == r.side)).any())
                    for r in sig.itertuples()]
    entries = his.groupby(["date", "buy_time"]).size().shape[0]
    s5.say(f"Stage 1: {len(sig)} of our signals on {len(days)} days of his; he took {int(sig.taken.sum())}. "
           f"His distinct entries: {his.drop_duplicates(['date', 'type', 'strike']).shape[0]} (by option), "
           f"{his.bt.dt.floor('min').nunique()} distinct minutes; entries matched to a signal: "
           f"{sum(any((r.bt >= t) and (r.bt <= t + pd.Timedelta(seconds=60)) for t in sig.t) for r in his.itertuples())}/{len(his)}")
    tk, sk = sig[sig.taken], sig[~sig.taken]
    best, best_score = None, -9.0
    s5.say(f"{'rule':5s} {'keeps his':>10s} {'skips his skipped':>18s} {'score':>7s}")
    for f in ("F1", "F2", "F3", "F4", "F5"):
        keep = 1 - tk[f].mean() if len(tk) else 0
        power = sk[f].mean() if len(sk) else 0
        score = keep + power - 1
        s5.say(f"{f:5s} {keep:10.0%} {power:18.0%} {score:+7.2f}")
        if keep >= 0.70 and score > best_score:
            best, best_score = f, score
    s5.say("By trigger (taken / all): " + ", ".join(f"{k} {int(g.taken.sum())}/{len(g)}" for k, g in sig.groupby("trigger")))
    s5.say("By hour (taken / all): " + ", ".join(f"{h:02d}h {int(g.taken.sum())}/{len(g)}" for h, g in sig.groupby(sig.t.dt.hour)))
    s5.say(f"FILTER = {best} (score {best_score:+.2f})" if best else "FILTER = none (no rule keeps 70% of his signals)")
    return best


def simulate(q, sig, opts, cents, itm=False, skip=None, maxrun=2, target=0.025, stop=0.06, hold=10):
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
        if skip and getattr(r, skip):
            continue
        k = (int(np.floor(r.px)) if r.side == "C" else int(np.ceil(r.px))) if itm else int(round(r.px))
        b = opts.day(d, nxt[d], rng.lo[d], rng.hi[d]).get((r.side, k))
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
        run = run + 1 if pnl < 0 else 0
    tr = pd.DataFrame(trades)
    return tr.pnl.groupby(tr.day).sum().reindex(days, fill_value=0.0), len(tr), float((tr.pnl > 0).mean())


def main() -> int:
    flt = stage1()
    q = s5.load_qqq()
    late, early = signals2(q, "09:45"), signals2(q, "09:31")
    opts = s5.Options(False, q)
    rules = {"BASE": (late, {}), "EARLY": (early, {}), "ITM": (late, {"itm": True})}
    if flt:
        rules["FILTER"] = (late, {"skip": flt})
        rules["COMBO"] = (early, {"itm": True, "skip": flt})
    else:
        rules["COMBO"] = (early, {"itm": True})
    s5.say(f"\nStage 2. {len(set(q.index.normalize()))} days. Signals from 09:45: {len(late):,}; from 09:31: {len(early):,}")
    res = {(k, c): simulate(q, sg, opts, c, **kw) for c in (1, 2) for k, (sg, kw) in rules.items()}
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
