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
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

STATE = Path(__file__).resolve().parent.parent / "state" / "qqqbot"
TARGET, STOP, HOLD_MIN, FEE = 0.025, 0.06, 10, 0.03
TRADE_MESSAGES = True
# Only buy or sell on a quote stamped within the last minute. On 19 Nov 2026 the data feed served the previous day's
# closing quotes until 10:30; a bot bought at a stale 9.68 and the real price (8.21) arrived 5 seconds later: a fake -$147.
# This is a data-error fix for every bot, not a strategy change. False = the old behaviour.
FRESH_QUOTES_ONLY = True
FRESH_SECONDS = 60
# "His style": the third options bot, fourth bot in all (comparison only, no trade messages). Same entries as the
# other options bots (they already match his timing), with the exits read off his 57 posted trades (11-17 Nov 2026):
# his losers were -10% to -14%, so a 12% stop; his winners +0.5% to +16% (median +3.5%), so on +2.5% it keeps the
# trade and sells 1.5% below the best price (15-minute limit). He trades calls and puts on the same day, so no trend
# filter here (with_trend is tested separately). NOT tested on history yet: research/TREND_TRAIL_PROTOCOL.md (WT).
HIS_STYLE = {"stop": 0.12, "trail": 0.015, "hold_min": 15, "with_trend": False}
# Extra options paper bots, run side by side with the main and original bots for comparison. Same entries; only the
# settings below differ. All of them also stop for the day after 2 losses in a row, like the main bot. They send no Telegram messages of their own: their totals are added to the main bot's
# summaries, and every one has its own card on the live page. Remove a line to stop that bot; the others are unaffected.
#   key: (state folder, name, settings)
EXTRA_BOTS = {
    # Study 8's best rule: keep a winner from +2.5%, sell 1.5% below its best (-$10 a day vs -$38 on 2.7 years).
    "trail": ("qqqbot_trail", "stop after 2 losses + trailing exit", {"trail": 0.015, "hold_min": 15}),
    # Both rules that helped in Study 8 (trailing exit, and with the day's direction only), with the normal 6% stop.
    # This exact mix was not run in Study 8.
    "trailtrend": ("qqqbot_trailtrend", "stop after 2 losses + trailing exit + trend", {"trail": 0.015, "hold_min": 15,
                                                                            "with_trend": True}),
    "his": ("qqqbot_his", "his style: stop after 2 losses + 12% stop + trail", HIS_STYLE),
    # Study 9 (research/HIS_FILTER_REPORT.md): skip a signal when the close is less than $0.10 past the line it crossed.
    # Better than the main bot on 2.7 years (-$32 a day vs -$38, paired t +5.9, also in the holdout and at 2 cents).
    "skipweak": ("qqqbot_skipweak", "stop after 2 losses + skip weak crosses", {"skip": "F3"}),
    # Study 9 COMBO: the same skip rule, signals from 09:31, and the strike just in the money (-$35 a day, t +2.9).
    "combo": ("qqqbot_combo", "stop after 2 losses + skip weak crosses + 9:31 start + in the money",
              {"skip": "F3", "first": "09:31", "itm": True}),
    # Study 10 ALL: picks signals the way he does (EMA9/EMA20 agree, strong candle, before 12:00, not a weak cross).
    # On 2.7 years: -$12 a day vs -$38, but keeping a RANDOM 10% of signals does as well (research/STRESS_REPORT.md):
    # the gain is from trading less, not from better picks. Kept as a comparison with his live results.
    "picks": ("qqqbot_picks", "picks like him (stop after 2 losses)", {"skip": "F3", "pick": True}),
    # "His clone": the same picks plus the exits read off his 83 posted trades: +3.5% target, -10% stop, 6-minute limit.
    "clone": ("qqqbot_clone", "his clone: picks like him + his exits (stop after 2 losses)",
              {"skip": "F3", "pick": True, "target": 0.035, "stop": 0.10, "hold_min": 6}),
    # Study 12 (research/BRAKES_REPORT.md): his brakes. Stop for the day at +$50 or -$100 (and after 2 losses in a row).
    # +$2.85 a day vs the main bot on 2.7 years, 5 of 6 stress tests; not profitable on its own.
    "brakes": ("qqqbot_brakes", "profit brake +$50 / loss brake -$100 (stop after 2 losses)",
               {"profit_brake": 50, "loss_brake": 100}),
    # Study 13 (research/NEW_ENTRIES_REPORT.md): three different kinds of entry. 5-minute crosses: still a coin flip
    # (-$16 a day). Opening move: -$2.46 a day. One-a-day options: +$14.44 a day, every year positive, beats all 20
    # placebos, but t 1.73 (just short of the 2.0 line), so not proven.
    "five": ("qqqbot_five", "5-minute crosses (stop after 2 losses)",
             {"mode": "five", "target": 0.05, "stop": 0.10, "hold_min": 30}),
    "open30": ("qqqbot_open30", "opening move at 10:00 (one a day)",
               {"mode": "open30", "target": 0.10, "stop": 0.10, "hold_min": 60}),
    "oneaday": ("qqqbot_oneaday", "one-a-day breakout on options (follows the shares bot)",
                {"mode": "follow", "target": 9.0, "stop": 0.99, "hold_min": 600, "max_losses": 0}),
}
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
                 max_losses: int | None = None, trade_messages: bool | None = None, target: float = TARGET,
                 stop: float = STOP, hold_min: float = HOLD_MIN, trail: float = 0.0, with_trend: bool = False,
                 summaries: bool = True, first: str = "09:45", itm: bool = False, skip: str | None = None,
                 pick: bool = False, profit_brake: float = 0.0, loss_brake: float = 0.0, max_spread: float = 0.0,
                 resume_wait: float = 0.0, mode: str = "cross"):
        # target/stop/hold_min: the exit rule. trail > 0: on reaching the target do not sell at once, keep the trade
        # and sell when the bid falls `trail` below its best since. with_trend: calls only while QQQ is above today's
        # opening price, puts only while below. The defaults are the tested baseline rules, unchanged.
        self.target, self.stop, self.hold_min, self.trail, self.with_trend = target, stop, hold_min, trail, with_trend
        self.summaries = summaries
        # first: earliest signal time (VWAP / 50 EMA crosses; the range break still needs 09:45). itm: buy the strike just
        # in the money instead of the nearest. skip: a Study 9 skip rule ("F1".."F5", research/HIS_FILTER_PROTOCOL.md).
        self.first, self.itm, self.skip = first, itm, skip
        # pick: Study 10's "pick like him" rule: take a signal only when EMA9 is on the trade's side of EMA20, the signal
        # candle is strong in the trade's direction (body over 60% of its range), and it is before 12:00 New York time.
        self.pick = pick
        # Study 12 (research/BRAKES_PROTOCOL.md). profit_brake / loss_brake: stop for the day once the day's result is
        # at least +$profit_brake or at most -$loss_brake (0 = off). max_spread: don't buy when the ask is more than this
        # fraction above the bid. resume_wait: don't buy for this many minutes after quotes come back from a gap of 2+
        # minutes (stale data). All off by default.
        self.profit_brake, self.loss_brake = profit_brake, loss_brake
        self.max_spread, self.resume_wait = max_spread, resume_wait
        self.last_fresh, self.resumed_at = None, None
        # Study 13 (research/NEW_ENTRIES_PROTOCOL.md) entry modes: "cross" (the usual one-minute crosses), "five"
        # (the same crosses on 5-minute candles), "open30" (the opening move at 10:00, one trade a day), "follow" (buy the
        # at-the-money option when the shares bot enters, sell when it exits; the recorder sets .pending / .follow_exit).
        self.mode = mode
        self.pending, self.follow_exit, self.prev_all = None, False, None
        self.compare = None  # optional: a function giving the other bots' lines for this bot's summaries
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
                    self.prev_all = p
                    break
            if self.prev is None:
                self.prev = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([]))
        b = self.bars_fn(now)
        b = b[(b.index.normalize() == pd.Timestamp(self.day)) & (b.index <= want)]
        self.bars = b
        if len(b) < 2 or b.index[-1] != want:
            return None
        if self.mode == "follow":
            return None
        if self.mode == "open30":
            if (want + timedelta(minutes=1)).strftime("%H:%M") != "10:00" or "open30" in self.s["range_done"]:
                return None
            self.s["range_done"].append("open30")
            mv = b.close.iloc[-1] / b.open.iloc[0] - 1
            if abs(mv) < 0.0025:
                return None
            return ("C" if mv > 0 else "P"), "OPEN30", b.close.iloc[-1], abs(mv)
        if self.mode == "five":
            return self._signal_five(b, want)
        tp = (b.high + b.low + b.close) / 3
        vol = b.volume.where(b.volume > 0, 1.0)
        vwap = (tp * vol).cumsum() / vol.cumsum()
        ema = pd.concat([self.prev.close, b.close]).ewm(span=50, adjust=False).mean().iloc[-len(b):]
        c, pc = b.close.iloc[-1], b.close.iloc[-2]
        tod = (want + timedelta(minutes=1)).strftime("%H:%M")
        if not (self.first <= tod <= LAST):
            return None
        for name, line in (("EMA50", ema), ("VWAP", vwap)):
            if pc <= line.iloc[-2] and c > line.iloc[-1]:
                return "C", name, c, abs(c - line.iloc[-1])
            if pc >= line.iloc[-2] and c < line.iloc[-1]:
                return "P", name, c, abs(c - line.iloc[-1])
        if len(b) > 15:
            hi, lo = b.high.iloc[:15].max(), b.low.iloc[:15].min()
            if c > hi and "C" not in self.s["range_done"]:
                self.s["range_done"].append("C")
                return "C", "RANGE", c, c - hi
            if c < lo and "P" not in self.s["range_done"]:
                self.s["range_done"].append("P")
                return "P", "RANGE", c, lo - c
        return None

    # ------------------------------------------------------------------ the 5-second tick
    def on_poll(self, now: datetime, rows: list[dict]):
        quotes = {(r["expiry"], r["type"], float(r["strike"])): r for r in rows}
        tod = now.strftime("%H:%M")
        if self.resume_wait:
            try:
                newest = max(pd.Timestamp(r["quote_time"]) for r in rows if r.get("quote_time"))
                if self.last_fresh is not None and (newest - self.last_fresh).total_seconds() >= 120:
                    self.resumed_at = now  # quotes just came back after a gap: treat the next minutes with suspicion
                self.last_fresh = newest if self.last_fresh is None else max(self.last_fresh, newest)
            except (ValueError, KeyError, TypeError):
                pass
        o = self.s["open"]
        if o:
            q = quotes.get((o["expiry"], o["type"], o["strike"]))
            bid = float(q["bid"]) if q and q["bid"] not in ("", None) and self._fresh(q, now) else 0.0
            age = (now.replace(tzinfo=None) - pd.Timestamp(o["t"])).total_seconds() / 60
            why = None
            if bid > 0:
                if self.trail and bid >= o["entry"] * (1 + self.target):
                    o["best"] = max(o.get("best", 0.0), bid)
                if self.trail and o.get("best"):
                    if bid <= o["best"] * (1 - self.trail):
                        why = "trail"
                    elif age >= self.hold_min or tod >= FLAT:
                        why = "time" if tod < FLAT else "end of day"
                elif not self.trail and bid >= o["entry"] * (1 + self.target):
                    why = "target"
                elif bid <= o["entry"] * (1 - self.stop):
                    why = "stop"
                elif age >= self.hold_min:
                    why = "time"
                elif tod >= FLAT:
                    why = "end of day"
            if self.mode == "follow" and self.follow_exit and bid > 0:
                why = "shares bot exit"
            if why:
                self._close(now, bid, why)
        if now.second >= 3 and tod != self.last_min:
            self.last_min = tod
            try:
                sig = self._signal(now)
                if self.mode == "follow" and self.pending and not self.s["open"] and \
                        "follow" not in self.s["range_done"]:
                    sig = self.pending
                    self.s["range_done"].append("follow")
            except Exception as exc:
                print(f"{tod} bars: {type(exc).__name__}: {str(exc)[:100]}")
                sig = None
            run = 0
            for tr in reversed(self.s["trades"]):
                if tr["pnl"] >= 0:
                    break
                run += 1
            stopped = bool(self.max_losses) and run >= self.max_losses
            day_pnl = sum(t["pnl"] for t in self.s["trades"])
            if (self.profit_brake and day_pnl >= self.profit_brake) or (self.loss_brake and day_pnl <= -self.loss_brake):
                stopped = True
            if stopped and "stopped" not in self.s["sent"]:
                self.s["sent"].append("stopped")
                self._tell(f"⏸ <b>Stopped for the day</b> after {run} losses in a row (paper). Back tomorrow.")
                self.save()
            if sig and self.skip:
                sig = self._skip_check(sig, now)
            if sig and self.pick and not self._pick_ok(sig, tod):
                sig = None
            if sig and self.with_trend and self.bars is not None and len(self.bars):
                day_open = float(self.bars.open.iloc[0])
                if (sig[0] == "C" and sig[2] <= day_open) or (sig[0] == "P" and sig[2] >= day_open):
                    sig = None  # against today's direction: skipped
            if sig and not self.s["open"] and tod < FLAT and not stopped:
                side, trig, px = sig[:3]
                today = now.strftime("%Y-%m-%d")
                exps = sorted({k[0] for k in quotes if k[0] > today})
                k = float((math.floor(px) if side == "C" else math.ceil(px)) if self.itm else round(px))
                q = quotes.get((exps[0], side, k)) if exps else None
                if q is not None and not self._fresh(q, now):
                    q = None  # stale price: don't buy on it
                ask = float(q["ask"]) if q and q["ask"] not in ("", None) else 0.0
                bid = float(q["bid"]) if q and q["bid"] not in ("", None) else 0.0
                if self.max_spread and (bid <= 0 or ask > bid * (1 + self.max_spread)):
                    ask = 0.0  # abnormal price: don't buy
                if self.resume_wait and self.resumed_at is not None and \
                        (now - self.resumed_at).total_seconds() < self.resume_wait * 60:
                    ask = 0.0  # prices only just came back: don't buy yet
                if ask >= 0.5:
                    self.s["open"] = {"t": now.strftime("%Y-%m-%d %H:%M:%S"), "type": side, "strike": k,
                                      "expiry": exps[0], "entry": ask, "trigger": trig, "qqq": round(px, 2),
                                      "stop_px": round(ask * (1 - self.stop), 2), "target_px": round(ask * (1 + self.target), 2)}
                    if self.trail:
                        self.s["open"]["trail"] = self.trail
                    print(f"{now:%H:%M:%S} BOUGHT 1x QQQ {int(k)} {'CALL' if side == 'C' else 'PUT'} @ {ask:.2f} ({trig})")
                    self._tell(f"🟢 <b>BOUGHT</b> 1× QQQ {int(k)} {'CALL' if side == 'C' else 'PUT'} @ {ask:.2f}\n"
                               f"{now:%a %m/%d · %I:%M:%S %p} ET · {trig} · paper")
                    self.save()
            self._summaries(now)

    def _signal_five(self, b, want):
        """VWAP / 50 EMA crosses on 5-minute candles, judged when a 5-minute candle has just closed."""
        t = want + timedelta(minutes=1)
        if t.minute % 5 or not (self.first <= t.strftime("%H:%M") <= LAST):
            return None
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        f = b.resample("5min", label="left", closed="left").agg(agg).dropna()
        if len(f) < 2 or f.index[-1] + timedelta(minutes=5) != t:
            return None
        prev = self.prev_all if self.prev_all is not None and len(self.prev_all) else self.prev
        pf = prev.resample("5min", label="left", closed="left").agg(agg).dropna() if len(prev) else f.iloc[:0]
        tp = (f.high + f.low + f.close) / 3
        vol = f.volume.where(f.volume > 0, 1.0)
        vwap = (tp * vol).cumsum() / vol.cumsum()
        ema = pd.concat([pf.close, f.close]).ewm(span=50, adjust=False).mean().iloc[-len(f):]
        c, pc = f.close.iloc[-1], f.close.iloc[-2]
        for name, line in (("EMA50_5", ema), ("VWAP5", vwap)):
            if pc <= line.iloc[-2] and c > line.iloc[-1]:
                return "C", name, c, abs(c - line.iloc[-1])
            if pc >= line.iloc[-2] and c < line.iloc[-1]:
                return "P", name, c, abs(c - line.iloc[-1])
        return None

    @staticmethod
    def _fresh(q: dict, now: datetime) -> bool:
        if not FRESH_QUOTES_ONLY:
            return True
        try:
            age = (pd.Timestamp(now.replace(tzinfo=None)) - pd.Timestamp(q["quote_time"])).total_seconds()
        except (KeyError, ValueError, TypeError):
            return True  # no time stamp to judge by: behave as before
        return age <= FRESH_SECONDS

    def _pick_ok(self, sig, tod: str) -> bool:
        """Study 10 ALL entries (with skip="F3" for the weak-cross part), judged on the candle that just closed."""
        b = self.bars
        if b is None or len(b) < 2 or tod >= "12:00":
            return False
        closes = pd.concat([self.prev.close, b.close]) if self.prev is not None and len(self.prev) else b.close
        e9 = closes.ewm(span=9, adjust=False).mean().iloc[-1]
        e20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
        last = b.iloc[-1]
        body, rng = float(last.close - last.open), float(last.high - last.low)
        if sig[0] == "C":
            return e9 > e20 and body > 0.6 * rng
        return e9 < e20 and -body > 0.6 * rng

    def _skip_check(self, sig, now: datetime):
        """Study 9 skip rules, judged against every earlier signal today (taken or not), as in the backtest."""
        side, px, dist = sig[0], sig[2], sig[3]
        t = (now.replace(second=0, microsecond=0, tzinfo=None)).strftime("%H:%M")
        hist = self.s.setdefault("sigs", [])
        prev = hist[-1] if hist else None
        hist.append([t, side])
        gap = None
        if prev:
            h1, m1 = map(int, prev[0].split(":"))
            h2, m2 = map(int, t.split(":"))
            gap = (h2 * 60 + m2) - (h1 * 60 + m1)
        day_open = float(self.bars.open.iloc[0]) if self.bars is not None and len(self.bars) else px
        rule = {"F1": gap is not None and gap <= 2 and prev[1] != side,
                "F2": gap is not None and gap <= 2,
                "F3": dist < 0.10,
                "F4": (side == "C" and px <= day_open) or (side == "P" and px >= day_open),
                "F5": gap is not None and gap < 5}.get(self.skip, False)
        return None if rule else sig

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
        lines.append("<i>Paper only, 1 contract a trade, bought at the real ask and sold at the real bid. "
                     + (f"Exit: keeps a winner from +{self.target:.1%} and sells {self.trail:.1%} below its best; "
                        f"stop -{self.stop:.0%}. " if self.trail else "Exit: +2.5% target, -6% stop. ")
                     + "History test: still loses (research/TREND_TRAIL_REPORT.md).</i>")
        if self.compare:
            try:
                extra = self.compare(upto)
                if extra:
                    lines += ["", "<b>Comparison bots</b> (same entries, different exits)"] + extra
            except Exception:
                pass
        return "\n".join(lines)

    def total_line(self, upto: str | None = None) -> str:
        tr = [t for t in self.s["trades"] if upto is None or t["exit_t"][11:16] < upto]
        total = sum(t["pnl"] for t in tr)
        return (f"{self.name}: {len(tr)} trades · {sum(t['pnl'] > 0 for t in tr)}W / "
                f"{sum(t['pnl'] <= 0 for t in tr)}L · <b>{total:+,.0f} USD</b>")

    def _summaries(self, now: datetime):
        if not self.summaries:
            return
        tod = now.strftime("%H:%M")
        for key, at, title in (("morning", MORNING_AT, "Morning summary"), ("day", DAY_AT, "Today's summary")):
            if tod >= at and key not in self.s["sent"] and not (key == "day" and self.s["open"]):
                if self.say(self.summary(title, MORNING_AT if key == "morning" else None)):
                    self.s["sent"].append(key)
                    self.save()
