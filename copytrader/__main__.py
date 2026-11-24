"""
Command line for the QQQ Trader replication system (paper only).

    python -m copytrader import-text messages.txt [--year 2026]
    python -m copytrader import-csv state/discord_trades.csv
    python -m copytrader fetch-discord            (only once the server admin has approved our bot)
    python -m copytrader report                   (his performance, per trader)
    python -m copytrader paper [--delay 300] [--size 1] [--daily-loss 6.6] [--stop 6.6]
    python -m copytrader telegram-daily           (sends the report to Telegram)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import notify
from .ledger import build
from .paper import Mirror, QuoteBook
from .sources import DiscordBotSource, import_text, import_transcribed_csv
from .stats import by_trader, measures
from .store import DEFAULT_DB, Store


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="copytrader")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("import-text")
    a.add_argument("path")
    a.add_argument("--year", type=int)
    b = sub.add_parser("import-csv")
    b.add_argument("path")
    sub.add_parser("fetch-discord")
    sub.add_parser("report")
    p = sub.add_parser("paper")
    p.add_argument("--delay", type=float, default=0.0, help="seconds between his message and our action")
    p.add_argument("--size", type=int, default=1)
    p.add_argument("--daily-loss", type=float, help="stop copying a trader for the day after this paper loss (USD)")
    p.add_argument("--stop", type=float, help="our own stop per trade (USD)")
    sub.add_parser("telegram-daily")
    args = ap.parse_args(argv)
    st = Store(args.db)

    if args.cmd == "import-text":
        print("stored messages, events:", import_text(st, Path(args.path), args.year))
    elif args.cmd == "import-csv":
        print("stored rows, events:", import_transcribed_csv(st, Path(args.path)))
    elif args.cmd == "fetch-discord":
        src = DiscordBotSource()
        if not src.configured:
            print("Discord bot not configured yet (waiting for the server admin's approval). Nothing fetched.")
            return 0
        print("stored messages, events:", src.fetch(st))
    elif args.cmd in ("report", "telegram-daily"):
        book = build(st.trade_events())
        stats = by_trader(book.closed)
        if args.cmd == "report":
            print(json.dumps(stats, indent=1, default=str))
            print(f"open positions: {len(book.open)}; problems: {len(book.problems)}")
            for x in book.problems[:20]:
                print("  -", x)
        else:
            from .tracker_bridge import send
            send(notify.performance("His trades so far", stats))
    elif args.cmd == "paper":
        m = Mirror(size=args.size, delay_s=args.delay, daily_loss_limit=args.daily_loss, stop_usd=args.stop,
                   quotes=QuoteBook())
        m.run(st.trade_events())
        groups = {}
        for t in m.trades:
            groups.setdefault(t.trader, []).append(t)
        for tr, ts in sorted(groups.items()):
            verified = sum(1 for t in ts if "recorded" in t.entry_src and "recorded" in (t.exit_src or ""))
            print(f"Trader #{tr}: {len(ts)} paper copies, {verified} fully priced from our recorded quotes, "
                  f"total {sum(t.pnl for t in ts):+,.2f} USD, wins {sum(t.pnl > 0 for t in ts)}")
        for n in m.notes[:10]:
            print("  note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
