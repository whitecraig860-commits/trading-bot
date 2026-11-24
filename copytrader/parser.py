"""
Parse QQQ Trader messages into structured events. Never guesses: anything missing or unclear is flagged.

Examples it reads (copied from the trades channel):
    BOUGHT 3x QQQ 662 CALL @ 7.51
    SOLD 12x QQQ 612 PUT @ 11.47 / +$12 (+0.1%) / Fri 11/20 - 3:43:54 PM ET
    SOLD 15× QQQ 660 PUT @ 7.29 +$525 (+5.0%) · Thu 11/19 · 10:11:13 AM ET
    QQQ Trader #1: 7 trades · 3W / 4L · +$1,737          (daily summary line)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

TRADER_RE = re.compile(r"QQQ\s*Trader\s*#\s*(\d)", re.I)
TRADE_RE = re.compile(
    r"\b(?P<action>BOUGHT|SOLD|BUY|SELL)\s+(?P<qty>\d+)\s*[x×X]\s*(?P<sym>[A-Z]{1,5})\s+(?P<strike>\d+(?:\.\d+)?)\s*"
    r"(?P<right>CALL|PUT|C|P)\b\s*@\s*\$?(?P<price>\d+(?:\.\d+)?)", re.I)
PNL_RE = re.compile(r"(?P<sign>[+\-−–])\s*\$\s*(?P<amt>[\d,]+(?:\.\d+)?)\s*\(\s*(?P<psign>[+\-−–]?)\s*(?P<pct>\d+(?:\.\d+)?)\s*%\s*\)")
AT_COST_RE = re.compile(r"\bat cost\b", re.I)
TIME_RE = re.compile(r"(?:(?P<dow>Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s*[·\-–,]?\s*)?(?P<mon>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2,4}))?"
                     r"\s*[·\-–,]?\s*(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\s*(?P<ampm>AM|PM)\s*(?P<tz>ET|EST|EDT)?", re.I)
SUMMARY_RE = re.compile(r"QQQ\s*Trader\s*#\s*(?P<tr>\d)\s*:\s*(?P<n>\d+)\s*trades?\s*[·\-–,]\s*(?P<w>\d+)\s*W\s*/\s*(?P<l>\d+)\s*L"
                        r"(?:\s*/\s*(?P<c>\d+)\s*at\s*cost)?\s*[·\-–,]\s*(?P<sign>[+\-−–])\s*\$\s*(?P<amt>[\d,]+(?:\.\d+)?)", re.I)
MINUS = "-−–"


@dataclass
class Event:
    kind: str                      # "trade" or "summary"
    trader: int | None = None
    action: str | None = None      # "BUY" or "SELL" (to open / to close; a SELL never opens a short)
    qty: int | None = None
    symbol: str | None = None
    strike: float | None = None
    right: str | None = None       # "C" or "P"
    price: float | None = None
    expiry: str | None = None      # never in his messages: stays None unless the source gives it
    reported_pnl: float | None = None
    reported_pct: float | None = None
    at_cost: bool = False
    ts: str | None = None          # time in the message, New York time, "YYYY-MM-DD HH:MM:SS"
    summary: dict | None = None
    flags: list[str] = field(default_factory=list)


def _ts(m: re.Match, default_year: int | None) -> tuple[str | None, list[str]]:
    flags = []
    year = m.group("year")
    if year:
        year = int(year) + (2000 if len(year) == 2 else 0)
    elif default_year:
        year = default_year
        flags.append("year not in message (taken from the receipt date)")
    else:
        return None, ["no year available"]
    h = int(m.group("h")) % 12 + (12 if m.group("ampm").upper() == "PM" else 0)
    s = int(m.group("s") or 0)
    if not m.group("s"):
        flags.append("time has no seconds")
    try:
        dt = datetime(year, int(m.group("mon")), int(m.group("day")), h, int(m.group("m")), s)
    except ValueError:
        return None, ["invalid date"]
    dow = m.group("dow")
    if dow and dt.strftime("%a").lower() != dow[:3].lower():
        flags.append(f"weekday {dow} does not match the date")
    return dt.strftime("%Y-%m-%d %H:%M:%S"), flags


def parse(text: str, trader_hint: int | None = None, default_year: int | None = None) -> list[Event]:
    """Parse one message (or a block of messages). `trader_hint` is the author (e.g. from Discord) if known."""
    events: list[Event] = []
    for m in SUMMARY_RE.finditer(text):
        amt = float(m.group("amt").replace(",", "")) * (-1 if m.group("sign") in MINUS else 1)
        events.append(Event(kind="summary", trader=int(m.group("tr")),
                            summary={"trades": int(m.group("n")), "wins": int(m.group("w")), "losses": int(m.group("l")),
                                     "at_cost": int(m.group("c") or 0), "pnl": amt}))
    trades = list(TRADE_RE.finditer(text))
    for i, m in enumerate(trades):
        end = trades[i + 1].start() if i + 1 < len(trades) else len(text)
        tail = text[m.end():end]
        before = text[:m.start()]
        flags: list[str] = []
        trader = trader_hint
        names = TRADER_RE.findall(before)
        if names:
            trader = int(names[-1])
        if trader is None:
            flags.append("trader unknown")
        action = {"BOUGHT": "BUY", "BUY": "BUY", "SOLD": "SELL", "SELL": "SELL"}[m.group("action").upper()]
        right = m.group("right").upper()[0]
        ev = Event(kind="trade", trader=trader, action=action, qty=int(m.group("qty")), symbol=m.group("sym").upper(),
                   strike=float(m.group("strike")), right=right, price=float(m.group("price")))
        if ev.symbol != "QQQ":
            flags.append(f"symbol {ev.symbol} is not QQQ")
        p = PNL_RE.search(tail)
        if p:
            ev.reported_pnl = float(p.group("amt").replace(",", "")) * (-1 if p.group("sign") in MINUS else 1)
            ev.reported_pct = float(p.group("pct")) * (-1 if p.group("psign") in MINUS else 1)
        if AT_COST_RE.search(tail):
            ev.at_cost = True
        if action == "SELL" and not p and not ev.at_cost:
            flags.append("sell without a reported result")
        t = TIME_RE.search(tail)
        if t:
            ev.ts, f2 = _ts(t, default_year)
            flags += f2
        else:
            flags.append("no time stamp in the message")
        flags.append("expiry not stated in the message")
        ev.flags = flags
        events.append(ev)
    return events
