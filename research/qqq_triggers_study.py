"""
Study 5: the three one-minute QQQ triggers, run exactly as research/QQQ_TRIGGERS_PROTOCOL.md says
==================================================================================================
Read-only market data (Alpaca). No orders.   python research/qqq_triggers_study.py [--synthetic]
"""

from __future__ import annotations

import argparse
import math
import os
import pickle
import sys
import tempfile
import time
from statistics import NormalDist

import numpy as np
import pandas as pd

NY = "America/New_York"
START, END, HOLDOUT = "2024-03-01", "2026-11-01", pd.Timestamp("2026-01-01")
GBP = 0.76
FEE = 0.03


def say(*a):
    print(*a, flush=True)


def load_qqq() -> pd.DataFrame:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    parts = []
    for a, b in zip(pd.date_range(START, END, freq="MS"), pd.date_range(START, END, freq="MS")[1:]):
        df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute,
                                                 start=a.tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                                                 end=b.tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                                                 feed=DataFeed.SIP)).df
        if df is not None and len(df):
            parts.append(df.xs("QQQ", level=0))
    q = pd.concat(parts)
    q.index = pd.DatetimeIndex(q.index).tz_convert(NY).tz_localize(None)
    q = q.between_time("09:30", "15:59")[["open", "high", "low", "close", "volume"]].astype(float)
    return q[~q.index.duplicated()]


class Options:
    """Real one-minute option trade bars, fetched one day at a time for the strikes that day could need."""

    def __init__(self, synthetic=False, qqq=None):
        self.syn, self.q, self.cache = synthetic, qqq, {}
        self.dir = tempfile.mkdtemp(prefix="optbars")
        if not synthetic:
            from alpaca.data.historical import OptionHistoricalDataClient

            self.cli = OptionHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])

    def day(self, day: pd.Timestamp, expiry: pd.Timestamp, lo: float, hi: float) -> dict:
        if day in self.cache:
            return self.cache[day]
        f = os.path.join(self.dir, f"{day:%Y%m%d}.pkl")
        if os.path.exists(f):
            with open(f, "rb") as fh:
                out = pickle.load(fh)
            self.cache = {day: out}
            return out
        out = {}
        if self.syn:
            d = self.q[self.q.index.normalize() == day]
            for k in range(int(lo) - 1, int(hi) + 3):
                for typ in "CP":
                    intr = np.maximum((d.close - k) if typ == "C" else (k - d.close), 0)
                    px = (intr + 3.5 * np.exp(-((d.close - k) / 6) ** 2)).round(2)
                    out[(typ, k)] = pd.DataFrame({"open": px.shift(1).fillna(px), "high": px + 0.03, "low": px - 0.03,
                                                  "close": px}, index=d.index)
        else:
            from alpaca.data.requests import OptionBarsRequest
            from alpaca.data.timeframe import TimeFrame

            syms = {f"QQQ{expiry:%y%m%d}{t}{k * 1000:08d}": (t, k) for k in range(int(lo) - 1, int(hi) + 3) for t in "CP"}
            for attempt in range(3):
                try:
                    df = self.cli.get_option_bars(OptionBarsRequest(
                        symbol_or_symbols=list(syms), timeframe=TimeFrame.Minute,
                        start=(day + pd.Timedelta(hours=9, minutes=30)).tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                        end=(day + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC").to_pydatetime())).df
                    break
                except Exception as exc:
                    df = None
                    say(f"{day.date()} option bars: {type(exc).__name__}: {str(exc)[:100]}")
                    time.sleep(3 * (attempt + 1))
            if df is not None and len(df):
                for s in df.index.get_level_values(0).unique():
                    b = df.xs(s, level=0)[["open", "high", "low", "close"]].astype(float)
                    b.index = pd.DatetimeIndex(b.index).tz_convert(NY).tz_localize(None)
                    out[syms[s]] = b
        with open(f, "wb") as fh:
            pickle.dump(out, fh)
        self.cache = {day: out}  # keep one day in memory, the rest on disk
        return out


def signals(q: pd.DataFrame) -> pd.DataFrame:
    """§3: one row per signal: time of the bar close, side, trigger, QQQ close."""
    day = q.index.normalize()
    tp = (q.high + q.low + q.close) / 3
    vwap = (tp * q.volume).groupby(day).cumsum() / q.volume.groupby(day).cumsum()
    ema = q.close.ewm(span=50, adjust=False).mean()
    rows = []
    for name, line in (("VWAP", vwap), ("EMA50", ema)):
        prev_c, prev_l = q.close.shift(1), line.shift(1)
        same_day = day == pd.Series(day, index=q.index).shift(1).to_numpy()
        up = same_day & (prev_c <= prev_l) & (q.close > line)
        dn = same_day & (prev_c >= prev_l) & (q.close < line)
        rows += [(t, "C", name) for t in q.index[up]] + [(t, "P", name) for t in q.index[dn]]
    for d, g in q.groupby(day):
        if len(g) < 30:
            continue
        orb = g.iloc[:15]
        hi, lo = orb.high.max(), orb.low.min()
        rest = g.iloc[15:]
        a, b = rest.index[rest.close > hi], rest.index[rest.close < lo]
        if len(a):
            rows.append((a[0], "C", "RANGE"))
        if len(b):
            rows.append((b[0], "P", "RANGE"))
    s = pd.DataFrame(rows, columns=["bar", "side", "trigger"]).sort_values(["bar", "trigger"])
    s["t"] = s.bar + pd.Timedelta(minutes=1)  # the bar's close
    s["px"] = q.close.reindex(s.bar).to_numpy()
    tod = s.t.dt.strftime("%H:%M")
    return s[(tod >= "09:45") & (tod <= "15:30")].drop_duplicates("bar").reset_index(drop=True)


def simulate(q, sig, opts, target=0.025, stop=0.06, hold=10, triggers=None, optimistic=False):
    days = sorted(set(q.index.normalize()))
    nxt = dict(zip(days[:-1], days[1:]))
    rng = q.groupby(q.index.normalize()).agg(lo=("low", "min"), hi=("high", "max"))
    trades, skipped, free_at = [], 0, pd.Timestamp("1900-01-01")
    for r in sig.itertuples():
        if triggers and r.trigger not in triggers:
            continue
        if r.t < free_at:
            continue
        d = r.t.normalize()
        if d not in nxt:
            continue
        chain = opts.day(d, nxt[d], rng.lo[d], rng.hi[d])
        b = chain.get((r.side, int(round(r.px))))
        if b is None:
            skipped += 1
            continue
        b = b[(b.index >= r.t) & (b.index <= d + pd.Timedelta(hours=15, minutes=55))]
        if b.empty or b.index[0] > r.t + pd.Timedelta(minutes=3):
            skipped += 1
            continue
        entry = float(b.open.iloc[0])
        if entry < 0.5:
            skipped += 1
            continue
        tgt, stp, t0 = entry * (1 + target), entry * (1 - stop), b.index[0]
        exit_px = exit_t = why = None
        for i, bar in enumerate(b.itertuples()):
            hit_s = bar.low <= stp
            hit_t = bar.high >= tgt
            if i > 0 and bar.open <= stp:
                exit_px, why = bar.open, "stop (gap)"
            elif hit_s and hit_t:
                exit_px, why = (tgt, "target") if optimistic else (stp, "stop")
            elif hit_s:
                exit_px, why = stp, "stop"
            elif hit_t:
                exit_px, why = tgt, "target"
            elif bar.Index >= t0 + pd.Timedelta(minutes=hold):
                exit_px, why = bar.close, "time"
            if exit_px is not None:
                exit_t = bar.Index
                break
        if exit_px is None:
            exit_px, exit_t, why = float(b.close.iloc[-1]), b.index[-1], "end of day"
        free_at = exit_t + pd.Timedelta(minutes=1)
        trades.append({"day": d, "t": t0, "side": r.side, "trigger": r.trigger, "entry": entry, "exit": float(exit_px),
                       "why": why, "mins": (exit_t - t0).total_seconds() / 60})
    return pd.DataFrame(trades), skipped


def nw_t(x: np.ndarray, lags=5) -> float:
    n = len(x)
    u = x - x.mean()
    v = u @ u / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    se = math.sqrt(v / n)
    return x.mean() / se if se > 0 else 0.0


def daily(tr: pd.DataFrame, cents: float, all_days) -> pd.Series:
    pnl = (tr.exit - tr.entry - 2 * cents / 100) * 100 - 2 * FEE
    return pnl.groupby(tr.day).sum().reindex(all_days, fill_value=0.0)


def line(label, tr, cents, all_days):
    if tr.empty:
        return f"{label:34s} no trades"
    pnl = (tr.exit - tr.entry - 2 * cents / 100) * 100 - 2 * FEE
    d = daily(tr, cents, all_days)
    w, l = pnl[pnl > 0], pnl[pnl <= 0]
    return (f"{label:34s} {len(tr):6d} trades ({len(tr) / len(all_days):4.1f}/day)  win {len(w) / len(tr):4.0%}  "
            f"avg win ${w.mean() if len(w) else 0:5.1f}  avg loss ${l.mean() if len(l) else 0:6.1f}  per trade ${pnl.mean():+6.2f}  "
            f"per day ${d.mean():+7.2f} (£{d.mean() * GBP:+6.2f})  t {nw_t(d.to_numpy()):+5.2f}  total ${d.sum():+,.0f}")


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
        say("*** SYNTHETIC DATA: results are meaningless ***")
    else:
        q = load_qqq()
    all_days = sorted(set(q.index.normalize()))
    say(f"Study 5. QQQ one-minute bars: {len(q):,} from {q.index[0]} to {q.index[-1]}, {len(all_days)} days. "
        f"Protocol: research/QQQ_TRIGGERS_PROTOCOL.md. One contract per trade.")
    sig = signals(q)
    say(f"Signals 09:45-15:30: {len(sig):,} ({len(sig) / len(all_days):.1f} a day): "
        + ", ".join(f"{k} {v:,}" for k, v in sig.trigger.value_counts().items()))
    opts = Options(a.synthetic, q)
    t0 = time.time()
    base, skipped = simulate(q, sig, opts)
    say(f"Base run: {len(base):,} trades, {skipped:,} signals skipped for no option price ({time.time() - t0:.0f}s)\n")

    say("=== BASE CASE (all three triggers, target +2.5%, stop -6%, 10-minute limit, conservative ordering) ===")
    for c in (0, 1, 2):
        say(line(f"{c} cent(s) per side" + ("  <- base" if c == 1 else ""), base, c, all_days))
    say("\nExit reasons: " + ", ".join(f"{k} {v:,}" for k, v in base.why.value_counts().items())
        + f"; median hold {base.mins.median():.0f} min")
    say("\n--- By trigger (1 cent)")
    for k, g in base.groupby("trigger"):
        say(line(k, g, 1, all_days))
    say("\n--- By side (1 cent)")
    for k, g in base.groupby("side"):
        say(line("calls" if k == "C" else "puts", g, 1, all_days))
    say("\n--- By year (1 cent)")
    for y, g in base.groupby(base.day.dt.year):
        say(line(str(y), g, 1, [d for d in all_days if d.year == y]))
    say("\n--- By time of day (1 cent)")
    for lab, lo, hi in (("09:45-10:30", "09:45", "10:30"), ("10:30-12:00", "10:30", "12:00"),
                        ("12:00-14:00", "12:00", "14:00"), ("14:00-15:30", "14:00", "15:35")):
        tod = base.t.dt.strftime("%H:%M")
        say(line(lab, base[(tod >= lo) & (tod < hi)], 1, all_days))
    hold_days = [d for d in all_days if d >= HOLDOUT]
    hb = base[base.day >= HOLDOUT]
    say("\n--- Holdout (2026 onward)")
    for c in (0, 1, 2):
        say(line(f"{c} cent(s) per side", hb, c, hold_days))

    d1, d2 = daily(base, 1, all_days), daily(base, 2, all_days)
    dh = daily(hb, 1, hold_days) if len(hb) else pd.Series([0.0])
    t1 = nw_t(d1.to_numpy())
    c1, c2, c3 = d1.mean() > 0 and t1 >= 2.0, dh.mean() > 0, d2.mean() > 0
    say("\n=== PASS / FAIL (§7) ===")
    say(f"   {'PASS' if c1 else 'fail'}  1. mean daily profit > 0 with t >= 2 at 1 cent  (${d1.mean():+.2f}, t {t1:+.2f}, "
        f"p {1 - NormalDist().cdf(t1):.3f})")
    say(f"   {'PASS' if c2 else 'fail'}  2. positive in the holdout at 1 cent  (${dh.mean():+.2f} a day)")
    say(f"   {'PASS' if c3 else 'fail'}  3. positive at 2 cents  (${d2.mean():+.2f} a day)")
    say("VERDICT: " + ("PASSES" if c1 and c2 and c3 else "FAILS"))
    say(f"Days with a loss (1 cent): {(d1 < 0).mean():.0%}; best day ${d1.max():+,.0f}; worst day ${d1.min():+,.0f}; "
        f"worst run of losses ${(d1.cumsum() - d1.cumsum().cummax()).min():+,.0f}")

    say("\n=== SENSITIVITY (1 cent; reported, never picked) ===")
    for label, kw in (("optimistic ordering", {"optimistic": True}), ("target 2%", {"target": 0.02}),
                      ("target 4%", {"target": 0.04}), ("stop 4%", {"stop": 0.04}), ("stop 10%", {"stop": 0.10}),
                      ("time limit 5 min", {"hold": 5}), ("time limit 20 min", {"hold": 20}),
                      ("VWAP only", {"triggers": ["VWAP"]}), ("EMA50 only", {"triggers": ["EMA50"]}),
                      ("RANGE only", {"triggers": ["RANGE"]})):
        tr, _ = simulate(q, sig, opts, **kw)
        say(line(label, tr, 1, all_days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
