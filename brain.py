"""
The chart brain: reads SPY, QQQ and IWM on three timeframes before the scalper trades
=====================================================================================
  1 hour     the big picture: trend, and the major support and resistance (yesterday's high/low, hourly swings)
  15 minutes market structure: higher highs/lows or lower highs/lows, breaks of structure, changes of character
  5 minutes  the trade itself: candles and wicks, sweeps, failed breakouts, fair value gaps, VWAP, volume, RSI
  (1-minute bars are only used to build these: on their own they're mostly noise.)

What it looks for (every one only uses candles that have finished, so the backtest sees what the bot would have seen):
  - Liquidity sweep: a wick pokes past a previous high/low (or yesterday's, the pre-market's, the opening range's)
    and the candle closes back inside. Stops above/below that level were taken, then price turned: a failed
    breakout / liquidity grab. It measures how fast (in candles) and how far (in ATRs) it came back.
  - Rejection zones: several wicks turned back in the same area, kept as a zone (low to high), not one price.
  - Break of structure (BOS): a close past the last swing high/low in the trend's direction.
    Change of character (CHoCH): the first close past the last swing AGAINST the trend (an uptrend losing its last
    higher low).
  - Fair value gaps: three candles where the 1st and 3rd don't overlap (a gap price moved through too fast). It
    tracks whether price came back into the gap and whether the gap held (respected) or was filled through.
  - VWAP: above or below, how far, rising or falling, and whether price has been bouncing off it (support) or
    being pushed back by it (resistance).
  - Volume: spikes, fading volume, a breakout WITHOUT volume, and the volume on up-candles vs down-candles. That
    last one is only a rough estimate from candles, not real order flow (see orderflow.py for what Alpaca gives).
  - RSI divergence: a new price low with a higher RSI low (bullish), a new price high with a lower RSI high (bearish).
  - Inside bars (compression: getting ready to move) and outside bars (expansion).
  - Equal highs / equal lows: clusters of matching highs or lows, where stop orders pile up (liquidity pools).
  - Volatility: ATR now vs normal (expanding, contracting), and candles far bigger than normal (chasing).
  - Session levels: yesterday's high/low/close, the pre-market high/low (4:00-9:30 New York, which overlaps the
    London session), the opening range and today's high/low. Asian-session levels can't be read for these US funds:
    Alpaca has no overnight trading for them.
  - Candle patterns: the bot's own (hammer, shooting star, engulfing, doji...) plus TA-Lib's 61 if it's installed.

analyse() turns all of that into a score and a written explanation: the setup, what it saw for the trade, the
concerns, risk/reward, and the decision. Only a few of these move the decision (tested in optionbt.py); the rest are
there so you can see whether it understands the chart.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import candles

OHLCV = ["Open", "High", "Low", "Close", "Volume"]

try:  # optional: 61 candlestick patterns. The bot works the same without it.
    import talib  # type: ignore

    _TALIB_PATTERNS = [f for f in talib.get_function_groups().get("Pattern Recognition", [])]
except Exception:  # pragma: no cover - TA-Lib not installed
    talib = None
    _TALIB_PATTERNS = []


# ---------------------------------------------------------------------------
# Building the three timeframes
# ---------------------------------------------------------------------------


def resample(df: pd.DataFrame, rule: str, offset: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    out = df[OHLCV].resample(rule, label="left", closed="left", offset=offset).agg(agg)
    return out.dropna(subset=["Open"])


def rth(df: pd.DataFrame) -> pd.DataFrame:
    return df.between_time("09:30", "15:59") if df is not None and len(df) else df


def add_indicators(m: pd.DataFrame, ema_len: int = 20) -> pd.DataFrame:
    m = m.copy()
    pc = m["Close"].shift(1)
    tr = pd.concat([m["High"] - m["Low"], (m["High"] - pc).abs(), (m["Low"] - pc).abs()], axis=1).max(axis=1)
    m["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=3).mean()
    d = m["Close"].diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=5).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=5).mean()
    m["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    m["ema"] = m["Close"].ewm(span=ema_len, adjust=False).mean()
    m["vol_avg"] = m["Volume"].rolling(20, min_periods=5).mean()
    return m


def build(today1: pd.DataFrame, hist: pd.DataFrame | None = None, pre1: pd.DataFrame | None = None,
          ema_len: int = 20) -> dict | None:
    """Everything the brain reads, from finished bars only.
    today1: today's 1-minute bars from 9:30 (finished ones). hist: earlier days, 1- or 5-minute bars (any hours).
    pre1: today's pre-market 1-minute bars (4:00-9:29), optional."""
    if today1 is None or len(today1) < 5:
        return None
    day = today1.index[-1].normalize()
    m5t = resample(today1, "5min")
    if len(today1) and len(m5t):
        last_end = today1.index[-1] + pd.Timedelta(minutes=1)
        if m5t.index[-1] + pd.Timedelta(minutes=5) > last_end:
            m5t = m5t.iloc[:-1]  # the last 5-minute candle isn't finished yet
    if len(m5t) < 2:
        return None
    h5 = pd.DataFrame(columns=OHLCV)
    prev = None
    if hist is not None and len(hist):
        hr = rth(hist[hist.index < day])
        if len(hr):
            h5 = resample(hr, "5min")
            last_day = hr.index[-1].normalize()
            pd_bars = hr[hr.index >= last_day]
            prev = {"high": float(pd_bars["High"].max()), "low": float(pd_bars["Low"].min()),
                    "close": float(pd_bars["Close"].iloc[-1])}
    m5 = add_indicators(pd.concat([h5, m5t])[OHLCV].astype(float), ema_len)
    tp = (m5t["High"] + m5t["Low"] + m5t["Close"]) / 3
    v = m5t["Volume"].clip(lower=0)
    cv = v.cumsum()
    vwap = ((tp * v).cumsum() / cv.replace(0, np.nan)).fillna(tp.expanding().mean())
    m5["vwap"] = np.nan
    m5.loc[m5t.index, "vwap"] = vwap.to_numpy()
    full5 = m5[OHLCV]
    m15 = add_indicators(resample(full5, "15min"), ema_len)
    h1 = add_indicators(resample(full5, "60min", offset="30min"), ema_len)
    # drop a still-forming 15-minute or 1-hour candle
    end = m5t.index[-1] + pd.Timedelta(minutes=5)
    m15 = m15[m15.index + pd.Timedelta(minutes=15) <= end]
    h1 = h1[h1.index + pd.Timedelta(minutes=60) <= end]
    pre = None
    if pre1 is not None and len(pre1):
        p = pre1[(pre1.index >= day + pd.Timedelta(hours=4)) & (pre1.index < day + pd.Timedelta(hours=9, minutes=30))]
        if len(p):
            pre = {"high": float(p["High"].max()), "low": float(p["Low"].min())}
    o3 = m5t.iloc[:3]
    return {"m5": m5, "n_today": len(m5t), "m15": m15, "h1": h1, "prev": prev, "pre": pre,
            "or": {"high": float(o3["High"].max()), "low": float(o3["Low"].min())} if len(m5t) >= 3 else None,
            "day_open": float(m5t["Open"].iloc[0]), "today_high": float(m5t["High"].max()),
            "today_low": float(m5t["Low"].min()), "time": m5t.index[-1] + pd.Timedelta(minutes=5)}


# ---------------------------------------------------------------------------
# What it looks for
# ---------------------------------------------------------------------------


def trend_1h(h1: pd.DataFrame) -> tuple[int, str]:
    if len(h1) < 8:
        return 0, "1-hour: not enough history"
    c, e = float(h1["Close"].iloc[-1]), float(h1["ema"].iloc[-1])
    slope = float(h1["ema"].iloc[-1] - h1["ema"].iloc[-4])
    st, txt = candles.structure(h1, len(h1) - 1, k=2)
    if c > e and slope > 0 and st != "down":
        return 1, f"1-hour trend up (above its rising 20 EMA; {txt})"
    if c < e and slope < 0 and st != "up":
        return -1, f"1-hour trend down (below its falling 20 EMA; {txt})"
    return 0, f"1-hour trend unclear ({txt})"


def structure_events(m: pd.DataFrame, k: int = 2) -> dict:
    """Trend from swings, plus break of structure (BOS) and change of character (CHoCH) on the last candle."""
    i = len(m) - 1
    if i < 6:
        return {"trend": "unclear", "text": "not enough candles", "bos": 0, "choch": 0}
    st, txt = candles.structure(m, i, k)
    highs, lows = candles.swing_points(m, i, k)
    c, pc = float(m["Close"].iloc[i]), float(m["Close"].iloc[i - 1])
    bos = choch = 0
    if highs and pc <= highs[-1][1] < c:
        if st == "up":
            bos = 1
        elif st == "down":
            choch = 1
    if lows and pc >= lows[-1][1] > c:
        if st == "down":
            bos = -1
        elif st == "up":
            choch = -1
    return {"trend": st, "text": txt, "bos": bos, "choch": choch,
            "last_high": highs[-1][1] if highs else None, "last_low": lows[-1][1] if lows else None}


def key_levels(ctx: dict) -> list[tuple[str, float]]:
    m5, n = ctx["m5"], ctx["n_today"]
    today = m5.iloc[-n:]
    out = []
    if ctx.get("prev"):
        out += [("yesterday's high", ctx["prev"]["high"]), ("yesterday's low", ctx["prev"]["low"])]
    if ctx.get("pre"):
        out += [("the pre-market high", ctx["pre"]["high"]), ("the pre-market low", ctx["pre"]["low"])]
    if ctx.get("or") and n > 3:
        out += [("the opening-range high", ctx["or"]["high"]), ("the opening-range low", ctx["or"]["low"])]
    highs, lows = candles.swing_points(today, len(today) - 2, 2) if len(today) > 6 else ([], [])
    out += [("a recent swing high", h) for _, h in highs[-3:]] + [("a recent swing low", lo) for _, lo in lows[-3:]]
    return out


def sweeps(ctx: dict, atr: float) -> list[dict]:
    """Liquidity sweeps in the last 3 candles: a wick past a level and a close back inside."""
    m5, n = ctx["m5"], ctx["n_today"]
    today = m5.iloc[-n:]
    i = len(today) - 1
    found = []
    for name, lvl in key_levels(ctx):
        for j in range(max(1, i - 2), i + 1):
            lo, hi, c = float(today["Low"].iloc[j]), float(today["High"].iloc[j]), float(today["Close"].iloc[j])
            prior = today.iloc[:j]
            if lo < lvl and c > lvl and (not len(prior) or float(prior["Low"].min()) >= lvl - 0.05 * atr):
                found.append({"dir": 1, "level": lvl, "name": name, "bars_ago": i - j,
                              "depth": (lvl - lo) / atr, "back": (float(today["Close"].iloc[i]) - lvl) / atr})
            if hi > lvl and c < lvl and (not len(prior) or float(prior["High"].max()) <= lvl + 0.05 * atr):
                found.append({"dir": -1, "level": lvl, "name": name, "bars_ago": i - j,
                              "depth": (hi - lvl) / atr, "back": (lvl - float(today["Close"].iloc[i])) / atr})
    # keep the clearest one each way
    best = {}
    for f in found:
        if f["back"] > 0 and (f["dir"] not in best or f["back"] > best[f["dir"]]["back"]):
            best[f["dir"]] = f
    return list(best.values())


def failed_breakouts(ctx: dict, atr: float) -> list[dict]:
    """A CLOSE past a key level that couldn't hold: back inside within 3 candles. Speed = candles it lasted,
    strength = how far back inside it is now (ATRs)."""
    m5, n = ctx["m5"], ctx["n_today"]
    today = m5.iloc[-n:]
    i = len(today) - 1
    C = today["Close"].to_numpy(float)
    out = []
    for name, lvl in key_levels(ctx):
        for j in range(max(1, i - 5), i):
            if C[j] > lvl >= C[j - 1] and C[i] < lvl and all(C[k] >= lvl for k in range(j, min(i, j + 3))) and i - j <= 3:
                out.append({"dir": -1, "name": name, "level": lvl, "bars": i - j, "back": (lvl - C[i]) / atr})
            if C[j] < lvl <= C[j - 1] and C[i] > lvl and all(C[k] <= lvl for k in range(j, min(i, j + 3))) and i - j <= 3:
                out.append({"dir": 1, "name": name, "level": lvl, "bars": i - j, "back": (C[i] - lvl) / atr})
    return out


def zones(m: pd.DataFrame, atr: float, lookback: int = 60) -> tuple[list, list]:
    """Rejection zones: (low, high, touches) where 2+ wicks (at least 40% of their candle) turned back."""
    i = len(m) - 1
    j0 = max(0, i - lookback)
    tops, bots = [], []
    for j in range(j0, i + 1):
        o, h, lo, c = (float(m[k].iloc[j]) for k in ("Open", "High", "Low", "Close"))
        p = candles.parts(o, h, lo, c)
        if p["upper"] >= 0.4:
            tops.append(h)
        if p["lower"] >= 0.4:
            bots.append(lo)

    def cluster(xs):
        out = []
        for x in sorted(xs):
            if out and x - out[-1][1] <= 0.25 * atr:
                out[-1] = (out[-1][0], x, out[-1][2] + 1)
            else:
                out.append((x, x, 1))
        return [z for z in out if z[2] >= 2]

    return cluster(tops), cluster(bots)


def fair_value_gaps(m: pd.DataFrame, atr: float, lookback: int = 40) -> list[dict]:
    """Three-candle gaps: bullish when candle 3's low is above candle 1's high (and the reverse). For each: was it
    revisited, and did it hold (price reacted away) or get filled through?"""
    i = len(m) - 1
    H, L, C = (m[k].to_numpy(float) for k in ("High", "Low", "Close"))
    out = []
    for k in range(max(2, i - lookback), i + 1):
        if L[k] > H[k - 2] and (L[k] - H[k - 2]) >= 0.1 * atr:
            lo, hi = H[k - 2], L[k]
            later = range(k + 1, i + 1)
            touched = [j for j in later if L[j] <= hi]
            filled = any(C[j] < lo for j in later)
            held = bool(touched) and not filled and C[i] > hi
            out.append({"dir": 1, "low": lo, "high": hi, "age": i - k, "touched": bool(touched), "filled": filled,
                        "held": held, "reaction": (C[i] - hi) / atr if touched else 0.0})
        if H[k] < L[k - 2] and (L[k - 2] - H[k]) >= 0.1 * atr:
            lo, hi = H[k], L[k - 2]
            later = range(k + 1, i + 1)
            touched = [j for j in later if H[j] >= lo]
            filled = any(C[j] > hi for j in later)
            held = bool(touched) and not filled and C[i] < lo
            out.append({"dir": -1, "low": lo, "high": hi, "age": i - k, "touched": bool(touched), "filled": filled,
                        "held": held, "reaction": (lo - C[i]) / atr if touched else 0.0})
    return out


def vwap_role(m: pd.DataFrame, n: int, atr: float) -> dict:
    today = m.iloc[-n:]
    c, vw = float(today["Close"].iloc[-1]), float(today["vwap"].iloc[-1])
    slope = float(today["vwap"].iloc[-1] - today["vwap"].iloc[max(0, len(today) - 7)])
    sup = res = 0
    for j in range(max(0, len(today) - 12), len(today)):
        lo, hi, cl, v = (float(today[k].iloc[j]) for k in ("Low", "High", "Close", "vwap"))
        if lo <= v + 0.15 * atr and cl > v and lo > v - 0.6 * atr:
            sup += 1
        if hi >= v - 0.15 * atr and cl < v and hi < v + 0.6 * atr:
            res += 1
    return {"above": c > vw, "dist": (c - vw) / atr, "rising": slope > 0, "support": sup, "resistance": res, "vwap": vw}


def volume_read(m: pd.DataFrame, n: int) -> dict:
    today = m.iloc[-n:]
    v = float(today["Volume"].iloc[-1])
    avg = float(m["vol_avg"].iloc[-1]) if np.isfinite(m["vol_avg"].iloc[-1]) else v
    last5 = float(today["Volume"].iloc[-5:].mean())
    prior = float(m["Volume"].iloc[-25:-5].mean()) if len(m) > 25 else last5
    win = today.iloc[-12:]
    upv = float(win.loc[win["Close"] > win["Open"], "Volume"].sum())
    dnv = float(win.loc[win["Close"] < win["Open"], "Volume"].sum())
    return {"ratio": v / avg if avg > 0 else 1.0, "fading": prior > 0 and last5 < 0.7 * prior,
            "up_share": upv / (upv + dnv) if upv + dnv > 0 else 0.5}


def rsi_divergence(m: pd.DataFrame) -> tuple[int, str] | None:
    i = len(m) - 1
    highs, lows = candles.swing_points(m, i, 2)
    R = m["rsi"].to_numpy(float)
    if len(lows) >= 2:
        (j1, p1), (j2, p2) = lows[-2], lows[-1]
        if i - j2 <= 6 and p2 < p1 and np.isfinite(R[j1]) and np.isfinite(R[j2]) and R[j2] > R[j1] + 2:
            return 1, f"bullish RSI divergence: a lower low in price but a higher low in RSI ({R[j1]:.0f} → {R[j2]:.0f})"
    if len(highs) >= 2:
        (j1, p1), (j2, p2) = highs[-2], highs[-1]
        if i - j2 <= 6 and p2 > p1 and np.isfinite(R[j1]) and np.isfinite(R[j2]) and R[j2] < R[j1] - 2:
            return -1, f"bearish RSI divergence: a higher high in price but a lower high in RSI ({R[j1]:.0f} → {R[j2]:.0f})"
    return None


def compression(m: pd.DataFrame) -> dict:
    H, L = m["High"].to_numpy(float), m["Low"].to_numpy(float)
    i = len(m) - 1
    inside = 0
    j = i - 1
    while j >= 1 and H[j] <= H[j - 1] and L[j] >= L[j - 1]:
        inside += 1
        j -= 1
    rng = H - L
    nr7 = i >= 7 and rng[i - 1] <= rng[i - 7:i].min()
    outside = i >= 1 and H[i] > H[i - 1] and L[i] < L[i - 1]
    return {"inside_before": inside, "nr7_before": bool(nr7), "outside_now": bool(outside)}


def equal_levels(m: pd.DataFrame, atr: float) -> tuple[list, list]:
    """Clusters of 2+ swing highs (or lows) within 0.1 ATR: liquidity pools."""
    highs, lows = candles.swing_points(m, len(m) - 1, 2)

    def pools(pts):
        vals = sorted(p for _, p in pts)
        out, cur = [], []
        for x in vals:
            if cur and x - cur[-1] > 0.1 * atr:
                if len(cur) >= 2:
                    out.append((float(np.mean(cur)), len(cur)))
                cur = []
            cur.append(x)
        if len(cur) >= 2:
            out.append((float(np.mean(cur)), len(cur)))
        return out

    return pools(highs[-12:]), pools(lows[-12:])


def volatility(m: pd.DataFrame, n: int) -> dict:
    atr = float(m["atr"].iloc[-1])
    base = float(m["atr"].iloc[-min(len(m), 240):].median())
    rng = float(m["High"].iloc[-1] - m["Low"].iloc[-1])
    ratio = atr / base if base > 0 else 1.0
    return {"ratio": ratio, "state": "expanding" if ratio > 1.3 else ("contracting" if ratio < 0.75 else "normal"),
            "big_bar": rng > 2.5 * atr}


def talib_patterns(m: pd.DataFrame) -> list[tuple[str, int]]:
    if talib is None or len(m) < 12:
        return []
    o, h, lo, c = (m[k].to_numpy(float)[-60:] for k in ("Open", "High", "Low", "Close"))
    out = []
    for f in _TALIB_PATTERNS:
        try:
            v = int(getattr(talib, f)(o, h, lo, c)[-1])
        except Exception:
            continue
        if v:
            out.append((f[3:].replace("_", " ").title(), 1 if v > 0 else -1))
    return out


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------


def analyse(ctx: dict, side: str, risk: float, cfg: dict | None = None, extra: list | None = None) -> dict:
    """Score a call or a put and explain it. risk = the share's distance to the stop (VWAP).
    extra: more (sign, text) observations from elsewhere (e.g. order flow), shown but not scored."""
    cfg = cfg or {}
    want = 1 if side == "call" else -1
    m5, n = ctx["m5"], ctx["n_today"]
    i = len(m5) - 1
    c = float(m5["Close"].iloc[i])
    atr = float(m5["atr"].iloc[i]) if np.isfinite(m5["atr"].iloc[i]) else max(risk, c * 0.001)
    seen, concerns, notes = [], [], []
    score, veto, setup = 0, None, None

    def add(pts: int, text: str) -> None:
        nonlocal score
        score += pts
        (seen if pts > 0 else concerns if pts < 0 else notes).append(text)

    # 1 hour
    t1, t1_text = trend_1h(ctx["h1"])
    if t1 == want:
        add(1, t1_text)
    elif t1 == -want:
        add(-2, t1_text + f": against a {side}")
        if cfg.get("brain_veto_1h", False):
            veto = veto or f"the 1-hour trend is the other way ({t1_text})"
    else:
        add(0, t1_text)
    # 15 minutes
    s15 = structure_events(ctx["m15"])
    t15 = {"up": 1, "down": -1}.get(s15["trend"], 0)
    if t15 == want:
        add(1, f"15-minute: {s15['text']}")
    elif t15 == -want:
        add(-2, f"15-minute: {s15['text']}: against a {side}")
        if cfg.get("brain_veto_15m", True):
            veto = veto or f"the 15-minute highs and lows say the opposite ({s15['text']})"
    else:
        add(0, f"15-minute: {s15['text']}")
    if s15["choch"] == want:
        add(1, "15-minute change of character in its favour (the old trend just broke)")
    elif s15["choch"] == -want:
        add(-2, "15-minute change of character against it (the trend it relies on just broke)")
    if s15["bos"] == want:
        add(1, "15-minute break of structure in its direction")
    # 5 minutes: structure
    s5 = structure_events(m5)
    t5 = {"up": 1, "down": -1}.get(s5["trend"], 0)
    if t5 == want:
        add(1, f"5-minute: {s5['text']}")
    elif t5 == -want:
        add(-1, f"5-minute: {s5['text']}")
    if s5["bos"] == want:
        add(1, "5-minute break of structure (closed past the last swing " + ("high)" if want > 0 else "low)"))
    if s5["choch"] == -want:
        add(-1, "5-minute change of character against it")
    # sweeps and failed breakouts
    for sw in sweeps(ctx, atr):
        kind = "sell-side" if sw["dir"] > 0 else "buy-side"
        txt = (f"{kind} liquidity sweep: took out {sw['name']} ({sw['level']:.2f}) by {sw['depth']:.1f} ATR and "
               f"closed back {'above' if sw['dir'] > 0 else 'below'} ({sw['bars_ago'] + 1} candle"
               f"{'s' if sw['bars_ago'] else ''} ago, now {sw['back']:.1f} ATR back inside)")
        if sw["dir"] == want:
            add(2, txt)
            setup = setup or f"{kind} liquidity sweep"
        else:
            add(-2, txt)
    for fb in failed_breakouts(ctx, atr):
        txt = (f"failed break{'out above' if fb['dir'] < 0 else 'down below'} {fb['name']} ({fb['level']:.2f}): "
               f"couldn't hold for more than {fb['bars']} candle{'s' if fb['bars'] != 1 else ''}, "
               f"now {fb['back']:.1f} ATR back inside")
        if fb["dir"] == want:
            add(1, txt)
            setup = setup or "failed breakout the other way"
        else:
            add(-1, txt)
    # zones and room to the target
    tops, bots = zones(m5, atr)
    need = float(cfg.get("target_r", 1.0)) * max(risk, 1e-9)
    walls = [(lo, hi, t) for lo, hi, t in (tops if want > 0 else bots) if (lo - c) * want > 0 or (hi - c) * want > 0]
    walls = [z for z in walls if ((z[0] if want > 0 else z[1]) - c) * want > 0]
    levels = [(nm, lv) for nm, lv in key_levels(ctx) if (lv - c) * want > 0 and "recent swing" not in nm]
    room, wall_txt = None, None
    if walls:
        z = min(walls, key=lambda z: abs((z[0] if want > 0 else z[1]) - c))
        edge = z[0] if want > 0 else z[1]
        room, wall_txt = abs(edge - c), f"{'resistance' if want > 0 else 'support'} zone {z[0]:.2f}-{z[1]:.2f} ({z[2]} wicks)"
    if levels:
        nm, lv = min(levels, key=lambda x: abs(x[1] - c))
        if room is None or abs(lv - c) < room:
            room, wall_txt = abs(lv - c), f"{nm} at {lv:.2f}"
    if room is not None and room < need:
        add(-2, f"{wall_txt} is only {room:.2f} away and the target needs {need:.2f}")
    elif room is not None:
        add(0, f"room to the target: the next wall is {wall_txt}, {room:.2f} away")
    own = bots if want > 0 else tops
    near = [z for z in own if z[0] - 0.2 * atr <= float(m5["Low" if want > 0 else "High"].iloc[i]) <= z[1] + 0.2 * atr]
    if near:
        z = near[0]
        add(1, f"bounced off a {'support' if want > 0 else 'resistance'} zone {z[0]:.2f}-{z[1]:.2f} ({z[2]} wicks)")
        setup = setup or f"rejection from a {'support' if want > 0 else 'resistance'} zone"
    # fair value gaps
    for g in fair_value_gaps(m5, atr):
        if g["held"] and g["dir"] == want and g["age"] <= 24:
            add(1, f"price came back into a {'bullish' if want > 0 else 'bearish'} fair value gap "
                   f"({g['low']:.2f}-{g['high']:.2f}) and it held ({g['reaction']:.1f} ATR reaction)")
            setup = setup or "fair value gap retest"
            break
    against_gap = [g for g in fair_value_gaps(m5, atr) if g["dir"] == -want and not g["filled"]
                   and (((g["low"] - c) * want > 0) and abs((g["low"] if want > 0 else g["high"]) - c) < need)]
    if against_gap:
        g = against_gap[0]
        add(0, f"an unfilled {'bearish' if want > 0 else 'bullish'} gap sits in the way at {g['low']:.2f}-{g['high']:.2f}")
    # VWAP
    vr = vwap_role(m5, n, atr)
    side_ok = vr["above"] == (want > 0)
    vtxt = (f"price {'above' if vr['above'] else 'below'} VWAP ({vr['dist']:+.1f} ATR), VWAP "
            f"{'rising' if vr['rising'] else 'falling'}")
    if side_ok and (vr["rising"] == (want > 0)):
        add(0, vtxt)
    elif not side_ok:
        add(-1, vtxt)
    else:
        add(0, vtxt)
    if want > 0 and vr["support"] >= 2:
        add(1, f"VWAP acting as support ({vr['support']} bounces off it in the last hour)")
    if want < 0 and vr["resistance"] >= 2:
        add(1, f"VWAP acting as resistance ({vr['resistance']} rejections in the last hour)")
    if abs(vr["dist"]) > 2.5:
        add(-1, f"stretched {abs(vr['dist']):.1f} ATR from VWAP: chasing")
    # volume
    vo = volume_read(m5, n)
    if vo["ratio"] >= 1.8:
        add(1, f"volume spike: {vo['ratio']:.1f}x the average on the signal candle")
    elif s5["bos"] == want and vo["ratio"] < 0.8:
        add(-1, f"broke out WITHOUT volume ({vo['ratio']:.1f}x average): breakouts like that often fail")
    if vo["fading"]:
        add(0, "volume has been fading for the last 25 minutes")
    share = vo["up_share"] if want > 0 else 1 - vo["up_share"]
    add(0, f"{share:.0%} of the last hour's volume was on {'green' if want > 0 else 'red'} candles "
           "(a rough estimate from candles, not real order flow)")
    # momentum
    dv = rsi_divergence(m5)
    if dv:
        add(1 if dv[0] == want else -1, dv[1])
    r = float(m5["rsi"].iloc[i]) if np.isfinite(m5["rsi"].iloc[i]) else 50.0
    if (want > 0 and r >= 75) or (want < 0 and r <= 25):
        add(-1, f"RSI {r:.0f}: already {'overbought' if want > 0 else 'oversold'}")
    else:
        add(0, f"RSI {r:.0f}")
    # compression / expansion
    cp = compression(m5)
    if cp["inside_before"] >= 1 or cp["nr7_before"]:
        add(0, f"breaking out of compression ({cp['inside_before']} inside bar{'s' if cp['inside_before'] != 1 else ''}"
               f"{', narrowest range of 7' if cp['nr7_before'] else ''})")
    if cp["outside_now"]:
        add(0, "outside bar: the range is expanding")
    # equal highs / lows (liquidity pools)
    eh, el = equal_levels(m5.iloc[-max(n, 30):], atr)
    pools = [(lv, k) for lv, k in (eh if want > 0 else el) if (lv - c) * want > 0]
    if pools:
        lv, k = min(pools, key=lambda x: abs(x[0] - c))
        add(0, f"liquidity pool: {k} equal {'highs' if want > 0 else 'lows'} at {lv:.2f} (price is often drawn there)")
    # volatility
    vl = volatility(m5, n)
    if vl["big_bar"]:
        add(-1, "the signal candle is over 2.5x a normal candle: unusually aggressive, easy to chase")
    add(0, f"volatility {vl['state']} (ATR {vl['ratio']:.1f}x normal)")
    # candles
    for k in (i, i - 1):
        pat = candles.candle_pattern(m5, k)
        if pat and pat[1] != 0:
            add(1 if pat[1] == want else -1, f"{pat[0]}{' (last candle)' if k == i - 1 else ''}: {pat[2]}")
            break
    tl = talib_patterns(m5)
    if tl:
        add(0, "TA-Lib patterns: " + ", ".join(f"{nm} ({'bullish' if d > 0 else 'bearish'})" for nm, d in tl[:5]))
    for sgn, txt in (extra or []):
        (seen if sgn > 0 else concerns if sgn < 0 else notes).append(txt)

    stop = float(vr["vwap"])
    target = c + want * need
    rr_room = (room / max(risk, 1e-9)) if room is not None else None
    rr = (f"stop {stop:.2f} (VWAP, {risk:.2f} away), target {target:.2f} (1 : {need / max(risk, 1e-9):.1f})"
          + (f", room to the next wall 1 : {rr_room:.1f}" if rr_room is not None else ""))
    need_score = int(cfg.get("brain_min_score", 0))
    take = score >= need_score and veto is None
    if take:
        decision = "BUY CALL" if want > 0 else "BUY PUT"
    else:
        decision = "NO TRADE: " + (veto or f"the chart scores {score:+d} and needs {need_score:+d}")
    return {"score": score, "veto": veto, "take": take, "setup": setup or ("trend continuation" if t15 == want else "VWAP/EMA cross"),
            "seen": seen, "concerns": concerns, "notes": notes, "rr": rr, "decision": decision,
            "t1": t1, "t15": t15}


def explain(sym: str, side: str, a: dict, when: str = "") -> tuple[str, str]:
    """(short headline, full explanation) for Telegram."""
    head = (f"{sym} {side.upper()} {when}· {a['setup']} · chart {a['score']:+d} → "
            f"{'TAKE' if a['take'] else 'SKIP'}")
    lines = [f"Setup: {a['setup']}"]
    if a["seen"]:
        lines.append("Seen:")
        lines += [f"✅ {s}" for s in a["seen"]]
    if a["concerns"]:
        lines.append("Concerns:")
        lines += [f"⚠️ {s}" for s in a["concerns"]]
    if a["notes"]:
        lines.append("Also:")
        lines += [f"• {s}" for s in a["notes"][:6]]
    lines.append(f"Risk/reward: {a['rr']}")
    lines.append(f"Decision: {a['decision']}")
    return head, "\n".join(lines)


def sweep_trigger(ctx: dict | None, cfg: dict | None = None) -> tuple[str, list[str]] | None:
    """A trade trigger of its own: the candle that just finished swept a level (wick past it) and closed back
    inside by at least 0.1 ATR. A swept low gives a call, a swept high a put. The trend filter and the brain still
    have to agree afterwards (e.g. 1-hour up, 15-minute higher lows, 5-minute pullback sweeps a low: the classic)."""
    if not ctx:
        return None
    m5 = ctx["m5"]
    atr = float(m5["atr"].iloc[-1]) if np.isfinite(m5["atr"].iloc[-1]) else 0.0
    if atr <= 0:
        return None
    for sw in sorted(sweeps(ctx, atr), key=lambda x: -x["back"]):
        if sw["bars_ago"] == 0 and sw["back"] >= 0.1:
            side = "call" if sw["dir"] > 0 else "put"
            return side, [f"swept {sw['name']} ({sw['level']:.2f}) and closed back {'above' if sw['dir'] > 0 else 'below'}"]
    return None


def maybe_sweep(today5: pd.DataFrame, levels: list[float]) -> bool:
    """Cheap pre-check before building the whole picture: did the last candle wick past the last 6 candles' range,
    or past one of the day's key levels, and close back inside?"""
    if len(today5) < 3:
        return False
    lo, hi, c = (float(today5[k].iloc[-1]) for k in ("Low", "High", "Close"))
    prev = today5.iloc[-7:-1]
    if (lo < float(prev["Low"].min()) < c) or (hi > float(prev["High"].max()) > c):
        return True
    return any((lo < lv < c) or (hi > lv > c) for lv in levels)
