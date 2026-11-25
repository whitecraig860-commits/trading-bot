"""
Shared market context: ONE calculation used by the bots, the "+context" twin bots and the live page.

The live page shows exactly what `market(...)` returns (published in live.json as "ctx"), so what you see is what the
bots read. Built only from the one-minute QQQ bars the bots already hold: no extra data requests, nothing invented.
If there are too few bars the result says so ("ok": False) and the twins treat that as "don't trade".

Rules here mirror the page's "Market conditions" panel (docs/live/index.html, renderConditions):
- Trend: Bullish when EMA 9 > EMA 20 > EMA 50 and EMA 20 has risen over the last 10 minutes; Bearish the mirror image;
  otherwise Sideways. EMAs run over yesterday's last bars plus today's, so they are warm at the open.
- Choppy: Sideways, or 4+ closes crossing EMA 20 in the last 30 minutes.
- Volatility: last 15 minutes' average one-minute range vs the day's average: High above 1.3x, Low below 0.7x.
"""

from __future__ import annotations

import pandas as pd


def market(bars: pd.DataFrame | None, prev: pd.DataFrame | None = None) -> dict:
    if bars is None or len(bars) < 15:
        return {"ok": False, "why": f"only {0 if bars is None else len(bars)} one-minute bars today (need 15)"}
    allc = pd.concat([prev.close, bars.close]) if prev is not None and len(prev) else bars.close
    n = len(bars)
    e9 = allc.ewm(span=9, adjust=False).mean().iloc[-n:]
    e20 = allc.ewm(span=20, adjust=False).mean().iloc[-n:]
    e50 = allc.ewm(span=50, adjust=False).mean().iloc[-n:]
    c = bars.close
    tp = (bars.high + bars.low + bars.close) / 3
    vol = bars.volume.where(bars.volume > 0, 1.0)
    vwap = (tp * vol).cumsum() / vol.cumsum()
    slope = float(e20.iloc[-1] - e20.iloc[max(0, n - 11)])
    if e9.iloc[-1] > e20.iloc[-1] > e50.iloc[-1] and slope > 0:
        trend = "Bullish"
    elif e9.iloc[-1] < e20.iloc[-1] < e50.iloc[-1] and slope < 0:
        trend = "Bearish"
    else:
        trend = "Sideways"
    side = (c - e20).iloc[-31:]
    crosses = int(((side * side.shift(1)) < 0).sum())
    rng = (bars.high - bars.low)
    atr15, atr_day = float(rng.iloc[-15:].mean()), float(rng.mean())
    volat = "High" if atr15 > atr_day * 1.3 else "Low" if atr15 < atr_day * 0.7 else "Normal"
    d = allc.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean(), (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = float(100 - 100 / (1 + up.iloc[-1] / (dn.iloc[-1] or 1e-9)))
    m = allc.ewm(span=12, adjust=False).mean() - allc.ewm(span=26, adjust=False).mean()
    return {"ok": True, "t": bars.index[-1].strftime("%Y-%m-%d %H:%M"), "price": round(float(c.iloc[-1]), 2),
            "vwap": round(float(vwap.iloc[-1]), 2), "ema9": round(float(e9.iloc[-1]), 2), "ema20": round(float(e20.iloc[-1]), 2),
            "ema50": round(float(e50.iloc[-1]), 2), "trend": trend, "crosses30": crosses,
            "choppy": trend == "Sideways" or crosses >= 4, "volatility": volat, "rsi": round(rsi, 1),
            "macd": round(float(m.iloc[-1]), 3), "macd_signal": round(float(m.ewm(span=9, adjust=False).mean().iloc[-1]), 3),
            "day_high": round(float(bars.high.max()), 2), "day_low": round(float(bars.low.min()), 2),
            "atr1m_15": round(atr15, 3), "atr1m_day": round(atr_day, 3), "bars": n}


def gate(ctx: dict, side: str) -> str | None:
    """The +context twins' rule (research/CONTEXT_TWINS_PROTOCOL.md). None = allowed, else the reason it is blocked.
    side: "C"/"P" for options, or +1/-1 for shares (long/short)."""
    if not ctx or not ctx.get("ok"):
        return "context unavailable: " + (ctx or {}).get("why", "no data")
    long_ = side in ("C", 1)
    if ctx["choppy"]:
        return f"choppy market ({ctx['trend']}, {ctx['crosses30']} EMA 20 crosses in 30 min)"
    if long_ and ctx["trend"] != "Bullish":
        return f"call/long against a {ctx['trend']} trend"
    if not long_ and ctx["trend"] != "Bearish":
        return f"put/short against a {ctx['trend']} trend"
    return None
