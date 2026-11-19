"""
Study 6: the "one trade a day" QQQ bot, run exactly as research/ONE_A_DAY_PROTOCOL.md says
==========================================================================================
Read-only market data (Alpaca). No orders.   python research/one_a_day_study.py [--synthetic]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

import qqq_triggers_study as s5

NY, GBP, FEE = s5.NY, 0.76, 0.03
HOLDOUT = pd.Timestamp("2026-01-01")
say = s5.say


class Opt:
    def __init__(self, synthetic, q):
        self.syn, self.q, self.cache = synthetic, q, {}
        if not synthetic:
            from alpaca.data.historical import OptionHistoricalDataClient

            self.cli = OptionHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])

    def bars(self, day, expiry, typ, strike) -> pd.DataFrame:
        key = (day, expiry, typ, strike)
        if key in self.cache:
            return self.cache[key]
        if self.syn:
            d = self.q[self.q.index.normalize() == day]
            intr = np.maximum((d.close - strike) if typ == "C" else (strike - d.close), 0)
            px = (intr + 4.5 * np.exp(-((d.close - strike) / 8) ** 2)).round(2)
            out = pd.DataFrame({"open": px, "close": px}, index=d.index)
        else:
            from alpaca.data.requests import OptionBarsRequest
            from alpaca.data.timeframe import TimeFrame

            sym = f"QQQ{expiry:%y%m%d}{typ}{int(strike) * 1000:08d}"
            out = pd.DataFrame()
            for attempt in range(3):
                try:
                    df = self.cli.get_option_bars(OptionBarsRequest(
                        symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                        start=(day + pd.Timedelta(hours=9, minutes=30)).tz_localize(NY).tz_convert("UTC").to_pydatetime(),
                        end=(day + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC").to_pydatetime())).df
                    if df is not None and len(df):
                        out = df.xs(sym, level=0)[["open", "close"]].astype(float)
                        out.index = pd.DatetimeIndex(out.index).tz_convert(NY).tz_localize(None)
                    break
                except Exception as exc:
                    say(f"{sym}: {type(exc).__name__}: {str(exc)[:80]}")
                    time.sleep(2 * (attempt + 1))
        self.cache[key] = out
        return out


def prepare(q: pd.DataFrame):
    day = q.index.normalize()
    mod = q.index.hour * 60 + q.index.minute
    piv = pd.Series(q.close.to_numpy(), index=[day, mod]).unstack()
    opens = q.open.groupby(day).first()
    absmove = piv.div(opens, axis=0).sub(1).abs()
    sigma = absmove.rolling(14).mean().shift(1)  # previous 14 days only
    tp = (q.high + q.low + q.close) / 3
    vwap = (tp * q.volume).groupby(day).cumsum() / q.volume.groupby(day).cumsum()
    f = q.resample("5min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc = f.close.shift(1)
    tr = pd.concat([f.high - f.low, (f.high - pc).abs(), (f.low - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    return opens, sigma, vwap, atr


def run(q, prep, opt, dte=2, itm=2.0, trail=4.0, use_noise=True, buffer=0.3):
    opens, sigma, vwap, atr = prep
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
            t = d + pd.Timedelta(minutes=hh - 1)  # the candle that closes at the check time
            if t not in g.index:
                continue
            a = atr.get(d + pd.Timedelta(minutes=hh - 5))
            sg = sigma.loc[d].get(hh - 1)
            if a is None or a != a or sg != sg:
                continue
            c, vw = g.close[t], vwap[t]
            up = c > hi + buffer * a and c > vw and (not use_noise or c > o * (1 + sg))
            dn = c < lo - buffer * a and c < vw and (not use_noise or c < o * (1 - sg))
            if up or dn:
                trade = (t, 1 if up else -1, c, a)
                break
        if not trade:
            out.append({"day": d, "traded": False})
            continue
        t, side, entry, a = trade
        rest = g[g.index > t]
        best, why, xt, xp = 0.0, "time", None, None
        for bar in rest.itertuples():
            fav = (bar.close - entry) * side
            best = max(best, fav)
            if fav <= -10 * a:
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
        typ = "C" if side > 0 else "P"
        strike = round(entry - itm * side)
        ob = opt.bars(d, days[i + dte], typ, strike)
        o_in = o_out = None
        if len(ob):
            e = ob[(ob.index > t) & (ob.index <= t + pd.Timedelta(minutes=5))]
            x = ob[(ob.index <= xt) & (ob.index >= xt - pd.Timedelta(minutes=10)) & (ob.index > t)]
            if len(e) and len(x) and x.index[-1] > e.index[0]:
                o_in, o_out = float(e.open.iloc[0]), float(x.close.iloc[-1])
        out.append({"day": d, "traded": True, "t": t, "side": typ, "entry": entry, "exit": xp, "why": why, "atr": a,
                    "best_atr": best / a, "mins": (xt - t).total_seconds() / 60, "o_in": o_in, "o_out": o_out,
                    "shares": (xp - entry) * side * 100 - 2.0})
    return pd.DataFrame(out)


def line(label, r, cents, ndays=None, col="opt"):
    tr = r[r.traded.astype(bool)] if "traded" in r else r
    if col == "opt":
        tr = tr.dropna(subset=["o_in"])
        pnl = (tr.o_out - tr.o_in - 2 * cents / 100) * 100 - 2 * FEE
    else:
        pnl = tr.shares
    n = ndays or len(r)
    if not len(tr):
        return f"{label:30s} no trades"
    d = pnl.groupby(tr.day).sum().reindex(sorted(set(r.day)), fill_value=0.0) if ndays is None else pnl
    w, l = pnl[pnl > 0], pnl[pnl <= 0]
    t = s5.nw_t(d.to_numpy()) if len(d) > 10 else float("nan")
    return (f"{label:30s} {len(tr):4d} trades  win {len(w) / len(tr):4.0%}  avg win ${w.mean() if len(w) else 0:7.0f}  "
            f"avg loss ${l.mean() if len(l) else 0:7.0f}  per trade ${pnl.mean():+7.1f}  per day ${pnl.sum() / n:+7.2f} "
            f"(£{pnl.sum() / n * GBP:+6.2f})  t {t:+5.2f}  total ${pnl.sum():+,.0f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    if a.synthetic:
        rng = np.random.default_rng(2)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2025-09-01", "2026-02-27")
                                for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, 0.15, len(idx)))
        q = pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c + rng.normal(0, 0.03, len(idx)),
                          "volume": 1000.0}, index=idx)
        say("*** SYNTHETIC DATA: results are meaningless ***")
    else:
        q = s5.load_qqq()
    prep = prepare(q)
    opt = Opt(a.synthetic, q)
    say(f"Study 6. QQQ 1-minute bars {q.index[0]} to {q.index[-1]}. Protocol: research/ONE_A_DAY_PROTOCOL.md. "
        "One contract (options) or 100 shares.")
    r = run(q, prep, opt)
    tr = r[r.traded.astype(bool)]
    priced = tr.dropna(subset=["o_in"])
    say(f"Days tested {len(r)}; days with a trade {len(tr)} ({len(tr) / len(r):.0%}); trades with usable option prices "
        f"{len(priced)}; calls {sum(tr.side == 'C')}, puts {sum(tr.side == 'P')}")
    say(f"Exit reasons: {tr.why.value_counts().to_dict()}; median hold {tr.mins.median():.0f} min; "
        f"median ATR ${tr.atr.median():.2f}; median option entry ${priced.o_in.median():.2f}\n")
    say("=== BASE CASE ===")
    for c in (0, 2, 5):
        say(line(f"options, {c} cents per side" + ("  <- base" if c == 2 else ""), r, c))
    say(line("100 shares, 1 cent per side", r, 0, col="shares"))
    say("\n--- By side (options, 2 cents)")
    for k, g in tr.groupby("side"):
        say(line("calls" if k == "C" else "puts", g, 2, ndays=len(r)))
    say("\n--- By exit reason (options, 2 cents)")
    for k, g in tr.groupby("why"):
        say(line(k, g, 2, ndays=len(r)))
    say("\n--- By year (options, 2 cents | shares)")
    for y, g in r.groupby(r.day.dt.year):
        say(line(str(y), g, 2))
        say(line(f"{y} shares", g, 0, col="shares"))
    h = r[r.day >= HOLDOUT]
    say("\n--- Holdout, 2026 onward")
    for c in (2, 5):
        say(line(f"options, {c} cents", h, c))
    say(line("100 shares", h, 0, col="shares"))

    def daily(rr, cents):
        t2 = rr[rr.traded.astype(bool)].dropna(subset=["o_in"])
        p = (t2.o_out - t2.o_in - 2 * cents / 100) * 100 - 2 * FEE
        return p.groupby(t2.day).sum().reindex(sorted(set(rr.day)), fill_value=0.0)

    d2, d5, dh = daily(r, 2), daily(r, 5), daily(h, 2)
    sh = tr.shares.groupby(tr.day).sum().reindex(sorted(set(r.day)), fill_value=0.0)
    t2 = s5.nw_t(d2.to_numpy())
    c1, c2, c3, c4 = d2.mean() > 0 and t2 >= 2, dh.mean() > 0, d5.mean() > 0, sh.mean() > 0
    say("\n=== PASS / FAIL (§6) ===")
    say(f"   {'PASS' if c1 else 'fail'}  1. options at 2 cents: mean daily > 0 with t >= 2  (${d2.mean():+.2f} a day, t {t2:+.2f})")
    say(f"   {'PASS' if c2 else 'fail'}  2. positive in the holdout  (${dh.mean():+.2f} a day)")
    say(f"   {'PASS' if c3 else 'fail'}  3. positive at 5 cents  (${d5.mean():+.2f} a day)")
    say(f"   {'PASS' if c4 else 'fail'}  4. shares version profitable  (${sh.mean():+.2f} a day, t {s5.nw_t(sh.to_numpy()):+.2f})")
    say("VERDICT: " + ("PASSES" if c1 and c2 and c3 and c4 else "FAILS"))
    cum = d2.cumsum()
    say(f"Options, 2 cents: losing days {(d2 < 0).mean():.0%} of all days; best day ${d2.max():+,.0f}; worst day "
        f"${d2.min():+,.0f}; worst losing run ${(cum - cum.cummax()).min():+,.0f}; "
        f"best 5 days make ${d2.nlargest(5).sum():+,.0f} of the ${d2.sum():+,.0f} total")

    say("\n=== SENSITIVITY (options at 2 cents | shares; reported, never picked) ===")
    for label, kw in (("expiry 1 day", {"dte": 1}), ("expiry 3 days", {"dte": 3}), ("at-the-money strike", {"itm": 0.0}),
                      ("trail at 3 ATR", {"trail": 3.0}), ("trail at 5 ATR", {"trail": 5.0}),
                      ("no noise band", {"use_noise": False}), ("no 0.3 ATR buffer", {"buffer": 0.0})):
        rr = run(q, prep, opt, **kw)
        say(line(label, rr, 2))
        say(line(label + " (shares)", rr, 0, col="shares"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
