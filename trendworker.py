"""
QQQ trend-day worker
====================
Built after the "payroll" bot screenshots (9 Nov 2026): one market (QQQ), traded all day, only WITH a clear trend,
buying pullbacks and fresh highs (puts on down days), a profit target, an ATR trail once it's well in profit, and
"never sells below what you paid" once it has been up. Re-enters after each exit while the trend lasts.

What it reads, on finished 5-minute candles (1-minute candles are only used to build them and to manage exits):
  - the day's trend: price above a RISING VWAP (or below a falling one), most recent candles on that side,
    and the day up (or down) from the open
  - the candles: every candle's body and wicks, the patterns (hammer, engulfing, shooting star, doji, inside bar,
    three in a row...), higher highs/lows, wick walls ahead and wick pressure (candles.read), TA-Lib's patterns
  - entries: (a) a PULLBACK: price dipped to the 20 EMA or VWAP in the last 3 candles and this candle closes back up
    strongly; (b) a CONTINUATION: a strong candle closing at a new high (low) of the last hour
  - news: no entries 30 minutes either side of big scheduled events, nor against a fresh Trump post (live only)

Each trade's stop is under the pullback's low (over its high for puts); 1R = that distance on the share.

backtest(): replays QQQ 1-minute prices and prices every trade with the REAL option contract's real 1-minute prices
from Alpaca (no formula), choosing the nearest strike the account can afford, paying a spread and fees.

  python trendworker.py --start 2024-03-01 --end 2026-11-10 [--day 2026-11-09]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

import candles

NY = "America/New_York"

DEFAULTS = {
    "tw_min_day_move_pct": 0.3,     # the day must be at least this far from the open, in the trade's direction
    "tw_side_bars": 9,              # of the last 12 candles, at least this many closed on the trend's side of VWAP
    "tw_vwap_slope_bars": 6,
    "tw_pullback_atr": 0.3,         # a pullback = a low within this many ATRs of the 20 EMA or VWAP
    "tw_breakout_bars": 12,         # a continuation = a close above the high of the last 12 candles (1 hour)
    "tw_min_body_pct": 45,
    "tw_close_zone_pct": 35,
    "tw_chart_min": -1,             # candles.read score needed (the wick/pattern read); None = not used
    "tw_max_risk_atr": 1.5,
    "tw_first_entry": "09:40",
    "tw_last_entry": "15:00",
    "tw_cooldown_minutes": 5,
    "tw_max_trades": 10,
    "tw_max_losses": 3,
    "tw_target_r": 2.0,             # take profit when the share has moved this many R
    "tw_be_after_r": 1.0,           # after this, never back below +be_lock R ("never sells below what you paid")
    "tw_be_lock_r": 0.1,
    "tw_trail_after_r": 1.5,        # trail armed
    "tw_trail_gap_r": 0.75,
    "tw_option_stop_pct": 40,       # and a hard stop on the option itself
    "tw_dte": 0,
}


def ny_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def trend_state(ind: pd.DataFrame, i: int, cfg: dict) -> int:
    """+1 trend day up, -1 down, 0 none, from candles up to i."""
    if i < 12:
        return 0
    c = float(ind["Close"].iloc[i])
    vw = ind["vwap"].to_numpy(float)
    cl = ind["Close"].to_numpy(float)
    slope = vw[i] - vw[i - int(cfg["tw_vwap_slope_bars"])]
    above = int((cl[i - 11:i + 1] > vw[i - 11:i + 1]).sum())
    move = (c / float(ind["Open"].iloc[0]) - 1) * 100
    need = int(cfg["tw_side_bars"])
    if c > vw[i] and slope > 0 and above >= need and move >= cfg["tw_min_day_move_pct"]:
        return 1
    if c < vw[i] and slope < 0 and (12 - above) >= need and move <= -cfg["tw_min_day_move_pct"]:
        return -1
    return 0


def strong(ind: pd.DataFrame, i: int, want: int, cfg: dict) -> bool:
    o, h, lo, c = (float(ind[k].iloc[i]) for k in ("Open", "High", "Low", "Close"))
    rng = h - lo
    if rng <= 0:
        return False
    if (c - o) * want <= 0 or abs(c - o) / rng * 100 < cfg["tw_min_body_pct"]:
        return False
    zone = cfg["tw_close_zone_pct"] / 100
    return (c >= h - zone * rng) if want > 0 else (c <= lo + zone * rng)


def signal(ind: pd.DataFrame, i: int, cfg: dict) -> tuple[str, float, list[str]] | None:
    """('call'|'put', stop price on the share, reasons) when candle i is an entry, else None."""
    cfg = {**DEFAULTS, **cfg}
    t = ind.index[i]
    mins = t.hour * 60 + t.minute + 5  # the candle has finished 5 minutes after its start
    if not ny_minutes(cfg["tw_first_entry"]) <= mins <= ny_minutes(cfg["tw_last_entry"]):
        return None
    want = trend_state(ind, i, cfg)
    if not want or not strong(ind, i, want, cfg):
        return None
    atr = float(ind["atr"].iloc[i]) if np.isfinite(ind["atr"].iloc[i]) else 0.0
    if atr <= 0:
        return None
    c = float(ind["Close"].iloc[i])
    lo3, hi3 = float(ind["Low"].iloc[i - 2:i + 1].min()), float(ind["High"].iloc[i - 2:i + 1].max())
    ema = float(ind["ema"].iloc[i])
    vw = float(ind["vwap"].iloc[i])
    why = []
    if want > 0:
        touched = min(abs(lo3 - ema), abs(lo3 - vw)) <= cfg["tw_pullback_atr"] * atr or lo3 <= ema
        prev_hi = float(ind["High"].iloc[max(0, i - cfg["tw_breakout_bars"]):i].max())
        if touched and c > float(ind["High"].iloc[i - 1]):
            why.append("pullback to the 20 EMA/VWAP held, strong green candle closed above the last one")
        elif c > prev_hi:
            why.append("trend continuation: strong green candle at a new 1-hour high")
        stop = lo3 - 0.1 * atr
    else:
        touched = min(abs(hi3 - ema), abs(hi3 - vw)) <= cfg["tw_pullback_atr"] * atr or hi3 >= ema
        prev_lo = float(ind["Low"].iloc[max(0, i - cfg["tw_breakout_bars"]):i].min())
        if touched and c < float(ind["Low"].iloc[i - 1]):
            why.append("pullback to the 20 EMA/VWAP failed, strong red candle closed below the last one")
        elif c < prev_lo:
            why.append("trend continuation: strong red candle at a new 1-hour low")
        stop = hi3 + 0.1 * atr
    if not why:
        return None
    risk = abs(c - stop)
    if risk > cfg["tw_max_risk_atr"] * atr or risk < c * 0.0008:
        return None
    side = "call" if want > 0 else "put"
    if cfg.get("tw_chart_min") is not None:
        rd = candles.read(ind, i, side, risk, {"target_r": cfg["tw_target_r"], "chart_veto_room": False,
                                                "chart_veto_structure": True, "chart_min_score": cfg["tw_chart_min"]})
        if not rd["ok"]:
            return None
        why.append(rd["summary"])
    why.insert(0, f"trend day {'up' if want > 0 else 'down'} (price {'above a rising' if want > 0 else 'below a falling'} VWAP)")
    return side, stop, why


def floor_r(best_r: float, cfg: dict) -> float | None:
    f = None
    if best_r >= cfg["tw_be_after_r"]:
        f = cfg["tw_be_lock_r"]
    if best_r >= cfg["tw_trail_after_r"]:
        f = max(f or 0.0, best_r - cfg["tw_trail_gap_r"])
    return f


# ---------------------------------------------------------------------------
# Backtest with REAL option prices
# ---------------------------------------------------------------------------


class RealOptions:
    """Real 1-minute prices of QQQ option contracts from Alpaca, fetched per day and cached on disk."""

    def __init__(self, cache: Path):
        from alpaca.data.historical import OptionHistoricalDataClient

        self.cli = OptionHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.mem: dict = {}

    def day(self, sym: str, day: pd.Timestamp, expiry: pd.Timestamp, side: str, strikes: list[float]) -> dict:
        key = f"{sym}_{day:%Y%m%d}_{expiry:%y%m%d}_{side}_{int(min(strikes))}_{int(max(strikes))}"
        if key in self.mem:
            return self.mem[key]
        f = self.cache / f"{key}.pkl"
        if f.exists():
            self.mem[key] = pd.read_pickle(f)
            return self.mem[key]
        from alpaca.data.requests import OptionBarsRequest
        from alpaca.data.timeframe import TimeFrame

        names = {f"{sym}{expiry:%y%m%d}{'C' if side == 'call' else 'P'}{int(round(k * 1000)):08d}": k for k in strikes}
        out = {}
        try:
            df = self.cli.get_option_bars(OptionBarsRequest(
                symbol_or_symbols=list(names), timeframe=TimeFrame.Minute,
                start=(day + pd.Timedelta(hours=9, minutes=30)).tz_convert("UTC").to_pydatetime(),
                end=(day + pd.Timedelta(hours=16)).tz_convert("UTC").to_pydatetime())).df
            if df is not None and len(df):
                for name in df.index.get_level_values(0).unique():
                    d = df.xs(name, level=0)
                    d.index = pd.DatetimeIndex(d.index).tz_convert(NY)
                    out[names[name]] = d["close"].astype(float)
        except Exception as exc:
            print(f"option bars {key}: {type(exc).__name__}: {str(exc)[:120]}")
        pd.to_pickle(out, f)
        self.mem[key] = out
        return out


def price_at(s: pd.Series | None, t: pd.Timestamp, stale: int = 5) -> float | None:
    if s is None or s.empty:
        return None
    w = s[(s.index <= t) & (s.index > t - pd.Timedelta(minutes=stale + 1))]
    return float(w.iloc[-1]) if len(w) else None


def backtest(bars: pd.DataFrame, cfg: dict, real: RealOptions, only_day: str | None = None, verbose: bool = False) -> list[dict]:
    """bars: QQQ 1-minute bars (any hours, NY time). Returns closed trades with real-option P&L in dollars."""
    import scalper

    cfg = {**DEFAULTS, **cfg}
    acct = float(cfg.get("account_size", 1000)) / 0.75
    risk_cash = acct * float(cfg.get("risk_per_trade_pct", 10)) / 100
    max_spend = acct * float(cfg.get("max_premium_pct", 35)) / 100
    fee = 0.03
    rth = bars.between_time("09:30", "15:59")
    days = sorted(set(rth.index.normalize()))
    trades = []
    for di, day in enumerate(days):
        if only_day and day.strftime("%Y-%m-%d") != only_day:
            continue
        d1 = rth[(rth.index >= day) & (rth.index < day + pd.Timedelta(days=1))]
        if len(d1) < 300:
            continue
        dte = int(cfg["tw_dte"])
        if dte and di + dte >= len(days):
            continue
        expiry = days[di + dte] if dte else day
        s5 = scalper.to_bars(d1, 5)
        ind = scalper.session_indicators(s5, {**scalper.DEFAULTS, "signal_minutes": 5, **cfg})
        open_t, last_exit, n_tr, n_loss = None, None, 0, 0
        for i in range(12, len(ind)):
            now = ind.index[i] + pd.Timedelta(minutes=5)
            if open_t is not None or n_tr >= cfg["tw_max_trades"] or n_loss >= cfg["tw_max_losses"]:
                pass
            elif last_exit is None or (now - last_exit).total_seconds() / 60 >= cfg["tw_cooldown_minutes"]:
                sig = signal(ind, i, cfg)
                if sig:
                    side, stop, why = sig
                    u0 = float(d1["Open"].get(now, np.nan)) if now in d1.index else float(ind["Close"].iloc[i])
                    atm = round(u0)
                    step = 1 if side == "call" else -1
                    strikes = [float(atm + step * k) for k in range(-1, 5)]
                    opts = real.day("QQQ", day, expiry, side, strikes)
                    pick = None
                    for k in [float(atm + step * j) for j in range(0, 5)]:  # nearest first, then cheaper (out of the money)
                        px = price_at(opts.get(k), now - pd.Timedelta(minutes=1))  # last real price before entry
                        if px is None or px < 0.10:
                            continue
                        fill = px * 1.01 + 0.01  # pay into the spread
                        qty = int(min(risk_cash / (fill * 100 * cfg["tw_option_stop_pct"] / 100), max_spend / (fill * 100)))
                        if qty >= 1:
                            pick = (k, fill, qty)
                            break
                    if pick:
                        k, fill, qty = pick
                        open_t = {"day": day.strftime("%Y-%m-%d"), "t": now, "side": side, "K": k, "qty": qty, "fill": fill,
                                  "u_entry": float(ind["Close"].iloc[i]), "u_risk": abs(float(ind["Close"].iloc[i]) - stop),
                                  "best_r": 0.0, "why": "; ".join(why)[:160], "series": opts.get(k)}
                        n_tr += 1
                        if verbose:
                            print(f"  {now:%H:%M} BUY {qty} {side} {k:g} @ {fill:.2f} · {why[1] if len(why) > 1 else why[0]}")
            if open_t is None:
                continue
            # manage on every 1-minute bar of the next 5 minutes (or to the end of the day)
            end = ind.index[i + 1] + pd.Timedelta(minutes=5) if i + 1 < len(ind) else now + pd.Timedelta(minutes=60)
            for m in d1.index[(d1.index >= now) & (d1.index < end)]:
                t_now = m + pd.Timedelta(minutes=1)
                t = open_t
                S = float(d1.at[m, "Close"])
                want = 1 if t["side"] == "call" else -1
                u_r = (S - t["u_entry"]) * want / t["u_risk"]
                t["best_r"] = max(t["best_r"], u_r)
                px = price_at(t["series"], m)
                fl = floor_r(t["best_r"], cfg)
                reason = None
                if t_now.hour * 60 + t_now.minute >= ny_minutes(cfg.get("flat_by", "15:50")):
                    reason = "end of day"
                elif u_r >= cfg["tw_target_r"]:
                    reason = "target"
                elif u_r <= -1:
                    reason = "stop (share)"
                elif fl is not None and u_r <= fl:
                    reason = "trail" if t["best_r"] >= cfg["tw_trail_after_r"] else "break-even lock"
                elif px is not None and px <= t["fill"] * (1 - cfg["tw_option_stop_pct"] / 100):
                    reason = "stop (option)"
                if reason:
                    exit_px = px if px is not None else price_at(t["series"], m, stale=30)
                    if exit_px is None:
                        exit_px = t["fill"]  # no real price at all: count it as flat rather than guess
                    sell = max(0.01, exit_px * 0.99 - 0.01)
                    pnl = (sell - t["fill"]) * 100 * t["qty"] - 2 * fee * t["qty"]
                    t.update(exit_t=t_now, exit=sell, reason=reason, pnl=pnl, u_exit=S)
                    t.pop("series", None)
                    trades.append(t)
                    if verbose:
                        print(f"  {t_now:%H:%M} SELL @ {sell:.2f} ({reason}) {'+' if pnl >= 0 else ''}${pnl:,.0f}")
                    open_t, last_exit = None, t_now
                    if pnl < 0:
                        n_loss += 1
                    break
    return trades


def report(name: str, t: pd.DataFrame, gbp: float = 0.75) -> None:
    if t.empty:
        print(f"{name}: no trades")
        return
    w, lo = t[t.pnl > 0], t[t.pnl <= 0]
    pf = w.pnl.sum() / -lo.pnl.sum() if lo.pnl.sum() < 0 else float("inf")
    days = t.groupby("day")["pnl"].sum() * gbp
    eq = days.cumsum()
    print(f"{name}: {len(t)} trades on {len(days)} days, {len(w) / len(t):.0%} won, avg win £{w.pnl.mean() * gbp if len(w) else 0:.0f}, "
          f"avg loss £{lo.pnl.mean() * gbp if len(lo) else 0:.0f}, profit factor {pf:.2f}, total £{t.pnl.sum() * gbp:,.0f}")
    print(f"    per trading day it traded: average £{days.mean():+.0f}, median £{days.median():+.0f}, "
          f"{(days > 0).mean():.0%} of days up, days ≥ £50: {(days >= 50).mean():.0%}, best £{days.max():.0f}, "
          f"worst £{days.min():.0f}, deepest fall £{(eq - eq.cummax()).min():.0f}")


def main() -> int:
    import optionbt

    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-03-01")
    ap.add_argument("--end", default=pd.Timestamp.now(tz=NY).strftime("%Y-%m-%d"))
    ap.add_argument("--day", default="2026-11-09")
    ap.add_argument("--cache", default="/tmp/tw_cache")
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    bars = optionbt.load_bars(["QQQ"], a.start, a.end, cache / "qqq.pkl")["QQQ"]
    real = RealOptions(cache / "options")
    base = {"account_size": 1000, "risk_per_trade_pct": 10, "max_premium_pct": 35, "flat_by": "15:50"}
    print(f"\n=== Replay of {a.day} (default settings, real option prices) ===")
    rep = backtest(bars, base, real, only_day=a.day, verbose=True)
    report("that day", pd.DataFrame(rep))
    variants = [
        ("default (0DTE, target 2R, trail 1.5R, chart read >= -1)", {}),
        ("no candle read", {"tw_chart_min": None}),
        ("candle read >= 0", {"tw_chart_min": 0}),
        ("target 3R", {"tw_target_r": 3.0}),
        ("target 1.5R", {"tw_target_r": 1.5}),
        ("no target (trail only)", {"tw_target_r": 99}),
        ("1DTE", {"tw_dte": 1}),
        ("bigger day move needed (0.6%)", {"tw_min_day_move_pct": 0.6}),
        ("entries until 12:00 only", {"tw_last_entry": "12:00"}),
    ]
    rows = []
    for name, over in variants:
        t = pd.DataFrame(backtest(bars, {**base, **over}, real))
        print(f"\n=== {name} ===")
        if t.empty:
            print("no trades")
            continue
        report("ALL", t)
        report("  2024-25 (choose)", t[t.day < "2026-01-01"])
        report("  2026 (check, unseen)", t[t.day >= "2026-01-01"])
        rows.append(t.assign(variant=name))
    if rows:
        allt = pd.concat(rows)
        allt.drop(columns=["series"], errors="ignore").to_csv("trendworker_trades.csv", index=False)
        d = allt[allt.variant == variants[0][0]]
        if len(d):
            print("\nDefault by exit reason:")
            for r, g in d.groupby("reason"):
                print(f"  {r}: {len(g)} trades, avg ${g.pnl.mean():+.0f}, total £{g.pnl.sum() * 0.75:,.0f}")
            print("\nDefault by month:")
            for mth, g in d.groupby(d.day.str[:7]):
                print(f"  {mth}: {len(g)} trades, £{g.pnl.sum() * 0.75:+,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
