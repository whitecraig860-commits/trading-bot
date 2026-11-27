"""
Records real QQQ option buying and selling prices (bid and ask), once a minute
==============================================================================
Why: Alpaca keeps no history of option quotes, so there was no way to test a fast options strategy with realistic
fills (buy at the ask, sell at the bid). This saves that history from now on. It only READS market data: it never
places an order and never touches the trading account.

Every 5 seconds it saves, for QQQ options expiring today and on the next expiry, with strikes within $6 of the share
price: bid, ask, sizes, the time of that quote, the last trade, and the QQQ share price.

  python tracker/recorder.py           record from now (or the 09:30 open) for up to 200 minutes, or until 16:20
  python tracker/recorder.py --test    3 quick polls right now, printed, nothing saved
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
MAX_MINUTES = 200   # one run; the workflow starts the next one, so a whole day is covered within GitHub's time limit
EVERY = 5           # seconds between polls
OUT = Path(__file__).resolve().parent.parent / "state" / "quotes"
FIELDS = ["poll_time", "contract", "expiry", "type", "strike", "bid", "ask", "bid_size", "ask_size", "quote_time",
          "last", "last_time", "qqq", "feed"]
WIDTH = 6  # dollars either side of the share price


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


def holiday_decision(polls: int, seen_today: bool, shares_trading) -> str:
    """CC-002 (audit/CHANGE_CONTROL.md). After 30 minutes (360 polls) with no option quote dated today, check every 5
    minutes whether QQQ shares are trading today. "stop" only on a real holiday; "wait" while the option feed is stale
    but the market is open (19 Nov 2026: stale until 10:30); "go" otherwise. If the check itself fails: "wait"."""
    if seen_today or polls < 360 or polls % 60:
        return "go"
    try:
        return "wait" if shares_trading() else "stop"
    except Exception:
        return "wait"


def main() -> int:
    ap = argparse.ArgumentParser()
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
    if now.weekday() >= 5:
        print("Weekend: nothing to record.")
        return 0
    open_, close = now.replace(hour=9, minute=30, second=0, microsecond=0), now.replace(hour=16, minute=20, second=0, microsecond=0)
    if now < open_ - timedelta(minutes=40) or now >= close - timedelta(minutes=5):
        print(f"{now:%H:%M} New York time is outside recording hours (09:30-16:20).")
        return 0
    while datetime.now(NY) < open_:
        time.sleep(5)
    begin = datetime.now(NY)
    end = min(begin + timedelta(minutes=MAX_MINUTES), close)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{begin:%Y-%m-%d-%H%M}.csv.gz"
    polls = errors = saved = 0
    seen_today = False
    bot, last_rows = None, []
    try:  # the paper bot rides on the same prices; if it breaks, recording carries on without it
        import qqqbot

        bot = qqqbot.PaperBot(qqqbot.alpaca_bars(feed.stk), begin, name="stop after 2 losses", key="options")
    except Exception as exc:
        print(f"Paper bot not started: {type(exc).__name__}: {str(exc)[:120]}")
    original = None
    ORIGINAL_ENABLED = False  # CC-006: the original (no loss stop) bot is retired; its code and history are kept
    try:  # the original rules with no loss stop, run side by side for comparison (summaries only, no trade messages)
        if ORIGINAL_ENABLED:
            original = qqqbot.PaperBot(qqqbot.alpaca_bars(feed.stk), begin, state_dir=qqqbot.STATE.parent / "qqqbot_original",
                                       name="original, no loss stop", max_losses=0, trade_messages=False)
    except Exception as exc:
        print(f"Original paper bot not started: {type(exc).__name__}: {str(exc)[:120]}")
    extras = {}
    for key, (folder, name, settings) in (qqqbot.EXTRA_BOTS.items() if bot else []):
        try:  # comparison bots: same entries, different exits; each in its own try so one can never stop another
            extras[key] = qqqbot.PaperBot(qqqbot.alpaca_bars(feed.stk), begin, state_dir=qqqbot.STATE.parent / folder,
                                          name=name, trade_messages=False, summaries=False, key=key, **settings)
        except Exception as exc:
            print(f"Comparison bot {key} not started: {type(exc).__name__}: {str(exc)[:120]}")
    if bot and extras:
        bot.compare = lambda upto: [b.total_line(upto) for k, b in extras.items() if not k.endswith("_ctx")]  # twins: page only
    nb = extras.get("news")
    if nb is not None:
        try:  # free headlines for the news bot (tracker/newsfeed.py); a failure only means no new headlines
            import newsfeed

            nb.news_fn = newsfeed.Feed().get
        except Exception as exc:
            print(f"News feed not started: {type(exc).__name__}")
    controls = None
    try:  # the owner's pause switch (tracker/controls.py); every bot checks it before opening a trade
        import controls as controls_mod

        controls = controls_mod.Controls()
        for b in [bot, *extras.values()]:
            if b is not None:
                b.controls = controls.check
    except Exception as exc:
        print(f"Pause switch not available: {type(exc).__name__}")
    live = None
    try:  # the live web page; never affects recording or the bots
        import livepage

        live = livepage.Publisher()
    except Exception as exc:
        print(f"Live page not started: {type(exc).__name__}")
    shares = None
    try:  # the separate one-a-day SHARES paper bot; an error here never affects anything else
        import sharesbot

        if sharesbot.ENABLED:
            shares = sharesbot.SharesBot(qqqbot.alpaca_bars(feed.stk), lambda n: sharesbot.history_bars(feed.stk, n),
                                         begin, qqqbot.send_telegram)
    except Exception as exc:
        print(f"Shares bot not started: {type(exc).__name__}: {str(exc)[:120]}")
    shares_ctx = None
    try:  # its "+context" twin (research/CONTEXT_TWINS_PROTOCOL.md): no Telegram messages, own state folder
        if shares and getattr(qqqbot, "CONTEXT_TWINS", False):
            shares_ctx = sharesbot.SharesBot(qqqbot.alpaca_bars(feed.stk), lambda n: sharesbot.history_bars(feed.stk, n),
                                             begin, lambda m: None, state_dir=sharesbot.STATE.parent / "sharesbot_ctx",
                                             ctx_gate=True, key="shares_ctx")
        for b in (shares, shares_ctx):
            if b is not None and controls is not None:
                b.controls = controls.check
    except Exception as exc:
        print(f"Shares twin not started: {type(exc).__name__}: {str(exc)[:120]}")
    with gzip.open(path, "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        while (t := datetime.now(NY)) < end:
            polls += 1
            try:
                r = rows(feed, t)
                today = t.strftime("%Y-%m-%d")
                seen_today = seen_today or any(x["quote_time"].startswith(today) for x in r)
                decision = holiday_decision(polls, seen_today, lambda: len(qqqbot.alpaca_bars(feed.stk)(t)) > 0)
                if decision == "stop":
                    print("No quotes dated today after 30 minutes and no QQQ trading today (market holiday): stopping.")
                    break
                if decision == "wait":
                    print(f"{t:%H:%M} option quotes still stale but QQQ is trading: waiting for fresh quotes.")
                w.writerows(r)
                f.flush()
                saved += len(r)
                last_rows = r
                if bot and seen_today:
                    try:
                        bot.on_poll(t, r)
                    except Exception as exc:
                        print(f"{t:%H:%M:%S} paper bot: {type(exc).__name__}: {str(exc)[:120]}")
                if original and seen_today:
                    try:
                        original.on_poll(t, r)
                    except Exception as exc:
                        print(f"{t:%H:%M:%S} original bot: {type(exc).__name__}: {str(exc)[:120]}")
                for key, xb in (extras.items() if seen_today else []):
                    try:
                        xb.on_poll(t, r)
                    except Exception as exc:
                        print(f"{t:%H:%M:%S} comparison bot {key}: {type(exc).__name__}: {str(exc)[:120]}")
                for sb, nm in ((shares, "shares bot"), (shares_ctx, "shares twin")):
                    if sb and seen_today:
                        try:
                            sb.on_poll(t)
                        except Exception as exc:
                            print(f"{t:%H:%M:%S} {nm}: {type(exc).__name__}: {str(exc)[:120]}")
                for fk in ("oneaday", "oneaday_ctx"):
                    fb = extras.get(fk)
                    if fb and shares:  # the options copies of the shares bot's one-a-day trade (the twin adds its own check)
                        try:
                            st = shares.s.get("trade") or {}
                            if st and not st.get("exit") and fb.pending is None:
                                fb.pending = ("C" if st["side"] > 0 else "P", "ONEADAY", float(st["entry"]), 1.0)
                            if st and st.get("exit"):
                                fb.follow_exit = True
                        except Exception as exc:
                            print(f"{t:%H:%M:%S} one-a-day options bot {fk}: {type(exc).__name__}: {str(exc)[:120]}")
                if live and seen_today and live.due():
                    try:
                        live.publish(livepage.payload(t, bot, shares, original, extras, shares_ctx=shares_ctx,
                                                      controls=controls, poll_errors=errors))
                    except Exception as exc:
                        print(f"{t:%H:%M:%S} live page: {type(exc).__name__}")
            except Exception as exc:
                errors += 1
                print(f"{t:%H:%M:%S} poll failed: {type(exc).__name__}: {str(exc)[:120]}")
            time.sleep(max(0.5, EVERY - (datetime.now(NY) - t).total_seconds()))
    for key, xb in (extras.items() if seen_today else []):
        try:  # before the main bot finishes, so its summary sees their final totals
            xb.finish(datetime.now(NY), last_rows)
        except Exception as exc:
            print(f"Comparison bot {key} finish: {type(exc).__name__}: {str(exc)[:120]}")
    if original and seen_today:
        try:
            original.finish(datetime.now(NY), last_rows)
        except Exception as exc:
            print(f"Original bot finish: {type(exc).__name__}: {str(exc)[:120]}")
    if bot and seen_today:
        try:
            bot.finish(datetime.now(NY), last_rows)
        except Exception as exc:
            print(f"Paper bot finish: {type(exc).__name__}: {str(exc)[:120]}")
    if saved == 0 or not seen_today:
        path.unlink(missing_ok=True)
    print(f"Recorded {begin:%H:%M}-{datetime.now(NY):%H:%M}: {polls} polls, {errors} failed, {saved} rows saved, feed {feed.feed}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
