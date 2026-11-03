"""
Intraday market reading on 5-minute bars
========================================
Used by "python bot.py pulse" (every 5 minutes) and by the 0DTE scalper's trend filter.

For each market it works out, from the latest finished 5-minute bar:
  - the direction (up, down or none), from VWAP, its slope, fast and slow averages, the 1-hour trend,
    the opening range and the day's open
  - the kind of market: trending, range-bound (choppy) or mixed
  - which of four day-trading approaches has actually worked on that market over the last ~60 days:
      trend   buy dips to the 21 EMA in an uptrend (sell rallies in a downtrend)
      orb     the first break of the opening range
      fade    in a range, fade a stretch beyond the VWAP bands back towards VWAP
      vwap    every VWAP cross (what the old scalper did): the benchmark to beat
      late    "market intraday momentum": if the first half-hour moved strongly from yesterday's close,
              trade the same way for the last half-hour (Gao, Han, Li & Zhou, J. Financial Economics 2018)
  - and whether the best approach has a fresh signal right now.

Every approach enters at the next bar's open, uses a stop, exits by the end of the session, and pays
a small cost, so the recent record is something you could actually have got. A recent record is
still a small sample: treat it as evidence, not proof.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MARKETS = {
    "SPY": {"name": "S&P 500 (SPY)", "tz": "America/New_York", "start": "09:30", "end": "16:00"},
    "QQQ": {"name": "Nasdaq 100 (QQQ)", "tz": "America/New_York", "start": "09:30", "end": "16:00"},
    "IWM": {"name": "Russell 2000 (IWM)", "tz": "America/New_York", "start": "09:30", "end": "16:00"},
    "^FTSE": {"name": "FTSE 100", "tz": "Europe/London", "start": "08:00", "end": "16:30"},
    "GC=F": {"name": "Gold", "tz": "America/New_York", "start": "03:00", "end": "17:00"},  # London open to the COMEX close
    "BTC-USD": {"name": "Bitcoin", "tz": "UTC", "start": "00:00", "end": "24:00"},
}

APPROACHES = {
    "trend": "Trend pullback",
    "orb": "Opening-range breakout",
    "fade": "Fade back to VWAP",
    "vwap": "VWAP cross",
    "late": "Last-half-hour momentum",
}

HOW = {
    ("trend", "long"): "buy dips to the 21 EMA while it keeps rising; stop under the last 3 bars' low",
    ("trend", "short"): "sell rallies to the 21 EMA while it keeps falling; stop over the last 3 bars' high",
    ("orb", "long"): "buy the first close above the opening range; stop at the middle of the range",
    ("orb", "short"): "sell the first close below the opening range; stop at the middle of the range",
    ("fade", "long"): "buy when price snaps back inside the lower VWAP band; target VWAP",
    ("fade", "short"): "sell when price snaps back inside the upper VWAP band; target VWAP",
    ("vwap", "long"): "buy the close back above VWAP",
    ("vwap", "short"): "sell the close back below VWAP",
    ("late", "long"): "the first half-hour was strongly up, so buy for the last half-hour and sell at the close",
    ("late", "short"): "the first half-hour was strongly down, so sell for the last half-hour and buy back at the close",
}


def spec_for(sym: str, overrides: dict | None = None) -> dict:
    out = dict(MARKETS.get(sym.upper(), {"name": sym, "tz": "America/New_York", "start": "09:30", "end": "16:00"}))
    out.update(overrides or {})
    return out


def _hm(s: str) -> int:
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def prepare(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Bars in the market's own time zone, inside its session hours, labelled by session (trading day)."""
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx
    out = df[["Open", "High", "Low", "Close", "Volume"]].astype(float).copy()
    out.index = idx.tz_convert(spec["tz"])
    out = out[~out.index.duplicated(keep="last")].sort_index().dropna(subset=["Open", "High", "Low", "Close"])
    mins = out.index.hour * 60 + out.index.minute
    out = out[(mins >= _hm(spec["start"])) & (mins < _hm(spec["end"]))]
    out["session"] = out.index.strftime("%Y-%m-%d")
    return out


def _wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def add_intraday(df: pd.DataFrame, spec: dict, bar_minutes: int = 5, or_minutes: int = 30) -> pd.DataFrame:
    """All the intraday lines, scores and signals. df comes from prepare()."""
    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"].clip(lower=0)
    g = df["session"]
    out = df.copy()
    tp = (h + l + c) / 3.0
    w = v if (v > 0).mean() > 0.5 else pd.Series(1.0, index=df.index)  # no volume (indexes): time-weighted
    cw = w.groupby(g).cumsum()
    vwap = (tp * w).groupby(g).cumsum() / cw
    var = ((tp * tp * w).groupby(g).cumsum() / cw - vwap ** 2).clip(lower=0)
    out["vwap"], out["vwap_sd"] = vwap, np.sqrt(var)
    out["vwap_slope"] = vwap - vwap.groupby(g).shift(6)
    for n in (9, 21, 50):
        out[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    out["atr"] = _wilder(tr, 14)
    up_m, dn_m = h.diff(), -l.diff()
    pdm = up_m.where((up_m > dn_m) & (up_m > 0), 0.0)
    mdm = dn_m.where((dn_m > up_m) & (dn_m > 0), 0.0)
    pdi, mdi = 100 * _wilder(pdm, 14) / out["atr"], 100 * _wilder(mdm, 14) / out["atr"]
    out["adx"] = _wilder(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), 14)
    out["er"] = (c - c.shift(12)).abs() / c.diff().abs().rolling(12).sum()  # 1 = straight line, 0 = pure chop

    mins = df.index.hour * 60 + df.index.minute
    since = pd.Series(mins - _hm(spec["start"]), index=df.index)
    out["mins_left"] = _hm(spec["end"]) - mins
    in_or = since < or_minutes
    enough = in_or.groupby(g).transform("sum") >= max(2, or_minutes // bar_minutes // 2)
    or_done = (since >= or_minutes) & enough
    out["or_high"] = h.where(in_or).groupby(g).transform("max").where(or_done)
    out["or_low"] = l.where(in_or).groupby(g).transform("min").where(or_done)
    out["sess_open"] = o.groupby(g).transform("first")
    last_close = c.groupby(g).last()
    out["prev_close"] = g.map(last_close.shift(1))
    first30 = c.where(since < 30).groupby(g).transform("last")  # close of the first half-hour
    out["r_first30"] = (first30 / out["prev_close"] - 1.0).where(since >= 30)

    # 1-hour trend, from finished hours only
    hc = c.resample("60min").last().dropna()
    he = hc.ewm(span=20, adjust=False, min_periods=10).mean()
    h_up, h_dn = (hc > he) & (he > he.shift(3)), (hc < he) & (he < he.shift(3))
    shift = pd.Timedelta(minutes=60)
    out["h1_up"] = pd.Series(h_up.values, index=h_up.index + shift).reindex(df.index, method="ffill").fillna(False).astype(bool)
    out["h1_down"] = pd.Series(h_dn.values, index=h_dn.index + shift).reindex(df.index, method="ffill").fillna(False).astype(bool)

    up = (20 * (c > vwap) + 15 * (out["vwap_slope"] > 0) + 15 * (out["ema9"] > out["ema21"]) + 10 * (c > out["ema50"])
          + 20 * out["h1_up"] + 10 * (c > out["or_high"]) + 10 * (c > out["sess_open"]))
    dn = (20 * (c < vwap) + 15 * (out["vwap_slope"] < 0) + 15 * (out["ema9"] < out["ema21"]) + 10 * (c < out["ema50"])
          + 20 * out["h1_down"] + 10 * (c < out["or_low"]) + 10 * (c < out["sess_open"]))
    out["up_score"], out["down_score"] = up.astype(float), dn.astype(float)
    direction = np.select([(up >= 65) & (up - dn >= 40), (dn >= 65) & (dn - up >= 40)], ["up", "down"], "none")
    trendy = (out["er"] >= 0.35) | (out["adx"] >= 25)
    rangey = (out["er"] < 0.25) & (out["adx"] < 20)
    out["direction"] = direction
    out["kind"] = np.where(direction != "none", np.where(trendy, "trend", "mixed"), np.where(rangey, "range", "mixed"))

    # Signals, judged on the close of each bar (entries at the next bar's open)
    same = g == g.shift(1)
    ok = same & (since >= 15) & (out["mins_left"] > 30)
    low3, high3 = l.rolling(3).min(), h.rolling(3).max()
    a = out["atr"]
    up_t = (out["direction"] == "up") & (out["kind"] == "trend")
    dn_t = (out["direction"] == "down") & (out["kind"] == "trend")
    out["trend_long"] = ok & up_t & (low3 <= out["ema21"]) & (c > out["ema9"]) & (pc <= out["ema9"].shift(1))
    out["trend_short"] = ok & dn_t & (high3 >= out["ema21"]) & (c < out["ema9"]) & (pc >= out["ema9"].shift(1))
    out["trend_lstop"], out["trend_sstop"] = low3 - 0.1 * a, high3 + 0.1 * a
    br_up = (c > out["or_high"]).fillna(False)
    br_dn = (c < out["or_low"]).fillna(False)
    out["orb_long"] = ok & br_up & (br_up.astype(int).groupby(g).cumsum() == 1)
    out["orb_short"] = ok & br_dn & (br_dn.astype(int).groupby(g).cumsum() == 1)
    mid = (out["or_high"] + out["or_low"]) / 2
    out["orb_lstop"], out["orb_sstop"] = mid, mid
    lo_band, hi_band = vwap - 2 * out["vwap_sd"], vwap + 2 * out["vwap_sd"]
    rng = out["kind"] == "range"
    out["fade_long"] = ok & rng & (pc < lo_band.shift(1)) & (c > lo_band) & (c < vwap)
    out["fade_short"] = ok & rng & (pc > hi_band.shift(1)) & (c < hi_band) & (c > vwap)
    out["fade_lstop"], out["fade_sstop"] = low3 - 0.2 * a, high3 + 0.2 * a
    out["vwap_long"] = ok & (c > vwap) & (pc <= vwap.shift(1))
    out["vwap_short"] = ok & (c < vwap) & (pc >= vwap.shift(1))
    out["vwap_lstop"], out["vwap_sstop"] = c - 1.5 * a, c + 1.5 * a
    # last half-hour momentum: the bar that ends 30 minutes before the close, after a big first half-hour
    # (big = more than a quarter of a normal day's range, judged on this market's own 5-minute ATR x 8)
    late_bar = same & (out["mins_left"] > 30) & (out["mins_left"] <= 30 + bar_minutes)
    big = out["r_first30"].abs() * c > 2.0 * a
    out["late_long"] = late_bar & big & (out["r_first30"] > 0)
    out["late_short"] = late_bar & big & (out["r_first30"] < 0)
    out["late_lstop"], out["late_sstop"] = c - 2.0 * a, c + 2.0 * a
    return out


MIN_RISK_ATR = 1.0  # stops closer than one normal 5-minute bar get shaken out by noise, and costs swamp them


def follow(ind: pd.DataFrame, i: int, approach: str, side: str, cost_pct: float = 0.02,
           min_risk_atr: float | None = None) -> dict | None:
    """One trade signalled on bar i's close: enters at bar i+1's open and follows it to the exit.
    Returns None if it can't be taken, else a dict with status 'open' or 'closed' and the result in R."""
    n = len(ind)
    if i + 1 >= n:
        return {"status": "waiting"}
    sess = ind["session"].iat[i]
    if ind["session"].iat[i + 1] != sess:
        return None
    long = side == "long"
    entry = float(ind["Open"].iat[i + 1])
    stop = float(ind[f"{approach}_{'l' if long else 's'}stop"].iat[i])
    atr = float(ind["atr"].iat[i])
    risk = (entry - stop) if long else (stop - entry)
    if not (np.isfinite(risk) and np.isfinite(atr) and atr > 0) or risk <= 0 or risk > 3 * atr:
        return None
    risk = max(risk, (MIN_RISK_ATR if min_risk_atr is None else min_risk_atr) * atr)
    stop = entry - risk if long else entry + risk
    if approach == "fade":
        target = float(ind["vwap"].iat[i])
        if ((target - entry) if long else (entry - target)) < 0.8 * risk:
            return None
    elif approach == "late":
        target = entry + 10 * risk if long else entry - 10 * risk  # no target: held to the close
    else:
        target = entry + 2 * risk if long else entry - 2 * risk
    exit_px, reason, j = None, "", i + 1
    for j in range(i + 1, n):
        if ind["session"].iat[j] != sess:
            j -= 1
            exit_px, reason = float(ind["Close"].iat[j]), "end of the session"
            break
        o, hi, lo, c = (float(ind[k].iat[j]) for k in ("Open", "High", "Low", "Close"))
        first = j == i + 1
        if long:
            if lo <= stop:
                exit_px, reason = (o if (not first and o < stop) else stop), "stop"
                break
            if hi >= target:
                exit_px, reason = (o if (not first and o > target) else target), "target"
                break
            if approach in {"trend", "vwap"} and c < float(ind["vwap"].iat[j]):
                exit_px, reason = c, "closed back below VWAP"
                break
        else:
            if hi >= stop:
                exit_px, reason = (o if (not first and o > stop) else stop), "stop"
                break
            if lo <= target:
                exit_px, reason = (o if (not first and o < target) else target), "target"
                break
            if approach in {"trend", "vwap"} and c > float(ind["vwap"].iat[j]):
                exit_px, reason = c, "closed back above VWAP"
                break
        if float(ind["mins_left"].iat[j]) <= 5:
            exit_px, reason = c, "end of the session"
            break
    trade = {"approach": approach, "side": side, "signal_time": str(ind.index[i]), "entry_time": str(ind.index[i + 1]),
             "entry": entry, "stop": stop, "target": target, "risk": risk, "session": sess}
    if exit_px is None:
        trade.update(status="open", last=float(ind["Close"].iat[-1]))
        return trade
    cost_r = 2 * cost_pct / 100.0 * entry / risk
    r = ((exit_px - entry) if long else (entry - exit_px)) / risk - cost_r
    trade.update(status="closed", exit=exit_px, exit_time=str(ind.index[j]), reason=reason, r=float(r))
    return trade


def backtest(ind: pd.DataFrame, approach: str, cost_pct: float = 0.02, min_risk_atr: float | None = None) -> list[dict]:
    """Every trade the approach would have taken, one at a time."""
    trades = []
    longs, shorts = ind[f"{approach}_long"].to_numpy(bool), ind[f"{approach}_short"].to_numpy(bool)
    busy_until = -1
    pos = {t: k for k, t in enumerate(ind.index)}
    for i in range(len(ind) - 1):
        if i <= busy_until or not (longs[i] or shorts[i]):
            continue
        t = follow(ind, i, approach, "long" if longs[i] else "short", cost_pct, min_risk_atr)
        if not t or t.get("status") != "closed":
            continue
        trades.append(t)
        busy_until = pos[pd.Timestamp(t["exit_time"])]
    return trades


def stats(trades: list[dict]) -> dict:
    r = np.array([t["r"] for t in trades], float)
    if not len(r):
        return {"trades": 0, "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0}
    return {"trades": int(len(r)), "win_rate": float((r > 0).mean()), "avg_r": float(r.mean()), "total_r": float(r.sum())}


def recent_record(ind: pd.DataFrame, cost_pct: float = 0.02, min_risk_atr: float | None = None) -> dict:
    return {a: stats(backtest(ind, a, cost_pct, min_risk_atr)) | {"sessions": int(ind["session"].nunique())}
            for a in APPROACHES}


def suits(direction: str, kind: str) -> list[str]:
    if kind == "trend":
        return ["trend", "orb", "vwap", "late"]
    if kind == "range":
        return ["fade"]
    return []


def best_approach(direction: str, kind: str, record: dict, min_trades: int = 15) -> str | None:
    """The approach that fits today's kind of market AND has made money on this market lately."""
    good = [(record[a]["avg_r"], a) for a in suits(direction, kind)
            if a in record and record[a]["trades"] >= min_trades and record[a]["avg_r"] > 0]
    return max(good)[1] if good else None


def signal_now(ind: pd.DataFrame, approach: str, direction: str) -> str | None:
    """'long' or 'short' if the approach signals on the latest finished bar, in today's direction."""
    if not len(ind):
        return None
    for side in ("long", "short"):
        if bool(ind[f"{approach}_{side}"].iat[-1]):
            if approach in {"orb", "vwap", "late"} and direction != ("up" if side == "long" else "down"):
                continue  # only with the trend
            return side
    return None


def describe(direction: str, kind: str) -> str:
    if kind == "trend":
        return "TRENDING UP" if direction == "up" else "TRENDING DOWN"
    if kind == "range":
        return "RANGE-BOUND (choppy)"
    if direction == "up":
        return "LEANING UP, not trending cleanly"
    if direction == "down":
        return "LEANING DOWN, not trending cleanly"
    return "MIXED: no clear direction"


def advice(direction: str, kind: str, best: str | None) -> str:
    if best:
        side = "long" if direction == "up" else "short" if direction == "down" else "long"
        if best == "fade":
            return "fade the extremes back to VWAP (both ways): " + HOW[("fade", "long")].split(";")[0] + " / " + HOW[("fade", "short")].split(";")[0]
        return f"{APPROACHES[best].lower()}: {HOW[(best, side)]}"
    if kind == "trend":
        return ("go with the trend only (" + ("longs" if direction == "up" else "shorts") +
                "), but none of the approaches has made money here lately: small size or sit out")
    if kind == "range":
        return "choppy: breakouts and trend trades keep failing here. Fade extremes or sit out"
    return "no edge right now: sit out and wait for a clear direction"
