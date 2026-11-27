"""
Study 15 (research/NEWS_BOT_PROTOCOL.md): the free word-scored news bot on Mar 2024 - Oct 2026, real option prices.
Read-only data (Alpaca); no orders.   python research/news_study.py [--synthetic]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))
import newsscore  # noqa: E402
import qqq_triggers_study as s5  # noqa: E402
import stress_study as s11  # noqa: E402

SYMS = ["QQQ", "SPY", "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO"]
THRESH, TARGET, STOP, HOLD = 4.0, 0.10, 0.10, 30


def load_news(syn: bool) -> pd.DataFrame:
    if syn:
        rng = np.random.default_rng(1)
        ts = pd.date_range("2025-06-02 09:00", "2026-02-27 16:00", freq="37min")
        ts = ts[(ts.hour >= 9) & (ts.hour < 16) & (ts.dayofweek < 5)]
        words = ["Nvidia beats estimates, shares surge", "Fed signals rate cut", "Apple misses estimates",
                 "Tariffs on China raised, stocks plunge", "Microsoft announces partnership", "Market quiet"]
        return pd.DataFrame({"t": ts, "h": rng.choice(words, len(ts)), "sym": [["NVDA"]] * len(ts)})
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest

    cli = NewsClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    rows = []
    for a, b in zip(pd.date_range(s5.START, s5.END, freq="MS"), pd.date_range(s5.START, s5.END, freq="MS")[1:]):
        tok = None
        while True:
            req = NewsRequest(symbols=",".join(SYMS), start=a.to_pydatetime(), end=b.to_pydatetime(), limit=50,
                              include_content=False, page_token=tok)
            res = cli.get_news(req)
            data = res.data.get("news", []) if hasattr(res, "data") else []
            rows += [{"t": pd.Timestamp(n.created_at).tz_convert(s5.NY).tz_localize(None), "h": n.headline,
                      "sym": list(n.symbols)} for n in data]
            tok = getattr(res, "next_page_token", None)
            if not tok:
                break
    df = pd.DataFrame(rows).drop_duplicates(subset=["t", "h"]).sort_values("t")
    s5.say(f"news: {len(df)} headlines {df.t.min()} to {df.t.max()}")
    return df


def trend_series(q: pd.DataFrame) -> pd.Series:
    """The shared trend (tracker/context.py) per minute, computed causally over the whole series."""
    c = q.close
    e9, e20, e50 = (c.ewm(span=n, adjust=False).mean() for n in (9, 20, 50))
    slope = e20 - e20.shift(10)
    side = (c - e20)
    crosses = ((side * side.shift(1)) < 0).astype(int).rolling(31).sum()
    tr = pd.Series("Sideways", index=q.index)
    tr[(e9 > e20) & (e20 > e50) & (slope > 0)] = "Bullish"
    tr[(e9 < e20) & (e20 < e50) & (slope < 0)] = "Bearish"
    tr[crosses >= 4] = "Sideways"
    return tr


def signals(q, news, trend, use_news_sign=True):
    sc = news.apply(lambda r: newsscore.score(r.h, r.sym), axis=1)
    news = news.assign(score=[x["score"] for x in sc], imp=[x["importance"] for x in sc])
    news = news[news.score != 0]
    out, last = [], {"C": pd.Timestamp("1900"), "P": pd.Timestamp("1900")}
    times = news.t.to_numpy()
    for t in q.index:
        tod = t.strftime("%H:%M")
        if not ("09:45" <= tod <= "15:30"):
            continue
        lo = np.searchsorted(times, np.datetime64(t - pd.Timedelta(minutes=30)))
        hi = np.searchsorted(times, np.datetime64(t), side="right")
        if hi <= lo:
            continue
        w = news.iloc[lo:hi]
        age = (t - w.t).dt.total_seconds() / 60
        p = float((w.score * w.imp * 0.5 ** (age / 15)).sum())
        if abs(p) < THRESH:
            continue
        side = "C" if p > 0 else "P"
        if t - last[side] < pd.Timedelta(minutes=30):
            continue
        if trend.get(t) != ("Bullish" if side == "C" else "Bearish"):
            continue
        last[side] = t
        out.append({"t": t + pd.Timedelta(minutes=1), "side": side, "px": float(q.close[t]), "p": p})
    return pd.DataFrame(out, columns=["t", "side", "px", "p"])


def placebo(q, trend, n, rng):
    ok = q.index[(q.index.strftime("%H:%M") >= "09:45") & (q.index.strftime("%H:%M") <= "15:30")]
    ok = ok[trend.reindex(ok).isin(["Bullish", "Bearish"]).to_numpy()]
    pick = np.sort(rng.choice(len(ok), size=min(n, len(ok)), replace=False))
    t = ok[pick]
    return pd.DataFrame({"t": t + pd.Timedelta(minutes=1), "side": ["C" if trend[x] == "Bullish" else "P" for x in t],
                         "px": q.close.reindex(t).to_numpy()})


def main():
    syn = "--synthetic" in sys.argv
    if syn:
        rng = np.random.default_rng(0)
        idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=570 + m) for d in pd.bdate_range("2025-06-02", "2026-02-27") for m in range(390)])
        c = 600 + np.cumsum(rng.normal(0, .12, len(idx)))
        q = pd.DataFrame({"open": np.r_[600, c[:-1]], "high": c + .08, "low": c - .08, "close": c, "volume": 1000.0}, index=idx)
        s5.say("*** SYNTHETIC: meaningless ***")
    else:
        q = s5.load_qqq()
    news = load_news(syn)
    opts = s5.Options(syn, q)
    trend = trend_series(q)
    sig = signals(q, news, trend)
    s5.say(f"Study 15 news bot: {len(sig)} signals ({(sig.side == 'C').sum()} calls, {(sig.side == 'P').sum()} puts) "
           f"over {q.index.normalize().nunique()} days; threshold {THRESH}, exits +{TARGET:.0%}/-{STOP:.0%}/{HOLD} min")
    res = {}
    for cents in (1, 5):
        d, n = s11.simulate(q, sig.sort_values("t").reset_index(drop=True), opts, cents, target=TARGET, stop=STOP, hold=HOLD)
        res[cents] = d
        yrs = " ".join(f"{y}:{d[d.index.year == y].mean():+.2f}" for y in sorted(set(d.index.year)))
        s5.say(f"{cents} cent(s): trades {n} per day {d.mean():+.2f} t {s5.nw_t(d.to_numpy()):+.2f} "
               f"2026 {d[d.index >= '2026-01-01'].mean():+.2f} | {yrs}")
    rng = np.random.default_rng(15)
    pl = []
    for _ in range(20):
        ps = placebo(q, trend, len(sig), rng)
        pl.append(s11.simulate(q, ps, opts, 1, target=TARGET, stop=STOP, hold=HOLD)[0].mean())
    base = res[1].mean()
    s5.say(f"Placebo (a) random minutes on the trend's side: news {base:+.2f} vs median {np.median(pl):+.2f}, "
           f"best {max(pl):+.2f}; beats {sum(base > x for x in pl)}/20")
    tb = sig.copy()  # (b): trend alone at the same minutes = same trades by construction (sign agrees with trend)
    s5.say("Placebo (b) trend alone at the same minutes: identical by construction (news only picks the minutes); "
           "so (a) is the test of whether news-picked minutes beat random trend minutes.")
    d5 = res[5]
    t5 = s5.nw_t(d5.to_numpy())
    yrs_ok = all(d5[d5.index.year == y].mean() > 0 for y in sorted(set(d5.index.year)))
    ok = d5.mean() > 0 and t5 >= 2 and yrs_ok and d5[d5.index >= "2026-01-01"].mean() > 0 and sum(base > x for x in pl) >= 19
    s5.say(f"VERDICT: {'PASS' if ok else 'FAIL'} (5 cents {d5.mean():+.2f}/day t {t5:+.2f}; every year positive {yrs_ok})")
    _ = tb


if __name__ == "__main__":
    main()
