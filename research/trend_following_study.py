"""
Study 3: diversified ETF trend following, run exactly as research/TREND_FOLLOWING_PROTOCOL.md says
==================================================================================================
Section numbers (§) refer to the protocol. Nothing here places orders or touches a broker account: it downloads
public price history, simulates, and prints.

  python research/trend_following_study.py               real data (Yahoo; Alpaca cross-check if keys are set)
  python research/trend_following_study.py --synthetic   fake prices, to check the code runs (results meaningless)
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import pickle
import sys
import time
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

ND = NormalDist()
SEED = 20261111

# §2 universe
UNIVERSE = {
    "SPY": "US equity", "QQQ": "US equity", "IWM": "US equity",
    "EFA": "Intl equity", "EEM": "Intl equity",
    "IEF": "Bonds", "TLT": "Bonds", "LQD": "Bonds", "TIP": "Bonds",
    "GLD": "Real assets", "DBC": "Real assets", "VNQ": "Real assets", "SLV": "Real assets",
}
TICKERS = list(UNIVERSE)
CLS = np.array([UNIVERSE[t] for t in TICKERS])
EQUITY = np.isin(CLS, ["US equity", "Intl equity"])
REAL = CLS == "Real assets"

# §13 costs (fractions of traded notional, per side)
HALF_SPREAD = {**{t: 0.0002 for t in ["SPY", "QQQ", "IWM", "EFA", "IEF", "TLT", "LQD", "GLD"]},
               **{t: 0.0005 for t in ["EEM", "TIP", "VNQ", "SLV"]}, "DBC": 0.0010}
SLIP, FXC, FXC_STRESS = 0.0005, 0.0015, 0.0050
COST = {
    "gross": np.zeros(len(TICKERS)),
    "net": np.array([HALF_SPREAD[t] + SLIP + FXC for t in TICKERS]),
    "stress": np.array([3 * (HALF_SPREAD[t] + SLIP) + FXC_STRESS for t in TICKERS]),
}
NO_TRADE = 0.0025      # §8
CASH_HAIRCUT = 0.0010  # §14
HOLDOUT = pd.Timestamp("2018-01-01")  # §16
PRIMARY = ["A", "B3", "B6", "B12", "C", "D", "E"]
VARIANTS = ["A6", "A8", "A12", "A200d", "D8", "D12", "E8", "E12"]
CRISES = {"GFC": ("2007-10", "2009-03"), "Euro crisis": ("2011-05", "2011-10"), "China/oil": ("2015-08", "2016-02"),
          "Q4 2018": ("2018-10", "2018-12"), "COVID": ("2020-02", "2020-03"),
          "2022 inflation bear": ("2022-01", "2022-10"), "2025 tariff shock": ("2025-02", "2025-04")}


def say(*a):
    print(*a, flush=True)


def hdr(t):
    say("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


# ---------------------------------------------------------------------------------------------------- data (§4)

def yf_one(t: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    last = None
    for attempt in range(5):
        try:
            df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False, actions=False, threads=False)
            if df is not None and len(df):
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
                return df[["Open", "Close"]].astype(float)
        except Exception as exc:  # network hiccups on shared runners
            last = exc
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not download {t}: {last}")


def fred(series: str) -> pd.Series | None:
    try:
        df = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
        s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(df.iloc[:, 0]))
        return s.dropna()
    except Exception as exc:
        say(f"FRED {series} not available: {type(exc).__name__}: {str(exc)[:100]}")
        return None


def load_real(end: str, cache: Path) -> dict:
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    raw = {t: yf_one(t, "1993-01-01", end) for t in TICKERS}
    irx = yf_one("^IRX", "1993-01-01", end)["Close"]
    gbp = yf_one("GBPUSD=X", "2003-01-01", end)["Close"]
    data = {"raw": raw, "irx": irx, "irx_src": "Yahoo ^IRX", "gbp": gbp,
            "usrec": fred("USREC"), "cpi": fred("CPIAUCSL")}
    if irx.dropna().empty:
        d = fred("DTB3")
        data["irx"], data["irx_src"] = d, "FRED DTB3"
    cache.write_bytes(pickle.dumps(data))
    return data


def load_synthetic(end: str) -> dict:
    rng = np.random.default_rng(1)
    days = pd.bdate_range("1993-01-29", pd.Timestamp(end) - pd.Timedelta(days=1))
    first = {"SPY": "1993-01-29", "QQQ": "1999-03-10", "IWM": "2000-05-26", "EFA": "2001-08-17", "EEM": "2003-04-14",
             "IEF": "2002-07-30", "TLT": "2002-07-30", "LQD": "2002-07-30", "TIP": "2003-12-05", "GLD": "2004-11-18",
             "DBC": "2006-02-06", "VNQ": "2004-09-29", "SLV": "2006-04-28"}
    raw = {}
    for t in TICKERS:
        d = days[days >= pd.Timestamp(first[t])]
        vol = 0.18 if EQUITY[TICKERS.index(t)] else 0.08
        r = rng.normal(0.06 / 252, vol / math.sqrt(252), len(d))
        c = 50 * np.exp(np.cumsum(r))
        o = c * np.exp(rng.normal(0, vol / math.sqrt(252) / 3, len(d)))
        raw[t] = pd.DataFrame({"Open": o, "Close": c}, index=d)
    return {"raw": raw, "irx": pd.Series(2.0, index=days), "irx_src": "synthetic",
            "gbp": pd.Series(1.3 * np.exp(np.cumsum(rng.normal(0, 0.005, len(days)))), index=days)[days >= "2003-12-01"],
            "usrec": None, "cpi": None}


def alpaca_monthly(end: str) -> dict[str, pd.Series] | None:
    if not os.environ.get("ALPACA_KEY"):
        return None
    try:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
        df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=TICKERS, timeframe=TimeFrame.Day,
                                                 start=pd.Timestamp("2015-12-01").to_pydatetime(),
                                                 end=pd.Timestamp(end).to_pydatetime(),
                                                 adjustment=Adjustment.ALL, feed=DataFeed.SIP)).df
    except Exception as exc:
        say(f"Alpaca cross-check not available: {type(exc).__name__}: {str(exc)[:120]}")
        return None
    out = {}
    for s in df.index.get_level_values(0).unique():
        d = df.xs(s, level=0)["close"].astype(float)
        d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").tz_localize(None).normalize()
        out[s] = d.groupby(d.index.to_period("M")).last().pct_change().dropna()
    return out


# ---------------------------------------------------------------------------------------------------- prep (§22)

class Mkt:
    pass


def prepare(data: dict, end: str) -> Mkt:
    hdr("DATA QUALITY (§22) - checked before any result")
    raw = data["raw"]
    cal = raw["SPY"].dropna().index
    cal = cal[cal < pd.Timestamp(end)]
    m = Mkt()
    m.cal = cal
    K, T = len(TICKERS), len(cal)
    m.open, m.close = np.full((T, K), np.nan), np.full((T, K), np.nan)
    m.first = {}
    problems = 0
    for k, t in enumerate(TICKERS):
        df = raw[t].copy()
        df = df[~df.index.duplicated()]
        bad = (df <= 0).sum().sum()
        df = df.where(df > 0)
        first = df["Close"].first_valid_index()
        m.first[t] = first
        d = df.reindex(cal[cal >= first])
        miss = d.isna()
        # longest run of missing values in either column
        longest = 0
        for col in ["Open", "Close"]:
            run = (miss[col] != miss[col].shift()).cumsum()
            if miss[col].any():
                longest = max(longest, int(miss[col].groupby(run).sum().max()))
        filled = int(miss.sum().sum())
        d = d.ffill()
        ret = d["Close"].pct_change()
        jumps = ret[ret.abs() > 0.25]
        stale = (d["Close"].diff() == 0).astype(int)
        stale_runs = int((stale.groupby((stale == 0).cumsum()).sum() >= 4).sum())  # 4 zero diffs = 5 equal closes
        flag = "OK" if longest <= 3 else "GAP > 3 DAYS"
        say(f"{t:4s} first {first.date()}  {len(d):5d} days  filled {filled:3d} values (longest gap {longest} d)  "
            f"price<=0: {bad}  |moves|>25%: {len(jumps)}  stale runs (5+ equal closes): {stale_runs}  {flag}")
        for dt, r in jumps.items():
            say(f"       move {dt.date()} {r:+.1%}")
        if longest > 3:
            problems += 1
        pos = cal.get_indexer(d.index)
        m.open[pos, k], m.close[pos, k] = d["Open"].to_numpy(), d["Close"].to_numpy()
    if problems:
        raise SystemExit(f"STOP: {problems} ETF(s) have a data gap longer than 3 trading days (§22.1)")

    irx = data["irx"].reindex(cal.union(data["irx"].index)).sort_index()
    gaps = int(irx.reindex(cal).isna().sum())
    irx = irx.ffill().reindex(cal)
    med = float(irx.median())
    say(f"Cash rate: {data['irx_src']}, median {med:.2f}%, {gaps} NYSE days carried forward (§22.5); "
        f"covers {irx.first_valid_index().date()} to {irx.last_valid_index().date()}")
    if not 0 <= med <= 20:
        raise SystemExit("STOP: cash-rate series is not in percent")
    daily = np.maximum(irx.shift(1).bfill().to_numpy() / 100 - CASH_HAIRCUT, 0) / 252
    m.ci = np.cumprod(1 + daily)  # cash index (§14)
    m.gbp = data["gbp"].reindex(cal.union(data["gbp"].index)).sort_index().ffill().reindex(cal)

    # month ends (§8)
    per = cal.to_period("M")
    m.me = np.flatnonzero(per[1:] != per[:-1])  # last day of each month except the final one
    m.me = np.append(m.me, T - 1)
    m.me_dates = cal[m.me]
    # §2 eligibility: 13 full calendar months after the first month
    mi = np.array([d.year * 12 + d.month for d in m.me_dates])
    m.elig = np.zeros((len(m.me), K), bool)
    for k, t in enumerate(TICKERS):
        f = m.first[t]
        m.elig[:, k] = mi - (f.year * 12 + f.month) >= 13
    for t in TICKERS:
        k = TICKERS.index(t)
        say(f"  {t} eligible from {m.me_dates[np.argmax(m.elig[:, k])].date()}")
    # §3 start
    us, bo, intl = CLS == "US equity", CLS == "Bonds", CLS == "Intl equity"
    ok = (m.elig.sum(1) >= 8) & m.elig[:, us].any(1) & m.elig[:, bo].any(1) & m.elig[:, intl].any(1)
    m.s0 = int(np.argmax(ok))
    say(f"Evaluation starts at month-end {m.me_dates[m.s0].date()} with {m.elig[m.s0].sum()} eligible ETFs (§3)")
    m.spy0 = int(np.argmax(m.elig[:, TICKERS.index("SPY")]))
    return m


# ---------------------------------------------------------------------------------------------------- signals (§5)

def signals(m: Mkt) -> dict[str, np.ndarray]:
    cl = pd.DataFrame(m.close, index=m.cal, columns=TICKERS)
    mc = cl.iloc[m.me]
    ci = pd.Series(m.ci, index=m.cal).iloc[m.me].to_numpy()[:, None]
    dr = cl.pct_change()
    m.sig12 = (dr.rolling(252).std() * math.sqrt(252)).iloc[m.me].to_numpy()
    m.sig60 = (dr.rolling(60).std() * math.sqrt(252)).iloc[m.me].to_numpy()
    m.dret = dr.to_numpy()
    mcv = mc.to_numpy()

    def mom(L):
        prev = np.vstack([np.full((L, len(TICKERS)), np.nan), mcv[:-L]])
        cprev = np.vstack([np.full((L, 1), np.nan), ci[:-L]])
        return (mcv / prev - 1) - (ci / cprev - 1)

    def sma(L):
        return (mcv > mc.rolling(L).mean().to_numpy()).astype(float)

    sma200 = (cl > cl.rolling(200).mean()).astype(float).iloc[m.me].to_numpy()
    b3, b6, b12 = [(mom(L) > 0).astype(float) for L in (3, 6, 12)]
    c = np.clip(mom(12) / m.sig12, 0, 1)
    a = sma(10)
    e = (a + b3 + b6 + b12) / 4
    ex = {"A": a, "B3": b3, "B6": b6, "B12": b12, "C": c, "D": b12, "E": e,
          "A6": sma(6), "A8": sma(8), "A12": sma(12), "A200d": sma200, "D8": b12, "D12": b12, "E8": e, "E12": e}
    for k in ex:
        ex[k] = np.where(m.elig, np.nan_to_num(ex[k]), np.nan)
    return ex


SIZING = {"D": 0.10, "E": 0.10, "D8": 0.08, "D12": 0.12, "E8": 0.08, "E12": 0.12}


def caps(w: np.ndarray) -> np.ndarray:
    """§12: single ETF <= 25%, equities <= 60%, real assets <= 40%; excess to cash."""
    w = w.copy()
    for _ in range(10):
        w = np.minimum(w, 0.25)
        for grp, cap in ((EQUITY, 0.60), (REAL, 0.40)):
            s = w[:, grp].sum(1, keepdims=True)
            w[:, grp] *= np.where(s > cap, cap / np.maximum(s, 1e-12), 1.0)
        if (w <= 0.25 + 1e-12).all() and (w[:, EQUITY].sum(1) <= 0.60 + 1e-9).all() and \
                (w[:, REAL].sum(1) <= 0.40 + 1e-9).all():
            break
    return w


def covs(m: Mkt):
    """252-day daily covariance at each month-end (eligible ETFs only), cached."""
    if hasattr(m, "cov"):
        return m.cov
    m.cov = []
    for i, d in enumerate(m.me):
        el = m.elig[i]
        if i < m.s0 or not el.any():
            m.cov.append(None)
            continue
        win = m.dret[d - 251:d + 1][:, el]
        m.cov.append(np.cov(win, rowvar=False) * 252)
    return m.cov


def weights(m: Mkt, expo: np.ndarray, name: str) -> np.ndarray:
    e = np.nan_to_num(expo)
    el = m.elig
    if name in SIZING:  # §10
        target = SIZING[name]
        cv = covs(m)
        inv = np.where(el, 1 / np.where(m.sig60 > 0, m.sig60, np.nan), 0)
        inv = np.nan_to_num(inv)
        w = e * inv / np.maximum(inv.sum(1, keepdims=True), 1e-12)
        for i in range(len(w)):
            if cv[i] is None or w[i].sum() <= 0:
                w[i] = 0
                continue
            x = w[i, el[i]]
            pv = math.sqrt(max(float(x @ cv[i] @ x), 1e-16))
            w[i] *= target / pv
            if w[i].sum() > 1:
                w[i] /= w[i].sum()
    else:  # §9 equal slots
        n = el.sum(1, keepdims=True)
        w = e / np.maximum(n, 1)
    return caps(w)


# ---------------------------------------------------------------------------------------------------- simulation (§8)

class Run:
    pass


def simulate(m: Mkt, W: np.ndarray, cost: np.ndarray, s0: int | None = None, detail: bool = True) -> Run:
    """W: target weights at each month-end (rows = all month-ends). Trades at the next session's open."""
    s0 = m.s0 if s0 is None else s0
    T, K = m.close.shape
    op, cl, ci = np.nan_to_num(m.open), np.nan_to_num(m.close), m.ci
    nav = np.full(T, np.nan)
    d0 = m.me[s0]
    nav[d0] = 1.0
    shares, cash = np.zeros(K), 1.0
    contrib, costs_k, last_val = np.zeros(K), np.zeros(K), np.zeros(K)
    reb = []
    rows = [i for i in range(s0, len(m.me)) if m.me[i] + 1 < T]
    for j, i in enumerate(rows):
        d = m.me[i] + 1
        dn = m.me[rows[j + 1]] + 1 if j + 1 < len(rows) else T
        val = shares * op[d]
        contrib += val - last_val
        nav_o = cash + val.sum()
        tgt = W[i] * nav_o
        tr = tgt - val
        tr[np.abs(tr) < NO_TRADE * nav_o] = 0.0
        c = np.abs(tr) * cost
        new = val + tr
        shares = np.divide(new, op[d], out=np.zeros(K), where=op[d] > 0)
        cash = nav_o - new.sum() - c.sum()
        contrib -= c
        costs_k += c
        last_val = new
        seg = cl[d:dn] @ shares
        cpath = cash * ci[d:dn] / ci[d - 1]
        nav[d:dn] = seg + cpath
        cash = cpath[-1]
        if detail:
            reb.append((m.cal[d], new.sum() / nav_o, np.abs(tr).sum() / nav_o, c.sum() / nav_o))
    contrib += shares * cl[T - 1] - last_val
    r = Run()
    r.nav = pd.Series(nav, index=m.cal).iloc[d0:]
    r.nav = r.nav.ffill()
    me = m.me[s0:]
    r.mnav = pd.Series(nav[me], index=m.cal[me]).ffill()
    r.mret = r.mnav.pct_change().dropna()
    if detail:
        r.contrib = pd.Series(contrib, index=TICKERS)
        r.cash_contrib = float(r.nav.iloc[-1] - 1 - contrib.sum())
        r.reb = pd.DataFrame(reb, columns=["date", "exposure", "turnover", "cost"]).set_index("date")
    return r


# ---------------------------------------------------------------------------------------------------- metrics (§21)

def maxdd(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def longest_dd_months(nav: pd.Series) -> float:
    under = nav < nav.cummax()
    best = cur = 0
    for u in under.to_numpy():
        cur = cur + 1 if u else 0
        best = max(best, cur)
    return best / 21


def sharpe(x: np.ndarray) -> float:
    x = np.asarray(x)
    s = x.std(ddof=1)
    return float(x.mean() / s * math.sqrt(12)) if s > 0 else 0.0


def metrics(r: Run, cash_m: pd.Series, lo=None, hi=None) -> dict:
    nav = r.nav
    mret = r.mret
    if lo is not None:
        nav = nav[nav.index >= lo]
        mret = mret[mret.index >= lo]
    if hi is not None:
        nav = nav[nav.index <= hi]
        mret = mret[mret.index <= hi]
    if len(mret) < 3:
        return {}
    ex = (mret - cash_m.reindex(mret.index)).to_numpy()
    yrs = len(mret) / 12
    growth = float(np.prod(1 + mret.to_numpy()))
    cagr = growth ** (1 / yrs) - 1
    dd = maxdd(nav)
    down = np.sqrt(np.mean(np.minimum(ex, 0) ** 2))
    roll12 = (1 + mret).rolling(12).apply(np.prod, raw=True) - 1
    out = {"months": len(mret), "CAGR": cagr, "Vol": float(mret.std(ddof=1) * math.sqrt(12)), "Sharpe": sharpe(ex),
           "Sortino": float(ex.mean() / down * math.sqrt(12)) if down > 0 else 0.0, "MaxDD": dd,
           "LongestDD_m": longest_dd_months(nav), "Calmar": cagr / abs(dd) if dd < 0 else float("nan"),
           "PosMonths": float((mret > 0).mean()), "Best": float(mret.max()), "Worst": float(mret.min()),
           "Worst12m": float(roll12.min()) if roll12.notna().any() else float("nan"),
           "Skew": float(pd.Series(mret).skew())}
    if hasattr(r, "reb"):
        rb = r.reb
        if lo is not None:
            rb = rb[rb.index >= lo]
        if hi is not None:
            rb = rb[rb.index <= hi]
        out.update({"Exposure": float(rb.exposure.mean()), "Turnover_yr": float(rb.turnover.sum() / 2 / yrs),
                    "CostDrag_yr": float(rb.cost.sum() / yrs)})
    return out


def show(rows: dict[str, dict], cols=("CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "LongestDD_m", "Calmar",
                                      "PosMonths", "Best", "Worst", "Worst12m", "Skew", "Exposure", "Turnover_yr",
                                      "CostDrag_yr")):
    pct = {"CAGR", "Vol", "MaxDD", "PosMonths", "Best", "Worst", "Worst12m", "Exposure", "Turnover_yr", "CostDrag_yr"}
    say(f"{'':10s}" + "".join(f"{c[:10]:>11s}" for c in cols))
    for k, v in rows.items():
        if not v:
            say(f"{k:10s} (too short)")
            continue
        cells = []
        for c in cols:
            x = v.get(c, float("nan"))
            cells.append(f"{x:>10.1%} " if c in pct and x == x else f"{x:>10.2f} ")
        say(f"{k:10s}" + "".join(cells))


# ---------------------------------------------------------------------------------------------------- statistics (§18)

def newey_west(x: np.ndarray, lags: int = 6) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    n = len(x)
    u = x - x.mean()
    v = u @ u / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    se = math.sqrt(v / n)
    t = x.mean() / se if se > 0 else 0.0
    return x.mean(), t, 1 - ND.cdf(t)


def holm(p: dict[str, float]) -> dict[str, float]:
    keys = sorted(p, key=p.get)
    n, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (n - i) * p[k]))
        out[k] = run
    return out


def sb_idx(n_src: int, n_out: int, reps: int, rng, block: float = 6.0) -> np.ndarray:
    """Stationary bootstrap indices (Politis & Romano 1994), mean block length `block`."""
    idx = np.empty((reps, n_out), np.int64)
    idx[:, 0] = rng.integers(0, n_src, reps)
    new = rng.random((reps, n_out)) < 1 / block
    jump = rng.integers(0, n_src, (reps, n_out))
    for t in range(1, n_out):
        idx[:, t] = np.where(new[:, t], jump[:, t], (idx[:, t - 1] + 1) % n_src)
    return idx


def boot_sharpe(x: np.ndarray, y: np.ndarray | None, reps=10_000):
    rng = np.random.default_rng(SEED)
    idx = sb_idx(len(x), len(x), reps, rng)

    def sh(a):
        s = a.std(1, ddof=1)
        return a.mean(1) / np.where(s > 0, s, np.nan) * math.sqrt(12)

    sx = sh(x[idx])
    out = {"ci": (float(np.nanpercentile(sx, 2.5)), float(np.nanpercentile(sx, 97.5)))}
    if y is not None:
        diff = sx - sh(y[idx])
        out["diff_ci"] = (float(np.nanpercentile(diff, 2.5)), float(np.nanpercentile(diff, 97.5)))
        out["diff_p"] = float(np.nanmean(diff <= 0))
    return out


def deflated_sharpe(x: np.ndarray, trial_srs: np.ndarray) -> float:
    """Bailey & Lopez de Prado (2014). Monthly (non-annualised) Sharpe ratios."""
    n_trials = len(trial_srs)
    sr = x.mean() / x.std(ddof=1)
    g = 0.5772156649
    v = np.var(trial_srs, ddof=1)
    sr0 = math.sqrt(v) * ((1 - g) * ND.inv_cdf(1 - 1 / n_trials) + g * ND.inv_cdf(1 - 1 / (n_trials * math.e)))
    s = pd.Series(x)
    skew, kurt = float(s.skew()), float(s.kurt()) + 3
    den = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    return ND.cdf((sr - sr0) * math.sqrt(len(x) - 1) / den)


def pbo(M: np.ndarray, S: int = 16) -> float:
    """CSCV probability of backtest overfitting (Bailey, Borwein, Lopez de Prado & Zhu 2017)."""
    T, N = M.shape
    T2 = T - T % S
    M = M[T - T2:]  # drop the earliest months so the blocks are equal
    B = M.reshape(S, T2 // S, N)
    s1, s2, cnt = B.sum(1), (B ** 2).sum(1), np.full(S, T2 // S)
    combos = np.array([[i in c for i in range(S)] for c in itertools.combinations(range(S), S // 2)], float)

    def shp(mask):
        n = mask @ cnt
        mu = (mask @ s1) / n[:, None]
        var = (mask @ s2) / n[:, None] - mu ** 2
        return mu / np.sqrt(np.maximum(var, 1e-18))

    ins, oos = shp(combos), shp(1 - combos)
    best = ins.argmax(1)
    rank = (oos < oos[np.arange(len(oos)), best][:, None]).sum(1) + 1  # 1 = worst ... N = best
    w = rank / (N + 1)
    lam = np.log(w / (1 - w))
    return float((lam <= 0).mean())


# ---------------------------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--placebos", type=int, default=1000)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--cache", default="/tmp/trend_study_data.pkl")
    a = ap.parse_args()
    end = pd.Timestamp.now(tz="America/New_York").to_period("M").start_time.strftime("%Y-%m-%d")
    say(f"Study 3, diversified ETF trend following. Protocol: research/TREND_FOLLOWING_PROTOCOL.md. "
        f"Data up to (not including) {end}." + ("  *** SYNTHETIC DATA: results are meaningless ***" if a.synthetic else ""))
    data = load_synthetic(end) if a.synthetic else load_real(end, Path(a.cache))
    m = prepare(data, end)

    # §22.4 cross-check
    if not a.synthetic:
        alp = alpaca_monthly(end)
        if alp:
            cl = pd.DataFrame(m.close, index=m.cal, columns=TICKERS)
            yfm = cl.groupby(cl.index.to_period("M")).last().pct_change()
            fails = []
            for t in TICKERS:
                if t not in alp:
                    say(f"  {t}: no Alpaca data")
                    fails.append(t)
                    continue
                both = pd.concat([yfm[t], alp[t]], axis=1, join="inner").dropna()
                both = both[both.index >= pd.Period("2016-01", "M")]
                mad = float((both.iloc[:, 0] - both.iloc[:, 1]).abs().median() * 100)
                ok = mad < 0.10
                fails += [] if ok else [t]
                say(f"  Alpaca vs Yahoo {t}: {len(both)} months, median |difference| {mad:.3f} pp  {'OK' if ok else 'FLAG'}")
            m.dq_label = "data quality unconfirmed" if len(fails) > 2 else "data quality confirmed"
            say(f"Cross-check: {len(fails)} ETF(s) flagged {fails} -> {m.dq_label}")
        else:
            m.dq_label = "Alpaca cross-check not run"
            say("Cross-check: not run (no Alpaca access)")
    else:
        m.dq_label = "synthetic"

    ex = signals(m)
    cash_run = simulate(m, np.zeros((len(m.me), len(TICKERS))), COST["net"])
    cash_m = cash_run.mret
    ci_m = pd.Series(m.ci, index=m.cal).iloc[m.me]
    cash_m_all = ci_m.pct_change()

    W = {k: weights(m, ex[k], k) for k in PRIMARY + VARIANTS}
    K = len(TICKERS)
    elig = m.elig.astype(float)
    spy = np.zeros((len(m.me), K)); spy[:, TICKERS.index("SPY")] = 1
    qqq = np.zeros((len(m.me), K)); qqq[:, TICKERS.index("QQQ")] = 1
    ief = np.zeros((len(m.me), K)); ief[:, TICKERS.index("IEF")] = 1
    sixty = 0.6 * spy + 0.4 * ief
    bench = {"BH-SPY": spy, "BH-QQQ": qqq, "BH-DIV": elig / elig.sum(1, keepdims=True).clip(1), "60/40": sixty,
             "CASH": np.zeros_like(spy), "BH-IEF": ief,
             "SMA-SPY": spy * np.nan_to_num(ex["A"][:, [TICKERS.index("SPY")]]),
             "TSM-SPY": spy * np.nan_to_num(ex["B12"][:, [TICKERS.index("SPY")]])}
    allw = {**W, **bench}
    runs = {c: {k: simulate(m, w, COST[c]) for k, w in allw.items()} for c in ("net", "gross", "stress")}
    net = runs["net"]

    # §17.1 walk-forward selection
    wf = np.zeros_like(spy)
    cands = ["A", "B3", "B6", "B12", "C", "D"]
    wf_pick = {}
    for i, dt in enumerate(m.me_dates):
        if dt.month == 12 and dt.year >= 2008 and i >= m.s0 + 60:
            sc = {}
            for c in cands:
                x = net[c].mret
                x = (x - cash_m_all.reindex(x.index))[x.index <= dt].iloc[-60:]
                sc[c] = sharpe(x.to_numpy()) if len(x) == 60 else -9
            pick = max(sc, key=sc.get)
            wf_pick[dt.year + 1] = pick
            for j in range(i, min(i + 12, len(m.me))):
                wf[j] = W[pick][j]
    wf_run = simulate(m, wf, COST["net"])
    wf_lo = pd.Timestamp(f"{min(wf_pick) if wf_pick else 2009}-01-01")

    # ---------------------------------------------------------------- headline tables
    start, last = m.me_dates[m.s0], m.me_dates[-1]
    hdr(f"RESULTS, full period {start.date()} to {last.date()} (USD). Strategies: A B3 B6 B12 C D E; rest are benchmarks")
    for c, label in (("net", "NET of base-case costs (§13)"), ("gross", "GROSS (no costs)"),
                     ("stress", "STRESS costs (3x spread+slippage, 0.5% FX)")):
        say(f"\n--- {label}")
        show({k: metrics(runs[c][k], cash_m) for k in PRIMARY + list(bench)})
    say("\n--- Sensitivity variants (§5), net. Reported, never picked")
    show({k: metrics(net[k], cash_m) for k in VARIANTS})

    say("\n--- Pre-holdout (to 2017-12) and holdout (2018-01 on), net")
    for lab, lo, hi in (("PRE", None, HOLDOUT - pd.Timedelta(days=1)), ("HOLDOUT", HOLDOUT, None)):
        say(f"[{lab}]")
        show({k: metrics(net[k], cash_m, lo, hi) for k in PRIMARY + ["BH-DIV", "BH-SPY", "60/40"]},
             cols=("CAGR", "Vol", "Sharpe", "MaxDD", "Calmar", "Worst12m"))

    # GBP (§21)
    gbp_runs = {}
    g = m.gbp
    for k in PRIMARY + list(bench):
        r = net[k]
        rr = Run()
        nav_g = (r.nav / g.reindex(r.nav.index)).dropna()
        nav_g = nav_g[nav_g.index >= "2004-01-01"]
        rr.nav = nav_g / nav_g.iloc[0]
        rr.mnav = rr.nav.groupby(rr.nav.index.to_period("M")).last()
        rr.mnav.index = rr.nav.groupby(rr.nav.index.to_period("M")).apply(lambda s: s.index[-1])
        rr.mret = rr.mnav.pct_change().dropna()
        rr.reb = r.reb
        gbp_runs[k] = rr
    say("\n--- NET, in GBP (a UK investor's pounds), from 2004")
    show({k: metrics(v, cash_m) for k, v in gbp_runs.items()}, cols=("CAGR", "Vol", "Sharpe", "MaxDD", "Calmar",
                                                                       "Worst12m"))
    say("(Sharpe in GBP is measured over USD T-bills, so treat it as indicative.)")

    say("\n--- Walk-forward selection (§17.1): each January pick the best of A,B3,B6,B12,C,D on the last 60 months")
    say("picks: " + ", ".join(f"{y}:{p}" for y, p in sorted(wf_pick.items())))
    show({"WF": metrics(wf_run, cash_m, wf_lo), "E": metrics(net["E"], cash_m, wf_lo),
          "BH-DIV": metrics(net["BH-DIV"], cash_m, wf_lo)}, cols=("CAGR", "Vol", "Sharpe", "MaxDD", "Calmar"))

    # ---------------------------------------------------------------- statistics
    hdr("STATISTICAL TESTS (§18)")
    xs = {k: (net[k].mret - cash_m.reindex(net[k].mret.index)).to_numpy() for k in PRIMARY + VARIANTS + list(bench)}
    nw = {k: newey_west(xs[k]) for k in PRIMARY}
    hp = holm({k: nw[k][2] for k in PRIMARY})
    trial_srs = np.array([xs[k].mean() / xs[k].std(ddof=1) for k in PRIMARY + VARIANTS])
    pb = pbo(np.column_stack([xs[k] for k in PRIMARY + VARIANTS]))
    say(f"Family PBO (CSCV, 16 blocks, 15 configurations): {pb:.2f}  (pass line <= 0.50)")
    stats = {}
    for k in PRIMARY:
        b = boot_sharpe(xs[k], xs["BH-DIV"], a.boot)
        dsr = deflated_sharpe(xs[k], trial_srs)
        stats[k] = {"mean_m": nw[k][0], "t": nw[k][1], "p": nw[k][2], "p_holm": hp[k], "sharpe_ci": b["ci"],
                    "diff_ci": b["diff_ci"], "diff_p": b["diff_p"], "dsr": dsr}
        say(f"{k:4s} mean excess {nw[k][0] * 100:+.2f}%/mo  NW t {nw[k][1]:5.2f} (HLZ t>3: {'yes' if nw[k][1] > 3 else 'no'})"
            f"  p {nw[k][2]:.4f}  Holm p {hp[k]:.4f}  Sharpe 95% CI [{b['ci'][0]:.2f}, {b['ci'][1]:.2f}]"
            f"  vs BH-DIV diff CI [{b['diff_ci'][0]:+.2f}, {b['diff_ci'][1]:+.2f}] p {b['diff_p']:.3f}  DSR {dsr:.3f}")
    b = boot_sharpe(xs["BH-DIV"], None, a.boot)
    say(f"BH-DIV Sharpe 95% CI [{b['ci'][0]:.2f}, {b['ci'][1]:.2f}]")

    # §18.4 random-timing null
    say(f"\nRandom-timing null (§18.4): {a.placebos} placebos per strategy, exposures shuffled in 3-month blocks")
    rng = np.random.default_rng(SEED)
    plc = {}
    for k in PRIMARY:
        e = np.nan_to_num(ex[k])
        sh_, dd_ = [], []
        t0 = time.time()
        for _ in range(a.placebos):
            e2 = e.copy()
            for j in range(K):
                rows = np.flatnonzero(m.elig[:, j])
                rows = rows[rows >= m.s0]
                if len(rows) < 2:
                    continue
                chunks = [rows[i:i + 3] for i in range(0, len(rows), 3)]
                order = rng.permutation(len(chunks))
                e2[rows, j] = np.concatenate([e[chunks[o], j] for o in order])
            ww = weights(m, np.where(m.elig, e2, np.nan), k)
            rr = simulate(m, ww, COST["net"], detail=False)
            x = (rr.mret - cash_m.reindex(rr.mret.index)).to_numpy()
            sh_.append(sharpe(x))
            dd_.append(maxdd(rr.nav))
        real_sh, real_dd = sharpe(xs[k]), maxdd(net[k].nav)
        plc[k] = {"pct_sharpe": float(np.mean(np.array(sh_) < real_sh)),
                  "pct_dd": float(np.mean(np.array(dd_) < real_dd)),  # share of placebos with a WORSE drawdown
                  "placebo_sharpe_median": float(np.median(sh_)), "placebo_sharpe_95": float(np.percentile(sh_, 95))}
        say(f"{k:4s} real Sharpe {real_sh:.2f} vs placebo median {np.median(sh_):.2f}, 95th pct {np.percentile(sh_, 95):.2f}"
            f" -> percentile {plc[k]['pct_sharpe']:.1%};  max DD {real_dd:.1%} worse-than-real placebos "
            f"{plc[k]['pct_dd']:.1%}  ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- verdicts (§19)
    hdr("PASS / FAIL (§19)")
    bd = metrics(net["BH-DIV"], cash_m)
    bd_h = metrics(net["BH-DIV"], cash_m, HOLDOUT)
    verdict = {}
    for k in PRIMARY:
        f = metrics(net[k], cash_m)
        h = metrics(net[k], cash_m, HOLDOUT)
        st = metrics(runs["stress"][k], cash_m)
        subs = []
        for lo, hi in ((None, "2009-12-31"), ("2010-01-01", "2017-12-31"), ("2018-01-01", None)):
            q = metrics(net[k], cash_m, pd.Timestamp(lo) if lo else None, pd.Timestamp(hi) if hi else None)
            subs.append(q.get("CAGR", float("nan")))
        r = net[k]
        profit = float(r.nav.iloc[-1] - 1)
        share = float(r.contrib.max() / profit) if profit > 0 else float("inf")
        c = {
            "1 significance (Holm p<0.05)": stats[k]["p_holm"] < 0.05,
            "2 Sharpe>=BH-DIV and DD<=0.75xBH-DIV": f["Sharpe"] >= bd["Sharpe"] and abs(f["MaxDD"]) <= 0.75 * abs(bd["MaxDD"]),
            "3 holdout Sharpe>0 and DD<=BH-DIV": h["Sharpe"] > 0 and abs(h["MaxDD"]) <= abs(bd_h["MaxDD"]),
            "4 beats 95% of random timing": plc[k]["pct_sharpe"] >= 0.95,
            "5 DSR>=0.95 and PBO<=0.5": stats[k]["dsr"] >= 0.95 and pb <= 0.50,
            "6 positive CAGR in >=2 of 3 sub-periods": sum(x > 0 for x in subs) >= 2,
            "7 Sharpe>0 at stress costs": st["Sharpe"] > 0,
            "8 no ETF >50% of profit": share <= 0.50,
        }
        n_pass = sum(c.values())
        if all(c.values()):
            v = "VALIDATED"
        elif all(c[x] for x in c if x[0] in "23678"):
            v = "PROMISING (not built)"
        else:
            v = "FAILED"
        verdict[k] = {"verdict": v, "criteria": c, "n_pass": n_pass, "subperiod_cagr": subs, "top_etf_share": share,
                      "full": f, "holdout": h, "stress_sharpe": st["Sharpe"]}
        say(f"\n{k}: {v}  ({n_pass}/8)")
        for name, ok in c.items():
            say(f"   {'PASS' if ok else 'fail'}  {name}")
        say(f"   detail: Sharpe {f['Sharpe']:.2f} vs BH-DIV {bd['Sharpe']:.2f}; maxDD {f['MaxDD']:.1%} vs line "
            f"{-0.75 * abs(bd['MaxDD']):.1%}; holdout Sharpe {h['Sharpe']:.2f}, DD {h['MaxDD']:.1%} vs BH-DIV "
            f"{bd_h['MaxDD']:.1%}; sub-period CAGR {', '.join(f'{x:+.1%}' for x in subs)}; stress Sharpe "
            f"{st['Sharpe']:.2f}; biggest single-ETF share of profit {share:.0%}")

    # ---------------------------------------------------------------- descriptive (§20, §21)
    hdr("BY DECADE, net (CAGR / Sharpe / max DD)")
    for lab, lo, hi in (("2000s", None, "2009-12-31"), ("2010s", "2010-01-01", "2019-12-31"), ("2020s", "2020-01-01", None)):
        say(f"[{lab}]")
        show({k: metrics(net[k], cash_m, pd.Timestamp(lo) if lo else None, pd.Timestamp(hi) if hi else None)
              for k in PRIMARY + ["BH-DIV", "BH-SPY", "60/40"]}, cols=("CAGR", "Sharpe", "MaxDD"))

    hdr("BY CALENDAR YEAR, net return")
    cols = PRIMARY + ["BH-DIV", "BH-SPY", "BH-QQQ", "60/40", "CASH"]
    say(f"{'year':6s}" + "".join(f"{c:>8s}" for c in cols))
    yr = {c: (1 + net[c].mret).groupby(net[c].mret.index.year).prod() - 1 for c in cols}
    for y in sorted(yr["A"].index):
        say(f"{y:<6d}" + "".join(f"{yr[c].get(y, float('nan')):>8.1%}" for c in cols))

    hdr("CRISIS WINDOWS (§20.2): return over the window / worst drawdown inside it")
    say(f"{'':22s}" + "".join(f"{c:>15s}" for c in PRIMARY + ["BH-DIV", "BH-SPY"]))
    for name, (lo, hi) in CRISES.items():
        lo_t = pd.Period(lo, "M").start_time
        hi_t = pd.Period(hi, "M").end_time
        cells = []
        for c in PRIMARY + ["BH-DIV", "BH-SPY"]:
            mr = net[c].mret[(net[c].mret.index >= lo_t) & (net[c].mret.index <= hi_t)]
            nv = net[c].nav[(net[c].nav.index >= lo_t - pd.Timedelta(days=4)) & (net[c].nav.index <= hi_t)]
            cells.append(f"{np.prod(1 + mr) - 1:>+7.1%}/{maxdd(nv):>+6.1%}" if len(mr) else f"{'n/a':>15s}")
        say(f"{name:22s}" + " ".join(cells))

    hdr("REGIMES (§20.3): mean monthly return, Sharpe, months")
    spy_m = net["BH-SPY"].mret
    spy12 = (1 + spy_m).rolling(12).apply(np.prod, raw=True) - 1
    reg = {"bull (SPY 12m >= 0)": spy12.shift(1) >= 0, "bear (SPY 12m < 0)": spy12.shift(1) < 0}
    if data.get("usrec") is not None:
        rec = data["usrec"].groupby(data["usrec"].index.to_period("M")).last()
        rr_ = pd.Series(spy_m.index.to_period("M").map(rec).astype(float), index=spy_m.index)
        reg["NBER recession"], reg["expansion"] = rr_ == 1, rr_ == 0
    if data.get("cpi") is not None:
        cpi = data["cpi"].groupby(data["cpi"].index.to_period("M")).last()
        yoy = cpi.pct_change(12)
        yy = pd.Series(spy_m.index.to_period("M").map(yoy).astype(float), index=spy_m.index)
        reg["inflation > 4%"], reg["inflation <= 4%"] = yy > 0.04, yy <= 0.04
    else:
        say("CPI regime: not available")
    for name, mask in reg.items():
        say(f"[{name}]")
        for c in PRIMARY + ["BH-DIV", "BH-SPY", "60/40"]:
            mr = net[c].mret
            mk = mask.reindex(mr.index).fillna(False).astype(bool)
            x = mr[mk]
            if len(x) < 3:
                continue
            exx = (x - cash_m.reindex(x.index)).to_numpy()
            say(f"   {c:7s} mean {x.mean():+.2%}/mo  Sharpe {sharpe(exx):5.2f}  months {len(x)}")

    hdr("DIVERSIFICATION (§20.1)")
    cl = pd.DataFrame(m.close, index=m.cal, columns=TICKERS)
    em = cl.iloc[m.me].pct_change()
    em = em[em.index > start]
    stress_mask = em["SPY"] <= em["SPY"].quantile(0.10)
    pd.set_option("display.width", 250)
    say("Monthly correlation of the 13 ETFs, all months:")
    say(em.corr().round(2).to_string())
    say(f"\nSame, SPY's worst 10% of months only ({int(stress_mask.sum())} months):")
    say(em[stress_mask].corr().round(2).to_string())
    avg_all = em.corr().where(~np.eye(K, dtype=bool)).stack().mean()
    avg_st = em[stress_mask].corr().where(~np.eye(K, dtype=bool)).stack().mean()
    say(f"Average pairwise correlation: all months {avg_all:.2f}, stress months {avg_st:.2f}")
    say("\nStrategy correlation / beta to SPY: all months | SPY-down months | stress months")
    for c in PRIMARY + ["BH-DIV", "60/40"]:
        x = net[c].mret
        s = spy_m.reindex(x.index)
        out = []
        for mk in (s.notna(), s < 0, s <= s.quantile(0.10)):
            xx, ss = x[mk], s[mk]
            beta = np.cov(xx, ss)[0, 1] / ss.var() if len(xx) > 2 else float("nan")
            out.append(f"{xx.corr(ss):+.2f} / {beta:+.2f}")
        say(f"   {c:7s} " + " | ".join(out))

    hdr("CONTRIBUTION TO NET PROFIT, by asset class and ETF (share of total profit; cash interest separate)")
    for c in PRIMARY + ["BH-DIV"]:
        r = net[c]
        prof = float(r.nav.iloc[-1] - 1)
        bycls = r.contrib.groupby(CLS).sum()
        say(f"{c:7s} total profit per $1: {prof:+.2f}  | " + "  ".join(f"{k}: {v / prof:+.0%}" for k, v in bycls.items())
            + f"  cash: {r.cash_contrib / prof:+.0%}")
        say("        " + "  ".join(f"{t} {v / prof:+.0%}" for t, v in r.contrib.sort_values(ascending=False).items()))

    hdr("ROLLING 60-MONTH WINDOWS (§17.2): share of windows beating BH-DIV")
    bdm = net["BH-DIV"].mret
    for c in PRIMARY:
        x = net[c].mret
        n = len(x)
        win_s = win_d = tot = 0
        for i in range(60, n + 1):
            xs_, bs_ = x.iloc[i - 60:i], bdm.iloc[i - 60:i]
            cm = cash_m.reindex(xs_.index)
            tot += 1
            win_s += sharpe((xs_ - cm).to_numpy()) > sharpe((bs_ - cm).to_numpy())
            win_d += maxdd((1 + xs_).cumprod()) > maxdd((1 + bs_).cumprod())
        say(f"   {c:4s} {tot} windows: higher Sharpe in {win_s / tot:.0%}, smaller max drawdown in {win_d / tot:.0%}")

    say("\nSPY-only supplementary from 1994 (§3; does not count toward pass/fail):")
    show({k: metrics(simulate(m, w, COST["net"], s0=m.spy0), cash_m_all)
          for k, w in (("BH-SPY", spy), ("SMA-SPY", bench["SMA-SPY"]), ("TSM-SPY", bench["TSM-SPY"]))},
         cols=("CAGR", "Vol", "Sharpe", "MaxDD", "Calmar", "Worst12m"))

    # ---------------------------------------------------------------- capital (§23)
    hdr("CAPITAL AND THE £30-A-DAY QUESTION (§23), net GBP returns, block bootstrap, 20 years")
    best = max(PRIMARY, key=lambda k: (verdict[k]["n_pass"], verdict[k]["full"]["Sharpe"]))
    say(f"Best-scoring primary strategy: {best} ({verdict[best]['verdict']}).  £630/month withdrawn, +2.5%/yr.")
    cap_out = {}
    for c in [best, "BH-DIV", "60/40", "BH-SPY"]:
        x = gbp_runs[c].mret.to_numpy()
        yrs = (1 + gbp_runs[c].mret).groupby(gbp_runs[c].mret.index.year).prod() - 1
        yrs = yrs[yrs.index > 2004]  # 2004 starts in January from 2004-01-31, so its first month is missing
        rng = np.random.default_rng(SEED)
        idx = sb_idx(len(x), 240, a.boot, rng)
        R = x[idx]
        wd = 630 * 1.025 ** (np.arange(240) // 12)
        say(f"\n[{c}] historical GBP: CAGR {metrics(gbp_runs[c], cash_m)['CAGR']:.1%}; losing calendar years "
            f"{(yrs < 0).sum()}/{len(yrs)}; worst year {yrs.min():+.1%} ({yrs.idxmin()})")
        cap_out[c] = {}
        for cap in (25_000, 50_000, 100_000, 150_000, 250_000):
            line = []
            for tax_name, rate in (("ISA", 0.0), ("GIA basic 18%", 0.18), ("GIA higher 24%", 0.24)):
                pot = np.full(a.boot, float(cap))
                dead = np.zeros(a.boot, bool)
                year_start, carry, wd_year = pot.copy(), np.zeros(a.boot), np.zeros(a.boot)
                for t in range(240):
                    pot = pot * (1 + R[:, t]) - wd[t]
                    wd_year += wd[t]
                    if t % 12 == 11 and rate > 0:
                        gain = pot - year_start + wd_year - carry
                        taxable = np.maximum(gain - 3000, 0)
                        carry = np.where(gain < 0, -gain, 0)  # losses carried forward (simplified)
                        pot = pot - rate * taxable
                    if t % 12 == 11:
                        year_start, wd_year = pot.copy(), np.zeros(a.boot)
                    dead |= pot <= 0
                    pot = np.where(dead, 0, pot)
                line.append((tax_name, float(dead.mean()), float(np.median(pot)), float(np.percentile(pot, 10))))
            cap_out[c][cap] = line
            say(f"   start £{cap:>7,}: " + " | ".join(f"{n}: runs out {d:.0%}, median £{md:,.0f}, bad-case(10%) £{p10:,.0f}"
                                                   for n, d, md, p10 in line)
                + f" | worst year ≈ £{yrs.min() * cap:,.0f}; typical £/trading day ≈ £{max(metrics(gbp_runs[c], cash_m)['CAGR'], 0) * cap / 252:,.0f}")
    say("\nNotes: ISA contributions are capped at £20,000 a year. 'GIA' taxes each year's gain above £3,000 as a capital "
        "gain (income is not separated out, so this understates tax for higher-rate payers). US-listed ETFs are usually "
        "non-reporting funds for UK tax (gains taxed as income); a UK investor would use UCITS equivalents (§24.4-5).")

    # ---------------------------------------------------------------- summary
    hdr("SUMMARY")
    for k in PRIMARY:
        say(f"{k:4s} {verdict[k]['verdict']:24s} {verdict[k]['n_pass']}/8  net Sharpe {verdict[k]['full']['Sharpe']:.2f}  "
            f"CAGR {verdict[k]['full']['CAGR']:.1%}  max DD {verdict[k]['full']['MaxDD']:.1%}")
    say(f"BH-DIV                               net Sharpe {bd['Sharpe']:.2f}  CAGR {bd['CAGR']:.1%}  max DD {bd['MaxDD']:.1%}")
    say(f"Data: {m.dq_label}. Family PBO {pb:.2f}.")
    out = {"verdict": {k: {kk: vv for kk, vv in v.items() if kk != "criteria"} | {"criteria": {n: bool(b) for n, b in v["criteria"].items()}}
                       for k, v in verdict.items()},
           "stats": stats, "placebo": plc, "pbo": pb, "wf_picks": wf_pick, "data": m.dq_label,
           "start": str(start.date()), "end": str(last.date())}
    Path("research_trend_summary.json").write_text(json.dumps(out, indent=1, default=str))
    say("\nJSON:\n" + json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
