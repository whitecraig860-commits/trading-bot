"""Performance measures per trader, from closed trades (each trader kept separate)."""

from __future__ import annotations

from collections import defaultdict

from .ledger import Closed


def measures(trades: list[Closed]) -> dict:
    if not trades:
        return {"trades": 0}
    pnl = [t.pnl for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    flat = [p for p in pnl if p == 0]
    eq = peak = dd = 0.0
    for p in pnl:
        eq += p
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    holds = [t.hold_min for t in trades if t.hold_min is not None]
    by_hour = defaultdict(lambda: [0, 0.0])
    for t in trades:
        h = (t.opened or "")[11:13]
        if h:
            by_hour[h][0] += 1
            by_hour[h][1] += t.pnl
    rep = [t for t in trades if t.reported_pnl is not None]
    mismatch = [t for t in rep if abs(t.reported_pnl - t.pnl) > max(2.0, 0.02 * abs(t.pnl))]
    return {"trades": len(trades), "wins": len(wins), "losses": len(losses), "flat": len(flat),
            "win_rate": len(wins) / len(trades), "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0, "total": sum(pnl), "max_drawdown": dd,
            "avg_hold_min": sum(holds) / len(holds) if holds else None,
            "by_hour": {h: {"trades": n, "pnl": round(v, 2)} for h, (n, v) in sorted(by_hour.items())},
            "reported_checked": len(rep), "reported_mismatch": len(mismatch)}


def by_trader(trades: list[Closed]) -> dict[int, dict]:
    groups = defaultdict(list)
    for t in trades:
        groups[t.trader].append(t)
    return {k: measures(v) for k, v in sorted(groups.items())}
