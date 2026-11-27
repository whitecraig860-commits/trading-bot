"""
Free headlines for the news bot: Alpaca news (QQQ, SPY and the 8 biggest QQQ holdings), fetched at most once a minute.
Read-only. If the feed fails, the bot simply sees no new headlines (it never invents any).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

SYMS = "QQQ,SPY,AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AVGO"


class Feed:
    def __init__(self):
        self.items, self.seen, self.last, self.error, self.ok_at = [], set(), 0.0, None, None

    def get(self) -> list[dict]:
        """Headlines from the last hour: {"id", "t" (New York time, naive), "h", "sym", "src"}."""
        if time.time() - self.last >= 60:
            self.last = time.time()
            try:
                from zoneinfo import ZoneInfo

                from alpaca.data.historical.news import NewsClient
                from alpaca.data.requests import NewsRequest

                cli = NewsClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
                res = cli.get_news(NewsRequest(symbols=SYMS, start=datetime.now(timezone.utc) - timedelta(minutes=60), limit=50))
                for n in (res.data.get("news", []) if hasattr(res, "data") else []):
                    if n.id in self.seen:
                        continue
                    self.seen.add(n.id)
                    t = n.created_at.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
                    self.items.append({"id": n.id, "t": t, "h": n.headline, "sym": list(n.symbols), "src": n.source})
                self.error, self.ok_at = None, time.time()
            except Exception as exc:
                self.error = type(exc).__name__
                print(f"News feed: {self.error}")
        cut = datetime.now() - timedelta(hours=2)
        self.items = [x for x in self.items if x["t"] >= cut] if len(self.items) > 500 else self.items
        return self.items
