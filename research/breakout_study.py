"""
Study 2 (see PROTOCOL.md): the swing breakout, on a point-in-time S&P 500 universe, out of sample.

The entry and exit rules are bot.py's, unchanged. What's new is only what it's tested on and how it's measured:
  - universe: S&P 500 members AS OF each signal date (current list + public change history, removed companies included)
  - data: Alpaca daily bars, all US exchanges, split- and dividend-adjusted, 2016 onwards
  - costs: 0.10 / 0.25 / 0.50% per side
  - periods: development 2016-21, validation 2022-23, untouched holdout 2024 onwards
  - null: the same exits from random entry days
  - robustness: without the 10 best trades, without the 10 best shares, by year, by market regime
  - portfolio: £1,000, 2% risk a trade, at most 10 open, cash-limited; daily P&L, Sharpe, Sortino, worst fall

  python research/breakout_study.py            (needs ALPACA_KEY / ALPACA_SECRET and internet access to Wikipedia)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bot  # noqa: E402

DEV_END, VAL_END = "2021-12-31", "2023-12-31"
COSTS = (0.0010, 0.0025, 0.0050)
MAIN_COST = 0.0025


# ---------------------------------------------------------------------------
# Point-in-time universe
# ---------------------------------------------------------------------------


def sp500_membership() -> dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """{ticker: [(from, to)]}: S&P 500 membership on every date, from the public dataset github.com/fja05680/sp500
    (a CSV of the index's members after every change since 1996, removed companies included)."""
    import re

    import requests

    files = requests.get("https://api.github.com/repos/fja05680/sp500/contents", timeout=30).json()
    cands = sorted(f["name"] for f in files if f["name"].startswith("S&P 500 Historical Components") and f["name"].endswith(".csv"))
    url = next(f["download_url"] for f in files if f["name"] == cands[-1])
    hist = pd.read_csv(io.StringIO(requests.get(url, timeout=60).text))
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date")

    def norm(t: str) -> str:
        t = t.strip().upper().replace(".", "-")
        return re.sub(r"-\d{6}$", "", t)  # old tickers later reused carry a -YYYYMM suffix in the dataset

    spans: dict[str, list] = {}
    open_since: dict[str, pd.Timestamp] = {}
    prev: set = set()
    for _, r in hist.iterrows():
        cur = {norm(x) for x in str(r["tickers"]).split(",") if x.strip()}
        d = r["date"]
        for t in cur - prev:
            open_since[t] = d
        for t in prev - cur:
            spans.setdefault(t, []).append((open_since.pop(t), d))
        prev = cur
    end = pd.Timestamp("2100-01-01")
    for t in prev:
        spans.setdefault(t, []).append((open_since.pop(t), end))
    print(f"Universe: {cands[-1]}: {len(prev)} current members, {len(spans)} tickers in the index at some point since "
          f"{hist['date'].min():%Y-%m-%d}")
    return spans


def member(spans: dict, sym: str, d: pd.Timestamp) -> bool:
    return any(a <= d < b for a, b in spans.get(sym, []))


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_daily(symbols: list[str], start: str, end: str, cache: Path) -> dict[str, pd.DataFrame]:
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    cli = StockHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    out = {}
    syms = sorted(set(symbols))
    for k in range(0, len(syms), 50):
        chunk = [s.replace("-", ".") for s in syms[k:k + 50]]
        try:
            df = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day,
                                                     start=pd.Timestamp(start).to_pydatetime(),
                                                     end=pd.Timestamp(end).to_pydatetime(),
                                                     adjustment=Adjustment.ALL, feed=DataFeed.SIP)).df
        except Exception as exc:
            print(f"bars {chunk[0]}..: {type(exc).__name__}: {str(exc)[:100]}")
            continue
        if df is None or df.empty:
            continue
        for s in df.index.get_level_values(0).unique():
            d = df.xs(s, level=0).rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]].astype(float)
            d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York").tz_localize(None).normalize()
            out[s.replace(".", "-")] = d
    cache.write_bytes(pickle.dumps(out))
    return out


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


def trades_for(sym: str, df: pd.DataFrame, spy: pd.DataFrame, cfg: dict, random_seed: int | None = None) -> list[dict]:
    if len(df) < 260:
        return []
    ind = bot.add_indicators(df, cfg)
    bench = bot.align_benchmark(ind, spy)
    sigs = bot.compute_signals(ind, bench, cfg, sym, "SPY")
    key = ("breakout", "long")
    if key not in sigs:
        return []
    frame, extra = sigs[key]
    min_score = bot.min_score_for("breakout", cfg, "paper")
    if random_seed is not None:
        # same number of entries as the real signals, on random days, same exits
        n_real = int((frame["trig"].astype(bool) & (frame["score"] >= min_score)).sum())
        rng = np.random.default_rng(random_seed * 100_003 + sum(map(ord, sym)))
        ok = np.where(ind["sma200"].notna().to_numpy())[0] if "sma200" in ind else np.arange(200, len(ind))
        frame = frame.copy()
        frame["trig"] = False
        frame["score"] = 100
        if n_real and len(ok):
            pick = rng.choice(ok, size=min(n_real, len(ok)), replace=False)
            frame.iloc[pick, frame.columns.get_loc("trig")] = True
    trades = bot.run_backtest_symbol(ind, {key: (frame, extra)}, cfg, sym, "1d", 0.0, min_score)
    dv = (ind["Close"] * ind["Volume"]).rolling(20).mean()
    out = []
    for t in trades:
        if not t.entry_date or t.exit_reason == "still open at the end of the data" or not t.risk_per_unit:
            continue
        sd = pd.Timestamp(t.signal_date)
        if sd not in ind.index:
            continue
        out.append({"sym": sym, "signal": sd, "entry_date": pd.Timestamp(t.entry_date), "exit_date": pd.Timestamp(t.exit_date),
                    "entry": t.entry_price, "exit": t.exit_price, "risk": t.risk_per_unit, "score": t.score,
                    "bars": t.bars_held, "price_ok": float(ind.at[sd, "Close"]) >= 5,
                    "liq_ok": float(dv.get(sd, 0) or 0) >= 10e6, "reason": t.exit_reason})
    return out


def r_at(t: pd.DataFrame, c: float) -> pd.Series:
    return (t["exit"] * (1 - c) - t["entry"] * (1 + c)) / t["risk"]


def stats(r: pd.Series, bars: pd.Series | None = None) -> dict:
    r = r.dropna()
    if not len(r):
        return {"n": 0}
    w, lo = r[r > 0], r[r <= 0]
    streak = best = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return {"n": int(len(r)), "win": float(len(w) / len(r)), "avg_win": float(w.mean()) if len(w) else 0.0,
            "avg_loss": float(lo.mean()) if len(lo) else 0.0, "pf": float(w.sum() / -lo.sum()) if lo.sum() < 0 else float("inf"),
            "exp": float(r.mean()), "t": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 1 else 0.0,
            "longest_losing_run": int(best), "avg_bars": float(bars.mean()) if bars is not None and len(bars) else None}


def line(name: str, s: dict) -> str:
    if not s.get("n"):
        return f"{name:<40} no trades"
    return (f"{name:<40} {s['n']:>5} tr  {s['win']:>4.0%} won  avg win {s['avg_win']:+5.2f}R  avg loss {s['avg_loss']:+5.2f}R  "
            f"PF {s['pf']:4.2f}  exp {s['exp']:+.3f}R  (t {s['t']:+.1f})  worst run {s['longest_losing_run']}"
            + (f"  hold {s['avg_bars']:.0f}d" if s.get("avg_bars") else ""))


def portfolio(t: pd.DataFrame, c: float, start_gbp: float = 1000.0, risk_pct: float = 2.0, max_open: int = 10,
              max_pos_pct: float = 35.0) -> dict:
    """Cash-limited £1,000 account: each day's signals ranked by score, 2% risk, at most 10 open, never more than the
    free cash. Returns daily P&L (on exit days), Sharpe, Sortino, worst fall."""
    t = t.sort_values(["entry_date", "score"], ascending=[True, False])
    eq, peak, max_dd = start_gbp, start_gbp, 0.0
    open_: list = []
    pnl_by_day: dict = {}
    taken = 0
    for _, x in t.iterrows():
        still = []
        for o in open_:
            if o["exit_date"] <= x["entry_date"]:
                eq += o["pnl"]
                pnl_by_day[o["exit_date"]] = pnl_by_day.get(o["exit_date"], 0.0) + o["pnl"]
                peak = max(peak, eq)
                max_dd = max(max_dd, 1 - eq / peak)
            else:
                still.append(o)
        open_ = still
        if len(open_) >= max_open or eq <= 0:
            continue
        frac = x["risk"] / x["entry"]
        want = eq * risk_pct / 100 / frac
        free = eq - sum(o["value"] for o in open_)
        value = min(want, eq * max_pos_pct / 100, free)
        if value < 25:
            continue
        units = value / x["entry"]
        pnl = units * (x["exit"] * (1 - c) - x["entry"] * (1 + c))
        open_.append({"exit_date": x["exit_date"], "pnl": pnl, "value": value})
        taken += 1
    for o in open_:
        eq += o["pnl"]
        pnl_by_day[o["exit_date"]] = pnl_by_day.get(o["exit_date"], 0.0) + o["pnl"]
        peak = max(peak, eq)
        max_dd = max(max_dd, 1 - eq / peak)
    days = pd.bdate_range(t["entry_date"].min(), t["exit_date"].max())
    daily = pd.Series(pnl_by_day).reindex(days, fill_value=0.0)
    equity = start_gbp + daily.cumsum()
    ret = daily / equity.shift(1).fillna(start_gbp)
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0.0
    down = ret[ret < 0]
    sortino = float(ret.mean() / down.std() * np.sqrt(252)) if len(down) > 1 and down.std() > 0 else 0.0
    monthly = daily.resample("ME").sum()
    years = max(0.5, len(days) / 252)
    return {"taken": taken, "final": float(eq), "cagr": float((eq / start_gbp) ** (1 / years) - 1) if eq > 0 else -1.0,
            "max_dd": float(max_dd), "sharpe": sharpe, "sortino": sortino, "avg_day": float(daily.mean()),
            "losing_months": int((monthly < 0).sum()), "months": int(len(monthly))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-11-10")
    ap.add_argument("--cache", default="/tmp/breakout_cache")
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    cfg = bot.load_config(str(ROOT / "config.toml"))
    spans = sp500_membership()
    data = load_daily(list(spans) + ["SPY"], a.start, a.end, cache / "daily.pkl")
    spy = data.get("SPY")
    if spy is None:
        print("No SPY data: stop.")
        return 1
    since = pd.Timestamp(a.start)
    relevant = [s for s, sp in spans.items() if any(b > since for _, b in sp)]
    removed = [s for s in relevant if all(b < pd.Timestamp("2100-01-01") for _, b in spans[s])]
    have = [s for s in relevant if s in data]
    print(f"Tickers in the index at some point since {a.start}: {len(relevant)}; with price data: {len(have)}; "
          f"removed since then: {len(removed)}, of which with data: {len([s for s in removed if s in data])} "
          "(the rest is residual survivorship bias)")
    rows, null_rows = [], []
    for s in have:
        rows += trades_for(s, data[s], spy, cfg)
        for seed in (1, 2, 3):
            null_rows += [dict(x, seed=seed) for x in trades_for(s, data[s], spy, cfg, random_seed=seed)]
    t = pd.DataFrame(rows)
    nl = pd.DataFrame(null_rows)
    if t.empty:
        print("No trades.")
        return 1

    def eligible(df):
        ok = df.apply(lambda x: member(spans, x["sym"], x["signal"]), axis=1) & df["price_ok"] & df["liq_ok"]
        return df[ok & (df["signal"] >= since + pd.Timedelta(days=300))].copy()

    t, nl = eligible(t), eligible(nl)
    t["year"] = t["signal"].dt.year
    period = np.where(t["signal"] <= DEV_END, "development 2016-21", np.where(t["signal"] <= VAL_END, "validation 2022-23", "HOLDOUT 2024-26"))
    t["period"] = period
    nl["period"] = np.where(nl["signal"] <= DEV_END, "development 2016-21", np.where(nl["signal"] <= VAL_END, "validation 2022-23", "HOLDOUT 2024-26"))
    spy_ind = spy.copy()
    spy_ind["sma200"] = spy_ind["Close"].rolling(200).mean()
    spy_ind["vol20"] = spy_ind["Close"].pct_change().rolling(20).std() * np.sqrt(252)
    reg = spy_ind.reindex(t["signal"].values)
    t["regime"] = np.where(reg["Close"].values > reg["sma200"].values, "SPY above 200-day", "SPY below 200-day")
    t["vol"] = np.where(reg["vol20"].values > spy_ind["vol20"].median(), "high volatility", "low volatility")

    out = {}
    print("\n==== STUDY 2 RESULTS (rules unchanged; point-in-time S&P 500) ====")
    for c in COSTS:
        print(f"\n-- cost {c * 100:.2f}% per side --")
        r = r_at(t, c)
        print(line("ALL", stats(r, t["bars"])))
        for p in ("development 2016-21", "validation 2022-23", "HOLDOUT 2024-26"):
            m = t["period"] == p
            print(line(f"  {p}", stats(r[m], t.loc[m, "bars"])))
            out[f"{p}|{c}"] = stats(r[m])
    c = MAIN_COST
    r = r_at(t, c)
    t["R"] = r
    h = t[t["period"] == "HOLDOUT 2024-26"]
    print(f"\n-- at {c * 100:.2f}% per side --")
    print("By year:")
    for y, g in t.groupby("year"):
        print(line(f"  {y}", stats(g["R"])))
    print("By market regime (all periods):")
    for col in ("regime", "vol"):
        for k, g in t.groupby(col):
            print(line(f"  {k}", stats(g["R"])))
    top10 = h.nlargest(10, "R").index
    best_syms = h.groupby("sym")["R"].sum().nlargest(10).index
    print("Holdout robustness:")
    print(line("  holdout", stats(h["R"])))
    print(line("  holdout without its 10 best trades", stats(h.drop(top10)["R"])))
    print(line("  holdout without its 10 best shares", stats(h[~h["sym"].isin(best_syms)]["R"])))
    print(f"  (10 best holdout shares: {', '.join(best_syms)})")
    print("Random-entry null (same exits, same shares, same counts, 3 seeds):")
    nl["R"] = r_at(nl, c)
    for p, g in nl.groupby("period"):
        print(line(f"  random entries, {p}", stats(g["R"])))
    hn = nl[nl["period"] == "HOLDOUT 2024-26"]["R"].mean()
    print("Portfolio, £1,000 cash-limited, 2% risk, max 10 open:")
    pf_all = portfolio(t, c)
    pf_h = portfolio(h, c)
    for name, p in (("all periods", pf_all), ("holdout only", pf_h)):
        print(f"  {name}: {p['taken']} trades taken, £1,000 -> £{p['final']:,.0f} ({p['cagr']:+.1%} a year), worst fall "
              f"{p['max_dd']:.0%}, Sharpe {p['sharpe']:.2f}, Sortino {p['sortino']:.2f}, average £{p['avg_day']:+.2f} a day, "
              f"{p['losing_months']} losing months of {p['months']}")
    spy_h = spy[spy.index >= "2024-01-01"]["Close"]
    print(f"  benchmark: SPY buy-and-hold over the holdout {spy_h.iloc[-1] / spy_h.iloc[0] - 1:+.1%}")

    # the pre-registered verdict
    sh = stats(h["R"])
    checks = [
        ("1. at least 150 holdout trades", sh["n"] >= 150, sh["n"]),
        ("2. holdout expectancy > +0.15R", sh["exp"] > 0.15, round(sh["exp"], 3)),
        ("3. holdout profit factor > 1.3", sh["pf"] > 1.3, round(sh["pf"], 2)),
        ("4. > 0 without the 10 best trades", stats(h.drop(top10)["R"])["exp"] > 0, round(stats(h.drop(top10)["R"])["exp"], 3)),
        ("5. > 0 without the 10 best shares", stats(h[~h["sym"].isin(best_syms)]["R"])["exp"] > 0,
         round(stats(h[~h["sym"].isin(best_syms)]["R"])["exp"], 3)),
        ("6. beats random entries by >= 0.10R", sh["exp"] - hn >= 0.10, round(sh["exp"] - hn, 3)),
        ("7. positive in development AND validation", out[f"development 2016-21|{c}"]["exp"] > 0 and out[f"validation 2022-23|{c}"]["exp"] > 0,
         (round(out[f"development 2016-21|{c}"]["exp"], 3), round(out[f"validation 2022-23|{c}"]["exp"], 3))),
        ("8. £1,000 holdout portfolio worst fall < 35%", pf_h["max_dd"] < 0.35, f"{pf_h['max_dd']:.0%}"),
    ]
    print("\n==== PRE-REGISTERED VERDICT (PROTOCOL.md) ====")
    for name, ok, val in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {val}")
    print("  OVERALL: " + ("PASS" if all(ok for _, ok, _ in checks) else "FAIL"))
    t.to_csv("research_breakout_trades.csv", index=False)
    Path("research_breakout_summary.json").write_text(json.dumps({"checks": [(n, bool(o), str(v)) for n, o, v in checks],
                                                                  "portfolio_holdout": pf_h, "portfolio_all": pf_all}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
