"""Stage 2 tests: decision log, pause switch, context twins, live option value. No network, no orders.
Run:  python tests/test_stage2.py"""

from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fixes import DAY, make_bot, rows  # noqa: E402

import context  # noqa: E402
import controls  # noqa: E402
import qqqbot  # noqa: E402

T = DAY.replace(hour=10, minute=1, second=5)


class DecisionLog(unittest.TestCase):
    def test_entry_is_logged_with_inputs(self):
        b = make_bot()
        b.on_poll(T, rows(T, 662))
        self.assertIsNotNone(b.s["open"])
        d = b.s["decisions"][-1]
        self.assertEqual(d["out"], "entered")
        self.assertEqual(d["sig"]["side"], "C")
        self.assertIsNotNone(d["ind"])  # the shared context it saw
        self.assertIn("trend", b.s["open"]["ctx"])

    def test_no_signal_minutes_are_logged(self):
        b = make_bot()
        t = DAY.replace(hour=9, minute=40, second=5)  # before the first signal time
        b.on_poll(t, rows(t, 660))
        self.assertEqual(b.s["decisions"][-1]["out"], "no signal")

    def test_exit_is_logged_and_open_trade_is_valued(self):
        b = make_bot()
        b.on_poll(T, rows(T, 662))
        t2 = T + timedelta(seconds=5)
        b.on_poll(t2, rows(t2, 662, bid=5.02))
        self.assertEqual(b.s["open"]["mark"], 5.02)  # the live bid the page uses for unrealised P&L
        t3 = T + timedelta(minutes=11)
        b.on_poll(t3, rows(t3, 662))
        self.assertEqual(len(b.s["trades"]), 1)
        self.assertTrue(any(x["out"] == "exited" for x in b.s["decisions"]))


class PauseSwitch(unittest.TestCase):
    def test_pause_blocks_new_trades_and_says_why(self):
        b = make_bot(key="combo")
        b.controls = lambda k: "EMERGENCY PAUSE (all bots)"
        b.on_poll(T, rows(T, 662))
        self.assertIsNone(b.s["open"])
        self.assertEqual(b.s["decisions"][-1]["out"], "rejected")
        self.assertIn("EMERGENCY PAUSE", b.s["decisions"][-1]["why"])

    def test_unreadable_switch_means_no_trade(self):
        b = make_bot()

        def boom(k):
            raise RuntimeError("x")
        b.controls = boom
        b.on_poll(T, rows(T, 662))
        self.assertIsNone(b.s["open"])

    def test_controls_state_rules(self):
        c = controls.Controls()
        c.last_try = 1e18  # no network in tests
        self.assertIsNone(c.check("combo"))
        c.state = {"pause_all": False, "paused": ["combo"]}
        self.assertIn("paused", c.check("combo"))
        self.assertIsNone(c.check("five"))
        c.state = {"pause_all": True, "paused": []}
        self.assertIn("EMERGENCY", c.check("five"))


class ContextTwins(unittest.TestCase):
    def test_gate_rules(self):
        base = {"ok": True, "trend": "Bullish", "choppy": False, "crosses30": 1}
        self.assertIsNone(context.gate(base, "C"))
        self.assertIn("against", context.gate(base, "P"))
        self.assertIn("choppy", context.gate(dict(base, choppy=True), "C"))
        self.assertIn("unavailable", context.gate({"ok": False, "why": "x"}, "C"))
        self.assertIsNone(context.gate(dict(base, trend="Bearish"), -1))

    def test_twin_blocked_when_context_says_no(self):
        b = make_bot(ctx_gate=True)
        orig = context.market
        context.market = lambda bars, prev=None: {"ok": True, "trend": "Bearish", "choppy": False, "crosses30": 0}
        try:
            b.on_poll(T, rows(T, 662))
        finally:
            context.market = orig
        self.assertIsNone(b.s["open"])
        self.assertIn("blocked by context", b.s["decisions"][-1]["why"])

    def test_original_ignores_context(self):
        b = make_bot()
        orig = context.market
        context.market = lambda bars, prev=None: {"ok": True, "trend": "Bearish", "choppy": True, "crosses30": 9}
        try:
            b.on_poll(T, rows(T, 662))
        finally:
            context.market = orig
        self.assertIsNotNone(b.s["open"])  # originals trade exactly as before

    def test_every_bot_has_a_twin(self):
        base = [k for k in qqqbot.EXTRA_BOTS if not k.endswith("_ctx") and k != "news"]  # the news bot already uses the context
        for k in base:
            self.assertIn(k + "_ctx", qqqbot.EXTRA_BOTS)
            self.assertTrue(qqqbot.EXTRA_BOTS[k + "_ctx"][2]["ctx_gate"])
        self.assertIn("options_ctx", qqqbot.EXTRA_BOTS)

    def test_context_calc_on_real_shaped_bars(self):
        from test_fixes import bars_with_cross
        day, prev = bars_with_cross()
        c = context.market(day.iloc[:60], prev)
        self.assertTrue(c["ok"])
        self.assertIn(c["trend"], ("Bullish", "Bearish", "Sideways"))
        self.assertFalse(context.market(day.iloc[:5], prev)["ok"])


class NewsBot(unittest.TestCase):
    def news(self, t, text):
        return lambda: [{"id": 1, "t": t, "h": text, "sym": ["NVDA"]}, {"id": 2, "t": t, "h": text + " again", "sym": ["NVDA"]}]

    def test_scorer(self):
        import newsscore
        self.assertGreater(newsscore.score("Nvidia beats estimates, shares surge")["score"], 0)
        self.assertLess(newsscore.score("Apple misses estimates as tariffs hit; stock plunges")["score"], 0)
        self.assertEqual(newsscore.score("Fed signals rate cut", [])["importance"], 3)
        self.assertLess(newsscore.score("Company does not expect strong growth")["score"], 1)

    def test_good_news_with_bullish_chart_buys_a_call(self):
        b = make_bot(mode="news", key="news", target=0.10, stop=0.10, hold_min=30)
        t = DAY.replace(hour=10, minute=13, second=5)
        b.news_fn = self.news(t.replace(tzinfo=None) - timedelta(minutes=2), "Nvidia beats estimates, record revenue, shares surge")
        b.on_poll(t, rows(t, 662))
        self.assertIsNotNone(b.s["open"])
        self.assertEqual(b.s["open"]["type"], "C")
        self.assertIn("news pressure", b.s["decisions"][-1]["why"])

    def test_bad_news_against_bullish_chart_does_not_trade(self):
        b = make_bot(mode="news", key="news")
        t = DAY.replace(hour=10, minute=13, second=5)
        b.news_fn = self.news(t.replace(tzinfo=None) - timedelta(minutes=2), "Nvidia misses estimates, shares plunge on tariffs")
        b.on_poll(t, rows(t, 662))
        self.assertIsNone(b.s["open"])
        self.assertIn("chart disagrees", b.s["decisions"][-1]["why"])

    def test_no_headlines_no_trade(self):
        b = make_bot(mode="news", key="news")
        b.news_fn = lambda: []
        t = DAY.replace(hour=10, minute=13, second=5)
        b.on_poll(t, rows(t, 662))
        self.assertIsNone(b.s["open"])


class DogeBot(unittest.TestCase):
    def frame(self, closes):
        import pandas as pd
        idx = pd.date_range("2026-11-27 00:00", periods=len(closes), freq="15min", tz="UTC")
        c = pd.Series(closes, index=idx, dtype=float)
        return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c})

    def start(self):
        return {"start_usd": 1315.79, "cash": 1315.79, "open": None, "trades": [], "last": None}

    def test_buys_after_8pct_drop_and_sells_at_target(self):
        import dogebot
        closes = [0.40] * 17 + [0.36] + [0.36] * 3 + [0.38]
        s = dogebot.step(self.start(), self.frame(closes), say=lambda m: None)
        self.assertEqual(len(s["trades"]), 1)
        self.assertIn("target", s["trades"][0]["why"])
        self.assertGreater(s["trades"][0]["pnl"], 0)

    def test_no_drop_no_trade_and_no_double_processing(self):
        import dogebot
        b = self.frame([0.40] * 30)
        s = dogebot.step(self.start(), b, say=lambda m: None)
        s2 = dogebot.step(dict(s), b, say=lambda m: None)
        self.assertEqual(len(s2["trades"]), 0)
        self.assertIsNone(s2["open"])

    def test_stop_loss(self):
        import dogebot
        closes = [0.40] * 17 + [0.36] + [0.34]
        s = dogebot.step(self.start(), self.frame(closes), say=lambda m: None)
        self.assertIn("stop", s["trades"][0]["why"])
        self.assertLess(s["trades"][0]["pnl"], 0)


class ExtraNotifications(unittest.TestCase):
    def test_target_and_loss_messages_once(self):
        import tempfile
        import notify_extra
        notify_extra.DIR = Path(tempfile.mkdtemp())
        sent = []
        n = notify_extra.Notifier("2026-11-30", sent.append)

        class B:
            name = "stop after 2 losses"
            s = {"trades": [{"pnl": 45.0}, {"pnl": 10.0}]}
        n.check({"options": B()})
        self.assertEqual(len(sent), 1)
        self.assertIn("+£40", sent[0])
        self.assertNotIn("+£50", sent[0])
        n.check({"options": B()})
        self.assertEqual(len(sent), 1)  # not repeated
        B.s = {"trades": [{"pnl": -120.0}]}
        n.check({"options": B()})
        self.assertIn("Critical", sent[-1])


class TelegramLength(unittest.TestCase):
    def test_long_messages_are_split_under_the_limit(self):
        text = "\n\n".join(f"<b>Bot {i}</b>\n" + "x" * 300 for i in range(40))
        parts = qqqbot.split_message(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) < 4096 for p in parts))
        self.assertTrue(all(p.count("<b>") == p.count("</b>") for p in parts))

    def test_short_messages_unchanged(self):
        self.assertEqual(qqqbot.split_message("hello"), ["hello"])


if __name__ == "__main__":
    unittest.main()
