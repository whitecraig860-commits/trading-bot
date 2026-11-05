"""
The trade journal that learns
=============================
After every trade, win or lose, the bot writes a post-mortem:
  - what the trade looked like when it was taken (the "conditions": how stretched the price was, the size of the
    signal day, volume, the market's trend, confidence, the news, insiders, and for the scalper the trigger and
    the time of day)
  - how it played out: the best and worst it got (in R), whether it was winning and gave it back, whether it was
    wrong from the start, whether it gapped through the stop
  - after the exit (once the next few bars are in): was the stop shaken out before the move came, did it sell
    too early and miss the run, or did the stop save it from a bigger loss
  - for wins: earned (the signals lined up and price moved its way) or probably luck (weak signals, or it went
    against the trade first and only just recovered)

Every post-mortem goes into state/lessons.json, together with lessons from 10 years of simulated trades
("python bot.py learn"), so the journal starts full, not empty. Lessons are kept per condition, per share and per
setup. A lesson is only USED when it's strong evidence, not luck: at least `min_trades` trades and a difference
from the setup's normal result with a t-statistic of 2 or more. Then it adds or takes away a confidence point,
which changes the size of the next trade, and the alert says which lesson it used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

AFTER_BARS = 10  # how many bars after the exit the "what happened next" check looks at


def bucket(name: str, value) -> str | None:
    """Turns a measurement into a condition a person can read, e.g. stretch 2.4 -> 'bought 2-3 ATR above the 20-day'."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None if value in (None, "") else f"{name}: {value}"
    if not math.isfinite(v):
        return None
    edges = {
        "stretch": [(1, "close to the 20-day average"), (2, "1-2 ATR from the 20-day average"),
                    (3, "2-3 ATR from the 20-day average (stretched)"), (1e9, "3+ ATR from the 20-day average (chasing)")],
        "day": [(1, "signal day was a normal-sized move"), (2, "signal day was a big move (1-2 ATR)"),
                (1e9, "signal day was a huge move (2+ ATR)")],
        "volume": [(0.8, "light volume"), (1.5, "normal volume"), (1e9, "heavy volume (1.5x+)")],
        "adx": [(20, "weak trend (ADX under 20)"), (30, "steady trend (ADX 20-30)"), (1e9, "strong trend (ADX 30+)")],
        "swing": [(2, "calm market (under 2% a day)"), (4, "lively market (2-4% a day)"), (1e9, "wild market (4%+ a day)")],
        "score": [(60, "score under 60"), (80, "score 60-79"), (1e9, "score 80+")],
        "hour": [(10.5, "first hour of trading"), (12, "late morning"), (14, "lunchtime"), (1e9, "afternoon")],
        "body": [(50, "weak candle"), (75, "solid candle"), (1e9, "very strong candle")],
    }
    for top, label in edges.get(name, []):
        if v < top:
            return label
    return f"{name} {v:g}"


def conditions(setup: str, raw: dict) -> list[str]:
    """The readable conditions for a trade: [setup-wide labels...]."""
    out = []
    for k in ("stretch", "day", "volume", "adx", "swing", "score", "hour", "body"):
        if k in raw:
            b = bucket(k, raw[k])
            if b:
                out.append(b)
    for k in ("regime", "news", "insiders", "confidence", "trigger", "trend"):
        if raw.get(k) not in (None, ""):
            out.append(f"{k}: {raw[k]}")
    return out


def diagnose(entry: float, stop0: float, exit_: float, long: bool, path: pd.DataFrame, exit_reason: str = "",
             after: pd.DataFrame | None = None) -> dict:
    """Post-mortem from the bars the trade was open (path) and, if known, the bars after it closed (after).
    Returns best/worst in R, the result in R, and plain-English findings."""
    risk = abs(entry - stop0) or 1e-9
    sign = 1 if long else -1
    hi, lo = float(path["High"].max()), float(path["Low"].min())
    mfe = ((hi - entry) if long else (entry - lo)) / risk
    mae = ((entry - lo) if long else (hi - entry)) / risk
    r = sign * (exit_ - entry) / risk
    found = []
    if r <= 0:
        if mfe < 0.3:
            found.append(("wrong from the start", "it never really went your way: the entry was early, late or the setup failed"))
        elif mfe >= 1.0:
            found.append(("gave it back", f"it was up {mfe:.1f}R and still lost: the exit should have locked in profit sooner"))
        if "gap" in exit_reason:
            found.append(("gapped through the stop", "price jumped past the stop overnight, usually on news"))
    else:
        if mae >= 0.7:
            found.append(("lucky", f"it went {mae:.1f}R against you before it worked: it nearly stopped out"))
        if mfe >= r + 1.5:
            found.append(("gave some back", f"it reached {mfe:.1f}R but you kept {r:.1f}R"))
    if after is not None and len(after):
        ahi, alo = float(after["High"].max()), float(after["Low"].min())
        if r <= 0 and "stop" in exit_reason:
            if (long and ahi >= entry + risk) or ((not long) and alo <= entry - risk):
                found.append(("shaken out", "after stopping you out it went 1R+ your way: the stop was too tight for this one"))
            elif (long and alo <= exit_ - risk) or ((not long) and ahi >= exit_ + risk):
                found.append(("stop saved you", "it kept going against you after the stop: the stop did its job"))
        if r > 0:
            more = ((ahi - exit_) if long else (exit_ - alo)) / risk
            if more >= 2:
                found.append(("sold too early", f"it ran another {more:.1f}R after you sold: missed the rest of the move"))
    return {"r": float(r), "mfe": float(mfe), "mae": float(mae), "findings": found}


def verdict(r: float, points: int, findings: list) -> str:
    tags = {f[0] for f in findings}
    if r > 0:
        if "lucky" in tags or points <= 0:
            return "WON, but probably luck" + (": the signals were weak" if points <= 0 else "")
        return "WON, and it was earned: the signals lined up and price went your way"
    if "shaken out" in tags:
        return "LOST, and the stop was too tight: it came good after you were out"
    if "stop saved you" in tags:
        return "LOST, but it was the right call to get out: it kept going the wrong way"
    if points >= 3:
        return "LOST even though everything lined up: that happens, a good setup still loses about half the time"
    return "LOST"


# ---------------------------------------------------------------------------
# The journal
# ---------------------------------------------------------------------------


def path_(state_dir: Path, name: str = "lessons.json") -> Path:
    return state_dir / name


def load(state_dir: Path, name: str = "lessons.json") -> dict:
    p = path_(state_dir, name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"history": {}, "paper": [], "pending": []}


def save(state_dir: Path, d: dict, name: str = "lessons.json") -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    d["paper"] = d.get("paper", [])[-2000:]
    tmp = path_(state_dir, name).with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=0, default=float), encoding="utf-8")
    tmp.replace(path_(state_dir, name))


def _stats(rs: list[float]) -> dict:
    a = np.asarray(rs, float)
    n = len(a)
    if not n:
        return {"n": 0, "avg": 0.0, "win": 0.0, "sd": 0.0}
    return {"n": n, "avg": float(a.mean()), "win": float((a > 0).mean()), "sd": float(a.std(ddof=1)) if n > 1 else 0.0}


def build_tables(records: list[dict]) -> dict:
    """{kind|setup: {"all": stats, "cond": {label: stats}, "symbol": {sym: stats}, "finding": {tag: count}}}"""
    groups: dict = {}
    for rec in records:
        g = groups.setdefault(f"{rec['kind']}|{rec['setup']}", {"rs": [], "cond": {}, "symbol": {}, "finding": {}})
        g["rs"].append(rec["r"])
        for c in rec.get("conditions", []):
            g["cond"].setdefault(c, []).append(rec["r"])
        g["symbol"].setdefault(rec["symbol"], []).append(rec["r"])
        for f in rec.get("findings", []):
            g["finding"][f] = g["finding"].get(f, 0) + 1
    out = {}
    for k, g in groups.items():
        out[k] = {"all": _stats(g["rs"]), "cond": {c: _stats(v) for c, v in g["cond"].items()},
                  "symbol": {s: _stats(v) for s, v in g["symbol"].items()}, "finding": g["finding"]}
    return out


def _t(sub: dict, base: dict) -> float:
    if sub["n"] < 2 or sub["sd"] <= 0:
        return 0.0
    return (sub["avg"] - base["avg"]) / (sub["sd"] / math.sqrt(sub["n"]))


def lessons_for(journal: dict, kind: str, setup: str, symbol: str, conds: list[str], min_trades: int = 30,
                min_t: float = 2.0, min_gap: float = 0.15) -> list[tuple[int, str]]:
    """The proven lessons that apply to this trade: [(+1 or -1, plain-English reason)]. A lesson needs at least
    min_trades trades, a result at least min_gap R a trade away from the setup's normal, and |t| >= min_t."""
    out = []
    for source, table in (("10 years of history", journal.get("history", {})),
                          ("the paper account", journal.get("paper_tables", {}))):
        g = table.get(f"{kind}|{setup}")
        if not g or not g["all"]["n"]:
            continue
        base = g["all"]
        need = min_trades if source.startswith("10") else max(15, min_trades // 2)
        for c in conds:
            sub = g["cond"].get(c)
            if not sub or sub["n"] < need:
                continue
            gap, t = sub["avg"] - base["avg"], _t(sub, base)
            if abs(gap) >= min_gap and abs(t) >= min_t:
                out.append((1 if gap > 0 else -1,
                            f"lesson from {source}: {c} → {sub['avg']:+.2f}R a trade ({sub['n']} trades, "
                            f"{sub['win']:.0%} won) vs {base['avg']:+.2f}R normally"))
        sub = g["symbol"].get(symbol)
        if sub and sub["n"] >= max(10, need // 3):
            gap, t = sub["avg"] - base["avg"], _t(sub, base)
            if abs(gap) >= min_gap and abs(t) >= min_t * 0.75:
                out.append((1 if gap > 0 else -1,
                            f"lesson on {symbol} ({source}): {sub['avg']:+.2f}R a trade over {sub['n']} trades "
                            f"({sub['win']:.0%} won) vs {base['avg']:+.2f}R normally"))
    # strongest first, at most 3, and never more than one point each way in total
    out.sort(key=lambda x: -abs(x[0]))
    return out[:3]


def symbol_story(journal: dict, kind: str, setup: str, symbol: str) -> str | None:
    """A short line about this share's own record and its most common post-mortem findings."""
    g = journal.get("history", {}).get(f"{kind}|{setup}")
    if not g:
        return None
    s = g["symbol"].get(symbol)
    if not s or s["n"] < 5:
        return None
    return f"On {symbol}, this setup has made {s['avg']:+.2f}R a trade over {s['n']} past trades ({s['win']:.0%} won)."


def top_findings(journal: dict, kind: str, setup: str, n: int = 3) -> list[str]:
    g = journal.get("paper_tables", {}).get(f"{kind}|{setup}") or journal.get("history", {}).get(f"{kind}|{setup}")
    if not g or not g.get("finding"):
        return []
    total = max(1, g["all"]["n"])
    return [f"{k} ({v} of {total} trades)" for k, v in sorted(g["finding"].items(), key=lambda x: -x[1])[:n]]
