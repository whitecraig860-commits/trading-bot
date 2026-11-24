"""SQLite store: raw messages (never altered), parsed events, and flags. One file, free, no server."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .parser import Event

DEFAULT_DB = Path(__file__).resolve().parent.parent / "state" / "copytrader" / "copytrader.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,            -- 'discord-bot', 'text-import', 'transcribed-csv', ...
    source_id TEXT,                  -- e.g. the Discord message id
    author TEXT,
    posted_at TEXT,                  -- when the source says it was posted (UTC ISO, milliseconds if given)
    received_at TEXT NOT NULL,       -- when we read it (UTC ISO)
    raw TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE        -- the same message is stored once
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id),
    kind TEXT NOT NULL,
    trader INTEGER, action TEXT, qty INTEGER, symbol TEXT, strike REAL, right_ TEXT, price REAL, expiry TEXT,
    reported_pnl REAL, reported_pct REAL, at_cost INTEGER, ts TEXT, summary TEXT, flags TEXT
);
CREATE INDEX IF NOT EXISTS ev_trader_ts ON events(trader, ts);
"""


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path) if str(path) != ":memory:" else path
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.executescript(SCHEMA)

    def add_message(self, raw: str, source: str, received_at: str, events: list[Event], source_id: str | None = None,
                    author: str | None = None, posted_at: str | None = None) -> int | None:
        """Store a message and its parsed events. Returns the message id, or None if it was already stored."""
        h = hashlib.sha256(f"{source}|{source_id}|{raw}".encode()).hexdigest()
        cur = self.db.execute("SELECT id FROM messages WHERE hash = ?", (h,))
        if cur.fetchone():
            return None
        cur = self.db.execute("INSERT INTO messages (source, source_id, author, posted_at, received_at, raw, hash) "
                              "VALUES (?,?,?,?,?,?,?)", (source, source_id, author, posted_at, received_at, raw, h))
        mid = cur.lastrowid
        for e in events:
            self.db.execute("INSERT INTO events (message_id, kind, trader, action, qty, symbol, strike, right_, price, expiry, "
                            "reported_pnl, reported_pct, at_cost, ts, summary, flags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (mid, e.kind, e.trader, e.action, e.qty, e.symbol, e.strike, e.right, e.price, e.expiry,
                             e.reported_pnl, e.reported_pct, int(e.at_cost), e.ts, json.dumps(e.summary) if e.summary else None,
                             json.dumps(e.flags)))
        self.db.commit()
        return mid

    def trade_events(self, trader: int | None = None) -> list[dict]:
        q = ("SELECT e.*, m.source, m.posted_at, m.received_at FROM events e JOIN messages m ON m.id = e.message_id "
             "WHERE e.kind = 'trade'" + (" AND e.trader = ?" if trader is not None else "") + " ORDER BY e.ts, e.id")
        cur = self.db.execute(q, (trader,) if trader is not None else ())
        cols = [c[0] for c in cur.description]
        out = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["flags"] = json.loads(d["flags"] or "[]")
            out.append(d)
        return out

    def summaries(self) -> list[dict]:
        cur = self.db.execute("SELECT e.trader, e.summary, m.posted_at, m.received_at FROM events e JOIN messages m "
                              "ON m.id = e.message_id WHERE e.kind = 'summary' ORDER BY e.id")
        return [{"trader": t, **json.loads(s), "posted_at": p, "received_at": r} for t, s, p, r in cur.fetchall()]

    def last_source_id(self, source: str) -> str | None:
        cur = self.db.execute("SELECT source_id FROM messages WHERE source = ? AND source_id IS NOT NULL "
                              "ORDER BY CAST(source_id AS INTEGER) DESC LIMIT 1", (source,))
        r = cur.fetchone()
        return r[0] if r else None
