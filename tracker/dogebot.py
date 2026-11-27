"""
Dogecoin dip-buy PAPER bot (owner's request 27 Nov 2026; rule M3 of research/MEME_COIN_PROTOCOL.md, "promising, not
proven": t 2.71 against the 3.0 bar). No orders anywhere: a ledger only. Runs every 15 minutes from .github/workflows/doge.yml; the ledger is doge.json on the live-data branch.

Rule (fixed, exactly as tested):
- 15-minute DOGE/USD bars (Alpaca crypto data, free).
- BUY when a bar closes more than 8% below the close 4 hours (16 bars) earlier, and no trade is open.
- SELL at +5% (target), at -5% (stop), or 12 hours (48 bars) after buying.
- Costs as in the test: 0.25% fee each side plus 0.05% slippage each side.
- Account: £1,000 at the start (fresh start 27 Nov 2026), fully invested in each trade (long only).
It replays every bar closed since its last check, so a late or missed run never skips or invents a trade.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

STATE = Path(__file__).resolve().parent.parent / "state" / "doge" / "state.json"
SYM, DROP, LOOKBACK, TP, SL, HOLD = "DOGE/USD", 0.08, 16, 0.05, 0.05, 48
FEE, SLIP, START_GBP, GBP_USD = 0.0025, 0.0005, 1000.0, 1 / 0.76


def bars(since: datetime) -> pd.DataFrame:
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    df = CryptoHistoricalDataClient().get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=SYM, start=since,
                                                      timeframe=TimeFrame(15, TimeFrameUnit.Minute))).df
    d = df.xs(SYM, level=0)[["open", "high", "low", "close"]].astype(float)
    return d[d.index <= datetime.now(timezone.utc) - timedelta(minutes=15)]  # closed bars only


def step(s: dict, b: pd.DataFrame, say=print) -> dict:
    """Process every closed bar after s['last'] (UTC ISO). Pure ledger logic; tested in tests/test_stage2.py."""
    last = pd.Timestamp(s["last"]) if s.get("last") else None
    c = b.close
    for i in range(len(b)):
        t = b.index[i]
        if last is not None and t <= last:
            continue
        o = s.get("open")
        if o:
            held = sum(1 for x in b.index if pd.Timestamp(o["t"]) < x <= t)
            why = px = None
            if b.low.iloc[i] <= o["stop"]:
                why, px = "stop −5%", o["stop"]
            elif b.high.iloc[i] >= o["target"]:
                why, px = "target +5%", o["target"]
            elif held >= HOLD:
                why, px = "12 hours", float(c.iloc[i])
            if why:
                fill = px * (1 - SLIP)
                usd = o["qty"] * fill * (1 - FEE)
                pnl = usd - o["cost"]
                s["cash"] += usd
                s["trades"].append({**o, "exit_t": t.isoformat(), "exit": round(fill, 6), "why": why, "pnl": round(pnl, 2)})
                s["open"] = None
                say(f"🐶 <b>DOGE paper</b>: SOLD at {fill:.5f} ({why}) · <b>{'+' if pnl >= 0 else '−'}${abs(pnl):.2f}</b> · balance ${s['cash']:.2f}")
        elif i >= LOOKBACK and c.iloc[i] / c.iloc[i - LOOKBACK] - 1 < -DROP:
            fill = float(c.iloc[i]) * (1 + SLIP)
            cost = s["cash"]
            qty = cost * (1 - FEE) / fill
            s["open"] = {"t": t.isoformat(), "entry": round(fill, 6), "qty": qty, "cost": round(cost, 2),
                         "drop": round(c.iloc[i] / c.iloc[i - LOOKBACK] - 1, 4),
                         "target": fill * (1 + TP), "stop": fill * (1 - SL)}
            s["cash"] = 0.0
            say(f"🐶 <b>DOGE paper</b>: BOUGHT ${cost:.2f} at {fill:.5f} after a {s['open']['drop']:+.1%} fall in 4 hours (dip-buy rule)")
        s["last"] = t.isoformat()
    if len(b):
        s["px"], s["px_t"] = float(c.iloc[-1]), b.index[-1].isoformat()
    return s


def _gh():
    import os

    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    return (tok, repo) if tok and repo else (None, None)


def load():
    """The ledger lives on the repo's live-data branch (doge.json), so 15-minute updates don't touch main."""
    tok, repo = _gh()
    if tok:
        import base64

        import requests

        r = requests.get(f"https://api.github.com/repos/{repo}/contents/doge.json", params={"ref": "live-data"},
                         headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        return json.loads(base64.b64decode(r.json()["content"])), r.json()["sha"]
    return (json.loads(STATE.read_text()), None) if STATE.exists() else (None, None)


def save(s, sha):
    tok, repo = _gh()
    if tok:
        import base64

        import requests

        body = {"message": "DOGE paper ledger", "branch": "live-data",
                "content": base64.b64encode(json.dumps(s, indent=1).encode()).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(f"https://api.github.com/repos/{repo}/contents/doge.json", json=body,
                         headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        print(f"saved: {r.status_code}")
        r.raise_for_status()
        return
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def main() -> int:
    s, sha = load()
    s = s or {
        "start_usd": round(START_GBP * GBP_USD, 2), "cash": round(START_GBP * GBP_USD, 2), "open": None, "trades": [],
        "last": None, "started": datetime.now(timezone.utc).isoformat()}
    since = (pd.Timestamp(s["last"]) - timedelta(hours=6)) if s.get("last") else datetime.now(timezone.utc) - timedelta(hours=6)
    try:
        b = bars(since.to_pydatetime() if hasattr(since, "to_pydatetime") else since)
    except Exception as exc:
        print(f"DOGE data: {type(exc).__name__}; nothing changed")
        return 0
    if s.get("last") is None and len(b):
        s["last"] = b.index[-1 - LOOKBACK].isoformat() if len(b) > LOOKBACK else b.index[0].isoformat()
    from qqqbot import send_telegram

    s = step(s, b, say=send_telegram)
    s["checked"] = datetime.now(timezone.utc).isoformat()
    save(s, sha)
    print(f"DOGE: last bar {s.get('last')}, price {s.get('px')}, cash {s['cash']:.2f}, open {bool(s['open'])}, trades {len(s['trades'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
