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


_FX: dict = {"t": 0.0, "v": None}


def fx() -> dict | None:
    """USD->GBP from free public sources (ECB reference rate via Frankfurter; fallback open.er-api.com), at most hourly.
    Fetched here because the page's own browser request can be blocked. Returns the last good value if all fail."""
    import time

    if time.time() - _FX["t"] < 3600 and _FX["v"]:
        return _FX["v"]
    _FX["t"] = time.time()
    import requests

    srcs = [("https://api.frankfurter.dev/v1/latest?base=USD&symbols=GBP", lambda j: (j["rates"]["GBP"], j["date"]), "ECB via frankfurter.dev"),
            ("https://api.frankfurter.app/latest?from=USD&to=GBP", lambda j: (j["rates"]["GBP"], j["date"]), "ECB via frankfurter.app"),
            ("https://open.er-api.com/v6/latest/USD", lambda j: (j["rates"]["GBP"], j["time_last_update_utc"][5:16]), "open.er-api.com")]
    for url, get, name in srcs:
        try:
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            rate, date = get(r.json())
            _FX["v"] = {"rate": float(rate), "date": str(date), "source": name}
            return _FX["v"]
        except Exception as exc:
            print(f"FX {name}: {type(exc).__name__}")
    return _FX["v"]


_WEEK: dict = {}


def flagged() -> set:
    """Trades the daily check (research/fake_trade_scan.py) could not match to a fresh recorded quote: data errors, not
    results. They are left out of every total on the live page (and listed there with the reason). State files unchanged."""
    from pathlib import Path

    try:
        rows = json.loads((Path(__file__).resolve().parent.parent / "audit" / "flagged_trades.json").read_text())
        return {(r["bot"], r["t"]) for r in rows}
    except Exception:
        return set()


def week_history(today: str) -> dict:
    """Daily P&L for each bot on every day before today that it ran, from the saved state files (read once per run).
    The live page uses the last 7 days for its "last 7 days" figure and all of them for the calendar."""
    if today in _WEEK:
        return _WEEK[today]
    from datetime import date, timedelta
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "state"
    d0 = date.fromisoformat(today)
    folders = [("options", "qqqbot"), ("shares", "sharesbot"), ("shares_ctx", "sharesbot_ctx")]  # "original" retired (CC-006)
    try:
        import qqqbot

        folders += [(k, v[0]) for k, v in qqqbot.EXTRA_BOTS.items()]
    except Exception:
        pass
    out = {k: {} for k, _ in folders}
    for key, folder in folders:
        for f in sorted((root / folder).glob("20??-??-??.json")) if (root / folder).is_dir() else []:
            day = f.stem
            if day >= today:
                continue
            try:
                st = json.loads(f.read_text())
                if key.startswith("shares"):
                    t = st.get("trade") or {}
                    out[key][day] = round(float(t.get("pnl_usd", 0) or 0), 2)
                else:
                    bad = flagged()
                    out[key][day] = round(sum(float(t["pnl"]) for t in st.get("trades", []) if (key, t.get("t")) not in bad), 2)
            except Exception:
                pass
    _WEEK[today] = out
    return out


_HIST: dict = {}
_BAD: set = set()


def trade_history(today: str) -> dict:
    """Every closed trade of each bot on the days before today, from the same saved state files (read once per run).
    Compact rows: [entry time, exit time, side, entry, exit, pnl USD, exit reason, trigger]. Display and statistics only."""
    if today in _HIST:
        return _HIST[today]
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "state"
    folders = [("options", "qqqbot"), ("shares", "sharesbot"), ("shares_ctx", "sharesbot_ctx")]
    try:
        import qqqbot

        folders += [(k, v[0]) for k, v in qqqbot.EXTRA_BOTS.items()]
    except Exception:
        pass
    out = {k: [] for k, _ in folders}
    _BAD.clear()
    _BAD.update(flagged())
    for key, folder in folders:
        for f in sorted((root / folder).glob("20??-??-??.json")) if (root / folder).is_dir() else []:
            if f.stem >= today:
                continue
            try:
                st = json.loads(f.read_text())
                rows = [st["trade"]] if key.startswith("shares") and st.get("trade") else st.get("trades", [])
                for t in rows:
                    if key.startswith("shares"):
                        if t.get("exit") is None:
                            continue
                        out[key].append([t.get("t"), t.get("exit_t"), "L" if t.get("side", 1) > 0 else "S", t.get("entry"),
                                         t.get("exit"), round(float(t.get("pnl_usd") or 0), 2), t.get("why"), "one-a-day"])
                    elif (key, t.get("t")) not in _BAD:
                        out[key].append([t.get("t"), t.get("exit_t"), t.get("type"), t.get("entry"), t.get("exit"),
                                         round(float(t["pnl"]), 2), t.get("why"), t.get("trigger")])
            except Exception:
                pass
    _HIST[today] = out
    return out


def _ohlcv(df) -> list:
    return [[t.strftime("%Y-%m-%d %H:%M"), round(float(r.open), 2), round(float(r.high), 2), round(float(r.low), 2),
             round(float(r.close), 2), int(r.volume)] for t, r in df.iterrows()]


def payload(now, bot, shares, original=None, extras=None, shares_ctx=None, controls=None, poll_errors=0) -> dict:
    """What the live page shows. Built from data the bots already hold: no extra market-data requests."""
    bars, prev = [], []
    if bot is not None and getattr(bot, "bars", None) is not None and len(bot.bars):
        bars = _ohlcv(bot.bars)
    if bot is not None and getattr(bot, "prev", None) is not None and len(bot.prev):
        prev = _ohlcv(bot.prev.tail(120))  # yesterday's last two hours: warms up the 50 EMA and MACD
    out = {"v": 2, "updated": now.strftime("%Y-%m-%d %H:%M:%S"), "bars": bars, "prev": prev,
           "options": None, "shares": None, "original": None, "week": {}, "days": {}}
    try:
        from datetime import timedelta

        today = now.strftime("%Y-%m-%d")
        out["days"] = week_history(today)  # every past day, for the calendar
        since = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        out["hist"] = trade_history(today)
        out["week"] = {k: {d: v for d, v in days.items() if d >= since} for k, days in out["days"].items()}
    except Exception:
        pass
    if bot is not None:
        out["options"] = {"trades": bot.s["trades"], "open": bot.s["open"]}
    if shares is not None:
        out["shares"] = shares.s.get("trade")
    if original is not None:
        out["original"] = {"trades": original.s["trades"], "open": original.s["open"]}
    for key, xb in (extras or {}).items():
        out[key] = {"trades": xb.s["trades"], "open": xb.s["open"]}
    out["news"] = news(now)
    # Stage 2: the shared context the bots used (same object as the page shows), each bot's recent decisions, the pause
    # switch as the bots see it, and health counters. All read from the running bots; nothing computed for display only.
    out["ctx"] = getattr(bot, "ctx", None)
    out["shares_ctx"] = shares_ctx.s.get("trade") if shares_ctx is not None else None
    dec = {}
    for k, b in [("options", bot), ("shares", shares), ("shares_ctx", shares_ctx), *((extras or {}).items())]:
        if b is not None:
            dd = b.s.get("decisions", [])
            dec[k] = {"n": len(dd), "signals": sum(1 for x in dd if x.get("sig")), "recent": dd[-60:]}
    out["decisions"] = dec
    out["controls"] = controls.status() if controls is not None else {"error": "pause switch not running"}
    out["poll_errors"] = poll_errors
    out["fx"] = fx()
    try:
        from pathlib import Path

        out["flagged"] = json.loads((Path(__file__).resolve().parent.parent / "audit" / "flagged_trades.json").read_text())
    except Exception:
        out["flagged"] = None
    from datetime import datetime, timezone

    out["now_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # heartbeat, unambiguous for the page
    out["last_bar"] = bars[-1][0] if bars else None
    return json.loads(json.dumps(out, default=float))


_NEWS = {"t": None, "items": []}


def news(now) -> list:
    """Latest headlines for QQQ and its biggest holdings (Alpaca news, free with the account), refreshed every 10 minutes.
    Display only: no bot reads it."""
    import os
    if _NEWS["t"] and (now - _NEWS["t"]).total_seconds() < 600:
        return _NEWS["items"]
    _NEWS["t"] = now
    try:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
        cli = NewsClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
        res = cli.get_news(NewsRequest(symbols="QQQ,AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AVGO", limit=15))
        rows = res.data.get("news", []) if hasattr(res, "data") else []
        _NEWS["items"] = [{"t": str(n.created_at)[:16], "h": n.headline, "src": n.source, "url": n.url,
                           "sym": list(n.symbols)[:4]} for n in rows]
    except Exception as exc:
        print(f"News: {type(exc).__name__}")
    return _NEWS["items"]
