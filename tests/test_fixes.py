"""
Tests for the fixes in audit/CHANGE_CONTROL.md (CC-001, CC-002, CC-003). No network, no orders.
Run:  python -m unittest tests/test_fixes.py -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))
import qqqbot  # noqa: E402
import recorder  # noqa: E402

NY = ZoneInfo("America/New_York")
DAY = datetime(2026, 11, 17, 9, 30, tzinfo=NY)


def bars_with_cross():
    """QQQ candles that produce a VWAP / EMA50 cross on the 10:00 candle (close jumps above everything)."""
    idx = pd.date_range("2026-11-17 09:30", "2026-11-17 15:59", freq="min")
    c = np.full(len(idx), 660.0)
    c[: 30] = 660 - np.arange(30) * 0.02          # drifting down to 09:59
    c[30:] = 662.0                                  # 10:00 candle closes well above
    o = np.r_[660, c[:-1]]
    day = pd.DataFrame({"open": o, "high": np.maximum(o, c) + .02, "low": np.minimum(o, c) - .02, "close": c,
                        "volume": 1000.0}, index=idx)
    prev = day.copy()
    prev.index = prev.index - pd.Timedelta(days=1)
    prev[:] = 661.0
    return day, prev


def make_bot(**kw):
    day, prev = bars_with_cross()
    bf = lambda n, back=0: prev if back else day[day.index <= pd.Timestamp(n.replace(tzinfo=None))]  # noqa: E731
    return qqqbot.PaperBot(bf, DAY, say=lambda t: True, state_dir=Path(tempfile.mkdtemp()), trade_messages=False,
                           summaries=False, **kw)


def rows(now, price, stamp_age_s=1, bid=None):
    qt = (now - timedelta(seconds=stamp_age_s)).strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for k in range(655, 670):
        for ty in "CP":
            v = 5.0
            out.append({"expiry": "2026-11-18", "type": ty, "strike": float(k), "bid": bid if bid is not None else v - .03,
                        "ask": v + .03, "quote_time": qt})
    return out


class CC001FreshQuotes(unittest.TestCase):
    def test_stale_quote_blocks_entry(self):
        b = make_bot()
        now = DAY.replace(hour=10, minute=1, second=5)
        b.on_poll(now, rows(now, 662, stamp_age_s=18 * 3600))  # quote from yesterday afternoon
        self.assertIsNone(b.s["open"])

    def test_fresh_quote_allows_entry(self):
        b = make_bot()
        now = DAY.replace(hour=10, minute=1, second=5)
        b.on_poll(now, rows(now, 662, stamp_age_s=2))
        self.assertIsNotNone(b.s["open"])

    def test_stale_bid_does_not_trigger_exit(self):
        b = make_bot()
        now = DAY.replace(hour=10, minute=1, second=5)
        b.on_poll(now, rows(now, 662, stamp_age_s=2))
        self.assertIsNotNone(b.s["open"])
        later = now + timedelta(seconds=5)
        b.on_poll(later, rows(later, 662, stamp_age_s=3600, bid=1.0))  # stale, absurd bid: must be ignored
        self.assertIsNotNone(b.s["open"])
        later2 = later + timedelta(seconds=5)
        b.on_poll(later2, rows(later2, 662, stamp_age_s=1, bid=1.0))   # fresh: the stop now applies
        self.assertIsNone(b.s["open"])
        self.assertEqual(b.s["trades"][-1]["why"], "stop")

    def test_switch_off_restores_old_behaviour(self):
        qqqbot.FRESH_QUOTES_ONLY = False
        try:
            b = make_bot()
            now = DAY.replace(hour=10, minute=1, second=5)
            b.on_poll(now, rows(now, 662, stamp_age_s=18 * 3600))
            self.assertIsNotNone(b.s["open"])
        finally:
            qqqbot.FRESH_QUOTES_ONLY = True


class CC002HolidayDecision(unittest.TestCase):
    def test_first_30_minutes_go(self):
        self.assertEqual(recorder.holiday_decision(100, False, lambda: False), "go")

    def test_fresh_quotes_go(self):
        self.assertEqual(recorder.holiday_decision(720, True, lambda: False), "go")

    def test_stale_but_market_open_waits(self):
        self.assertEqual(recorder.holiday_decision(360, False, lambda: True), "wait")

    def test_real_holiday_stops(self):
        self.assertEqual(recorder.holiday_decision(360, False, lambda: False), "stop")

    def test_check_failure_waits(self):
        def boom():
            raise RuntimeError("network")
        self.assertEqual(recorder.holiday_decision(420, False, boom), "wait")

    def test_only_checks_every_5_minutes(self):
        calls = []
        recorder.holiday_decision(361, False, lambda: calls.append(1) or True)
        self.assertEqual(calls, [])


class CC003FollowCarryOver(unittest.TestCase):
    def test_follow_keeps_option_through_restart_and_resumes(self):
        d = Path(tempfile.mkdtemp())
        day, prev = bars_with_cross()
        bf = lambda n, back=0: prev if back else day[day.index <= pd.Timestamp(n.replace(tzinfo=None))]  # noqa: E731
        kw = dict(qqqbot.EXTRA_BOTS["oneaday"][2])
        b = qqqbot.PaperBot(bf, DAY, say=lambda t: True, state_dir=d, trade_messages=False, summaries=False, **kw)
        now = DAY.replace(hour=10, minute=30, second=5)
        b.pending = ("C", "ONEADAY", 661.0, 1.0)
        b.on_poll(now, rows(now, 661))
        self.assertIsNotNone(b.s["open"])
        b.finish(DAY.replace(hour=12, minute=50), rows(now, 661))
        self.assertIsNotNone(b.s["open"], "follow bot must keep its option through a restart")
        b2 = qqqbot.PaperBot(bf, DAY, say=lambda t: True, state_dir=d, trade_messages=False, summaries=False, **kw)
        self.assertIsNotNone(b2.s["open"], "the next run resumes the open option")
        b2.follow_exit = True
        t2 = DAY.replace(hour=13, minute=30, second=5)
        b2.on_poll(t2, rows(t2, 661))
        self.assertIsNone(b2.s["open"])
        self.assertEqual(b2.s["trades"][-1]["why"], "shares bot exit")
        self.assertEqual(len(b2.s["trades"]), 1, "no duplicate position")

    def test_follow_closes_after_1555_at_finish(self):
        b = make_bot(**qqqbot.EXTRA_BOTS["oneaday"][2])
        now = DAY.replace(hour=10, minute=30, second=5)
        b.pending = ("C", "ONEADAY", 661.0, 1.0)
        b.on_poll(now, rows(now, 661))
        b.finish(DAY.replace(hour=15, minute=56), rows(now, 661))
        self.assertIsNone(b.s["open"])

    def test_other_bots_still_close_at_restart(self):
        b = make_bot()
        now = DAY.replace(hour=10, minute=1, second=5)
        b.on_poll(now, rows(now, 662))
        self.assertIsNotNone(b.s["open"])
        b.finish(DAY.replace(hour=12, minute=50), rows(now, 662))
        self.assertIsNone(b.s["open"])
        self.assertEqual(b.s["trades"][-1]["why"], "recorder restart")

    def test_follow_never_enters_twice(self):
        b = make_bot(**qqqbot.EXTRA_BOTS["oneaday"][2])
        t = DAY.replace(hour=10, minute=30, second=5)
        b.pending = ("C", "ONEADAY", 661.0, 1.0)
        b.on_poll(t, rows(t, 661))
        b.follow_exit = True
        t = t + timedelta(minutes=1)
        b.on_poll(t, rows(t, 661))
        b.follow_exit = False
        for m in range(2, 10):
            tt = DAY.replace(hour=10, minute=30 + m, second=5)
            b.on_poll(tt, rows(tt, 661))
        self.assertEqual(len(b.s["trades"]), 1)
        self.assertIsNone(b.s["open"])


if __name__ == "__main__":
    unittest.main()
