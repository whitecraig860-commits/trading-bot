"""
Extra Telegram notifications (owner's request, 27 Nov 2026). Messages only: nothing here changes what any bot does.
- Daily target reached: when a bot's closed trades for the day first reach +£30/£40/£50/£60 (the page's target versions,
  original bots only), one message listing every target newly reached.
- Critical alerts: a bot down $100+ today, the emergency pause switched on, the pause switch unreadable, many failed polls.
Each message is sent once a day (remembered in state/alerts/<day>.json, so a restart does not repeat it).
"""
from __future__ import annotations

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "state" / "alerts"
TARGETS_GBP, GBP_USD = (30, 40, 50, 60), 1 / 0.76
TARGET_BOTS = ("options", "skipweak", "combo", "picks", "clone", "brakes", "five")
LOSS_ALERT = 100.0


class Notifier:
    def __init__(self, day: str, say):
        self.say, self.path = say, DIR / f"{day}.json"
        try:
            self.sent = set(json.loads(self.path.read_text()))
        except Exception:
            self.sent = set()

    def _once(self, key: str) -> bool:
        if key in self.sent:
            return False
        self.sent.add(key)
        try:
            DIR.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(sorted(self.sent)))
        except Exception:
            pass
        return True

    def check(self, bots: dict, controls=None, poll_errors: int = 0):
        """bots: {key: PaperBot}. Never raises."""
        try:
            hits, crit = [], []
            for k, b in bots.items():
                if b is None:
                    continue
                day = sum(t["pnl"] for t in b.s.get("trades", []))
                if k in TARGET_BOTS:
                    for n in TARGETS_GBP:
                        if day >= n * GBP_USD and self._once(f"target:{k}:{n}"):
                            hits.append(f"{getattr(b, 'name', k)}: +£{n} (day +${day:.0f})")
                if day <= -LOSS_ALERT and self._once(f"loss:{k}"):
                    crit.append(f"{getattr(b, 'name', k)} is down ${-day:.0f} today")
            if controls is not None:
                st = controls.status()
                if st.get("pause_all") and self._once("pause_all"):
                    crit.append("EMERGENCY PAUSE is ON: no bot opens new trades")
                if st.get("error") and st.get("read_ago_s") is None and self._once("ctrl_unreadable"):
                    crit.append("the pause switch cannot be read: bots will not open trades (safe default)")
            if poll_errors >= 20 and self._once("poll_errors"):
                crit.append(f"{poll_errors} market-data polls have failed this session")
            if hits:
                self.say("🎯 <b>Daily target reached</b> (these versions stop for today)\n" + "\n".join(hits))
            if crit:
                self.say("🚨 <b>Critical alert</b>\n" + "\n".join(crit))
        except Exception as exc:
            print(f"Notifier: {type(exc).__name__}")
