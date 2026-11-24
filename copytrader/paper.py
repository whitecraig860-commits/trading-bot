"""
Phase 2: our paper mirror of each trader, kept separate from his own positions.

Rules (v1, stated in plain English in ARCHITECTURE.md):
- When a trader goes from no position to a position in a contract, we buy `size` contracts of it.
- His scale-ins and partial exits do not change our size; when he is fully out, we sell all of ours.
- Prices: our recorded bid/ask when a fresh quote (<= 60 s old) exists at the moment we would act (his message time plus
  `delay_s`): buy at the ask, sell at the bid. Otherwise his own price is used and the trade is marked "unverified price".
- Expiry: inferred from our recorded quotes (the expiry whose middle price is closest to his price, within $0.30); else unknown.
- Risk: we stop copying a trader for the rest of the day once our paper loss on him that day reaches `daily_loss_limit` ($).
  Optional per-trade stop `stop_usd`: closed at the first fresh bid at or below entry - stop_usd/100 (needs recorded quotes).
- Fees: `fee` dollars per contract per side.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

QUOTES = Path(__file__).resolve().parent.parent / "state" / "quotes"


class QuoteBook:
    """Our recorded 5-second option quotes, loaded per day on demand."""

    def __init__(self, folder: Path = QUOTES):
        self.folder, self.cache = folder, {}

    def day(self, d: str):
        if d not in self.cache:
            fs = sorted(self.folder.glob(f"{d}*.csv.gz"))
            self.cache[d] = pd.concat([pd.read_csv(gzip.open(f), dtype={"expiry": str}) for f in fs]) if fs else None
        return self.cache[d]

    def quote(self, ts: str, strike: float, right: str, expiry: str | None, ref_price: float | None):
        """(bid, ask, expiry, inferred) from the last poll at or before ts with a fresh quote, or None."""
        q = self.day(ts[:10])
        if q is None:
            return None
        g = q[(q.strike == float(strike)) & (q.type == right) & (q.poll_time <= ts)]
        if g.empty:
            return None
        last = g[g.poll_time == g.poll_time.max()]
        last = last[(pd.to_datetime(last.poll_time) - pd.to_datetime(last.quote_time)).dt.total_seconds() <= 60]
        if (pd.Timestamp(ts) - pd.Timestamp(g.poll_time.max())).total_seconds() > 30 or last.empty:
            return None
        inferred = False
        if expiry:
            last = last[last.expiry == expiry]
        elif ref_price is not None:
            last = last.assign(gap=((last.bid + last.ask) / 2 - ref_price).abs()).sort_values("gap")
            last = last[last.gap <= 0.30].head(1)
            inferred = True
        else:
            return None
        if last.empty:
            return None
        r = last.iloc[0]
        return float(r.bid), float(r.ask), str(r.expiry), inferred


@dataclass
class PaperTrade:
    trader: int
    contract: str
    expiry: str | None
    expiry_inferred: bool
    qty: int
    entry: float
    entry_ts: str
    entry_src: str
    exit: float | None = None
    exit_ts: str | None = None
    exit_src: str | None = None
    why: str | None = None
    pnl: float | None = None


@dataclass
class Mirror:
    size: int = 1
    delay_s: float = 0.0
    fee: float = 0.03
    daily_loss_limit: float | None = None
    stop_usd: float | None = None
    quotes: QuoteBook | None = None
    trades: list[PaperTrade] = field(default_factory=list)
    open: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def _at(self, ts: str) -> str:
        return (pd.Timestamp(ts) + pd.Timedelta(seconds=self.delay_s)).strftime("%Y-%m-%d %H:%M:%S")

    def _day_loss(self, trader: int, day: str) -> float:
        return sum(t.pnl for t in self.trades if t.trader == trader and t.exit_ts and t.exit_ts[:10] == day and t.pnl)

    def run(self, events: list[dict]) -> "Mirror":
        his: dict = {}
        for e in sorted(events, key=lambda x: (x.get("ts") or "", x.get("id") or 0)):
            if e.get("ts") is None or e.get("price") is None or e.get("trader") is None:
                continue
            right = e.get("right_") or e.get("right")
            key = (e["trader"], f"QQQ {e['strike']:g}{right}")
            before = his.get(key, 0)
            his[key] = max(0, before + (e["qty"] if e["action"] == "BUY" else -e["qty"]))
            when = self._at(e["ts"])
            self._check_stops(when)
            if e["action"] == "BUY" and before == 0 and key not in self.open:
                lim = self.daily_loss_limit
                if lim is not None and self._day_loss(e["trader"], when[:10]) <= -lim:
                    self.notes.append(f"{when} trader {e['trader']}: daily loss limit reached, not copied")
                    continue
                exp_known, inf0 = e.get("expiry"), False
                if self.quotes and not exp_known:  # identify the contract at HIS time, where his price is comparable
                    q0 = self.quotes.quote(e["ts"], e["strike"], right, None, e["price"])
                    if q0:
                        exp_known, inf0 = q0[2], True
                q = self.quotes.quote(when, e["strike"], right, exp_known, None) if (self.quotes and exp_known) else None
                if q:
                    q = (q[0], q[1], q[2], inf0)
                if q:
                    price, src, exp, inf = q[1], "recorded ask", q[2], q[3]
                else:
                    price, src, exp, inf = e["price"], "his price (unverified)", e.get("expiry"), False
                self.open[key] = PaperTrade(e["trader"], key[1], exp, inf, self.size, price, when, src)
            elif e["action"] == "SELL" and his[key] == 0 and key in self.open:
                self._close(key, when, e["price"], "he closed")

    # ------------------------------------------------------------------
    def _close(self, key, when, his_price, why):
        t = self.open.pop(key)
        q = self.quotes.quote(when, float(key[1].split()[1][:-1]), key[1][-1], t.expiry, his_price) if self.quotes else None
        if q:
            t.exit, t.exit_src = q[0], "recorded bid"
        else:
            t.exit, t.exit_src = his_price, "his price (unverified)"
        t.exit_ts, t.why = when, why
        t.pnl = round((t.exit - t.entry) * 100 * t.qty - 2 * self.fee * t.qty, 2)
        self.trades.append(t)

    def _check_stops(self, now: str):
        if not self.stop_usd or not self.quotes:
            return
        for key, t in list(self.open.items()):
            q = self.quotes.day(now[:10])
            if q is None or not t.expiry:
                continue
            g = q[(q.strike == float(key[1].split()[1][:-1])) & (q.type == key[1][-1]) & (q.expiry == t.expiry) &
                  (q.poll_time > t.entry_ts) & (q.poll_time <= now)]
            g = g[(pd.to_datetime(g.poll_time) - pd.to_datetime(g.quote_time)).dt.total_seconds() <= 60]
            hit = g[g.bid <= t.entry - self.stop_usd / 100 / t.qty]
            if len(hit):
                r = hit.iloc[0]
                self.open.pop(key)
                t.exit, t.exit_ts, t.exit_src, t.why = float(r.bid), r.poll_time, "recorded bid", "our stop"
                t.pnl = round((t.exit - t.entry) * 100 * t.qty - 2 * self.fee * t.qty, 2)
                self.trades.append(t)
