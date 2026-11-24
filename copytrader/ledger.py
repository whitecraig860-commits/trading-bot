"""
Rebuild each trader's positions from his events. Long options only: BUY opens or adds, SELL reduces or closes.
A SELL with no open position is flagged and ignored (never turned into a short). Average-cost accounting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

MULT = 100  # one QQQ option contract = 100 shares


@dataclass
class Closed:
    trader: int
    contract: str
    qty: int
    entry: float        # average entry price of the contracts closed
    exit: float
    opened: str
    closed: str
    pnl: float          # recomputed from his prices: (exit - entry) x qty x 100 (his fees unknown, not deducted)
    reported_pnl: float | None
    partial: bool       # True if some contracts stayed open after this sale

    @property
    def hold_min(self) -> float | None:
        try:
            return (datetime.fromisoformat(self.closed) - datetime.fromisoformat(self.opened)).total_seconds() / 60
        except (TypeError, ValueError):
            return None


@dataclass
class Book:
    closed: list[Closed] = field(default_factory=list)
    open: dict = field(default_factory=dict)          # (trader, contract) -> {"qty", "avg", "opened"}
    problems: list[str] = field(default_factory=list)


def contract_key(e: dict) -> str:
    return f"QQQ {e['strike']:g}{e['right_'] if 'right_' in e else e['right']}" + (f" {e['expiry']}" if e.get("expiry") else "")


def build(events: list[dict]) -> Book:
    book = Book()
    for e in sorted(events, key=lambda x: (x.get("ts") or "", x.get("id") or 0)):
        if e.get("price") is None or e.get("qty") is None or e.get("trader") is None:
            book.problems.append(f"skipped incomplete event {e.get('id')}: {e.get('flags')}")
            continue
        key = (e["trader"], contract_key(e))
        pos = book.open.get(key)
        if e["action"] == "BUY":
            if pos:
                tot = pos["qty"] + e["qty"]
                pos["avg"] = (pos["avg"] * pos["qty"] + e["price"] * e["qty"]) / tot
                pos["qty"] = tot
            else:
                book.open[key] = {"qty": e["qty"], "avg": e["price"], "opened": e.get("ts")}
        else:
            if not pos:
                book.problems.append(f"trader {e['trader']} sold {e['qty']} {key[1]} at {e.get('ts')} with no open position "
                                     "(missed buy message?); not treated as a short")
                continue
            q = min(e["qty"], pos["qty"])
            if e["qty"] > pos["qty"]:
                book.problems.append(f"trader {e['trader']} sold {e['qty']} {key[1]} but only {pos['qty']} were open; closed {q}")
            pos["qty"] -= q
            book.closed.append(Closed(e["trader"], key[1], q, pos["avg"], e["price"], pos["opened"], e.get("ts"),
                                      round((e["price"] - pos["avg"]) * q * MULT, 2), e.get("reported_pnl"), pos["qty"] > 0))
            if pos["qty"] == 0:
                del book.open[key]
    return book
