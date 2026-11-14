"""
QQQ SHARES paper bot: the owner's "one trade a day" rule, on paper, in QQQ shares
=================================================================================
Study 6 (research/ONE_A_DAY_REPORT.md) found this entry rule made money on QQQ SHARES over 2.7 years (t 2.7) but not
reliably on options. This runs it forward on paper to see whether it keeps working. It never places an order: it
keeps a ledger at real prices. It runs inside the price recorder, separately from the options bot; if it errors,
nothing else is affected. Switch it off with ENABLED = False.

Rules (exactly as tested; research/ONE_A_DAY_PROTOCOL.md section 2):
  - mark the 09:30-09:45 high and low
  - check the 1-minute candles closing at 10:00, 10:10 ... 14:00
  - BUY when a candle closes above the range high + 0.3 ATR (14 x 5-minute), above VWAP and above the noise band;
    SELL SHORT when it closes below all three. At most one trade a day.
  - exit: 10 ATR against it; or once 4 ATR in profit, if it gives back half; otherwise at 15:45
  - size: a notional £1,000 account, fractional shares; 1 cent per share slippage each way
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ENABLED = True
STATE = Path(__file__).resolve().parent.parent / "state" / "sharesbot"
ACCOUNT_GBP, GBP_USD, SLIP = 1000.0, 1.0 / 0.76, 0.01


def history_bars(stock_client, now: datetime) -> pd.DataFrame:
    """The previous ~20 sessions of 1-minute QQQ bars (for the noise band)."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    end = now.replace(hour=9, minute=0, second=0, microsecond=0)
    df = stock_client.get_stock_bars(StockBarsRequest(symbol_or_symbols="QQQ", timeframe=TimeFrame.Minute,
                                                      start=end - timedelta(days=35), end=end, feed=DataFeed.SIP)).df
    d = df.xs("QQQ", level=0)[["open", "high", "low", "close", "volume"]].astype(float)
    d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").tz_localize(None)
    return d.between_time("09:30", "15:59")


class SharesBot:
    def __init__(self, bars_fn, hist_fn, now: datetime, say, state_dir: Path = STATE):
        self.bars_fn, self.say, self.dir = bars_fn, say, state_dir
        self.day = now.strftime("%Y-%m-%d")
        self.path = self.dir / f"{self.day}.json"
        self.s = {"trade": None, "done": False, "sent": [], "checked": []}
        if self.path.exists():
            self.s.update(json.loads(self.path.read_text()))
        self.sigma = None
        self.prev = pd.DataFrame()
        self.hist_fn = hist_fn
        self.last_min = None

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.s, indent=1))

    def _noise(self, now):
        if self.sigma is None:
            h = self.hist_fn(now)
            h = h[h.index.normalize() < pd.Timestamp(self.day)]
            day = h.index.normalize()
            mod = h.index.hour * 60 + h.index.minute
            piv = pd.Series(h.close.to_numpy(), index=[day, mod]).unstack()
            opens = h.open.groupby(day).first()
            self.sigma = piv.div(opens, axis=0).sub(1).abs().tail(14).mean()
            self.prev = h[h.index.normalize() == h.index.normalize().max()] if len(h) else h
        return self.sigma

    def on_poll(self, now: datetime):
        tod = now.strftime("%H:%M")
        if now.second < 3 or tod == self.last_min:
            return
        self.last_min = tod
        if self.s["done"] and not self.s["trade"]:
            return
        b = self.bars_fn(now)
        b = b[b.index.normalize() == pd.Timestamp(self.day)]
        b = b[b.index <= now.replace(second=0, microsecond=0, tzinfo=None) - timedelta(minutes=1)]
        if len(b) < 20:
            return
        t = self.s["trade"]
        if t and not t.get("exit"):
            self._manage(now, b)
            return
        if self.s["done"] or not ("10:00" <= tod <= "14:00") or not tod.endswith("0") or tod in self.s["checked"]:
            return
        self.s["checked"].append(tod)
        orb = b.iloc[:15]
        hi, lo, o = orb.high.max(), orb.low.min(), b.open.iloc[0]
        sg = self._noise(now).get(b.index[-1].hour * 60 + b.index[-1].minute)
        f = pd.concat([self.prev, b]).resample("5min").agg({"high": "max", "low": "min", "close": "last"}).dropna()
        pc = f.close.shift(1)
        tr = pd.concat([f.high - f.low, (f.high - pc).abs(), (f.low - pc).abs()], axis=1).max(axis=1)
        atr = tr.iloc[:-1].tail(14).mean() if len(f) > 15 else None  # completed 5-minute candles, carried from yesterday
        if atr is None or sg is None or sg != sg:
            self.save()
            return
        tp = (b.high + b.low + b.close) / 3
        vw = float((tp * b.volume).sum() / b.volume.sum()) if b.volume.sum() > 0 else float(b.close.mean())
        c = float(b.close.iloc[-1])
        side = 1 if (c > hi + 0.3 * atr and c > vw and c > o * (1 + sg)) else \
            -1 if (c < lo - 0.3 * atr and c < vw and c < o * (1 - sg)) else 0
        if side:
            px = c + SLIP * side
            qty = round(ACCOUNT_GBP * GBP_USD / px, 4)
            self.s["trade"] = {"side": side, "t": now.strftime("%Y-%m-%d %H:%M:%S"), "entry": px, "qty": qty,
                               "atr": atr, "best": 0.0}
            self.s["done"] = True
            self.say(f"🟢 <b>{'BOUGHT' if side > 0 else 'SOLD SHORT'}</b> {qty:g} QQQ shares @ {px:.2f}\n"
                     f"{now:%a %m/%d · %I:%M %p} ET · one-a-day rule · paper (£1,000 account)")
        self.save()

    def _manage(self, now, b):
        t = self.s["trade"]
        c = float(b.close.iloc[-1])
        fav = (c - t["entry"]) * t["side"]
        t["best"] = max(t["best"], fav)
        why = "safety stop" if fav <= -10 * t["atr"] else \
            "trail" if t["best"] >= 4 * t["atr"] and fav <= t["best"] / 2 else \
            "time" if now.strftime("%H:%M") >= "15:45" else None
        if why:
            px = c - SLIP * t["side"]
            pnl = (px - t["entry"]) * t["side"] * t["qty"]
            t.update(exit=px, exit_t=now.strftime("%Y-%m-%d %H:%M:%S"), why=why, pnl_usd=round(pnl, 2))
            self.say(f"🔴 <b>{'SOLD' if t['side'] > 0 else 'BOUGHT BACK'}</b> {t['qty']:g} QQQ shares @ {px:.2f}\n"
                     f"<b>{'+' if pnl >= 0 else '−'}£{abs(pnl) / GBP_USD:,.2f}</b> ({fav / t['entry']:+.2%}) · "
                     f"{now:%I:%M %p} ET · {why} · paper")
        self.save()

    def finish(self, now):
        """End of a recording run. An open trade carries over to the next run (same day); after 15:45 it is closed."""
        self.save()
