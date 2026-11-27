"""Study 17 (research/MEME_COIN_PROTOCOL.md): meme-coin strategies on Alpaca crypto 15-minute bars. Research only."""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

COST = 0.006  # 0.25% fee + 0.05% slippage, each side
WANT = ["DOGE/USD", "SHIB/USD", "PEPE/USD", "TRUMP/USD", "BTC/USD"]


def say(*a):
    print(*a, flush=True)


def load(sym):
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    cli = CryptoHistoricalDataClient()
    parts = []
    m = pd.date_range("2023-01-01", "2026-11-01", freq="MS", tz="UTC")
    for a, b in zip(m, m[1:]):
        try:
            df = cli.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame(15, TimeFrameUnit.Minute),
                                                       start=a.to_pydatetime(), end=b.to_pydatetime())).df
        except Exception as exc:
            say(f"  {sym} {a:%Y-%m}: {type(exc).__name__}")
            continue
        if df is not None and len(df):
            parts.append(df.xs(sym, level=0)[["open", "high", "low", "close", "volume"]])
    if not parts:
        return None
    q = pd.concat(parts).astype(float)
    return q[~q.index.duplicated()].sort_index()


def nw_t(x, lags=5):
    x = np.asarray(x, float)
    n = len(x)
    if n < 10 or x.std() == 0:
        return float("nan")
    e = x - x.mean()
    v = (e @ e) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / n
    return float(x.mean() / np.sqrt(v / n)) if v > 0 else float("nan")


def exits(q, i, kind):
    """Return (exit index, gross return) for a long bought at bar i's close."""
    c, h, lo = q.close.to_numpy(), q.high.to_numpy(), q.low.to_numpy()
    e = c[i]
    if kind == "M1":
        tp, sl, n = e * 1.06, e * 0.97, 16
    elif kind == "M3":
        tp, sl, n = e * 1.05, e * 0.95, 48
    else:
        tp, sl, n = None, None, 96
    best = e
    for j in range(i + 1, min(i + 1 + n, len(c))):
        if kind in ("M1", "M3"):
            if lo[j] <= sl:
                return j, sl / e - 1
            if h[j] >= tp:
                return j, tp / e - 1
        else:
            best = max(best, h[j])
            if lo[j] <= best * 0.95:
                return j, best * 0.95 / e - 1
    j = min(i + n, len(c) - 1)
    return j, c[j] / e - 1


def entries(q, kind):
    c, v = q.close, q.volume
    if kind == "M1":
        return (v > 5 * v.rolling(96).mean().shift(1)) & (c / q.open - 1 > 0.02)
    if kind == "M3":
        return c / c.shift(16) - 1 < -0.08
    brk = c > q.high.rolling(192).max().shift(1)
    if kind == "M4":
        brk &= c > c.rolling(672).mean()
    return brk


def run(q, mask):
    idx = np.flatnonzero(mask.fillna(False).to_numpy())
    out, free = [], -1
    for i in idx:
        if i <= free or i + 1 >= len(q):
            continue
        j, r = exits(q, i, KIND)
        out.append((q.index[i], r - COST))
        free = j
    return pd.DataFrame(out, columns=["t", "r"])


KIND = None


def main():
    global KIND
    say("Study 17 meme coins (long only, 0.6% round-trip cost, 15-minute bars 2023-01..2026-10)")
    rng = np.random.default_rng(17)
    for sym in WANT:
        q = load(sym)
        if q is None or len(q) < 2000:
            say(f"{sym}: not available on Alpaca (or too little history); skipped")
            continue
        say(f"\n{sym}: {len(q)} bars {q.index[0]:%Y-%m-%d} to {q.index[-1]:%Y-%m-%d}; buy-and-hold {q.close.iloc[-1] / q.close.iloc[0] - 1:+.0%}")
        for KIND in ("M1", "M2", "M3", "M4"):
            tr = run(q, entries(q, KIND))
            if len(tr) < 10:
                say(f"  {KIND}: {len(tr)} trades (too few)")
                continue
            t = nw_t(tr.r.to_numpy())
            y = {yr: g.r.mean() for yr, g in tr.groupby(tr.t.dt.year)}
            pl = []
            for _ in range(20):
                m = pd.Series(False, index=q.index)
                m.iloc[rng.choice(len(q) - 200, size=len(tr), replace=False) + 100] = True
                p = run(q, m)
                pl.append(p.r.mean() if len(p) else 0)
            beats = sum(tr.r.mean() > p for p in pl)
            ok = tr.r.mean() > 0 and t >= 3 and y.get(2025, -1) > 0 and y.get(2026, -1) > 0 and beats >= 19
            say(f"  {KIND}: trades {len(tr)} avg {tr.r.mean():+.2%} win {(tr.r > 0).mean():.0%} t {t:+.2f} | "
                + " ".join(f"{k}:{v:+.2%}" for k, v in y.items()) + f" | beats placebo {beats}/20 -> {'PASS' if ok else 'fail'}")


if __name__ == "__main__":
    main()
