"""Telegram messages for the replication system (sent with the existing bot; secrets stay in GitHub)."""

from __future__ import annotations

from .ledger import Closed
from .paper import PaperTrade

GBP = 0.76


def new_trade(e: dict) -> str:
    side = "CALL" if (e.get("right_") or e.get("right")) == "C" else "PUT"
    extra = f" · {e['reported_pnl']:+,.0f} USD reported" if e.get("reported_pnl") is not None else ""
    flags = [f for f in e.get("flags", []) if "expiry" not in f]
    return (f"👀 <b>Trader #{e['trader']}</b> {'BOUGHT' if e['action'] == 'BUY' else 'SOLD'} {e['qty']}× QQQ {e['strike']:g} {side} "
            f"@ {e['price']:.2f}{extra}\n{e.get('ts') or 'no time'} ET · observed, not copied"
            + (f"\n⚠️ {'; '.join(flags)}" if flags else ""))


def paper_open(t: PaperTrade) -> str:
    return (f"🟢 <b>PAPER copy of Trader #{t.trader}</b>: bought {t.qty}× {t.contract} @ {t.entry:.2f} ({t.entry_src})\n"
            f"{t.entry_ts} ET" + (f" · expiry {t.expiry}{' (inferred)' if t.expiry_inferred else ''}" if t.expiry else " · expiry unknown"))


def paper_close(t: PaperTrade) -> str:
    return (f"🔴 <b>PAPER copy of Trader #{t.trader}</b>: sold {t.qty}× {t.contract} @ {t.exit:.2f} ({t.exit_src}) · {t.why}\n"
            f"<b>{t.pnl:+,.2f} USD</b> (£{t.pnl * GBP:+,.2f}) · {t.exit_ts} ET")


def performance(title: str, stats: dict[int, dict]) -> str:
    lines = [f"📊 <b>{title}</b> (his trades, recomputed from his own prices; fees unknown)"]
    for tr, m in stats.items():
        if not m.get("trades"):
            continue
        lines.append(f"Trader #{tr}: {m['trades']} trades · {m['wins']}W/{m['losses']}L ({m['win_rate']:.0%}) · "
                     f"<b>{m['total']:+,.0f} USD</b> · avg win {m['avg_win']:+.0f} / loss {m['avg_loss']:+.0f} · "
                     f"max drawdown {m['max_drawdown']:,.0f}")
    return "\n".join(lines)


def risk_warning(text: str) -> str:
    return f"⚠️ <b>Risk warning</b>: {text}"


def closed_line(c: Closed) -> str:
    return f"#{c.trader} {c.contract} {c.qty}× {c.entry:.2f}→{c.exit:.2f} {c.pnl:+.0f}"
