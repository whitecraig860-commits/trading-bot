"""
Reading the chart like a trader
===============================
The scalper used to look at one thing: did the candle close across VWAP or the EMA. This reads the chart the way a
person does, from the candles themselves, and says it in plain English:

  Every candle    how big its body is and how long its wicks are, and what that means:
                  - a long UPPER wick: buyers pushed it up and sellers threw it back down (selling pressure)
                  - a long LOWER wick: sellers pushed it down and buyers pushed it back up (buying pressure)
                  - a tiny body (doji): buyers and sellers were even, nobody's in control
                  - a full body with almost no wicks: one side was in control from open to close
  Patterns        hammer, shooting star, bullish/bearish engulfing, inside bar, three in a row
  Highs and lows  the swing highs and lows: higher highs + higher lows = an uptrend, lower highs + lower lows =
                  a downtrend, anything else = chop. A close past the last swing high or low is a "break".
  Wick levels     several wicks stopping at the same price = a level the other side is defending
                  (resistance above, support below). Buying a call just under resistance has no room to work.
  Wick pressure   over the last few candles, are the upper wicks or the lower wicks bigger?

read(df, i, side, risk) scores all of that for a call or a put and gives the reasons, so the bot's messages say
exactly what it saw. It only uses candles up to i (nothing from the future), so the backtest is fair.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def parts(o: float, h: float, l: float, c: float) -> dict:
    """Body and wicks as fractions of the candle's full range."""
    rng = max(h - l, 1e-9)
    return {"range": h - l, "body": abs(c - o) / rng, "upper": (h - max(o, c)) / rng, "lower": (min(o, c) - l) / rng,
            "green": c > o, "red": c < o}


def _row(df: pd.DataFrame, i: int) -> tuple[float, float, float, float]:
    return (float(df["Open"].iloc[i]), float(df["High"].iloc[i]), float(df["Low"].iloc[i]), float(df["Close"].iloc[i]))


def candle_pattern(df: pd.DataFrame, i: int) -> tuple[str, int, str] | None:
    """(name, direction +1 bullish / -1 bearish / 0 neutral, what it means) for candle i, or None if ordinary."""
    if i < 1:
        return None
    o, h, l, c = _row(df, i)
    po, ph, pl, pc = _row(df, i - 1)
    p, pp = parts(o, h, l, c), parts(po, ph, pl, pc)
    if p["range"] <= 0:
        return None
    if p["green"] and pp["red"] and c >= po and o <= pc and abs(c - o) > abs(pc - po):
        return "bullish engulfing", +1, "buyers swallowed the whole of the last red candle"
    if p["red"] and pp["green"] and c <= po and o >= pc and abs(c - o) > abs(pc - po):
        return "bearish engulfing", -1, "sellers swallowed the whole of the last green candle"
    if p["lower"] >= 0.55 and p["upper"] <= 0.15 and p["body"] >= 0.1:
        return "hammer", +1, "long lower wick: sellers pushed it down and buyers pushed it right back up"
    if p["upper"] >= 0.55 and p["lower"] <= 0.15 and p["body"] >= 0.1:
        return "shooting star", -1, "long upper wick: buyers pushed it up and sellers threw it back down"
    if p["body"] < 0.1:
        return "doji", 0, "tiny body: buyers and sellers were even, nobody's in control"
    if h <= ph and l >= pl:
        return "inside bar", 0, "a pause inside the last candle: waiting for a side to win"
    if p["body"] >= 0.85:
        return ("strong green candle" if p["green"] else "strong red candle"), (1 if p["green"] else -1), \
            "almost no wicks: one side was in control from open to close"
    if i >= 2:
        last3 = [parts(*_row(df, k)) for k in (i - 2, i - 1, i)]
        closes = [float(df["Close"].iloc[k]) for k in (i - 2, i - 1, i)]
        if all(x["green"] and x["body"] >= 0.5 for x in last3) and closes[0] < closes[1] < closes[2]:
            return "three green in a row", +1, "three solid green candles, each closing higher"
        if all(x["red"] and x["body"] >= 0.5 for x in last3) and closes[0] > closes[1] > closes[2]:
            return "three red in a row", -1, "three solid red candles, each closing lower"
    return None


def swing_points(df: pd.DataFrame, i: int, k: int = 2) -> tuple[list, list]:
    """Swing highs and lows up to candle i: a high higher than the k candles either side of it (only counted once
    those k later candles exist, so nothing is taken from the future)."""
    H = df["High"].to_numpy(float)[: i + 1]
    L = df["Low"].to_numpy(float)[: i + 1]
    highs, lows = [], []
    for j in range(k, len(H) - k):
        win_h, win_l = H[j - k: j + k + 1], L[j - k: j + k + 1]
        if H[j] == win_h.max() and H[j] > H[j - k: j].max():
            highs.append((j, float(H[j])))
        if L[j] == win_l.min() and L[j] < L[j - k: j].min():
            lows.append((j, float(L[j])))
    return highs, lows


def structure(df: pd.DataFrame, i: int, k: int = 2) -> tuple[str, str]:
    """('up'|'down'|'mixed'|'unclear', plain English) from the last two swing highs and lows."""
    highs, lows = swing_points(df, i, k)
    if len(highs) < 2 or len(lows) < 2:
        return "unclear", "not enough swings yet to see higher or lower highs"
    hh, hl = highs[-1][1] > highs[-2][1], lows[-1][1] > lows[-2][1]
    if hh and hl:
        return "up", "higher highs and higher lows (an uptrend)"
    if not hh and not hl:
        return "down", "lower highs and lower lows (a downtrend)"
    if hh and not hl:
        return "mixed", "a higher high but a lower low: swinging wider both ways (choppy)"
    return "mixed", "a lower high but a higher low: squeezing into a range"


def wick_levels(df: pd.DataFrame, i: int, tol: float, lookback: int = 40) -> tuple[list, list]:
    """Prices where several wicks stopped: [(level, touches)] for resistance (upper wicks) and support (lower
    wicks). A wick counts when it's at least 40% of its candle. tol = how close counts as the same price."""
    j0 = max(0, i - lookback)
    tops, bottoms = [], []
    for j in range(j0, i + 1):
        o, h, l, c = _row(df, j)
        p = parts(o, h, l, c)
        if p["upper"] >= 0.4:
            tops.append(h)
        if p["lower"] >= 0.4:
            bottoms.append(l)

    def cluster(xs):
        out = []
        for x in sorted(xs):
            if out and abs(x - out[-1][0]) <= tol:
                lvl, n = out[-1]
                out[-1] = ((lvl * n + x) / (n + 1), n + 1)
            else:
                out.append((x, 1))
        return [(lvl, n) for lvl, n in out if n >= 2]

    return cluster(tops), cluster(bottoms)


def wick_pressure(df: pd.DataFrame, i: int, n: int = 3) -> float:
    """Over the last n candles: (total lower wick - total upper wick) / total range. Above 0 = buyers keep
    pushing price back up; below 0 = sellers keep pushing it back down."""
    up = lo = rng = 0.0
    for j in range(max(0, i - n + 1), i + 1):
        o, h, l, c = _row(df, j)
        up += h - max(o, c)
        lo += min(o, c) - l
        rng += h - l
    return (lo - up) / rng if rng > 0 else 0.0


def read(df: pd.DataFrame, i: int, side: str, risk: float, cfg: dict | None = None) -> dict:
    """The chart read for a call (side='call') or a put at candle i.
    risk = how far the trade's stop is (the share's distance to VWAP): the trade needs at least target_r x risk of
    room before the next wall of wicks. Returns {"score", "veto", "why": [reasons], "summary"}."""
    cfg = cfg or {}
    want = 1 if side == "call" else -1
    c = float(df["Close"].iloc[i])
    atr = float(df["atr"].iloc[i]) if "atr" in df and np.isfinite(df["atr"].iloc[i]) else max(risk, c * 0.001)
    score, why, veto = 0, [], None

    st, st_text = structure(df, i)
    if st == ("up" if want > 0 else "down"):
        score += 1
        why.append(f"✅ {st_text}")
    elif st in ("up", "down"):
        score -= 2
        why.append(f"❌ {st_text}: against a {side}")
        if cfg.get("chart_veto_structure", True):
            veto = f"the highs and lows say the opposite ({st_text})"
    else:
        why.append(f"➖ {st_text}")

    highs, lows = swing_points(df, i)
    if want > 0 and highs and c > highs[-1][1]:
        score += 1
        why.append(f"✅ broke above the last swing high ({highs[-1][1]:.2f})")
    if want < 0 and lows and c < lows[-1][1]:
        score += 1
        why.append(f"✅ broke below the last swing low ({lows[-1][1]:.2f})")

    for k in (i, i - 1):
        pat = candle_pattern(df, k) if k >= 1 else None
        if pat and pat[1] != 0:
            name, d, meaning = pat
            if d == want:
                score += 1
                why.append(f"✅ {name}{' on the last candle' if k == i - 1 else ''}: {meaning}")
            else:
                score -= 1
                why.append(f"❌ {name}{' on the last candle' if k == i - 1 else ''}: {meaning}")
            break

    wp = wick_pressure(df, i)
    if wp * want >= 0.15:
        score += 1
        why.append("✅ the wicks favour it: " + ("buyers keep pushing it back up (long lower wicks)" if want > 0
                                                else "sellers keep pushing it back down (long upper wicks)"))
    elif wp * want <= -0.15:
        score -= 1
        why.append("❌ the wicks are against it: " + ("sellers keep rejecting higher prices (long upper wicks)"
                                                     if want > 0 else "buyers keep rejecting lower prices (long lower wicks)"))

    res, sup = wick_levels(df, i, tol=0.25 * atr)
    walls = [(lvl, n) for lvl, n in (res if want > 0 else sup) if (lvl - c) * want > 0]
    if walls:
        lvl, n = min(walls, key=lambda x: abs(x[0] - c))
        room = abs(lvl - c)
        need = float(cfg.get("target_r", 1.0)) * max(risk, 1e-9)
        kind = "resistance" if want > 0 else "support"
        if room < need:
            score -= 2
            why.append(f"❌ only {room:.2f} of room to {kind} at {lvl:.2f} ({n} wicks stopped there), "
                       f"and the target needs {need:.2f}")
            if cfg.get("chart_veto_room", True) and veto is None:
                veto = f"it's running into {kind} at {lvl:.2f}, where {n} wicks have already been turned back"
        else:
            why.append(f"✅ room to run: the next {kind} is at {lvl:.2f} ({n} wicks)")
    else:
        why.append(f"✅ no wall of wicks in the way {'above' if want > 0 else 'below'}")

    ok_score = score >= int(cfg.get("chart_min_score", 0))
    summary = (f"chart read {score:+d}: " + "; ".join(w.lstrip("✅❌➖ ") for w in why[:3]))
    return {"score": score, "veto": veto, "ok": ok_score and veto is None, "why": why, "summary": summary}
