"""
The pause switch, read by every bot before it opens a trade (enforced in the bots, not on the web page).

The owner changes it with the "Bot controls (pause / resume)" workflow on GitHub (Actions tab -> Run workflow), which
writes controls.json to the repo's live-data branch. The recorder reads that file at most once a minute.
- pause_all: no bot opens a new trade (open trades are still managed and closed by their normal exits).
- paused: a list of bot keys (e.g. "combo", "combo_ctx") that may not open new trades.
If the file has never been read, bots trade normally (there is no pause). If a read fails, the LAST KNOWN state is kept,
so a pause can never be lost by a network error.
"""

from __future__ import annotations

import base64
import json
import os
import time

BRANCH, FILE, EVERY = "live-data", "controls.json", 60


class Controls:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        self.state = {"pause_all": False, "paused": []}
        self.last_try, self.last_ok, self.error = 0.0, None, None

    def refresh(self):
        if time.time() - self.last_try < EVERY or not (self.token and self.repo):
            return
        self.last_try = time.time()
        try:
            import requests

            r = requests.get(f"https://api.github.com/repos/{self.repo}/contents/{FILE}", params={"ref": BRANCH},
                             headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}, timeout=10)
            if r.status_code == 404:
                self.state, self.error = {"pause_all": False, "paused": []}, None  # no switch file yet: nothing paused
            else:
                r.raise_for_status()
                st = json.loads(base64.b64decode(r.json()["content"]))
                self.state = {"pause_all": bool(st.get("pause_all")), "paused": [str(x) for x in st.get("paused", [])],
                              "updated": st.get("updated"), "note": st.get("note")}
                self.error = None
            self.last_ok = time.time()
        except Exception as exc:
            self.error = f"{type(exc).__name__}"  # keep the last known state
            print(f"Controls: read failed ({self.error}); keeping the last known pause state")

    def check(self, key: str) -> str | None:
        """None = allowed to open a trade; otherwise why not."""
        self.refresh()
        if self.state.get("pause_all"):
            return "EMERGENCY PAUSE (all bots)"
        if key in self.state.get("paused", []):
            return f"bot paused by owner ({key})"
        return None

    def status(self) -> dict:
        return dict(self.state, error=self.error, read_ago_s=None if self.last_ok is None else round(time.time() - self.last_ok))
