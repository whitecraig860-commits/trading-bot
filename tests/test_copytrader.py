"""Tests for the QQQ Trader replication system. No network, no orders.  python -m unittest tests/test_copytrader.py -v"""

from __future__ import annotations

import gzip
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from copytrader.ledger import build
from copytrader.paper import Mirror, QuoteBook
from copytrader.parser import parse
from copytrader.sources import DiscordBotSource, import_text, import_transcribed_csv
from copytrader.stats import by_trader
from copytrader.store import Store


class Parser(unittest.TestCase):
    def test_sold_with_pnl_and_dash_time(self):
        e = parse("QQQ Trader #1 APP\nSOLD 12x QQQ 612 PUT @ 11.47\n+$12 (+0.1%)\nFri 11/20 - 3:43:54 PM ET", default_year=2026)[0]
        self.assertEqual((e.trader, e.action, e.qty, e.strike, e.right, e.price), (1, "SELL", 12, 612.0, "P", 11.47))
        self.assertEqual((e.reported_pnl, e.reported_pct, e.ts), (12.0, 0.1, "2026-11-20 15:43:54"))

    def test_bought_with_multiplication_sign_and_dot_separator(self):
        e = parse("QQQ Trader #2 APP 14:42\nBOUGHT 3× QQQ 662 CALL @ 7.51\nTue 11/17 · 9:42:01 AM ET", default_year=2026)[0]
        self.assertEqual((e.trader, e.action, e.qty, e.right, e.price, e.ts), (2, "BUY", 3, "C", 7.51, "2026-11-17 09:42:01"))
        self.assertIsNone(e.reported_pnl)

    def test_negative_pnl_unicode_minus(self):
        e = parse("SOLD 15× QQQ 662 CALL @ 6.64\n−$1,395 (−12.3%) · Tue 11/17 · 9:44:22 AM ET", trader_hint=3, default_year=2026)[0]
        self.assertEqual((e.reported_pnl, e.reported_pct, e.trader), (-1395.0, -12.3, 3))

    def test_missing_information_is_flagged_not_invented(self):
        e = parse("SOLD 2x QQQ 650 PUT @ 8.00")[0]
        self.assertIsNone(e.trader)
        self.assertIsNone(e.ts)
        self.assertIn("trader unknown", e.flags)
        self.assertIn("no time stamp in the message", e.flags)
        self.assertIn("sell without a reported result", e.flags)
        self.assertIn("expiry not stated in the message", e.flags)

    def test_wrong_weekday_flagged(self):
        e = parse("BOUGHT 1x QQQ 600 CALL @ 5.00 Mon 11/20 - 10:00:00 AM ET", trader_hint=1, default_year=2026)[0]
        self.assertTrue(any("weekday" in f for f in e.flags))

    def test_summary_lines(self):
        txt = ("Today's summary (Thu 11/19)\nQQQ Trader #1: 7 trades · 3W / 4L · +$1,737\n"
               "QQQ Trader #3: 6 trades · 0W / 6L · −$2,919")
        s = [e for e in parse(txt) if e.kind == "summary"]
        self.assertEqual([(x.trader, x.summary["trades"], x.summary["pnl"]) for x in s], [(1, 7, 1737.0), (3, 6, -2919.0)])

    def test_two_trades_in_one_block(self):
        evs = parse("QQQ Trader #2\nBOUGHT 2x QQQ 659 PUT @ 8.16 Fri 11/20 - 10:50:01 AM ET\n"
                    "SOLD 2x QQQ 659 PUT @ 8.33 +$34 (+2.1%) Fri 11/20 - 10:52:28 AM ET", default_year=2026)
        self.assertEqual([(e.action, e.ts[11:]) for e in evs], [("BUY", "10:50:01"), ("SELL", "10:52:28")])


def store_with(*messages, hint=None):
    st = Store(":memory:")
    for i, m in enumerate(messages):
        st.add_message(m, "test", f"2026-11-20T00:00:{i:02d}Z", parse(m, trader_hint=hint, default_year=2026))
    return st


class StoreAndLedger(unittest.TestCase):
    def test_duplicates_stored_once(self):
        st = Store(":memory:")
        m = "BOUGHT 1x QQQ 600 CALL @ 5.00 Fri 11/20 - 10:00:00 AM ET"
        self.assertIsNotNone(st.add_message(m, "t", "x", parse(m, 1, 2026)))
        self.assertIsNone(st.add_message(m, "t", "y", parse(m, 1, 2026)))

    def test_scale_in_partial_exit_and_close(self):
        st = store_with("BOUGHT 2x QQQ 600 CALL @ 5.00 Fri 11/20 - 10:00:00 AM ET",
                        "BOUGHT 2x QQQ 600 CALL @ 6.00 Fri 11/20 - 10:01:00 AM ET",
                        "SOLD 1x QQQ 600 CALL @ 7.00 +$150 (+27%) Fri 11/20 - 10:02:00 AM ET",
                        "SOLD 3x QQQ 600 CALL @ 4.50 -$300 (-18%) Fri 11/20 - 10:05:00 AM ET", hint=1)
        b = build(st.trade_events())
        self.assertEqual([(c.qty, round(c.entry, 2), c.pnl, c.partial) for c in b.closed],
                         [(1, 5.5, 150.0, True), (3, 5.5, -300.0, False)])
        self.assertEqual(b.open, {})

    def test_sell_without_position_is_not_a_short(self):
        st = store_with("SOLD 5x QQQ 600 PUT @ 5.00 +$10 (+1%) Fri 11/20 - 10:00:00 AM ET", hint=2)
        b = build(st.trade_events())
        self.assertEqual(b.closed, [])
        self.assertEqual(b.open, {})
        self.assertTrue(any("no open position" in p for p in b.problems))

    def test_traders_kept_separate_and_stats(self):
        st = Store(":memory:")
        for tr, buy, sell, t in ((1, 5.0, 6.0, "10:00"), (2, 5.0, 4.0, "10:00"), (1, 5.0, 4.5, "11:00")):
            for m in (f"BOUGHT 1x QQQ 600 CALL @ {buy} Fri 11/20 - {t}:00 AM ET", f"SOLD 1x QQQ 600 CALL @ {sell} Fri 11/20 - {t}:30 AM ET"):
                st.add_message(m + f" #{tr}{t}", "test", "x", parse(m, tr, 2026))
        s = by_trader(build(st.trade_events()).closed)
        self.assertEqual((s[1]["trades"], s[1]["wins"], s[1]["total"], s[1]["max_drawdown"]), (2, 1, 50.0, -50.0))
        self.assertEqual((s[2]["trades"], s[2]["total"]), (1, -100.0))
        self.assertEqual(set(s[1]["by_hour"]), {"10", "11"})
        self.assertAlmostEqual(s[1]["avg_hold_min"], 0.5)


def fake_quotes(folder: Path):
    """Recorded-quote file for 20 Nov: the 600 call quoted 4.90/5.00 at 10:00 and 5.90/6.00 from 10:05; frozen after 10:10."""
    rows = []
    for m in range(0, 15):
        for s in range(0, 60, 5):
            pt = f"2026-11-20 10:{m:02d}:{s:02d}"
            bid, ask = (4.90, 5.00) if m < 5 else (5.90, 6.00)
            qt = pt if m < 10 else "2026-11-20 10:09:55"
            rows.append({"poll_time": pt, "contract": "C600", "expiry": "2026-11-23", "type": "C", "strike": 600.0,
                         "bid": bid, "ask": ask, "quote_time": qt})
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="w") as g:
        g.write(pd.DataFrame(rows).to_csv(index=False).encode())
    (folder / "2026-11-20-0930.csv.gz").write_bytes(buf.getvalue())


class PaperMirror(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        fake_quotes(self.tmp)

    def events(self, sell_time="10:06:00", sell_price=6.20):
        st = store_with("BOUGHT 3x QQQ 600 CALL @ 4.95 Fri 11/20 - 10:00:00 AM ET",
                        "BOUGHT 2x QQQ 600 CALL @ 5.10 Fri 11/20 - 10:01:00 AM ET",
                        "SOLD 2x QQQ 600 CALL @ 5.50 Fri 11/20 - 10:03:00 AM ET",
                        f"SOLD 3x QQQ 600 CALL @ {sell_price} Fri 11/20 - {sell_time} AM ET", hint=1)
        return st.trade_events()

    def test_priced_from_recorded_quotes_and_one_copy(self):
        m = Mirror(quotes=QuoteBook(self.tmp))
        m.run(self.events())
        self.assertEqual(len(m.trades), 1, "scale-ins and partial exits do not create extra copies")
        t = m.trades[0]
        self.assertEqual((t.entry, t.entry_src, t.exit, t.exit_src), (5.00, "recorded ask", 5.90, "recorded bid"))
        self.assertEqual(t.expiry, "2026-11-23")
        self.assertTrue(t.expiry_inferred)
        self.assertAlmostEqual(t.pnl, (5.90 - 5.00) * 100 - 0.06)

    def test_stale_quote_falls_back_to_his_price_marked_unverified(self):
        m = Mirror(quotes=QuoteBook(self.tmp))
        m.run(self.events(sell_time="10:14:00"))
        self.assertEqual(m.trades[0].exit_src, "his price (unverified)")

    def test_delay_changes_our_price(self):
        m = Mirror(quotes=QuoteBook(self.tmp), delay_s=300)
        m.run(self.events())
        self.assertEqual(m.trades[0].entry, 6.00)  # five minutes late we pay the later ask

    def test_daily_loss_limit_stops_copying(self):
        st = store_with("BOUGHT 1x QQQ 600 CALL @ 5.95 Fri 11/20 - 10:05:00 AM ET",
                        "SOLD 1x QQQ 600 CALL @ 5.00 Fri 11/20 - 10:06:00 AM ET",
                        "BOUGHT 1x QQQ 600 CALL @ 5.95 Fri 11/20 - 10:07:00 AM ET",
                        "SOLD 1x QQQ 600 CALL @ 5.00 Fri 11/20 - 10:08:00 AM ET", hint=1)
        m = Mirror(daily_loss_limit=1.0)
        m.run(st.trade_events())
        self.assertEqual(len(m.trades), 1)
        self.assertTrue(any("daily loss limit" in n for n in m.notes))

    def test_our_stop(self):
        st = store_with("BOUGHT 1x QQQ 600 CALL @ 5.95 Fri 11/20 - 10:05:00 AM ET",
                        "SOLD 1x QQQ 600 CALL @ 7.00 Fri 11/20 - 10:09:00 AM ET", hint=1)
        tmp = Path(tempfile.mkdtemp())
        fake_quotes(tmp)
        m = Mirror(quotes=QuoteBook(tmp), stop_usd=5.0)  # entry 6.00; a 5-dollar stop is hit by the 5.90 bid at once
        m.run(st.trade_events())
        self.assertEqual(m.trades[0].why, "our stop")


class Sources(unittest.TestCase):
    def test_text_import_and_trader_carry_over(self):
        p = Path(tempfile.mkdtemp()) / "msgs.txt"
        p.write_text("QQQ Trader #3 APP\nBOUGHT 1x QQQ 600 CALL @ 5.00\nFri 11/20 - 10:00:00 AM ET\n\n"
                     "SOLD 1x QQQ 600 CALL @ 5.50\n+$50 (+10%)\nFri 11/20 - 10:01:00 AM ET\n")
        st = Store(":memory:")
        self.assertEqual(import_text(st, p, 2026), (2, 2))
        self.assertEqual({e["trader"] for e in st.trade_events()}, {3})

    def test_transcribed_csv(self):
        p = Path(tempfile.mkdtemp()) / "t.csv"
        p.write_text("date,trader,qty,strike,type,expiry,buy_time,buy,sell_time,sell\n"
                     "2026-11-20,2,1,636,C,2026-11-23,09:32:01,10.00,09:33:07,9.81\n"
                     "2026-11-11,,8,686,C,2026-11-12,10:22:00,4.30,10:26:00,4.52\n")
        st = Store(":memory:")
        self.assertEqual(import_transcribed_csv(st, p), (1, 2))
        c = build(st.trade_events()).closed
        self.assertEqual((c[0].pnl, c[0].contract), (-19.0, "QQQ 636C 2026-11-23"))

    def test_discord_source_refuses_without_authorisation(self):
        src = DiscordBotSource(token=None, channel_id=None)
        self.assertFalse(src.configured)
        with self.assertRaises(RuntimeError):
            src.fetch(Store(":memory:"))


if __name__ == "__main__":
    unittest.main()
