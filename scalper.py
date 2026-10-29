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

BASE = Path(__file__).resolve().parent
STATE = BASE / "state"
NY = "America/New_York"

DEFAULTS = {
    "enabled": True,
    "symbols": ["SPY", "QQQ", "IWM"],
    "account_size": 5000.0,           # sizing is based on this, not Alpaca's $100k paper balance
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


# ---------------------------------------------------------------------------
# Indicators on 1-minute bars (one session)
# ---------------------------------------------------------------------------


def session_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """df: one session's 1-minute bars, index in New York time, columns Open High Low Close Volume."""
    out = df.copy()
    tp = (out["High"] + out["Low"] + out["Close"]) / 3.0
    vol = out["Volume"].clip(lower=0)
    cum_v = vol.cumsum()
    out["vwap"] = np.where(cum_v > 0, (tp * vol).cumsum() / cum_v.replace(0, np.nan), tp.expanding().mean())
    out["ema"] = out["Close"].ewm(span=int(cfg["ema_length"]), adjust=False).mean()
    n = int(cfg["opening_range_minutes"])
    start = out.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
    in_or = (out.index >= start) & (out.index < start + pd.Timedelta(minutes=n))
    if in_or.sum() >= max(3, n // 2):
        out["or_high"] = out.loc[in_or, "High"].max()
        out["or_low"] = out.loc[in_or, "Low"].min()
    else:
        out["or_high"] = np.nan
        out["or_low"] = np.nan
    out["or_done"] = out.index >= start + pd.Timedelta(minutes=n)
    return out


def signal_at(ind: pd.DataFrame, i: int, cfg: dict, orb_used: set) -> tuple[str, list[str]] | None:
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
    if "ema50" in trig and i >= int(cfg["ema_length"]) // 2:
        if pc <= pem and c > em:
            fired["call"].append(f"closed above the {cfg['ema_length']} EMA")
        if pc >= pem and c < em:
            fired["put"].append(f"closed below the {cfg['ema_length']} EMA")
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
        return side, fired[side]
    return None


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

    rows = []
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
        rows += backtest_frame(sym, df, cfg)
    return report_backtest(rows, cfg)


def backtest_frame(sym: str, df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Simulates the triggers on the share price. Risk = distance to VWAP or 0.15%, whichever is bigger;
    exits on the reverse cross, the time stop or the close. Results in R (multiples of that risk)."""
    trades = []
    for day, sess in df.groupby(df.index.date):
        sess = sess.between_time("09:30", "15:59")
        if len(sess) < 120:
            continue
        ind = session_indicators(sess[["Open", "High", "Low", "Close", "Volume"]], cfg)
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
                move = (c - pos["entry"]) if long else (pos["entry"] - c)
                r = move / pos["risk"]
                reverse = cfg["exit_on_reverse_cross"] and ((long and c < ind["vwap"].iloc[i]) or ((not long) and c > ind["vwap"].iloc[i]))
                timeout = (ts - pos["t"]).total_seconds() / 60 >= int(cfg["max_hold_minutes"])
                late = ts.hour * 60 + ts.minute >= fh * 60 + fm
                if r <= -1 or r >= 2 or reverse or timeout or late:
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
            if any("opening range" in w for w in why):
                orb_used.add(side)
            entry = float(ind["Open"].iloc[i + 1])
            risk = max(abs(entry - float(ind["vwap"].iloc[i])), entry * 0.0015)
            pos = {"sym": sym, "day": str(day), "t": ts, "side": side, "entry": entry, "risk": risk, "why": "; ".join(why)}
            n_today += 1
    return trades


def report_backtest(rows: list[dict], cfg: dict) -> int:
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


@dataclass
class Day:
    date: str
    trades: list = field(default_factory=list)
    orb_used: dict = field(default_factory=dict)
    last_exit: dict = field(default_factory=dict)
    seen_bar: dict = field(default_factory=dict)


def day_path(d: str) -> Path:
    return STATE / f"scalper_{d}.json"


def load_day(d: str) -> Day:
    p = day_path(d)
    if p.exists():
        raw = json.loads(p.read_text())
        return Day(date=raw["date"], trades=raw.get("trades", []), orb_used=raw.get("orb_used", {}),
                   last_exit=raw.get("last_exit", {}), seen_bar=raw.get("seen_bar", {}))
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

    def sell_all(self, contract: str):
        try:
            return self.trading.close_position(contract)
        except Exception as exc:
            print(f"close {contract}: {exc}")
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


def money(x: float) -> str:
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def run_session(cfg: dict, full: dict, args) -> int:
    api = Alpaca(cfg["key"], cfg["secret"])
    started = time.time()
    clock = api.clock()
    if not clock.is_open:
        nxt = pd.Timestamp(clock.next_open).tz_convert(NY)
        if (nxt - pd.Timestamp.now(tz=NY)).total_seconds() > 20 * 60:
            print(f"Market closed. Next open {nxt:%a %d %b %H:%M} New York time. Nothing to do.")
            return 0
        print(f"Waiting for the open at {nxt:%H:%M} New York time...")
        while not api.clock().is_open:
            time.sleep(20)
    today = pd.Timestamp.now(tz=NY).strftime("%Y-%m-%d")
    day = load_day(today)
    if day.orb_used.get("_done"):
        print("Today's session already finished.")
        return 0
    if not day.trades:
        say(full, f"<b>0DTE scalper on shift</b> (paper) · workers: {', '.join(cfg['symbols'])}\n"
                  f"Triggers: VWAP cross, {cfg['ema_length']} EMA cross, opening-range breakout. "
                  f"Daily loss limit {money(cfg['account_size'] * cfg['daily_loss_limit_pct'] / 100)}.", args)
    fh, fm = ny_time(cfg["flat_by"])
    while True:
        now = pd.Timestamp.now(tz=NY)
        flat_time = now.hour * 60 + now.minute >= fh * 60 + fm
        out_of_time = (time.time() - started) / 60 > float(cfg["max_runtime_minutes"])
        try:
            bars = api.bars_today(cfg["symbols"])
            tick(api, day, bars, cfg, full, args, now, force_exit=flat_time or out_of_time)
        except Exception as exc:
            print(f"{now:%H:%M:%S} error: {exc}")
        save_day(day)
        if flat_time or out_of_time:
            break
        time.sleep(int(cfg["poll_seconds"]))
    day.orb_used["_done"] = ["yes"]
    save_day(day)
    summary(day, full, args, cfg)
    return 0


def tick(api: Alpaca, day: Day, bars: dict, cfg: dict, full: dict, args, now, force_exit: bool) -> None:
    trades = [Trade(**t) for t in day.trades]
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
                          f"(${t.entry_price * 100 * t.qty:,.0f}) · {t.why}", args)
            elif (now - pd.Timestamp(t.entry_time)).total_seconds() > 90 or force_exit:
                api.cancel(t.order_id)
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
        ind = session_indicators(bars[t.worker], cfg) if t.worker in bars and len(bars[t.worker]) > 5 else None
        if force_exit:
            reason = "end of the trading window"
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
            api.sell_all(t.contract)
            t.exit_price, t.exit_time, t.exit_reason, t.status = px, str(now), reason, "closed"
            t.pnl = (px - t.entry_price) * 100 * t.qty
            day.last_exit[t.worker] = str(now)
            total = sum(x.pnl for x in trades if x.status == "closed")
            say(full, f"<b>{t.worker} sold</b> {t.contract}: {money(t.pnl)} ({chg:+.0f}%), {reason}. "
                      f"Today: {money(total)}", args)
    day.trades = [asdict(t) for t in trades]
    if force_exit:
        return
    # 2) risk limits before any new entry
    realised = sum(t.pnl for t in trades if t.status == "closed")
    if realised <= -cfg["account_size"] * cfg["daily_loss_limit_pct"] / 100:
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
    # 3) look for new signals on the latest finished bar
    for sym, df in bars.items():
        if len(df) < 20 or any(t.worker == sym and t.status in {"open", "pending"} for t in trades):
            continue
        last_ts = str(df.index[-1])
        if day.seen_bar.get(sym) == last_ts:
            continue
        day.seen_bar[sym] = last_ts
        if not in_window(df.index[-1], cfg) or ev:
            continue
        le = day.last_exit.get(sym)
        if le and (now - pd.Timestamp(le)).total_seconds() / 60 < int(cfg["cooldown_minutes"]):
            continue
        ind = session_indicators(df, cfg)
        used = set(day.orb_used.get(sym, []))
        sig = signal_at(ind, len(ind) - 1, cfg, used)
        if not sig:
            continue
        side, why = sig
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
            continue
        risk_cash = cfg["account_size"] * cfg["risk_per_trade_pct"] / 100
        per_contract_risk = ask * 100 * cfg["stop_loss_pct"] / 100
        max_spend = cfg["account_size"] * cfg["max_premium_pct"] / 100
        qty = int(min(risk_cash / per_contract_risk, max_spend / (ask * 100)))
        if qty < 1:
            print(f"{sym}: one contract (${ask * 100:,.0f}) is over your limits, skipped")
            continue
        if any("opening range" in w for w in why):
            day.orb_used[sym] = sorted(used | {side})
        o = api.buy(con.symbol, qty, ask)
        t = Trade(worker=sym, side=side, contract=con.symbol, qty=qty, entry_price=ask, entry_time=str(now),
                  why="; ".join(why), order_id=str(o.id), status="pending")
        trades.append(t)
        print(f"{now:%H:%M:%S} {sym}: buy {qty} {con.symbol} limit {ask:.2f} ({t.why})")
        if sum(1 for x in trades if x.status in {"open", "pending"}) >= int(cfg["max_open_positions"]):
            break
    day.trades = [asdict(t) for t in trades]


def summary(day: Day, full: dict, args, cfg: dict) -> None:
    closed = [Trade(**t) for t in day.trades if t["status"] == "closed"]
    total = sum(t.pnl for t in closed)
    wins = sum(1 for t in closed if t.pnl > 0)
    lines = [f"<b>0DTE scalper · {day.date} (paper)</b>", f"{len(closed)} trades · {wins} won · total {money(total)}"]
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
    if len(hist) > 1:
        lines.append(f"All paper days so far: {len(hist)} days, {money(hist['pnl'].sum())}, "
                     f"{(hist['pnl'] > 0).sum()} winning days")
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
    if not cfg.get("enabled", True) and args.command == "run":
        print("Scalper is switched off in config.toml ([scalper] enabled = false).")
        return 0
    return {"run": run_session, "check": cmd_check, "backtest": cmd_backtest, "report": cmd_report}[args.command](cfg, full, args)


if __name__ == "__main__":
    sys.exit(main())
