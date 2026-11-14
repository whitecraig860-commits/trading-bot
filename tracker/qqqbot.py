"""
QQQ paper bot: the three one-minute triggers, traded on paper at real buying and selling prices
===============================================================================================
BASELINE RULES. These are exactly the rules tested in research/QQQ_TRIGGERS_PROTOCOL.md (Study 5), where they LOST
money on 2.7 years of history. The bot runs them forward on paper to (1) measure real fills against that backtest and
(2) be the harness that better filters are added to, one tested change at a time. It never places an order anywhere:
it keeps a ledger, buying at the recorded ask and selling at the recorded bid.

Rules: one-minute QQQ candles. Buy a CALL when a candle closes up through VWAP or the 50 EMA, or first closes above
the first 15 minutes' high; a PUT for the same downwards. Next-expiry option, strike nearest the share price, one
contract, one trade at a time, signals 09:45-15:30 New York time. Sell at +2.5%, at -6%, or after 10 minutes.

It runs inside the price recorder (tracker/recorder.py), which calls on_poll() every 5 seconds.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

STATE = Path(__file__).resolve().parent.parent / "state" / "qqqbot"
TARGET, STOP, HOLD_MIN, FEE = 0.025, 0.06, 10, 0.03
TRADE_MESSAGES = True
MAX_LOSSES_IN_A_ROW = 2  # stop for the day after this many losses in a row (Study 7, research/LOSS_PAUSE_REPORT.md); 0 = off   # a short BOUGHT / SOLD line on Telegram for every trade; False = the two summaries only
FIRST, LAST, FLAT = "09:45", "15:30", "15:55"
MORNING_AT, DAY_AT = "12:00", "16:00"
GBP = 0.76


def alpaca_bars(stock_client):
    """Returns a function giving (yesterday's and) today's one-minute QQQ bars, New York time, oldest first."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    def fetch(now: datetime, days_back: int = 0) -> pd.DataFrame:
        start = (now - timedelta(days=days_back)).replace(hour=9, minute=30, second=0, microsecond=0)
        df = stock_client.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute,
                                                          start=start, feed=DataFeed.IEX)).df
        if df is None or df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([]))
        d = df.xs("QQQ", level=0)[["open", "high", "low", "close", "volume"]].astype(float)
        d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").tz_localize(None)
        return d.between_time("09:30", "15:59")

    return fetch


def send_telegram(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("(no Telegram settings; message not sent)\n" + text)
        return False
    try:
        import requests

        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"},
                          timeout=8)
        return r.ok
    except Exception as exc:
        print(f"Telegram: {type(exc).__name__}")  # never print the exception text: it can contain the token
        return False


class PaperBot:
    def __init__(self, bars_fn, now: datetime, say=send_telegram, state_dir: Path = STATE, name: str = "",
                 max_losses: int | None = None, trade_messages: bool | None = None):
        self.bars_fn, self.say, self.dir = bars_fn, say, state_dir
        self.name = name
        self.max_losses = MAX_LOSSES_IN_A_ROW if max_losses is None else max_losses
        self.trade_messages = TRADE_MESSAGES if trade_messages is None else trade_messages
        self.day = now.strftime("%Y-%m-%d")
        self.path = self.dir / f"{self.day}.json"
        self.s = {"trades": [], "open": None, "range_done": [], "sent": [], "seen_bars": 0}
        if self.path.exists():
            self.s.update(json.loads(self.path.read_text()))
        self.last_min = None
        self.prev = None      # earlier bars, to carry the 50 EMA into the open
        self.bars = None

    # ------------------------------------------------------------------ state
    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.s, indent=1))

    # ------------------------------------------------------------------ signals
    def _signal(self, now: datetime):
        """A signal from the candle that has just closed, or None."""
        want = now.replace(second=0, microsecond=0, tzinfo=None) - timedelta(minutes=1)
        if self.prev is None:
            for back in (1, 2, 3, 4):  # the last session before today (weekends, holidays)
                try:
                    p = self.bars_fn(now, back)
                    p = p[p.index.normalize() < pd.Timestamp(self.day)]
                except Exception:
                    p = pd.DataFrame()
                if len(p):
                    self.prev = p.tail(300)
                    break
            if self.prev is None:
                self.prev = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([]))
        b = self.bars_fn(now)
        b = b[(b.index.normalize() == pd.Timestamp(self.day)) & (b.index <= want)]
        self.bars = b
        if len(b) < 2 or b.index[-1] != want:
            return None
        tp = (b.high + b.low + b.close) / 3
        vol = b.volume.where(b.volume > 0, 1.0)
        vwap = (tp * vol).cumsum() / vol.cumsum()
        ema = pd.concat([self.prev.close, b.close]).ewm(span=50, adjust=False).mean().iloc[-len(b):]
        c, pc = b.close.iloc[-1], b.close.iloc[-2]
        tod = (want + timedelta(minutes=1)).strftime("%H:%M")
        if not (FIRST <= tod <= LAST):
            return None
        for name, line in (("EMA50", ema), ("VWAP", vwap)):
            if pc <= line.iloc[-2] and c > line.iloc[-1]:
                return "C", name, c
            if pc >= line.iloc[-2] and c < line.iloc[-1]:
                return "P", name, c
        if len(b) > 15:
            hi, lo = b.high.iloc[:15].max(), b.low.iloc[:15].min()
            if c > hi and "C" not in self.s["range_done"]:
                self.s["range_done"].append("C")
                return "C", "RANGE", c
            if c < lo and "P" not in self.s["range_done"]:
                self.s["range_done"].append("P")
                return "P", "RANGE", c
        return None

    # ------------------------------------------------------------------ the 5-second tick
    def on_poll(self, now: datetime, rows: list[dict]):
        quotes = {(r["expiry"], r["type"], float(r["strike"])): r for r in rows}
        tod = now.strftime("%H:%M")
        o = self.s["open"]
        if o:
            q = quotes.get((o["expiry"], o["type"], o["strike"]))
            bid = float(q["bid"]) if q and q["bid"] not in ("", None) else 0.0
            age = (now.replace(tzinfo=None) - pd.Timestamp(o["t"])).total_seconds() / 60
            why = None
            if bid > 0:
                if bid >= o["entry"] * (1 + TARGET):
                    why = "target"
                elif bid <= o["entry"] * (1 - STOP):
                    why = "stop"
                elif age >= HOLD_MIN:
                    why = "time"
                elif tod >= FLAT:
                    why = "end of day"
            if why:
                self._close(now, bid, why)
        if now.second >= 3 and tod != self.last_min:
            self.last_min = tod
            try:
                sig = self._signal(now)
            except Exception as exc:
                print(f"{tod} bars: {type(exc).__name__}: {str(exc)[:100]}")
                sig = None
            run = 0
            for tr in reversed(self.s["trades"]):
                if tr["pnl"] >= 0:
                    break
                run += 1
            stopped = bool(self.max_losses) and run >= self.max_losses
            if stopped and "stopped" not in self.s["sent"]:
                self.s["sent"].append("stopped")
                self._tell(f"⏸ <b>Stopped for the day</b> after {run} losses in a row (paper). Back tomorrow.")
                self.save()
            if sig and not self.s["open"] and tod < FLAT and not stopped:
                side, trig, px = sig
                today = now.strftime("%Y-%m-%d")
                exps = sorted({k[0] for k in quotes if k[0] > today})
                q = quotes.get((exps[0], side, float(round(px)))) if exps else None
                ask = float(q["ask"]) if q and q["ask"] not in ("", None) else 0.0
                if ask >= 0.5:
                    self.s["open"] = {"t": now.strftime("%Y-%m-%d %H:%M:%S"), "type": side, "strike": float(round(px)),
                                      "expiry": exps[0], "entry": ask, "trigger": trig, "qqq": round(px, 2)}
                    print(f"{now:%H:%M:%S} BOUGHT 1x QQQ {round(px)} {'CALL' if side == 'C' else 'PUT'} @ {ask:.2f} ({trig})")
                    self._tell(f"🟢 <b>BOUGHT</b> 1× QQQ {round(px)} {'CALL' if side == 'C' else 'PUT'} @ {ask:.2f}\n"
                               f"{now:%a %m/%d · %I:%M:%S %p} ET · {trig} · paper")
                    self.save()
            self._summaries(now)

    def _close(self, now: datetime, bid: float, why: str):
        o = self.s["open"]
        pnl = (bid - o["entry"]) * 100 - 2 * FEE
        self.s["trades"].append(dict(o, exit=bid, exit_t=now.strftime("%Y-%m-%d %H:%M:%S"), why=why, pnl=round(pnl, 2)))
        self.s["open"] = None
        print(f"{now:%H:%M:%S} SOLD @ {bid:.2f} ({why}) {pnl:+.0f}")
        self._tell(f"🔴 <b>SOLD</b> 1× QQQ {int(o['strike'])} {'CALL' if o['type'] == 'C' else 'PUT'} @ {bid:.2f}\n"
                   f"<b>{'+' if pnl >= 0 else '−'}${abs(pnl):,.0f}</b> ({(bid / o['entry'] - 1):+.1%}) · {now:%a %m/%d · %I:%M:%S %p} ET · {why}")
        self.save()

    def finish(self, now: datetime, rows: list[dict]):
        """Called when a recording run ends: nothing is carried across runs."""
        o = self.s["open"]
        if o:
            q = {(r["expiry"], r["type"], float(r["strike"])): r for r in rows}.get((o["expiry"], o["type"], o["strike"]))
            bid = float(q["bid"]) if q and q["bid"] not in ("", None) else o["entry"]
            self._close(now, bid, "recorder restart")
        self._summaries(now)
        self.save()

    def _tell(self, text: str):
        if self.trade_messages:
            try:
                self.say(text)
            except Exception:
                pass  # a failed message must never stop the bot

    # ------------------------------------------------------------------ summaries
    def summary(self, title: str, upto: str | None = None) -> str:
        tr = [t for t in self.s["trades"] if upto is None or t["exit_t"][11:16] < upto]
        wins = [t for t in tr if t["pnl"] > 0]
        total = sum(t["pnl"] for t in tr)
        lines = [f"📊 <b>{title}</b> ({pd.Timestamp(self.day):%a %d %b})",
                 f"QQQ paper bot{' (' + self.name + ')' if self.name else ''}: {len(tr)} trades · {len(wins)}W / {len(tr) - len(wins)}L · <b>{total:+,.0f} USD</b> (£{total * GBP:+,.0f})"]
        for trig in ("VWAP", "EMA50", "RANGE"):
            g = [t for t in tr if t["trigger"] == trig]
            if g:
                lines.append(f"{trig}: {len(g)} trades · {sum(t['pnl'] > 0 for t in g)}W / {sum(t['pnl'] <= 0 for t in g)}L · "
                             f"{sum(t['pnl'] for t in g):+,.0f}")
        if tr:
            best, worst = max(tr, key=lambda t: t["pnl"]), min(tr, key=lambda t: t["pnl"])
            lines.append(f"Best {best['pnl']:+,.0f} ({best['t'][11:16]} {int(best['strike'])}{best['type']}) · "
                         f"worst {worst['pnl']:+,.0f} ({worst['t'][11:16]} {int(worst['strike'])}{worst['type']})")
        lines.append("<i>Paper only, 1 contract a trade, bought at the real ask and sold at the real bid. These are the "
                     "baseline rules, which lost in the history test; filters are being worked out.</i>")
        return "\n".join(lines)

    def _summaries(self, now: datetime):
        tod = now.strftime("%H:%M")
        for key, at, title in (("morning", MORNING_AT, "Morning summary"), ("day", DAY_AT, "Today's summary")):
            if tod >= at and key not in self.s["sent"] and not (key == "day" and self.s["open"]):
                if self.say(self.summary(title, MORNING_AT if key == "morning" else None)):
                    self.s["sent"].append(key)
                    self.save()
