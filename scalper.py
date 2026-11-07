#!/usr/bin/env python3
"""
0DTE Scalper (paper trading only)
=================================
A day-trading bot in the style of the "Scalp City" video: it watches SPY, QQQ and IWM on
1-minute bars and buys same-day-expiry (0DTE) call or put options on three triggers:

  1. a candle closes across VWAP
  2. a candle closes across the 50-period EMA
  3. price breaks out of the first 15 minutes' range (opening range breakout)

Closing above means a call, closing below means a put. Each symbol is a "worker".
It trades on an Alpaca PAPER account only: no real money can be touched.

  python scalper.py run          trade the session on paper (leave it running from the US open)
  python scalper.py check        test the Alpaca keys, market clock and an option quote
  python scalper.py backtest     test the triggers on recent 1-minute prices (the share price, not options)
  python scalper.py report       today's paper trades

Needs ALPACA_KEY and ALPACA_SECRET (paper keys) as environment variables or in config.toml.
Education and tooling only, not financial advice. 0DTE options can lose 100% in minutes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import bot  # reuses Telegram, settings loading and the event calendar
import candles  # reads every candle, its wicks, the highs and lows and the wick levels
import charts  # chart pictures for Telegram
import intraday  # the 5-minute trend reading shared with "bot.py pulse"
import lessons  # the trade journal that learns
import trump  # reads Trump's posts for market-moving topics

BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
NY = "America/New_York"

DEFAULTS = {
    "enabled": True,
    "symbols": ["SPY", "QQQ", "IWM"],
    "account_size": 5000.0,           # sizing is based on this, not Alpaca's $100k paper balance
    "account_currency": "USD",        # the currency account_size is in; messages show money in it too
    "hod_after": "10:30",             # the "hod" trigger (new high/low of the day) only counts from this time
    "chart_read": False,              # read the candles, wicks, highs/lows and wick levels before each trade
    "chart_min_score": 0,
    "use_trump": True,                # don't trade against a fresh market-moving Trump post
    "trump_minutes": 60,              # ...for this long after it
    "account_start": "",              # YYYY-MM-DD: from this day the account grows and shrinks with the scalper's results
    "risk_per_trade_pct": 1.0,        # loss if the option's stop is hit
    "max_premium_pct": 10.0,          # never spend more than this % of the account on one trade
    "opening_range_minutes": 15,
    "ema_length": 50,
    "require_confluence": True,       # a call needs price above VWAP AND the 50 EMA (puts: below both)
    "triggers": ["vwap", "ema50", "orb"],
    "first_entry": "09:45",           # New York time
    "last_entry": "15:00",
    "flat_by": "15:50",
    "stop_loss_pct": 30.0,            # exit if the option falls 30%
    "take_profit_pct": 50.0,          # exit if it rises 50%
    "trail_after_pct": 25.0,          # once up 25%, a trailing stop follows the best price
    "trail_giveback_pct": 15.0,       # ...and exits if it falls 15% from that best price
    "max_hold_minutes": 30,
    "exit_on_reverse_cross": True,    # exit a call if price closes back below VWAP (puts: above)
    "max_trades_per_day": 6,
    "max_open_positions": 2,
    "daily_loss_limit_pct": 2.0,      # no new trades after losing 2% of account_size today
    "cooldown_minutes": 10,           # per worker, after any exit
    "max_spread_pct": 10.0,           # skip options whose bid/ask gap is over 10% of the price
    "event_blackout_minutes": 30,     # no entries 30 min either side of a big scheduled event
    "signal_minutes": 5,              # judge the triggers on 5-minute bars (1 = the old, twitchy 1-minute version)
    "ema_length_5m": 20,              # the EMA trigger's length on 5-minute bars (20 x 5 min = 100 minutes)
    "trend_filter": True,
    "candle_filter": True,            # only strong candles in the trade's direction, and no chasing stretched moves
    "min_body_pct": 50,
    "close_zone_pct": 30,
    "max_chase_atr": 1.5,             # calls only when the 5-min/1-hour trend is UP, puts only when it's DOWN, nothing when choppy
    "max_losses_per_worker": 2,       # a worker stops for the day after this many losing trades
    "loss_cooldown_minutes": 30,      # and waits this long after any loss (the normal cooldown applies after a win)
    "entry_offset_pct": 25,           # buy at mid + 25% of the way to the ask (0 = mid, 100 = the ask)
    "poll_seconds": 15,
    "max_runtime_minutes": 350,       # stops itself before GitHub's 6-hour job limit
}


def load_cfg(path: str) -> tuple[dict, dict]:
    full = bot.load_config(path)
    raw = {}
    p = Path(path)
    if p.exists():
        with open(p, "rb") as fh:
            raw = tomllib.load(fh).get("scalper", {})
    cfg = dict(DEFAULTS, **raw)
    cfg["key"] = os.environ.get("ALPACA_KEY") or raw.get("alpaca_key", "")
    cfg["secret"] = os.environ.get("ALPACA_SECRET") or raw.get("alpaca_secret", "")
    return cfg, full


def say(full: dict, text: str, args) -> None:
    bot.send_telegram(full, text, args)


def picture(full: dict, bars: dict, sym: str, caption: str, args, level: float | None = None) -> None:
    """A 5-minute chart of the share (the option follows it) at the moment of the trade."""
    try:
        df = to_bars(bars.get(sym, pd.DataFrame()), 5)
        if len(df) < 3:
            return
        ind = session_indicators(df, {**DEFAULTS, "signal_minutes": 5})
        png = charts.intraday_chart(ind.rename(columns={"ema": "ema21"}), bot.to_plain(caption)[:90], entry=level)
        bot.send_photo(full, png, caption, args, bot.chart_url(sym, 1))
    except Exception as exc:
        print(f"chart: {exc}")


# ---------------------------------------------------------------------------
# Indicators on 1-minute bars (one session)
# ---------------------------------------------------------------------------


def bar_minutes(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 1
    return max(1, int(round(pd.Series(df.index).diff().dropna().median().total_seconds() / 60)))


def ema_len(cfg: dict) -> int:
    return int(cfg["ema_length_5m"]) if int(cfg.get("signal_minutes", 1)) > 1 else int(cfg["ema_length"])


def to_bars(df1: pd.DataFrame, minutes: int, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """1-minute bars to finished N-minute bars (a 10:30 bar covers 10:30-10:34 and is done at 10:35)."""
    if minutes <= 1 or df1.empty:
        return df1
    out = df1.resample(f"{minutes}min", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    if now is not None:
        out = out[out.index + pd.Timedelta(minutes=minutes) <= now]
    return out


def trend_now(history5: pd.DataFrame | None, today5: pd.DataFrame, sym: str) -> tuple[str, str]:
    """(direction, kind) from the shared 5-minute reading: ('up'|'down'|'none', 'trend'|'range'|'mixed')."""
    frames = [f for f in (history5, today5) if f is not None and len(f)]
    if not frames:
        return "none", "mixed"
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    spec = intraday.spec_for(sym)
    ind = intraday.add_intraday(intraday.prepare(df, spec), spec)
    if not len(ind):
        return "none", "mixed"
    return str(ind["direction"].iat[-1]), str(ind["kind"].iat[-1])


def trend_allows(side: str, direction: str, kind: str) -> bool:
    if kind == "range":
        return False  # choppy: VWAP and EMA crosses mostly whipsaw
    return direction == ("up" if side == "call" else "down")


def session_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """df: one session's 1- or 5-minute bars, index in New York time, columns Open High Low Close Volume."""
    out = df.copy()
    tp = (out["High"] + out["Low"] + out["Close"]) / 3.0
    vol = out["Volume"].clip(lower=0)
    cum_v = vol.cumsum()
    out["vwap"] = np.where(cum_v > 0, (tp * vol).cumsum() / cum_v.replace(0, np.nan), tp.expanding().mean())
    out["ema"] = out["Close"].ewm(span=ema_len(cfg), adjust=False).mean()
    pc = out["Close"].shift(1)
    tr = pd.concat([out["High"] - out["Low"], (out["High"] - pc).abs(), (out["Low"] - pc).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=3).mean()
    n = int(cfg["opening_range_minutes"])
    start = out.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
    in_or = (out.index >= start) & (out.index < start + pd.Timedelta(minutes=n))
    if in_or.sum() >= max(2, n // bar_minutes(out) // 2):
        out["or_high"] = out.loc[in_or, "High"].max()
        out["or_low"] = out.loc[in_or, "Low"].min()
    else:
        out["or_high"] = np.nan
        out["or_low"] = np.nan
    out["or_done"] = out.index >= start + pd.Timedelta(minutes=n)
    return out


def signal_at(ind: pd.DataFrame, i: int, cfg: dict, orb_used: set, stats: dict | None = None) -> tuple[str, list[str]] | None:
    """Returns ('call'|'put', [triggers]) if bar i closes across a line, else None."""
    if i < 1:
        return None
    c, pc = ind["Close"].iloc[i], ind["Close"].iloc[i - 1]
    vw, pvw = ind["vwap"].iloc[i], ind["vwap"].iloc[i - 1]
    em, pem = ind["ema"].iloc[i], ind["ema"].iloc[i - 1]
    fired = {"call": [], "put": []}
    trig = set(cfg["triggers"])
    if "vwap" in trig:
        if pc <= pvw and c > vw:
            fired["call"].append("closed above VWAP")
        if pc >= pvw and c < vw:
            fired["put"].append("closed below VWAP")
    if "ema50" in trig and i >= min(ema_len(cfg) // 2, 10):
        if pc <= pem and c > em:
            fired["call"].append(f"closed above the {ema_len(cfg)} EMA")
        if pc >= pem and c < em:
            fired["put"].append(f"closed below the {ema_len(cfg)} EMA")
    if "hod" in trig and i >= 3:
        # trend days never cross back over VWAP: buy the next new high of the day (sell the next new low)
        t = ind.index[i]
        after = cfg.get("hod_after", "10:00")
        if t.hour * 60 + t.minute >= ny_time(after)[0] * 60 + ny_time(after)[1]:
            prior_hi, prior_lo = float(ind["High"].iloc[:i].max()), float(ind["Low"].iloc[:i].min())
            if c > prior_hi and pc <= prior_hi:
                fired["call"].append("made a new high for the day")
            if c < prior_lo and pc >= prior_lo:
                fired["put"].append("made a new low for the day")
    if "ema_bounce" in trig and i >= 10:
        # a dip to the EMA that holds, in a market already above it (or a bounce up to it that fails, below)
        atr = float(ind["atr"].iloc[i]) if np.isfinite(ind["atr"].iloc[i]) else 0.0
        lo2 = min(float(ind["Low"].iloc[i]), float(ind["Low"].iloc[i - 1]))
        hi2 = max(float(ind["High"].iloc[i]), float(ind["High"].iloc[i - 1]))
        if pc > pem and c > em and lo2 <= em + 0.1 * atr:
            fired["call"].append(f"dipped to the {ema_len(cfg)} EMA and held")
        if pc < pem and c < em and hi2 >= em - 0.1 * atr:
            fired["put"].append(f"bounced up to the {ema_len(cfg)} EMA and failed")
    if "orb" in trig and bool(ind["or_done"].iloc[i]) and np.isfinite(ind["or_high"].iloc[i]):
        hi, lo = ind["or_high"].iloc[i], ind["or_low"].iloc[i]
        if c > hi and pc <= hi and "call" not in orb_used:
            fired["call"].append("broke out above the opening range")
        if c < lo and pc >= lo and "put" not in orb_used:
            fired["put"].append("broke down below the opening range")
    for side in ("call", "put"):
        if not fired[side]:
            continue
        if cfg["require_confluence"]:
            ok = (c > vw and c > em) if side == "call" else (c < vw and c < em)
            if not ok:
                continue
        if cfg.get("day_agree"):
            # never buy calls while the share is down on the day (or puts while it's up)
            day_open = float(ind["Open"].iloc[0])
            if (side == "call" and c <= day_open) or (side == "put" and c >= day_open):
                if stats is not None:
                    stats["day"] = stats.get("day", 0) + 1
                continue
        if cfg.get("candle_filter", False) and not candle_ok(ind, i, side, cfg):
            if stats is not None:
                stats["candle"] = stats.get("candle", 0) + 1
            continue
        if cfg.get("chart_read", False):
            rd = candles.read(ind, i, side, max(abs(c - vw), c * 0.0015), cfg)
            if not rd["ok"]:
                if stats is not None:
                    stats["chart"] = stats.get("chart", 0) + 1
                    stats.setdefault("chart_why", []).append(
                        f"{ind.index[i]:%H:%M} {side}: " + (rd["veto"] or f"chart read only {rd['score']:+d}"))
                    stats["chart_why"] = stats["chart_why"][-20:]
                continue
            return side, fired[side] + [rd["summary"]]
        return side, fired[side]
    return None


def candle_ok(ind: pd.DataFrame, i: int, side: str, cfg: dict) -> bool:
    """Reads the candle itself, like a trader would. The signal candle must be a strong one in the trade's
    direction (a real body, closing near its high for a call or its low for a put: no long wick against it),
    and price must not already be stretched far from VWAP (no chasing a move that's already happened)."""
    o, h, l, c = (float(ind[k].iloc[i]) for k in ("Open", "High", "Low", "Close"))
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o) / rng * 100
    if body < float(cfg.get("min_body_pct", 50)):
        return False  # a doji or spinning top: indecision, not a breakout
    zone = float(cfg.get("close_zone_pct", 30)) / 100
    if side == "call" and (c <= o or c < h - zone * rng):
        return False  # red candle, or a long upper wick: sellers pushed it back down
    if side == "put" and (c >= o or c > l + zone * rng):
        return False
    atr = float(ind["atr"].iloc[i]) if "atr" in ind and np.isfinite(ind["atr"].iloc[i]) else 0.0
    if atr > 0 and abs(c - float(ind["vwap"].iloc[i])) > float(cfg.get("max_chase_atr", 1.5)) * atr:
        return False  # already stretched far from VWAP: the move has mostly happened
    return True


def ny_time(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def in_window(ts: pd.Timestamp, cfg: dict) -> bool:
    fh, fm = ny_time(cfg["first_entry"])
    lh, lm = ny_time(cfg["last_entry"])
    t = ts.hour * 60 + ts.minute
    return fh * 60 + fm <= t <= lh * 60 + lm


# ---------------------------------------------------------------------------
# Backtest on the share price (free 1-minute data from Yahoo, about the last month)
# ---------------------------------------------------------------------------


def cmd_backtest(cfg: dict, full: dict, args) -> int:
    import yfinance as yf

    frames_by_sym: dict[str, pd.DataFrame] = {}
    for sym in cfg["symbols"]:
        frames = []
        end = pd.Timestamp.now(tz="UTC")
        for k in range(4):  # Yahoo serves 1-minute bars in 8-day chunks, about 30 days back
            s, e = end - pd.Timedelta(days=7 * (k + 1)), end - pd.Timedelta(days=7 * k)
            try:
                d = yf.Ticker(sym).history(start=s, end=e, interval="1m", prepost=False, auto_adjust=False)
                if d is not None and len(d):
                    frames.append(d)
            except Exception as exc:
                print(f"{sym}: {exc}")
        if not frames:
            continue
        df = pd.concat(frames).sort_index()
        df = df[~df.index.duplicated()]
        df.index = df.index.tz_convert(NY)
        frames_by_sym[sym] = df
    if not frames_by_sym:
        print("No 1-minute data could be downloaded.")
        return 1
    old = dict(cfg, signal_minutes=1, trend_filter=False, candle_filter=False)
    print("\n=== OLD RULES: 1-minute triggers, no trend filter ===")
    report_backtest([r for sym, df in frames_by_sym.items() for r in backtest_frame(sym, df, old)], old, save=False)
    mid = dict(cfg, candle_filter=False)
    print(f"\n=== {cfg['signal_minutes']}-minute triggers + trend filter, NO candle check ===")
    report_backtest([r for sym, df in frames_by_sym.items() for r in backtest_frame(sym, df, mid)], mid, save=False)
    print(f"\n=== CURRENT RULES: {cfg['signal_minutes']}-minute triggers, trend filter {'on' if cfg['trend_filter'] else 'off'}, "
          f"candle check {'on' if cfg.get('candle_filter') else 'off'} ===")
    return report_backtest([r for sym, df in frames_by_sym.items() for r in backtest_frame(sym, df, cfg)], cfg)


def profit_floor(best_r: float, cfg: dict) -> float | None:
    """Once a trade has been well in profit, the least it may give back to: break-even after be_after_r, then
    trailing trail_gap_r behind its best after trail_after_r. None = no floor yet (only the normal stop)."""
    if not cfg.get("lock_profits"):
        return None
    floor = None
    if best_r >= float(cfg.get("be_after_r", 0.5)):
        floor = float(cfg.get("be_lock_r", 0.05))
    if best_r >= float(cfg.get("trail_after_r", 1.0)):
        floor = max(floor or 0.0, best_r - float(cfg.get("trail_gap_r", 0.4)))
    return floor


def backtest_frame(sym: str, df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Simulates the triggers on the share price. Risk = distance to VWAP or 0.15%, whichever is bigger;
    exits on the reverse cross, the time stop or the close. Results in R (multiples of that risk)."""
    trades = []
    mins = int(cfg.get("signal_minutes", 1))
    trend = None
    if cfg.get("trend_filter"):
        spec = intraday.spec_for(sym)
        d5 = to_bars(df.between_time("09:30", "15:59")[["Open", "High", "Low", "Close", "Volume"]], 5)
        t5 = intraday.add_intraday(intraday.prepare(d5, spec), spec)
        trend = t5[["direction", "kind"]]
        trend.index = trend.index + pd.Timedelta(minutes=5)  # known once the 5-minute bar has finished
    for day, sess in df.groupby(df.index.date):
        sess = sess.between_time("09:30", "15:59")
        if len(sess) < 120:
            continue
        sess = to_bars(sess[["Open", "High", "Low", "Close", "Volume"]], mins)
        ind = session_indicators(sess, cfg)
        orb_used: set = set()
        pos = None
        last_exit = None
        n_today = 0
        fh, fm = ny_time(cfg["flat_by"])
        for i in range(1, len(ind) - 1):
            ts = ind.index[i]
            c = float(ind["Close"].iloc[i])
            if pos:
                long = pos["side"] == "call"
                if cfg.get("lock_profits"):
                    h, lo_ = float(ind["High"].iloc[i]), float(ind["Low"].iloc[i])
                    fav = ((h - pos["entry"]) if long else (pos["entry"] - lo_)) / pos["risk"]
                    adv = ((lo_ - pos["entry"]) if long else (pos["entry"] - h)) / pos["risk"]
                    floor = profit_floor(pos.get("best", 0.0), cfg)
                    tgt = float(cfg.get("target_r", 2.0))
                    hit = None
                    if floor is not None and adv <= floor:
                        o = float(ind["Open"].iloc[i])
                        o_r = ((o - pos["entry"]) if long else (pos["entry"] - o)) / pos["risk"]
                        hit = (min(floor, o_r), "locked profit" if floor > 0 else "break-even")
                    elif fav >= tgt:
                        hit = (tgt, "target")
                    pos["best"] = max(pos.get("best", 0.0), fav)
                    if hit:
                        pos["r"], pos["exit"] = hit
                        trades.append(pos)
                        pos, last_exit = None, ts
                        continue
                move = (c - pos["entry"]) if long else (pos["entry"] - c)
                r = move / pos["risk"]
                reverse = cfg["exit_on_reverse_cross"] and ((long and c < ind["vwap"].iloc[i]) or ((not long) and c > ind["vwap"].iloc[i]))
                timeout = (ts - pos["t"]).total_seconds() / 60 >= int(cfg["max_hold_minutes"])
                late = ts.hour * 60 + ts.minute >= fh * 60 + fm
                if r <= -1 or r >= float(cfg.get("target_r", 2.0)) or reverse or timeout or late:
                    exit_px = float(ind["Open"].iloc[i + 1])
                    move = (exit_px - pos["entry"]) if long else (pos["entry"] - exit_px)
                    pos["r"] = max(-1.5, move / pos["risk"])
                    pos["exit"] = "stop" if r <= -1 else "target" if r >= 2 else "reverse" if reverse else "time" if timeout else "close"
                    trades.append(pos)
                    pos, last_exit = None, ts
                continue
            if n_today >= int(cfg["max_trades_per_day"]) or not in_window(ts, cfg):
                continue
            if last_exit is not None and (ts - last_exit).total_seconds() / 60 < int(cfg["cooldown_minutes"]):
                continue
            sig = signal_at(ind, i, cfg, orb_used)
            if not sig:
                continue
            side, why = sig
            if trend is not None:
                known = trend[trend.index <= ts + pd.Timedelta(minutes=mins)]
                if not len(known) or not trend_allows(side, known["direction"].iat[-1], known["kind"].iat[-1]):
                    continue
            if any("opening range" in w for w in why):
                orb_used.add(side)
            entry = float(ind["Open"].iloc[i + 1])
            risk = max(abs(entry - float(ind["vwap"].iloc[i])), entry * 0.0015)
            tk = ("up" if side == "call" else "down", "trend")
            if trend is not None:
                known = trend[trend.index <= ts + pd.Timedelta(minutes=mins)]
                tk = (known["direction"].iat[-1], known["kind"].iat[-1])
            pos = {"sym": sym, "day": str(day), "t": ts, "side": side, "entry": entry, "risk": risk, "why": "; ".join(why),
                   "conds": scalp_conditions(ind, i, why, *tk)}
            n_today += 1
    return trades


def report_backtest(rows: list[dict], cfg: dict, save: bool = True) -> int:
    if not rows:
        print("No trades (or no 1-minute data could be downloaded).")
        return 1
    df = pd.DataFrame(rows)
    print(f"\nBacktest on the SHARE PRICE, {df['day'].nunique()} days, {len(df)} trades "
          f"({', '.join(sorted(df['sym'].unique()))}). Not option prices: see the note below.\n")
    def line(name, r):
        r = np.asarray(r, float)
        if not len(r):
            return f"{name:<26} 0 trades"
        return (f"{name:<26} {len(r):>4} trades  {np.mean(r > 0):>4.0%} won  "
                f"avg {r.mean():+.2f}R  total {r.sum():+.1f}R")
    print(line("All", df["r"]))
    for side in ("call", "put"):
        print(line(f"  {side}s", df.loc[df["side"] == side, "r"]))
    for trig in ("VWAP", "EMA", "opening range"):
        print(line(f"  with {trig}", df.loc[df["why"].str.contains(trig), "r"]))
    for sym in sorted(df["sym"].unique()):
        print(line(f"  {sym}", df.loc[df["sym"] == sym, "r"]))
    days = df.groupby("day")["r"].sum()
    print(f"\nWinning days: {(days > 0).sum()} of {len(days)}. Best day {days.max():+.1f}R, worst {days.min():+.1f}R.")
    print("1R here = the share's distance to VWAP at entry. An option moves several times more than the share, both")
    print("ways, and loses value every minute (time decay), so option results swing far more than this.")
    print("A month of 1-minute data is a small sample: treat this as a sanity check, not proof.")
    if save:
        STATE.mkdir(exist_ok=True)
        df.to_csv(STATE / "scalper_backtest.csv", index=False)
    return 0


# ---------------------------------------------------------------------------
# Live paper trading with Alpaca
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    worker: str
    side: str
    contract: str
    qty: int
    entry_price: float
    entry_time: str
    why: str
    order_id: str = ""
    best: float = 0.0
    exit_price: float = 0.0
    exit_time: str = ""
    exit_reason: str = ""
    pnl: float = 0.0
    status: str = "open"
    u_entry: float = 0.0     # the share's price when the option was bought (for the post-mortem)
    u_stop: float = 0.0      # VWAP then: where the setup is wrong
    conds: str = ""          # JSON: the conditions when it was taken
    reviewed: bool = False   # the 20-minutes-later follow-up has been done
    best_r: float = 0.0      # the share's best move in its favour so far, in R (for locking in profit)
    risk_cash: float = 0.0   # dollars it risked when bought (so results in R stay right when the account size changes)


@dataclass
class Day:
    date: str
    trades: list = field(default_factory=list)
    orb_used: dict = field(default_factory=dict)
    last_exit: dict = field(default_factory=dict)
    seen_bar: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)   # signals seen and what stopped them (for the end-of-day summary)


def day_path(d: str) -> Path:
    return STATE / f"scalper_{d}.json"


def load_day(d: str) -> Day:
    p = day_path(d)
    if p.exists():
        raw = json.loads(p.read_text())
        return Day(date=raw["date"], trades=raw.get("trades", []), orb_used=raw.get("orb_used", {}),
                   last_exit=raw.get("last_exit", {}), seen_bar=raw.get("seen_bar", {}), stats=raw.get("stats", {}))
    return Day(date=d)


def save_day(day: Day) -> None:
    STATE.mkdir(exist_ok=True)
    tmp = day_path(day.date).with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(day), indent=1, default=str))
    tmp.replace(day_path(day.date))


class Alpaca:
    """Thin wrapper over the official alpaca-py SDK, paper account only."""

    def __init__(self, key: str, secret: str):
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient, OptionHistoricalDataClient

        if not key or not secret:
            raise SystemExit("Add your Alpaca PAPER keys: ALPACA_KEY and ALPACA_SECRET (GitHub secrets or environment).")
        self.trading = TradingClient(key, secret, paper=True)  # paper=True is hard-coded: no live trading
        self.stocks = StockHistoricalDataClient(key, secret)
        self.options = OptionHistoricalDataClient(key, secret)

    def clock(self):
        return self.trading.get_clock()

    def bars_today(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed

        now = pd.Timestamp.now(tz=NY)
        start = now.normalize() + pd.Timedelta(hours=9, minutes=30)
        req = StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Minute,
                               start=start.tz_convert("UTC").to_pydatetime(), feed=DataFeed.IEX)
        bs = self.stocks.get_stock_bars(req)
        out = {}
        df = bs.df
        if df is None or df.empty:
            return out
        for sym in symbols:
            if sym not in df.index.get_level_values(0):
                continue
            d = df.xs(sym, level=0).rename(columns=str.title)
            d.index = pd.DatetimeIndex(d.index).tz_convert(NY)
            # only finished bars: a bar stamped 10:31 is complete at 10:32
            d = d[d.index + pd.Timedelta(minutes=1) <= now]
            out[sym] = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
        return out

    def bars_history(self, symbols: list[str], days: int = 7) -> dict[str, pd.DataFrame]:
        """5-minute bars from the last few sessions, for the trend reading (fetched once at the start)."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.enums import DataFeed

        now = pd.Timestamp.now(tz=NY)
        req = StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                               start=(now - pd.Timedelta(days=days)).tz_convert("UTC").to_pydatetime(),
                               end=now.normalize().tz_convert("UTC").to_pydatetime(), feed=DataFeed.IEX)
        df = self.stocks.get_stock_bars(req).df
        out = {}
        if df is None or df.empty:
            return out
        for sym in symbols:
            if sym in df.index.get_level_values(0):
                d = df.xs(sym, level=0).rename(columns=str.title)
                d.index = pd.DatetimeIndex(d.index).tz_convert(NY)
                out[sym] = d[["Open", "High", "Low", "Close", "Volume"]].astype(float)
        return out

    def exit_fill(self, order, fallback: float) -> float:
        """The price the sale actually filled at (falls back to the quote if it can't be read)."""
        if order is None:
            return fallback
        for _ in range(6):
            try:
                o = self.trading.get_order_by_id(order.id)
                if getattr(o, "filled_avg_price", None):
                    return float(o.filled_avg_price)
            except Exception:
                pass
            time.sleep(1)
        return fallback

    def pick_contract(self, sym: str, side: str, price: float):
        from alpaca.trading.requests import GetOptionContractsRequest
        from alpaca.trading.enums import ContractType

        today = pd.Timestamp.now(tz=NY).date()
        req = GetOptionContractsRequest(
            underlying_symbols=[sym], expiration_date=today,
            type=ContractType.CALL if side == "call" else ContractType.PUT,
            strike_price_gte=str(round(price * 0.98, 2)), strike_price_lte=str(round(price * 1.02, 2)), limit=100,
        )
        res = self.trading.get_option_contracts(req)
        cons = [c for c in (res.option_contracts or []) if c.tradable]
        if not cons:
            return None
        # nearest to the money, slightly in the money first
        def dist(c):
            k = float(c.strike_price)
            itm = (k <= price) if side == "call" else (k >= price)
            return (abs(k - price), 0 if itm else 1)
        return sorted(cons, key=dist)[0]

    def quote(self, contract: str):
        from alpaca.data.requests import OptionLatestQuoteRequest
        from alpaca.data.enums import OptionsFeed

        q = self.options.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=contract, feed=OptionsFeed.INDICATIVE))
        q = q.get(contract)
        if not q or not q.ask_price or q.ask_price <= 0:
            return None
        return float(q.bid_price or 0), float(q.ask_price)

    def buy(self, contract: str, qty: int, limit: float):
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        return self.trading.submit_order(LimitOrderRequest(symbol=contract, qty=qty, side=OrderSide.BUY,
                                                           time_in_force=TimeInForce.DAY, limit_price=round(limit, 2)))

    def order(self, oid: str):
        return self.trading.get_order_by_id(oid)

    def cancel(self, oid: str):
        try:
            self.trading.cancel_order_by_id(oid)
        except Exception:
            pass

    def option_positions(self) -> list[tuple[str, int]]:
        """[(contract, qty)] for every option the paper account holds right now."""
        out = []
        for p in self.trading.get_all_positions():
            if "option" in str(getattr(p, "asset_class", "")).lower():
                out.append((str(p.symbol), int(float(p.qty))))
        return out

    def sell_all(self, contract: str):
        try:
            return self.trading.close_position(contract)
        except Exception as exc:
            print(bot.redact(f"close {contract}: {exc}", {}))
            return None


def blackout(full: dict, cfg: dict, now_ny: pd.Timestamp) -> str | None:
    mins = int(cfg["event_blackout_minutes"])
    if mins <= 0:
        return None
    try:
        for ev in bot.upcoming_events(full, 1):
            if not ev.get("has_time") or ev.get("region") != "US":
                continue
            gap = abs((ev["when"].tz_convert(NY) - now_ny).total_seconds()) / 60
            if gap <= mins:
                return bot.event_text(ev)
    except Exception:
        return None
    return None


JOURNAL_FILE = "lessons_scalper.json"


def scalp_conditions(ind: pd.DataFrame, i: int, why: list[str], direction: str, kind: str) -> list[str]:
    ts = ind.index[i]
    o, h, l, c = (float(ind[k].iloc[i]) for k in ("Open", "High", "Low", "Close"))
    body = abs(c - o) / (h - l) * 100 if h > l else 0.0
    trig = "VWAP" if any("VWAP" in w for w in why) else ("EMA" if any("EMA" in w for w in why) else "other")
    return [x for x in (lessons.bucket("hour", ts.hour + ts.minute / 60), f"trigger: {trig}",
                        f"trend: {direction}/{kind}", lessons.bucket("body", body)) if x]


def scalp_record(t: "Trade", cfg: dict) -> dict:
    risk_cash = t.risk_cash or 50.0  # trades before risk_cash was kept were all sized at $50 (1% of 5,000)
    return {"id": f"{t.worker}|{t.entry_time}", "kind": "scalper", "setup": "scalper", "symbol": t.worker,
            "r": t.pnl / risk_cash if risk_cash else 0.0, "conditions": json.loads(t.conds or "[]"),
            "findings": [], "date": t.exit_time[:10]}


def _u_levels(t: "Trade") -> tuple[float, float, bool]:
    long = t.side == "call"
    risk = max(abs(t.u_entry - t.u_stop), t.u_entry * 0.0015)
    return t.u_entry, (t.u_entry - risk if long else t.u_entry + risk), long


def post_mortem(t: "Trade", bars: dict, full: dict, cfg: dict, args, now) -> None:
    """Why this scalper trade won or lost, sent to Telegram and saved to its journal."""
    if not t.u_entry or t.worker not in bars:
        return
    df = bars[t.worker]
    path = df[(df.index >= pd.Timestamp(t.entry_time).floor("min")) & (df.index <= now)]
    if path.empty:
        return
    entry, stop0, long = _u_levels(t)
    diag = lessons.diagnose(entry, stop0, float(path["Close"].iloc[-1]), long, path, t.exit_reason)
    rec = scalp_record(t, cfg)
    if rec["r"] <= 0 and diag["mfe"] >= 1.0:
        diag["findings"].append(("option lagged", f"the share went {diag['mfe']:.1f}R your way but the option still lost: "
                                                  f"time decay, the spread, or the exit ({t.exit_reason}) came too soon"))
    rec["findings"] = [f[0] for f in diag["findings"]]
    j = lessons.load(STATE, JOURNAL_FILE)
    j.setdefault("paper", []).append(rec)
    lessons.save(STATE, j, JOURNAL_FILE)
    conds = json.loads(t.conds or "[]")
    lines = [f"📘 <b>Post-mortem: {t.worker} {t.side}</b> · {bot.esc(lessons.verdict(rec['r'], 1, diag['findings']))}",
             f"The share went {diag['mfe']:+.1f}R your way at best and {-diag['mae']:+.1f}R against you at worst "
             f"(1R = the distance to VWAP when you bought).", "When it was taken: " + bot.esc(", ".join(conds))]
    lines += [f"• {bot.esc(x)}" for _, x in diag["findings"]]
    lines.append("Saved to the journal. 20 minutes from now the bot checks what the share did next.")
    say(full, "\n".join(lines), args)


def follow_up(t: "Trade", bars: dict, full: dict, args, now) -> bool:
    """20 minutes after a scalper trade closed: shaken out? sold too early? Returns True once done."""
    if t.reviewed or not t.u_entry or t.worker not in bars or not t.exit_time:
        return t.reviewed
    ex = pd.Timestamp(t.exit_time)
    if (now - ex).total_seconds() < 20 * 60:
        return False
    df = bars[t.worker]
    at_exit = df[df.index <= ex]
    after = df[df.index > ex].head(20)
    if at_exit.empty or after.empty:
        return True
    entry, stop0, long = _u_levels(t)
    reason = "stop" if "stop" in t.exit_reason or "VWAP" in t.exit_reason else t.exit_reason
    diag = lessons.diagnose(entry, stop0, float(at_exit["Close"].iloc[-1]), long, after.head(1), reason, after)
    new = [x for x in diag["findings"] if x[0] in {"shaken out", "stop saved you", "sold too early"}]
    if new:
        j = lessons.load(STATE, JOURNAL_FILE)
        for rec in j.get("paper", []):
            if rec.get("id") == f"{t.worker}|{t.entry_time}":
                rec["findings"] = sorted(set(rec.get("findings", [])) | {x[0] for x in new})
        lessons.save(STATE, j, JOURNAL_FILE)
        say(full, f"📘 <b>Follow-up: {t.worker} {t.side}</b> ({money(t.pnl)}), 20 minutes after selling:\n" +
            "\n".join(f"• {bot.esc(x)}" for _, x in new), args)
    return True


def learn_records(full: dict) -> list[dict]:
    """The last month of 1-minute prices through the current rules, with each trade's conditions (for bot.py learn)."""
    import yfinance as yf

    cfg, _ = load_cfg(str(BASE / "config.toml"))
    out = []
    for sym in cfg["symbols"]:
        frames = []
        end = pd.Timestamp.now(tz="UTC")
        for k in range(4):
            s0, e0 = end - pd.Timedelta(days=7 * (k + 1)), end - pd.Timedelta(days=7 * k)
            try:
                d = yf.Ticker(sym).history(start=s0, end=e0, interval="1m", prepost=False, auto_adjust=False)
                if d is not None and len(d):
                    frames.append(d)
            except Exception:
                continue
        if not frames:
            continue
        df = pd.concat(frames).sort_index()
        df = df[~df.index.duplicated()]
        df.index = df.index.tz_convert(NY)
        for t in backtest_frame(sym, df, cfg):
            out.append({"kind": "scalper", "setup": "scalper", "symbol": sym, "r": float(t["r"]),
                        "conditions": t.get("conds", []), "findings": [], "date": t["day"]})
    return out


_SHOW = {"ccy": "USD", "per_usd": 1.0}  # money is kept in dollars (options are priced in dollars) and shown in this


def show_in(ccy: str) -> None:
    """Messages show money in the account's currency (e.g. pounds), converted at today's rate."""
    ccy = (ccy or "USD").upper()
    rate = 1.0 if ccy == "USD" else bot.fx_rate("USD", ccy)
    if not rate or not np.isfinite(rate) or rate <= 0:
        rate = {"GBP": 0.76, "EUR": 0.87}.get(ccy, 1.0)  # rough fallback if the rate can't be read
    _SHOW.update(ccy=ccy, per_usd=float(rate))


def money(x: float) -> str:
    sym = {"GBP": "£", "EUR": "€"}.get(_SHOW["ccy"], "$")
    v = x * _SHOW["per_usd"]
    return f"-{sym}{abs(v):,.0f}" if v < 0 else f"{sym}{v:,.0f}"


def account_usd(cfg: dict) -> float:
    """The scalper's own account, in dollars: account_size, plus everything it has made or lost since account_start
    (so it works off what it has: losses shrink the next trades, wins grow them)."""
    size = float(cfg["account_size"])
    ccy = str(cfg.get("account_currency", "USD")).upper()
    if ccy != "USD" and _SHOW["ccy"] != ccy:
        show_in(ccy)
    usd = size / _SHOW["per_usd"] if ccy != "USD" else size
    start = str(cfg.get("account_start") or "")
    log = STATE / "scalper_log.csv"
    if start and log.exists():
        try:
            hist = pd.read_csv(log)
            usd += float(hist.loc[hist["date"].astype(str) >= start, "pnl"].sum())
        except Exception:
            pass
    return max(0.0, usd)


def ny_now() -> pd.Timestamp:
    """New York time now (one place, so a test can run a whole day in seconds)."""
    return pd.Timestamp.now(tz=NY)


def pause(seconds: float) -> None:
    time.sleep(seconds)


def run_session(cfg: dict, full: dict, args) -> int:
    api = Alpaca(cfg["key"], cfg["secret"])
    started = time.time()

    def clock_now():
        for attempt in range(5):  # one failed check must not end the day's trading
            try:
                return api.clock()
            except Exception as exc:
                print(bot.redact(f"Alpaca clock check failed ({exc}), retrying", full))
                pause(10 * (attempt + 1))
        return api.clock()

    clock = clock_now()
    if not clock.is_open:
        nxt = pd.Timestamp(clock.next_open).tz_convert(NY)
        if (nxt - ny_now()).total_seconds() > 45 * 60:
            print(f"Market closed. Next open {nxt:%a %d %b %H:%M} New York time. Nothing to do.")
            return 0
        print(f"Waiting for the open at {nxt:%H:%M} New York time...")
        while not clock_now().is_open:
            pause(20)
    today = ny_now().strftime("%Y-%m-%d")
    day = load_day(today)
    if day.orb_used.get("_done"):
        print("Today's session already finished.")
        return 0
    lh, lm = ny_time(cfg["last_entry"])
    now0 = ny_now()
    still_open = [t for t in day.trades if t.get("status") in {"open", "pending"}]
    sweep_orphans(api, day, full, args)
    if now0.hour * 60 + now0.minute > lh * 60 + lm and not still_open:
        if day.stats.get("announced"):
            # an earlier run today traded the session but was stopped before it could send the summary: send it now
            finish_day(day, full, args, cfg, api)
            return 0
        # GitHub sometimes starts this hours late. Past the last entry time there's nothing to do, so say nothing
        # (no "on shift" and no "0 trades" summary) and don't log a fake no-trade day.
        print(f"Started at {now0:%H:%M} New York time, after the last entry time ({cfg['last_entry']}). Nothing to do.")
        return 0
    if not day.trades and not day.stats.get("announced"):
        trig = {"vwap": "VWAP cross", "ema50": f"{ema_len(cfg)} EMA cross", "orb": "opening-range breakout",
                "hod": f"a new high or low of the day (after {cfg.get('hod_after', '10:00')})",
                "ema_bounce": "a dip to the EMA that holds"}
        names = ", ".join(trig.get(t, t) for t in cfg["triggers"])
        say(full, f"<b>0DTE scalper on shift</b> (paper) · workers: {', '.join(cfg['symbols'])}\n"
                  f"Triggers on {cfg.get('signal_minutes', 1)}-minute bars: {names}"
                  f"{', only in the direction of the trend' if cfg.get('trend_filter') else ''}"
                  f"{', strong candles only' if cfg.get('candle_filter') else ''}. "
                  f"Entries {cfg['first_entry']} to {cfg['last_entry']} New York time. "
                  f"Daily loss limit {money(account_usd(cfg) * cfg['daily_loss_limit_pct'] / 100)}.\n"
                  f"Account {money(account_usd(cfg))} · each trade risks up to "
                  f"{money(account_usd(cfg) * cfg['risk_per_trade_pct'] / 100)} and spends at most "
                  f"{money(account_usd(cfg) * cfg['max_premium_pct'] / 100)}.", args)
        day.stats["announced"] = True
    history5: dict = {}
    if cfg.get("trend_filter"):
        try:
            history5 = api.bars_history(cfg["symbols"])
        except Exception as exc:
            print(bot.redact(f"Couldn't load earlier bars for the trend filter ({exc}); it will use today's bars only.", full))
    fh, fm = ny_time(cfg["flat_by"])
    while True:
        now = ny_now()
        flat_time = now.hour * 60 + now.minute >= fh * 60 + fm
        out_of_time = (time.time() - started) / 60 > float(cfg["max_runtime_minutes"])
        try:
            bars = api.bars_today(cfg["symbols"])
            tick(api, day, bars, cfg, full, args, now, force_exit=flat_time or out_of_time, history5=history5)
        except Exception as exc:
            print(bot.redact(f"{now:%H:%M:%S} error: {exc}", full))
        save_day(day)
        if flat_time or out_of_time:
            break
        past_last = now.hour * 60 + now.minute > lh * 60 + lm
        if past_last and not any(t.get("status") in {"open", "pending"} for t in day.trades):
            print(f"{now:%H:%M} past the last entry time with nothing open: the day's done.")
            break  # no new trades after last_entry, and nothing left to manage: finish now, with the summary
        pause(int(cfg["poll_seconds"]))
    finish_day(day, full, args, cfg, api)
    return 0


def sweep_orphans(api: "Alpaca", day: Day, full: dict, args) -> None:
    """Options the paper account holds that today's record doesn't know about (a run that was killed with a trade
    open) are sold at once, so nothing is ever left to expire."""
    try:
        known = {t["contract"] for t in day.trades if t.get("status") in {"open", "pending"}}
        orphans = [(c, q) for c, q in api.option_positions() if c not in known]
    except Exception as exc:
        print(bot.redact(f"position check: {exc}", full))
        return
    for c, q in orphans:
        api.sell_all(c)
    if orphans:
        say(full, "🧹 <b>Scalper tidy-up</b>: sold " + ", ".join(f"{q} x {c}" for c, q in orphans)
            + " left over from a run that was stopped.", args)


def finish_day(day: Day, full: dict, args, cfg: dict, api: "Alpaca | None" = None) -> None:
    """End of the session: make sure no option is still held, mark the day done, and always send the summary."""
    if api is not None:
        try:
            left = api.option_positions()
            for c, _q in left:
                api.sell_all(c)
            if left:
                say(full, "🧹 Sold " + ", ".join(f"{q} x {c}" for c, q in left) + " still held at the end of the session.", args)
        except Exception as exc:
            print(bot.redact(f"end-of-day position check: {exc}", full))
    day.orb_used["_done"] = ["yes"]
    save_day(day)
    try:
        summary(day, full, args, cfg)
    except Exception as exc:  # the summary must always arrive, even a short one
        print(bot.redact(f"summary failed: {exc}", full))
        closed = [t for t in day.trades if t.get("status") == "closed"]
        say(full, f"<b>0DTE scalper · {day.date} (paper)</b>\n{len(closed)} trades · total "
                  f"{money(sum(float(t.get('pnl', 0)) for t in closed))}", args)


def trump_bias(day: Day, cfg: dict, full: dict, args, now) -> dict:
    """Reads Trump's posts every few minutes. A fresh post that the keyword rules say should push SPY, QQQ or IWM
    one way stops the scalper trading AGAINST it for the next hour (no calls after a tariff threat, no puts after
    "great time to buy"). Trades with it still need the normal trigger and trend. {symbol: bias} still in force."""
    if not cfg.get("use_trump", True):
        return {}
    tb = day.stats.setdefault("trump_bias", {})
    last = day.stats.get("trump_checked")
    if not last or (now - pd.Timestamp(last)).total_seconds() >= 180:
        day.stats["trump_checked"] = str(now)
        posts = []
        try:
            import requests

            r = requests.get(trump.FEED, timeout=15, headers={"User-Agent": "Mozilla/5.0 (setup-scanner-bot)"})
            r.raise_for_status()
            posts = trump.parse_feed(r.text)
        except Exception as exc:
            print(f"Trump feed: {exc}")
        seen = day.stats.setdefault("trump_seen", [])
        mins = int(cfg.get("trump_minutes", 60))
        for p in posts:
            if p["id"] in seen:
                continue
            seen.append(p["id"])
            if p["when"] is None or (now - p["when"]).total_seconds() > 45 * 60:
                continue  # old news by now
            eff = {e["market"]: e for e in trump.read_post(p["text"])}
            if "SPY" in eff and "IWM" not in eff:
                eff["IWM"] = dict(eff["SPY"], market="IWM")  # small caps move with the whole market
            hit = []
            for sym in cfg["symbols"]:
                e = eff.get(sym)
                if e:
                    tb[sym] = {"dir": int(e["direction"]), "until": str(p["when"] + pd.Timedelta(minutes=mins)),
                               "topic": e["topic"], "text": p["text"][:90]}
                    hit.append(f"{sym} {'⬆ up' if e['direction'] > 0 else '⬇ down'} ({e['topic']})")
            if hit:
                say(full, f"🇺🇸 <b>Scalper read Trump's post</b>: “{bot.esc(p['text'][:200])}”\n"
                          f"Could move: {bot.esc(', '.join(hit))}. For the next {mins} minutes it won't trade against "
                          f"that on those markets.", args)
        day.stats["trump_seen"] = seen[-200:]
    return {s_: b for s_, b in tb.items() if pd.Timestamp(b["until"]) > now}


def tick(api: Alpaca, day: Day, bars: dict, cfg: dict, full: dict, args, now, force_exit: bool,
         history5: dict | None = None) -> None:
    trades = [Trade(**t) for t in day.trades]
    mins = int(cfg.get("signal_minutes", 1))
    sig_bars = {s: to_bars(d, mins, now) for s, d in bars.items()}
    # 1) manage open trades
    for t in trades:
        if t.status == "pending":
            o = api.order(t.order_id)
            st = str(getattr(o, "status", "")).lower()
            if "filled" in st and "partially" not in st:
                t.entry_price = float(o.filled_avg_price)
                t.best = t.entry_price
                t.status = "open"
                say(full, f"<b>{t.worker} bought {t.qty} x {t.side.upper()}</b> {t.contract} at ${t.entry_price:.2f} "
                          f"(${t.entry_price * 100 * t.qty:,.0f}) · {t.why}\n{bot.chart_link(t.worker, 1)} · "
                          f'<a href="https://app.alpaca.markets/paper/dashboard/overview">Alpaca paper account</a>', args)
                if t.worker in bars:
                    picture(full, bars, t.worker, f"<b>{t.worker}</b> when the scalper bought the {t.side}", args,
                            float(bars[t.worker]["Close"].iloc[-1]))
            elif (now - pd.Timestamp(t.entry_time)).total_seconds() > 90 or force_exit:
                api.cancel(t.order_id)
                got = 0
                try:  # a partly filled order still bought some contracts: keep managing those, never orphan them
                    o2 = api.order(t.order_id)
                    got = int(float(getattr(o2, "filled_qty", 0) or 0))
                    if got > 0:
                        t.entry_price = float(o2.filled_avg_price)
                except Exception as exc:
                    print(bot.redact(f"order check {t.contract}: {exc}", full))
                if got > 0:
                    t.qty, t.best, t.status = got, t.entry_price, "open"
                    say(full, f"<b>{t.worker} bought {got} x {t.side.upper()}</b> (part of the order) at "
                              f"${t.entry_price:.2f}", args)
                else:
                    t.status = "cancelled"
                    t.exit_reason = "not filled within 90 seconds"
                    day.last_exit[t.worker] = str(now)
            continue
        if t.status != "open":
            continue
        q = api.quote(t.contract)
        if not q:
            continue
        bid, ask = q
        px = bid if bid > 0 else (bid + ask) / 2
        t.best = max(t.best, px)
        chg = (px / t.entry_price - 1) * 100
        reason = None
        sb = sig_bars.get(t.worker)
        ind = session_indicators(sb, cfg) if sb is not None and len(sb) > 3 else None
        u_r = None
        if t.u_entry and t.worker in bars and len(bars[t.worker]):
            u_now = float(bars[t.worker]["Close"].iloc[-1])
            u_risk = max(abs(t.u_entry - t.u_stop), t.u_entry * 0.0015)
            u_r = ((u_now - t.u_entry) if t.side == "call" else (t.u_entry - u_now)) / u_risk
            t.best_r = max(t.best_r, u_r)
        floor = profit_floor(t.best_r, cfg)
        best_gain = (t.best / t.entry_price - 1) * 100
        if force_exit:
            reason = "end of the trading window"
        elif u_r is not None and cfg.get("lock_profits") and u_r >= float(cfg.get("target_r", 2.0)):
            reason = f"profit target: the share moved {u_r:.1f}R your way ({chg:+.0f}% on the option)"
        elif u_r is not None and floor is not None and u_r <= floor:
            reason = f"locked in profit: it was up {t.best_r:.1f}R and came back ({chg:+.0f}%)"
        elif cfg.get("lock_profits") and best_gain >= float(cfg.get("lock_after_pct", 15)) and \
                chg <= float(cfg.get("lock_floor_pct", 3)):
            reason = f"locked in profit: the option was up {best_gain:.0f}% and came back ({chg:+.0f}%)"
        elif chg <= -float(cfg["stop_loss_pct"]):
            reason = f"stop loss ({chg:.0f}%)"
        elif chg >= float(cfg["take_profit_pct"]):
            reason = f"profit target (+{chg:.0f}%)"
        elif (t.best / t.entry_price - 1) * 100 >= float(cfg["trail_after_pct"]) and \
                (px / t.best - 1) * 100 <= -float(cfg["trail_giveback_pct"]):
            reason = f"trailing stop ({chg:+.0f}%)"
        elif (now - pd.Timestamp(t.entry_time)).total_seconds() / 60 >= int(cfg["max_hold_minutes"]):
            reason = f"time stop ({cfg['max_hold_minutes']} min)"
        elif ind is not None and cfg["exit_on_reverse_cross"]:
            c, vw = ind["Close"].iloc[-1], ind["vwap"].iloc[-1]
            if (t.side == "call" and c < vw) or (t.side == "put" and c > vw):
                reason = "price closed back across VWAP"
        if reason:
            px = api.exit_fill(api.sell_all(t.contract), px)
            chg = (px / t.entry_price - 1) * 100
            t.exit_price, t.exit_time, t.exit_reason, t.status = px, str(now), reason, "closed"
            t.pnl = (px - t.entry_price) * 100 * t.qty
            day.last_exit[t.worker] = str(now)
            total = sum(x.pnl for x in trades if x.status == "closed")
            say(full, f"<b>{t.worker} {t.side.upper()} {'WON' if t.pnl > 0 else 'LOST'} {money(t.pnl)}</b> ({chg:+.0f}%)\n"
                      f"{t.qty} x {t.contract}: bought at ${t.entry_price:.2f}, sold at ${px:.2f}, {reason}.\n"
                      f"Today so far: {money(total)} (paper)", args)
            if t.worker in bars:
                picture(full, bars, t.worker, f"<b>{t.worker}</b> when the scalper sold: {'WON' if t.pnl > 0 else 'LOST'} "
                        f"{money(t.pnl)}", args)
            try:
                post_mortem(t, bars, full, cfg, args, now)
            except Exception as exc:
                print(f"post-mortem: {exc}")
    for t in trades:
        if t.status == "closed" and not t.reviewed:
            try:
                t.reviewed = follow_up(t, bars, full, args, now)
            except Exception as exc:
                print(f"follow-up: {exc}")
                t.reviewed = True
    day.trades = [asdict(t) for t in trades]
    if force_exit:
        return
    # 2) risk limits before any new entry
    realised = sum(t.pnl for t in trades if t.status == "closed")
    if realised <= -account_usd(cfg) * cfg["daily_loss_limit_pct"] / 100:
        if not day.orb_used.get("_limit_said"):
            say(full, f"<b>Daily loss limit hit</b> ({money(realised)}). No more trades today.", args)
            day.orb_used["_limit_said"] = ["yes"]
        return
    entered = [t for t in trades if t.status in {"open", "closed", "pending"}]
    if len(entered) >= int(cfg["max_trades_per_day"]):
        return
    if sum(1 for t in trades if t.status in {"open", "pending"}) >= int(cfg["max_open_positions"]):
        return
    ev = blackout(full, cfg, now)
    try:
        biases = trump_bias(day, cfg, full, args, now)
    except Exception as exc:  # the Trump check must never stop the trading
        print(f"Trump check: {exc}")
        biases = {}
    # 3) look for new signals on the latest finished bar
    for sym, df1 in bars.items():
        df = sig_bars.get(sym, df1)
        if len(df) < (4 if mins > 1 else 20) or any(t.worker == sym and t.status in {"open", "pending"} for t in trades):
            continue
        mine = [t for t in trades if t.worker == sym and t.status == "closed"]
        if sum(1 for t in mine if t.pnl < 0) >= int(cfg.get("max_losses_per_worker", 99)):
            continue  # this worker has had enough for today
        last_ts = str(df.index[-1])
        if day.seen_bar.get(sym) == last_ts:
            continue
        day.seen_bar[sym] = last_ts
        if not in_window(df.index[-1], cfg) or ev:
            continue
        le = day.last_exit.get(sym)
        wait = int(cfg["cooldown_minutes"])
        if mine and mine[-1].pnl < 0:
            wait = max(wait, int(cfg.get("loss_cooldown_minutes", wait)))
        if le and (now - pd.Timestamp(le)).total_seconds() / 60 < wait:
            continue
        ind = session_indicators(df, cfg)
        used = set(day.orb_used.get(sym, []))
        sig = signal_at(ind, len(ind) - 1, cfg, used, day.stats)
        if not sig:
            continue
        side, why = sig
        day.stats["signals"] = day.stats.get("signals", 0) + 1
        if cfg.get("trend_filter"):
            direction, kind = trend_now((history5 or {}).get(sym), to_bars(df1, 5, now), sym)
            if not trend_allows(side, direction, kind):
                print(f"{now:%H:%M} {sym}: {side} signal ({'; '.join(why)}) skipped: trend is {direction}/{kind}")
                day.stats["trend"] = day.stats.get("trend", 0) + 1
                continue
            why = why + [f"trend {direction}"]
        else:
            direction, kind = ("up" if side == "call" else "down"), "trend"
        b = biases.get(sym)
        if b:
            if side != ("call" if b["dir"] > 0 else "put"):
                print(f"{now:%H:%M} {sym}: {side} signal skipped: against Trump's post ({b['topic']})")
                day.stats["trump_skips"] = day.stats.get("trump_skips", 0) + 1
                continue
            why = why + [f"agrees with Trump's post ({b['topic']})"]
        conds = scalp_conditions(ind, len(ind) - 1, why, direction, kind)
        if cfg.get("learn_from_journal", True):
            proven = [w for p_, w in lessons.lessons_for(bot.journal(), "scalper", "scalper", sym, conds,
                                                          int(cfg.get("lesson_min_trades", 30)), 2.0) if p_ < 0]
            if proven:
                day.stats["journal"] = day.stats.get("journal", 0) + 1
                print(f"{now:%H:%M} {sym}: {side} signal skipped, the journal says: {proven[0]}")
                say(full, f"📘 <b>{sym} {side} skipped</b>: the journal has a proven lesson against it.\n{bot.esc(proven[0])}", args)
                continue
        price = float(ind["Close"].iloc[-1])
        con = api.pick_contract(sym, side, price)
        if not con:
            print(f"{sym}: no 0DTE {side} found")
            continue
        q = api.quote(con.symbol)
        if not q:
            continue
        bid, ask = q
        mid = (bid + ask) / 2 if bid > 0 else ask
        if bid <= 0 or (ask - bid) / mid * 100 > float(cfg["max_spread_pct"]):
            print(f"{sym}: {con.symbol} spread too wide ({bid}/{ask}), skipped")
            day.stats["spread"] = day.stats.get("spread", 0) + 1
            continue
        # Bid a little above the middle instead of paying the full asking price: research on retail 0DTE
        # traders found most of their losses came from trading costs (the bid/ask spread).
        limit = round(min(ask, mid + float(cfg.get("entry_offset_pct", 25)) / 100 * (ask - mid)) + 0.004, 2)
        acct = account_usd(cfg)
        risk_cash = acct * cfg["risk_per_trade_pct"] / 100
        per_contract_risk = limit * 100 * cfg["stop_loss_pct"] / 100
        max_spend = acct * cfg["max_premium_pct"] / 100
        # never spend more than the account has free: what's already in open or waiting trades is in use
        in_use = sum(x.entry_price * 100 * x.qty for x in trades if x.status in {"open", "pending"})
        max_spend = min(max_spend, acct - in_use)
        qty = int(min(risk_cash / per_contract_risk, max_spend / (limit * 100))) if max_spend > 0 else 0
        if qty < 1:
            print(f"{sym}: one contract ({money(limit * 100)}) is over your limits, skipped")
            day.stats["too_dear"] = day.stats.get("too_dear", 0) + 1
            continue
        if any("opening range" in w for w in why):
            day.orb_used[sym] = sorted(used | {side})
        o = api.buy(con.symbol, qty, limit)
        t = Trade(worker=sym, side=side, contract=con.symbol, qty=qty, entry_price=limit, entry_time=str(now),
                  why="; ".join(why), order_id=str(o.id), status="pending", u_entry=price,
                  u_stop=float(ind["vwap"].iloc[-1]), conds=json.dumps(conds),
                  risk_cash=qty * per_contract_risk)
        trades.append(t)
        print(f"{now:%H:%M:%S} {sym}: buy {qty} {con.symbol} limit {limit:.2f} (bid {bid:.2f} / ask {ask:.2f}) ({t.why})")
        if sum(1 for x in trades if x.status in {"open", "pending"}) >= int(cfg["max_open_positions"]):
            break
    day.trades = [asdict(t) for t in trades]


def summary(day: Day, full: dict, args, cfg: dict) -> None:
    closed = [Trade(**t) for t in day.trades if t["status"] == "closed"]
    total = sum(t.pnl for t in closed)
    wins = sum(1 for t in closed if t.pnl > 0)
    lines = [f"<b>0DTE scalper · {day.date} (paper)</b>", f"{len(closed)} trades · {wins} won · total {money(total)}"]
    st = day.stats
    if not closed:
        cross = st.get("signals", 0) + st.get("candle", 0)
        lines.append(
            f"Why no trades: {cross} VWAP/EMA cross signal{'s' if cross != 1 else ''} all day"
            + (f"; {st.get('candle', 0)} had a weak candle" if st.get("candle") else "")
            + (f"; {st.get('trend', 0)} went against the trend" if st.get("trend") else "")
            + (f"; {st.get('journal', 0)} matched a losing lesson in the journal" if st.get("journal") else "")
            + (f"; {st.get('spread', 0)} had too wide a bid/ask spread" if st.get("spread") else "")
            + (f"; {st.get('too_dear', 0)} cost more than the account allows" if st.get("too_dear") else "")
            + (f"; {st.get('chart', 0)} didn't fit the chart (highs and lows against it, rejection wicks, or no "
               f"room before a wall of wicks)" if st.get("chart") else "")
            + (f"; {st.get('trump_skips', 0)} went against a fresh Trump post" if st.get("trump_skips") else "")
            + ". It only trades when everything lines up: a quiet day is part of that.")
    for w in cfg["symbols"]:
        ws = [t for t in closed if t.worker == w]
        if ws:
            lines.append(f"{w}: {len(ws)} trades, {money(sum(t.pnl for t in ws))}")
    log = STATE / "scalper_log.csv"
    new = not log.exists()
    STATE.mkdir(exist_ok=True)
    with open(log, "a", newline="") as fh:
        wr = csv.writer(fh)
        if new:
            wr.writerow(["date", "trades", "won", "pnl"])
        wr.writerow([day.date, len(closed), wins, round(total, 2)])
    hist = pd.read_csv(log)
    traded = hist[hist["trades"] > 0]
    if len(traded) > 1:
        lines.append(f"All paper days with trades so far: {len(traded)} days, {money(traded['pnl'].sum())}, "
                     f"{(traded['pnl'] > 0).sum()} winning days")
    say(full, "\n".join(lines), args)


def cmd_check(cfg: dict, full: dict, args) -> int:
    api = Alpaca(cfg["key"], cfg["secret"])
    acct = api.trading.get_account()
    clk = api.clock()
    print(f"Alpaca paper account OK: status {acct.status}, buying power ${float(acct.buying_power):,.0f}")
    print(f"Options level: {getattr(acct, 'options_trading_level', 'unknown')}")
    print(f"Market {'OPEN' if clk.is_open else 'closed'}; next open {pd.Timestamp(clk.next_open).tz_convert(NY):%a %d %b %H:%M} NY")
    bars = api.bars_today(cfg["symbols"][:1])
    sym = cfg["symbols"][0]
    if sym in bars and len(bars[sym]):
        px = float(bars[sym]["Close"].iloc[-1])
        print(f"{sym} last 1-minute close ${px:.2f} ({len(bars[sym])} bars today)")
        con = api.pick_contract(sym, "call", px)
        if con:
            print(f"Nearest 0DTE call: {con.symbol}, quote {api.quote(con.symbol)}")
    else:
        print("No 1-minute bars yet today (normal before the US open).")
    say(full, "<b>0DTE scalper</b>: Alpaca paper account connected.", args)
    return 0


def cmd_report(cfg: dict, full: dict, args) -> int:
    d = pd.Timestamp.now(tz=NY).strftime("%Y-%m-%d")
    day = load_day(d)
    for t in day.trades:
        print(f"{t['worker']} {t['side']} {t['contract']} x{t['qty']} {t['status']} "
              f"in {t['entry_price']:.2f} out {t['exit_price']:.2f} {money(t['pnl'])} {t['exit_reason']}")
    if not day.trades:
        print("No scalper trades today.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="0DTE options scalper, paper trading only")
    ap.add_argument("command", choices=["run", "check", "backtest", "report"])
    ap.add_argument("--config", default=str(BASE / "config.toml"))
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args(argv)
    cfg, full = load_cfg(args.config)
    show_in(str(cfg.get("account_currency", "USD")))
    if not cfg.get("enabled", True) and args.command == "run":
        print("Scalper is switched off in config.toml ([scalper] enabled = false).")
        return 0
    return {"run": run_session, "check": cmd_check, "backtest": cmd_backtest, "report": cmd_report}[args.command](cfg, full, args)


if __name__ == "__main__":
    sys.exit(main())
