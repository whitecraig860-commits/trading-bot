"""
Honest scalper backtest: real prices, modelled option prices, costs, and an out-of-sample check
================================================================================================
The quick backtest in scalper.py measures the SHARE's move in R. That flatters an options scalper: a 0DTE option
loses value every minute (time decay), costs a spread to get in and out, and its stops and targets are on the
option's price. This one:

  - replays real 1-minute SPY, QQQ and IWM prices from Alpaca (all US exchanges), with the pre-market
  - prices the 0DTE option the bot would buy (nearest strike) every minute with Black-Scholes, using that day's
    VIX (SPY), VXN (QQQ) or RVX (IWM) as the volatility, so time decay and gamma are in
  - pays a realistic spread (the larger of $0.02 or 2% of the premium) and $0.03 a contract each way in fees,
    and fills the entry a quarter of the way into the spread, like the live limit order
  - sizes, enters and exits with the live rules: the same signals, trend filter, day-direction filter, chart read
    (and, if switched on, the multi-timeframe brain), the 11:30 cut-off, the -30% stop, +50% target, the profit
    locks, the 30-minute time stop, the reverse cross of VWAP, cooldowns, 2 losses per symbol, 2 open at once,
    6 trades a day and the daily loss limit
  - reports what matters: average win vs average loss, profit factor, the worst day, the deepest fall, and
    the results SPLIT into the month the rules were tuned on vs everything before it (out of sample)

Still a model, not the market: real fills, real implied volatility on the day and real spreads will differ.

  python optionbt.py --start 2025-01-02 --end 2026-11-06          (needs ALPACA_KEY / ALPACA_SECRET)
"""

from __future__ import annotations

import argparse
import math
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

import brain
import intraday
import scalper

NY = "America/New_York"
VOL_INDEX = {"SPY": "^VIX", "QQQ": "^VXN", "IWM": "^RVX"}
TUNED_FROM = "2026-10-06"  # the rules were chosen on data from here on: everything before is out of sample


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_bars(symbols, start, end, cache: Path) -> dict[str, pd.DataFrame]:
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    out = {}
    for sym in symbols:
        frames = []
        for s, e in _months(start, end):
            for feed in (DataFeed.SIP, DataFeed.IEX):
                try:
                    req = StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute, start=s, end=e,
                                           feed=feed, adjustment=Adjustment.RAW)
                    df = cli.get_stock_bars(req).df
                    break
                except Exception as exc:  # SIP not allowed on some plans: fall back to IEX
                    print(f"{sym} {s:%Y-%m}: {type(exc).__name__} on {feed}")
                    df = None
            if df is not None and len(df):
                d = df.xs(sym, level=0).rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]]
                d.index = pd.DatetimeIndex(d.index).tz_convert(NY)
                frames.append(d.astype(float))
        if frames:
            d = pd.concat(frames).sort_index()
            out[sym] = d[~d.index.duplicated()].between_time("04:00", "15:59")
            print(f"{sym}: {len(out[sym]):,} one-minute bars, {out[sym].index[0]:%Y-%m-%d} to {out[sym].index[-1]:%Y-%m-%d}")
    cache.write_bytes(pickle.dumps(out))
    return out


def _months(start, end):
    s = pd.Timestamp(start, tz="UTC")
    e = pd.Timestamp(end, tz="UTC")
    while s < e:
        n = min(s + pd.DateOffset(months=1), e)
        yield s.to_pydatetime(), n.to_pydatetime()
        s = n


def load_vol(start, end) -> dict[str, pd.Series]:
    import yfinance as yf

    out = {}
    for sym, idx in VOL_INDEX.items():
        try:
            h = yf.Ticker(idx).history(start=pd.Timestamp(start) - pd.Timedelta(days=10), end=end, interval="1d")
            s = (h["Close"] / 100).dropna()
            s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            out[sym] = s
        except Exception as exc:
            print(f"{idx}: {exc}")
    return out


# ---------------------------------------------------------------------------
# Option pricing
# ---------------------------------------------------------------------------


def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S: float, K: float, T: float, sigma: float, call: bool, r: float = 0.04) -> float:
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if call else (K - S))
    v = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / v
    d2 = d1 - v
    if call:
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def years_left(ts: pd.Timestamp) -> float:
    close = ts.normalize() + pd.Timedelta(hours=16)
    return max((close - ts).total_seconds() / 60, 1.0) / (252 * 390)


def strike_for(price: float, side: str) -> float:
    lo, hi = math.floor(price), math.ceil(price)
    if lo == hi:
        return float(lo)
    # nearest, slightly in the money on a tie (like pick_contract)
    near = lo if abs(price - lo) < abs(price - hi) else hi
    return float(near)


# ---------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------


def run(args) -> list[dict]:
    """args = (name, cfg, bars, vol, iv_mult). One variant over every day. Returns closed trades."""
    name, cfg, bars, vol, iv_mult = args
    syms = [s for s in cfg["symbols"] if s in bars]
    acct = 1000.0 / 0.75  # £1,000 in dollars, fixed so every year is sized the same
    risk_cash = acct * cfg["risk_per_trade_pct"] / 100
    fee = 0.03
    mins = int(cfg.get("signal_minutes", 5))
    trend = {}
    for s in syms:
        d5 = scalper.to_bars(bars[s].between_time("09:30", "15:59"), 5)
        spec = intraday.spec_for(s)
        t5 = intraday.add_intraday(intraday.prepare(d5, spec), spec)[["direction", "kind"]]
        t5.index = t5.index + pd.Timedelta(minutes=5)
        trend[s] = t5
    days = sorted(set.intersection(*[set(bars[s].index.normalize()) for s in syms]))
    trades = []
    for day in days:
        dd = {}
        for s in syms:
            b = bars[s]
            today = b[(b.index >= day) & (b.index < day + pd.Timedelta(days=1))]
            d1 = today.between_time("09:30", "15:59")
            if len(d1) < 300:
                continue
            s5 = scalper.to_bars(d1, mins)
            hist = b[(b.index < day) & (b.index >= day - pd.Timedelta(days=8))]
            iv = vol.get(s, vol.get("SPY", pd.Series(dtype=float)))
            prior = iv[iv.index < day.tz_localize(None)]
            sigma = float(prior.iloc[-1]) * iv_mult if len(prior) else 0.18
            pre = today.between_time("04:00", "09:29")
            hr = hist.between_time("09:30", "15:59")
            levels = []
            if len(hr):
                last = hr[hr.index >= hr.index[-1].normalize()]
                levels += [float(last["High"].max()), float(last["Low"].min())]
            if len(pre):
                levels += [float(pre["High"].max()), float(pre["Low"].min())]
            dd[s] = {"d1": d1, "s5": s5, "ind": scalper.session_indicators(s5, cfg), "pre": pre,
                     "hist": hist, "sigma": sigma, "orb": set(), "levels": levels}
        if not dd:
            continue
        open_, done, realised = [], [], 0.0
        last_exit, losses = {}, {}
        minutes = dd[next(iter(dd))]["d1"].index
        lh, lm = scalper.ny_time(cfg["last_entry"])
        fh, fm = scalper.ny_time(cfg["flat_by"])
        for m in minutes:
            now = m + pd.Timedelta(minutes=1)  # this 1-minute bar has just finished
            flat = now.hour * 60 + now.minute >= fh * 60 + fm
            # 1) manage open trades on this minute's close
            for t in list(open_):
                d = dd[t["sym"]]["d1"]
                if m not in d.index:
                    continue
                S = float(d.at[m, "Close"])
                mid = bs(S, t["K"], years_left(now), t["sigma"], t["side"] == "call")
                half = max(0.02, 0.02 * mid) / 2
                px = max(0.01, mid - half)
                t["best"] = max(t["best"], px)
                chg = (px / t["fill"] - 1) * 100
                u_r = ((S - t["u_entry"]) if t["side"] == "call" else (t["u_entry"] - S)) / t["u_risk"]
                t["best_r"] = max(t["best_r"], u_r)
                floor = scalper.profit_floor(t["best_r"], cfg)
                best_gain = (t["best"] / t["fill"] - 1) * 100
                reason = None
                if flat:
                    reason = "close"
                elif cfg.get("lock_profits") and u_r >= float(cfg.get("target_r", 2.0)):
                    reason = "target (share 1R)"
                elif floor is not None and u_r <= floor:
                    reason = "locked (share)"
                elif cfg.get("lock_profits") and best_gain >= float(cfg.get("lock_after_pct", 15)) and \
                        chg <= float(cfg.get("lock_floor_pct", 3)):
                    reason = "locked (option)"
                elif chg <= -float(cfg["stop_loss_pct"]):
                    reason = "stop"
                elif chg >= float(cfg["take_profit_pct"]):
                    reason = "target (+50%)"
                elif best_gain >= float(cfg["trail_after_pct"]) and (px / t["best"] - 1) * 100 <= -float(cfg["trail_giveback_pct"]):
                    reason = "trail"
                elif (now - t["t"]).total_seconds() / 60 >= int(cfg["max_hold_minutes"]):
                    reason = "time"
                elif cfg["exit_on_reverse_cross"] and now.minute % mins == 0:
                    ind = dd[t["sym"]]["ind"]
                    k = ind.index.searchsorted(now - pd.Timedelta(minutes=mins))
                    if k < len(ind) and ind.index[k] == now - pd.Timedelta(minutes=mins):
                        c, vw = float(ind["Close"].iloc[k]), float(ind["vwap"].iloc[k])
                        if (t["side"] == "call" and c < vw) or (t["side"] == "put" and c > vw):
                            reason = "reverse"
                if reason:
                    pnl = (px - t["fill"]) * 100 * t["qty"] - 2 * fee * t["qty"]
                    t.update(exit=px, exit_t=now, reason=reason, pnl=pnl, r=pnl / risk_cash)
                    open_.remove(t)
                    done.append(t)
                    realised += pnl
                    last_exit[t["sym"]] = (now, pnl)
                    if pnl < 0:
                        losses[t["sym"]] = losses.get(t["sym"], 0) + 1
            if flat:
                break
            # 2) new entries, on finished 5-minute candles only
            if now.minute % mins or realised <= -acct * cfg["daily_loss_limit_pct"] / 100:
                continue
            if len(done) + len(open_) >= int(cfg["max_trades_per_day"]) or len(open_) >= int(cfg["max_open_positions"]):
                continue
            if now.hour * 60 + now.minute > lh * 60 + lm + mins:
                continue
            for s in dd:
                if any(t["sym"] == s for t in open_) or losses.get(s, 0) >= int(cfg.get("max_losses_per_worker", 99)):
                    continue
                if len(open_) >= int(cfg["max_open_positions"]):
                    break
                ind = dd[s]["ind"]
                k = ind.index.searchsorted(now - pd.Timedelta(minutes=mins))
                if k >= len(ind) or ind.index[k] != now - pd.Timedelta(minutes=mins):
                    continue
                if not scalper.in_window(ind.index[k], cfg):
                    continue
                le = last_exit.get(s)
                if le:
                    wait = int(cfg["cooldown_minutes"]) if le[1] >= 0 else max(int(cfg["cooldown_minutes"]), int(cfg.get("loss_cooldown_minutes", 0)))
                    if (now - le[0]).total_seconds() / 60 < wait:
                        continue
                sig = scalper.signal_at(ind.iloc[: k + 1], k, cfg, dd[s]["orb"], {})
                ctx = None
                if not sig and "sweep" in cfg["triggers"] and brain.maybe_sweep(ind.iloc[: k + 1], dd[s]["levels"]):
                    ctx = brain.build(dd[s]["d1"][dd[s]["d1"].index < now], dd[s]["hist"], dd[s]["pre"])
                    sig = brain.sweep_trigger(ctx, cfg) if ctx else None
                if not sig:
                    continue
                side, why = sig
                if cfg.get("trend_filter"):
                    tr = trend[s][trend[s].index <= now]
                    if not len(tr) or not scalper.trend_allows(side, tr["direction"].iat[-1], tr["kind"].iat[-1]):
                        continue
                c = float(ind["Close"].iloc[k])
                vw = float(ind["vwap"].iloc[k])
                u_risk = max(abs(c - vw), c * 0.0015)
                if cfg.get("brain"):
                    ctx = ctx or brain.build(dd[s]["d1"][dd[s]["d1"].index < now], dd[s]["hist"], dd[s]["pre"])
                    if ctx is None:
                        continue
                    a = brain.analyse(ctx, side, u_risk, cfg)
                    if not a["take"]:
                        continue
                d1 = dd[s]["d1"]
                if now not in d1.index:
                    continue
                S0 = float(d1.at[now, "Open"])
                K = strike_for(S0, side)
                mid = bs(S0, K, years_left(now), dd[s]["sigma"], side == "call")
                if mid < 0.05:
                    continue
                half = max(0.02, 0.02 * mid) / 2
                fill = mid + 0.25 * half + 0.004
                in_use = sum(t["fill"] * 100 * t["qty"] for t in open_)
                max_spend = min(acct * cfg["max_premium_pct"] / 100, acct - in_use)
                qty = int(min(risk_cash / (fill * 100 * cfg["stop_loss_pct"] / 100), max_spend / (fill * 100))) if max_spend > 0 else 0
                if qty < 1:
                    continue
                open_.append({"sym": s, "side": side, "day": day.strftime("%Y-%m-%d"), "t": now, "K": K, "qty": qty,
                              "fill": fill, "best": fill, "u_entry": c, "u_risk": u_risk, "best_r": 0.0,
                              "sigma": dd[s]["sigma"], "why": "; ".join(why)[:80]})
        trades += done
    for t in trades:
        t["variant"] = name
    return trades


def report(name: str, t: pd.DataFrame) -> str:
    if t.empty:
        return f"{name:<44} no trades"
    w, lo = t[t.pnl > 0], t[t.pnl <= 0]
    pf = w.pnl.sum() / -lo.pnl.sum() if len(lo) and lo.pnl.sum() < 0 else float("inf")
    days = t.groupby("day")["pnl"].sum()
    eq = days.cumsum()
    dd = float((eq - eq.cummax()).min())
    gbp = 0.75
    return (f"{name:<44} {len(t):>4} tr {len(w) / len(t):>4.0%} won | avg win £{w.pnl.mean() * gbp if len(w) else 0:>5.1f} "
            f"avg loss £{lo.pnl.mean() * gbp if len(lo) else 0:>6.1f} | PF {pf:4.2f} | total £{t.pnl.sum() * gbp:>8.0f} "
            f"(£{t.pnl.mean() * gbp:+.1f}/trade) | days {(days > 0).mean():.0%} won, worst £{days.min() * gbp:.0f}, "
            f"deepest fall £{dd * gbp:.0f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-01-02")
    ap.add_argument("--end", default=pd.Timestamp.now(tz=NY).strftime("%Y-%m-%d"))
    ap.add_argument("--cache", default="/tmp/optionbt_bars.pkl")
    a = ap.parse_args()
    cfg, _ = scalper.load_cfg(str(Path(__file__).with_name("config.toml")))
    bars = load_bars(cfg["symbols"], a.start, a.end, Path(a.cache))
    vol = load_vol(a.start, a.end)
    old = dict(cfg, last_entry="15:00", lock_profits=False, day_agree=False, chart_read=False, triggers=["vwap", "ema50", "hod"])
    variants = [
        ("OLD rules (live until 6 Nov)", old, 1.0),
        ("NOW: main (chart read)", cfg, 1.0),
        ("NOW without chart read", dict(cfg, chart_read=False), 1.0),
        ("+ brain (15m veto, score>=0)", dict(cfg, brain=True), 1.0),
        ("+ brain (15m+1h veto, score>=0)", dict(cfg, brain=True, brain_veto_1h=True), 1.0),
        ("+ brain score>=2", dict(cfg, brain=True, brain_min_score=2), 1.0),
        ("+ brain + sweep trigger", dict(cfg, brain=True, triggers=cfg["triggers"] + ["sweep"]), 1.0),
        ("brain instead of chart read", dict(cfg, brain=True, chart_read=False), 1.0),
        ("NOW, volatility x0.8", cfg, 0.8),
        ("NOW, volatility x1.2", cfg, 1.2),
    ]
    jobs = [(n, c, bars, vol, m) for n, c, m in variants]
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as ex:
        results = list(ex.map(run, jobs))
    allt = pd.DataFrame([x for r in results for x in r])
    cut = TUNED_FROM
    print(f"\nPeriod {a.start} to {a.end}. Out of sample = before {cut}; in sample = {cut} onwards (the rules were tuned "
          "there). Money at £1,000 / £100 risk a trade, 1 contract mostly.\n")
    for n, _c, _m in variants:
        t = allt[allt.variant == n] if len(allt) else pd.DataFrame()
        if t.empty:
            print(report(n, t))
            continue
        print(report(n, t))
        print(report("    out of sample", t[t.day < cut]))
        print(report("    in sample (tuned)", t[t.day >= cut]))
    main_t = allt[allt.variant == "NOW: main (chart read)"]
    if len(main_t):
        main_t = main_t.assign(q=pd.to_datetime(main_t.day).dt.to_period("Q").astype(str))
        print("\nNOW by quarter:")
        for q, g in main_t.groupby("q"):
            print(report(f"    {q}", g))
        print("\nNOW by exit reason:")
        for r, g in main_t.groupby("reason"):
            print(report(f"    {r}", g))
        print("\nNOW by symbol and side:")
        for (s, sd), g in main_t.groupby(["sym", "side"]):
            print(report(f"    {s} {sd}", g))
    allt.to_csv("optionbt_trades.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
