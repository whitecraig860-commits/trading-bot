"""
Trump post watcher
==================
Reads Donald Trump's Truth Social posts (through the public archive at trumpstruth.org, because Truth Social
blocks automated readers) every few minutes while the market pulse runs. For each new post it looks for
market-moving topics (tariffs, China, the Fed and interest rates, oil and Iran, crypto, named companies, the
stock market itself), says which markets it could move and which way, and then checks what really happened
30 and 120 minutes later. Paper only: it never places a trade.

Honest limits:
  - It's minutes late. Big funds read these posts with machines in seconds, so the first move is usually over
    by the time a free feed shows the post. What's left is any follow-through.
  - Reading a post with keywords is rough. "China" can mean a deal or a threat. Each alert says which words it
    reacted to, and the 30/120-minute check is the real test of whether this works.
"""

from __future__ import annotations

import html
import re

FEED = "https://www.trumpstruth.org/feed"

# (name, pattern, [(market, direction, why)])  direction: +1 = likely up, -1 = likely down
RULES = [
    ("tariffs raised", r"\b(tariffs?|duties)\b.*\b(raise|raising|increase|impose|imposing|new|additional|\d+\s?%)|"
                       r"\b(impose|imposing|raise|raising)\b.*\btariffs?\b",
     [("SPY", -1, "new or higher tariffs have hit shares"), ("QQQ", -1, "tech is hit hardest by trade fights"),
      ("GC=F", +1, "gold tends to rise on trade fear")]),
    ("trade deal / tariff pause", r"\b(trade deal|deal with china|trade agreement|tariff pause|pause[ds]? (the |all )?tariffs?|"
                                  r"lower(ed|ing)? (the )?tariffs?|remove (the )?tariffs?|tariff relief|exempt(ed|ion)? from tariffs?)\b",
     [("SPY", +1, "trade deals and tariff pauses have lifted shares"), ("QQQ", +1, "tech gains most from trade relief")]),
    ("China", r"\b(china|chinese|xi jinping|president xi)\b", [("QQQ", -1, "China tension weighs on chip and tech shares")]),
    ("Fed / rates (pressure to cut)", r"\b(federal reserve|the fed|powell|interest rates?|rate cuts?|cut (interest )?rates)\b",
     [("SPY", +1, "pressure for lower rates has lifted shares"), ("GC=F", +1, "lower-rate talk tends to lift gold")]),
    ("oil / drilling", r"\b(drill|oil|opec|gasoline|energy prices?)\b", [("BZ=F", -1, "he usually wants oil prices lower")]),
    ("Iran / war / strikes", r"\b(iran|missiles?|military (action|strikes?)|air ?strikes?|bomb(ed|ing|s)?|declared? war|"
                             r"war (with|on) (iran|russia|china|venezuela))\b",
     [("BZ=F", +1, "conflict risk pushes oil up"), ("GC=F", +1, "gold is the fear trade"),
      ("SPY", -1, "war risk weighs on shares")]),
    ("crypto", r"\b(crypto|bitcoin|btc|digital assets?|strategic (bitcoin|crypto) reserve)\b",
     [("BTC-USD", +1, "his crypto posts have lifted Bitcoin")]),
    # Only when he talks the market UP ("record high", "great time to buy"). A post about a fall that has already
    # happened ("the stock market crashed today because...") says nothing about what comes next, so it's ignored.
    ("the stock market (talked up)", r"\b(great time to buy|(stock market|dow|s&p|markets?)\b[^.!?]{0,60}"
                                     r"\b(record highs?|all[- ]time highs?|booming|soaring|through the roof|up big))\b",
     [("SPY", +1, "he talks the market up")]),
]


COMPANIES = {
    "apple": "AAPL", "tesla": "TSLA", "nvidia": "NVDA", "intel": "INTC", "boeing": "BA", "amazon": "AMZN",
    "meta": "META", "facebook": "META", "google": "GOOGL", "microsoft": "MSFT", "exxon": "XOM", "walmart": "WMT",
    "general motors": "GM", "ford": "F", "lockheed": "LMT", "harley": "HOG", "netflix": "NFLX", "disney": "DIS",
}
PRAISE = re.compile(r"\b(great|tremendous|incredible|invest(ing|ment)?|thank you|congratulations|winning|"
                    r"fantastic|amazing|deal)\b", re.I)
ATTACK = re.compile(r"\b(bad|terrible|disgrace(ful)?|unfair|ashamed|boycott|fake|failing|weak|pathetic|ripped off|"
                    r"should be fired|loser)\b", re.I)


def parse_feed(xml_text: str) -> list[dict]:
    """The posts in the RSS feed, newest first: id, text, url, when (UTC timestamp or None)."""
    import xml.etree.ElementTree as ET

    import pandas as pd

    out = []
    root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link).strip()
        raw = it.findtext("description") or it.findtext("title") or ""
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        text = re.sub(r"\s+", " ", text).strip()
        when = None
        try:
            when = pd.Timestamp(it.findtext("pubDate") or "")
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
        except Exception:
            when = None
        if text:
            out.append({"id": guid, "text": text, "url": link, "when": when})
    return out


def read_post(text: str) -> list[dict]:
    """[{market, direction, why, topic}] the post could move, from keyword rules. Empty if nothing market-related."""
    t = text.lower()
    hits: dict[str, dict] = {}
    for topic, pattern, effects in RULES:
        if re.search(pattern, t):
            for market, direction, why in effects:
                if market in hits and hits[market]["direction"] != direction:
                    hits[market]["direction"] = 0  # the post points both ways for this market
                    hits[market]["why"] += f"; but also {why}"
                    continue
                hits.setdefault(market, {"market": market, "direction": direction, "why": why, "topic": topic})
    for name, sym in COMPANIES.items():
        if re.search(rf"\b{name}\b", t):
            good, bad = len(PRAISE.findall(t)), len(ATTACK.findall(t))
            if good != bad:
                d = 1 if good > bad else -1
                hits[sym] = {"market": sym, "direction": d, "topic": name.title(),
                             "why": f"he {'praised' if d > 0 else 'attacked'} {name.title()}"}
    return [h for h in hits.values() if h["direction"] != 0]
