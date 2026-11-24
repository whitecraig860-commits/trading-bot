"""
Message sources. All are authorised: the Discord one only works with a bot token the server admin has approved.
No self-bot, no personal login, no scraping.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .parser import Event, parse
from .store import Store


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def import_text(store: Store, path: Path, default_year: int | None = None) -> tuple[int, int]:
    """A text file of copied messages; messages separated by blank lines. Returns (messages stored, events)."""
    blocks = [b.strip() for b in Path(path).read_text(encoding="utf-8").split("\n\n") if b.strip()]
    n = ev = 0
    year = default_year or datetime.now().year
    last_trader = None
    for b in blocks:
        evs = parse(b, trader_hint=last_trader, default_year=year)
        for e in evs:
            if e.trader is not None:
                last_trader = e.trader
        if store.add_message(b, "text-import", now_utc(), evs) is not None:
            n += 1
            ev += len(evs)
    return n, ev


def import_transcribed_csv(store: Store, path: Path) -> tuple[int, int]:
    """Trades transcribed from screen recordings (state/discord_trades.csv): each row is one buy and one sell."""
    n = ev = 0
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("trader"):
                continue  # rows without a trader number (11 Nov story screenshots) cannot be attributed
            tr = int(float(r["trader"]))
            raw = f"QQQ Trader #{tr}: BOUGHT {r['qty']}x QQQ {r['strike']} {'CALL' if r['type'] == 'C' else 'PUT'} @ {r['buy']} " \
                  f"{r['date']} {r['buy_time']} / SOLD @ {r['sell']} {r['sell_time']}"
            flags = ["transcribed from a screen recording (not the original message)"]
            buy = Event(kind="trade", trader=tr, action="BUY", qty=int(r["qty"]), symbol="QQQ", strike=float(r["strike"]),
                        right=r["type"], price=float(r["buy"]), expiry=r.get("expiry") or None,
                        ts=f"{r['date']} {r['buy_time']}", flags=flags + ["expiry from the transcription"])
            sell = Event(kind="trade", trader=tr, action="SELL", qty=int(r["qty"]), symbol="QQQ", strike=float(r["strike"]),
                         right=r["type"], price=float(r["sell"]), expiry=r.get("expiry") or None,
                         ts=f"{r['date']} {r['sell_time']}", flags=flags + ["expiry from the transcription"])
            if store.add_message(raw, "transcribed-csv", now_utc(), [buy, sell]) is not None:
                n += 1
                ev += 2
    return n, ev


class DiscordBotSource:
    """Reads a channel with Discord's official bot API. Needs DISCORD_BOT_TOKEN (a bot the server admin invited, with
    View Channel + Read Message History) and DISCORD_CHANNEL_ID, both as environment variables / GitHub secrets."""

    API = "https://discord.com/api/v10"

    def __init__(self, token: str | None = None, channel_id: str | None = None):
        self.token = token or os.environ.get("DISCORD_BOT_TOKEN")
        self.channel = channel_id or os.environ.get("DISCORD_CHANNEL_ID")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.channel)

    def fetch(self, store: Store, limit: int = 100) -> tuple[int, int]:
        if not self.configured:
            raise RuntimeError("Discord bot not configured: waiting for the server admin to approve an authorised bot.")
        import requests

        params = {"limit": limit}
        after = store.last_source_id("discord-bot")
        if after:
            params["after"] = after
        r = requests.get(f"{self.API}/channels/{self.channel}/messages", params=params,
                         headers={"Authorization": f"Bot {self.token}"}, timeout=15)
        if r.status_code in (401, 403):
            raise RuntimeError(f"Discord refused access ({r.status_code}): the bot is not authorised for this channel.")
        r.raise_for_status()
        n = ev = 0
        for m in sorted(r.json(), key=lambda x: int(x["id"])):
            text = m.get("content") or ""
            for emb in m.get("embeds", []):  # trade bots often post embeds
                text += "\n" + "\n".join(filter(None, [emb.get("title"), emb.get("description")] +
                                                [f"{f.get('name')} {f.get('value')}" for f in emb.get("fields", [])]))
            author = (m.get("author") or {}).get("username", "")
            hint = None
            for k in ("1", "2", "3"):
                if f"#{k}" in author:
                    hint = int(k)
            posted = m.get("timestamp")
            year = int(posted[:4]) if posted else None
            evs = parse(f"{author}\n{text}", trader_hint=hint, default_year=year)
            if store.add_message(text, "discord-bot", now_utc(), evs, source_id=m["id"], author=author,
                                 posted_at=posted) is not None:
                n += 1
                ev += len(evs)
        return n, ev
