"""
Feeds the live web page (docs/live/index.html) during the US session
====================================================================
Every 2 minutes it writes one small file, live.json, to the repo's `live-data` branch through GitHub's API. The page
reads that file. It runs in a background thread with short timeouts, so a slow or failed upload can never hold up
the price recorder or the paper bots. Switch it off with ENABLED = False.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time

ENABLED = True
EVERY = 120  # seconds
BRANCH = "live-data"


class Publisher:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        self.last = 0.0
        self.sha = None
        self.busy = False

    def due(self) -> bool:
        return ENABLED and bool(self.token and self.repo) and not self.busy and time.time() - self.last >= EVERY

    def publish(self, payload: dict):
        self.last, self.busy = time.time(), True
        threading.Thread(target=self._put, args=(payload,), daemon=True).start()

    def _put(self, payload: dict):
        try:
            import requests

            url = f"https://api.github.com/repos/{self.repo}/contents/live.json"
            h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
            if self.sha is None:
                r = requests.get(url, headers=h, params={"ref": BRANCH}, timeout=10)
                self.sha = r.json().get("sha") if r.ok else None
                if r.status_code == 404:  # first run ever: make the branch from main
                    api = f"https://api.github.com/repos/{self.repo}/git"
                    m = requests.get(f"{api}/ref/heads/main", headers=h, timeout=10)
                    if m.ok:
                        requests.post(f"{api}/refs", headers=h, timeout=10,
                                      json={"ref": f"refs/heads/{BRANCH}", "sha": m.json()["object"]["sha"]})
            body = {"message": "live page data", "branch": BRANCH, "committer": {
                "name": "setup-scanner-bot", "email": "setup-scanner-bot@users.noreply.github.com"},
                "content": base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()}
            if self.sha:
                body["sha"] = self.sha
            r = requests.put(url, headers=h, json=body, timeout=15)
            self.sha = r.json().get("content", {}).get("sha") if r.ok else None
            if not r.ok:
                print(f"Live page: upload refused ({r.status_code})")
        except Exception as exc:
            print(f"Live page: {type(exc).__name__}")  # never print details: they could include the token
            self.sha = None
        finally:
            self.busy = False


_WEEK: dict = {}


def week_history(today: str) -> dict:
    """Daily P&L for each bot over the 7 days before today, from the saved state files (read once per run)."""
    if today in _WEEK:
        return _WEEK[today]
    from datetime import date, timedelta
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "state"
    d0 = date.fromisoformat(today)
    out = {"options": {}, "original": {}, "his": {}, "shares": {}}
    for k in range(1, 8):
        day = (d0 - timedelta(days=k)).isoformat()
        for key, folder in (("options", "qqqbot"), ("original", "qqqbot_original"), ("his", "qqqbot_his"),
                            ("shares", "sharesbot")):
            f = root / folder / f"{day}.json"
            if not f.exists():
                continue
            try:
                st = json.loads(f.read_text())
                if key == "shares":
                    t = st.get("trade") or {}
                    out[key][day] = round(float(t.get("pnl_usd", 0) or 0), 2)
                else:
                    out[key][day] = round(sum(float(t["pnl"]) for t in st.get("trades", [])), 2)
            except Exception:
                pass
    _WEEK[today] = out
    return out


def _ohlcv(df) -> list:
    return [[t.strftime("%Y-%m-%d %H:%M"), round(float(r.open), 2), round(float(r.high), 2), round(float(r.low), 2),
             round(float(r.close), 2), int(r.volume)] for t, r in df.iterrows()]


def payload(now, bot, shares, original=None, his=None) -> dict:
    """What the live page shows. Built from data the bots already hold: no extra market-data requests."""
    bars, prev = [], []
    if bot is not None and getattr(bot, "bars", None) is not None and len(bot.bars):
        bars = _ohlcv(bot.bars)
    if bot is not None and getattr(bot, "prev", None) is not None and len(bot.prev):
        prev = _ohlcv(bot.prev.tail(120))  # yesterday's last two hours: warms up the 50 EMA and MACD
    out = {"v": 2, "updated": now.strftime("%Y-%m-%d %H:%M:%S"), "bars": bars, "prev": prev,
           "options": None, "shares": None, "original": None, "his": None, "week": week_history(now.strftime("%Y-%m-%d"))}
    if bot is not None:
        out["options"] = {"trades": bot.s["trades"], "open": bot.s["open"]}
    if shares is not None:
        out["shares"] = shares.s.get("trade")
    if original is not None:
        out["original"] = {"trades": original.s["trades"], "open": original.s["open"]}
    if his is not None:
        out["his"] = {"trades": his.s["trades"], "open": his.s["open"]}
    return json.loads(json.dumps(out, default=float))
