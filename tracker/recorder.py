"""
Records real QQQ option buying and selling prices (bid and ask), once a minute
==============================================================================
Why: Alpaca keeps no history of option quotes, so there was no way to test a fast options strategy with realistic
fills (buy at the ask, sell at the bid). This saves that history from now on. It only READS market data: it never
places an order and never touches the trading account.

Each minute it saves, for QQQ options expiring today and on the next expiry, with strikes within $10 of the share
price: bid, ask, sizes, the time of that quote, the last trade, and the QQQ share price.

  python tracker/recorder.py --session am     09:30-13:05 New York time
  python tracker/recorder.py --session pm     12:45-16:20 New York time
  python tracker/recorder.py --test           3 quick polls right now, printed, nothing saved
"""

from __future__ import annotations

import argparse
import csv
import gzip
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
# Free Alpaca option quotes can arrive up to 15 minutes late, so each session runs 20 minutes past its end and
# the two overlap; every row keeps the time the quote was actually made (quote_time).
SESSIONS = {"am": ((9, 30), (13, 5)), "pm": ((12, 45), (16, 20))}
OUT = Path(__file__).resolve().parent.parent / "state" / "quotes"
FIELDS = ["poll_time", "contract", "expiry", "type", "strike", "bid", "ask", "bid_size", "ask_size", "quote_time",
          "last", "last_time", "qqq", "feed"]
WIDTH = 10  # dollars either side of the share price


def parse(contract: str) -> tuple[str, str, float]:
    """QQQ261112C00695000 -> ('2026-11-12', 'C', 695.0)"""
    body = contract[-15:]
    return f"20{body[0:2]}-{body[2:4]}-{body[4:6]}", body[6], int(body[7:]) / 1000


class Feed:
    def __init__(self):
        from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient

        key, secret = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]
        self.opt = OptionHistoricalDataClient(key, secret)
        self.stk = StockHistoricalDataClient(key, secret)
        self.feed = None  # 'opra' (real exchange quotes) if the account has it, otherwise 'indicative'

    def spot(self) -> float:
        from alpaca.data.requests import StockLatestTradeRequest

        return float(self.stk.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols="QQQ"))["QQQ"].price)

    def chain(self, spot: float, today) -> dict:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionChainRequest

        order = [self.feed] if self.feed else ["opra", "indicative"]
        last = None
        for name in order:
            try:
                snaps = self.opt.get_option_chain(OptionChainRequest(
                    underlying_symbol="QQQ", feed=OptionsFeed(name), strike_price_gte=spot - WIDTH,
                    strike_price_lte=spot + WIDTH, expiration_date_gte=today,
                    expiration_date_lte=today + timedelta(days=5)))
                self.feed = name
                return snaps
            except Exception as exc:
                last = exc
        raise last


def rows(feed: Feed, now: datetime) -> list[dict]:
    spot = feed.spot()
    snaps = feed.chain(spot, now.date())
    expiries = sorted({parse(c)[0] for c in snaps})[:2]
    out = []
    for c, s in snaps.items():
        exp, typ, strike = parse(c)
        if exp not in expiries:
            continue
        q, t = s.latest_quote, s.latest_trade
        out.append({"poll_time": now.strftime("%Y-%m-%d %H:%M:%S"), "contract": c, "expiry": exp, "type": typ,
                    "strike": strike, "bid": getattr(q, "bid_price", ""), "ask": getattr(q, "ask_price", ""),
                    "bid_size": getattr(q, "bid_size", ""), "ask_size": getattr(q, "ask_size", ""),
                    "quote_time": q.timestamp.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S") if q else "",
                    "last": getattr(t, "price", ""),
                    "last_time": t.timestamp.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S") if t else "",
                    "qqq": round(spot, 2), "feed": feed.feed})
    return sorted(out, key=lambda r: (r["expiry"], r["strike"], r["type"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", choices=list(SESSIONS))
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    now = datetime.now(NY)
    feed = Feed()
    if a.test:
        for i in range(3):
            r = rows(feed, datetime.now(NY))
            print(f"poll {i + 1}: {len(r)} contracts, feed {feed.feed}, QQQ {r[0]['qqq'] if r else '?'}")
            for x in r[:: max(1, len(r) // 6)][:6]:
                print("  ", x["contract"], "bid", x["bid"], "ask", x["ask"], "quoted", x["quote_time"])
            time.sleep(5)
        return 0
    (h0, m0), (h1, m1) = SESSIONS[a.session]
    start = now.replace(hour=h0, minute=m0, second=0, microsecond=0)
    end = now.replace(hour=h1, minute=m1, second=0, microsecond=0)
    if now.weekday() >= 5:
        print("Weekend: nothing to record.")
        return 0
    # Two start times are scheduled (US summer and winter clocks); only the one near the session start runs.
    if not (start - timedelta(minutes=30) <= now <= start + timedelta(minutes=25)):
        print(f"Started at {now:%H:%M} New York time, not near {start:%H:%M}: leaving it to the other scheduled start.")
        return 0
    while datetime.now(NY) < start:
        time.sleep(5)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{now:%Y-%m-%d}-{a.session}.csv.gz"
    polls = errors = saved = 0
    seen_today = False
    with gzip.open(path, "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        while (t := datetime.now(NY)) < end:
            polls += 1
            try:
                r = rows(feed, t)
                today = t.strftime("%Y-%m-%d")
                seen_today = seen_today or any(x["quote_time"].startswith(today) for x in r)
                if polls >= 30 and not seen_today:
                    print("No quotes dated today after 30 minutes (market holiday?): stopping.")
                    break
                w.writerows(r)
                f.flush()
                saved += len(r)
            except Exception as exc:
                errors += 1
                print(f"{t:%H:%M:%S} poll failed: {type(exc).__name__}: {str(exc)[:120]}")
            nxt = (datetime.now(NY) + timedelta(minutes=1)).replace(second=2, microsecond=0)
            time.sleep(max(1.0, (nxt - datetime.now(NY)).total_seconds()))
    if saved == 0 or not seen_today:
        path.unlink(missing_ok=True)
    print(f"Session {a.session}: {polls} polls, {errors} failed, {saved} rows saved, feed {feed.feed}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
