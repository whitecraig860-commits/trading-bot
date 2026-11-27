"""
Free word-based news scorer for QQQ (research/NEWS_BOT_PROTOCOL.md). Used by the news bot, its test and the live page.

Word lists: the most common positive and negative words of the Loughran-McDonald finance dictionary (the standard word
list researchers use for financial text), plus market words for headlines (rate cut, tariffs, beats, misses...).
Deliberately simple and transparent: every score shows which words produced it.
"""

from __future__ import annotations

import math
import re

GOOD = {
    # Loughran-McDonald positive (most frequent in financial text)
    "achieve", "achieved", "advance", "advances", "advantage", "beat", "beats", "benefit", "benefits", "best", "better",
    "boost", "boosts", "boosted", "breakthrough", "exceed", "exceeds", "exceeded", "excellent", "gain", "gains", "gained",
    "improve", "improves", "improved", "improvement", "innovative", "opportunity", "optimistic", "outperform",
    "outperforms", "positive", "profitable", "progress", "rebound", "rebounds", "record", "recovery", "strong",
    "stronger", "strength", "succeed", "success", "successful", "surpass", "surpasses",
    # market words (headlines)
    "surge", "surges", "surged", "soar", "soars", "soared", "jump", "jumps", "jumped", "rally", "rallies", "rallied",
    "climb", "climbs", "upgrade", "upgrades", "upgraded", "raises", "raised", "bullish", "buyback", "approval",
    "approved", "approves", "deal", "partnership", "tops", "topped", "higher", "growth", "accelerates", "expands",
    "cools", "cooling", "easing", "eases", "ceasefire", "truce", "stimulus", "dovish", "upbeat", "all-time",
}
BAD = {
    # Loughran-McDonald negative (most frequent)
    "loss", "losses", "decline", "declines", "declined", "adverse", "against", "breach", "concern", "concerns",
    "crisis", "critical", "deficit", "delay", "delays", "delayed", "deteriorate", "difficult", "disappoint",
    "disappoints", "disappointing", "downturn", "fail", "fails", "failed", "failure", "fraud", "impairment", "investigation",
    "lawsuit", "litigation", "negative", "penalty", "problem", "problems", "recall", "recession", "risk", "risks",
    "slowdown", "terminate", "uncertain", "uncertainty", "violation", "volatile", "warn", "warns", "warning", "weak",
    "weaker", "weakness", "worse", "worst",
    # market words (headlines)
    "miss", "misses", "missed", "plunge", "plunges", "plunged", "slump", "slumps", "tumble", "tumbles", "tumbled",
    "sink", "sinks", "drop", "drops", "dropped", "fall", "falls", "fell", "selloff", "sell-off", "crash", "downgrade",
    "downgrades", "downgraded", "cuts", "cut", "lower", "lowers", "bearish", "tariff", "tariffs", "sanction",
    "sanctions", "ban", "bans", "probe", "antitrust", "layoffs", "shutdown", "default", "hawkish", "hot", "sticky",
    "war", "strike", "strikes", "subpoena", "halt", "halts",
}
# Phrases checked before single words (sign, phrase).
PHRASES = [(+1, "rate cut"), (+1, "rate cuts"), (+1, "cut rates"), (+1, "cuts rates"), (-1, "rate hike"),
           (-1, "rate hikes"), (-1, "raises rates"), (+1, "beats estimates"), (-1, "misses estimates"),
           (-1, "guidance cut"), (-1, "cuts guidance"), (+1, "raises guidance"), (+1, "price target raised"),
           (-1, "price target cut"), (-1, "hotter than expected"), (+1, "cooler than expected"),
           (-1, "job cuts"), (-1, "export controls"), (+1, "trade deal")]
NEGATORS = {"not", "no", "never", "without", "fails", "unlikely"}
MACRO = {"fed", "powell", "fomc", "cpi", "inflation", "payrolls", "jobs", "unemployment", "tariff", "tariffs", "trump",
         "china", "treasury", "yields", "recession", "gdp", "pce"}
BIG = {"nvda", "nvidia", "aapl", "apple", "msft", "microsoft", "amzn", "amazon", "meta", "googl", "alphabet", "google",
       "tsla", "tesla", "avgo", "broadcom"}
MARKET = {"qqq", "nasdaq", "s&p", "spy", "stocks", "wall", "market", "markets"}
# words that are positive/negative in ordinary English but not in finance headlines (L-M's main point)
NEUTRAL_HERE = {"cut"}  # "cut" only counts inside a phrase ("rate cut", "job cuts")


def score(headline: str, symbols: list[str] | None = None) -> dict:
    """{"score": -3..3, "importance": 1..3, "good": [...], "bad": [...]}"""
    text = headline.lower()
    good, bad = [], []
    for sign, ph in PHRASES:
        if ph in text:
            (good if sign > 0 else bad).append(ph)
            text = text.replace(ph, " ")
    words = re.findall(r"[a-z&][a-z&\-']*", text)
    for i, w in enumerate(words):
        if w in NEUTRAL_HERE:
            continue
        s = 1 if w in GOOD else -1 if w in BAD else 0
        if s and any(x in NEGATORS for x in words[max(0, i - 3):i]):
            s = -s
        if s > 0:
            good.append(w)
        elif s < 0:
            bad.append(w)
    n = len(good) + len(bad)
    sc = 0.0 if n == 0 else max(-3.0, min(3.0, (len(good) - len(bad)) / math.sqrt(n)))
    syms = {s.lower() for s in (symbols or [])}
    toks = set(words) | syms
    imp = 3 if toks & MACRO or toks & BIG else 2 if toks & MARKET else 1
    return {"score": round(sc, 2), "importance": imp, "good": good, "bad": bad}


def pressure(items: list[dict], now, window_min: float = 30, half_life_min: float = 15) -> float:
    """Sum of score x importance over the last window, halving every half_life. items: {"t": datetime, "score", "importance"}."""
    tot = 0.0
    for it in items:
        age = (now - it["t"]).total_seconds() / 60
        if 0 <= age <= window_min:
            tot += it["score"] * it["importance"] * 0.5 ** (age / half_life_min)
    return round(tot, 2)
