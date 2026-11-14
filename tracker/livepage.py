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


def payload(now, bot, shares) -> dict:
    bars = []
    if bot is not None and getattr(bot, "bars", None) is not None and len(bot.bars):
        bars = [[t.strftime("%H:%M"), round(float(c), 2)] for t, c in bot.bars.close.items()]
    out = {"updated": now.strftime("%Y-%m-%d %H:%M:%S"), "bars": bars, "options": None, "shares": None}
    if bot is not None:
        out["options"] = {"trades": bot.s["trades"], "open": bot.s["open"]}
    if shares is not None:
        out["shares"] = shares.s.get("trade")
    return json.loads(json.dumps(out, default=float))
