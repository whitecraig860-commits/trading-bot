"""
Is the option model right? Checks optionbt.py's made-up option prices against REAL ones
=======================================================================================
optionbt.py prices the options with a formula (Black-Scholes at yesterday's VIX). This takes every trade it
makes, works out the real contract (e.g. SPY251107C00680000), downloads that contract's real 1-minute prices from
Alpaca (actual trades on the options exchanges, kept since early 2024), and compares:

  - the model's price vs the real price at the entry minute and the exit minute
  - each trade's profit with model prices vs with real prices (same entry and exit times, same spread charged)

Real 1-minute option bars are trade prices, not bid/ask quotes (Alpaca keeps no historical option quotes), so the
same spread assumption is used on both sides of the comparison. A minute with no trade in that contract uses the
last trade before it, up to 5 minutes old; trades with no real price near entry or exit are counted, not guessed.

  python optioncheck.py --start 2025-01-02 --end 2026-11-06      (needs ALPACA_KEY / ALPACA_SECRET)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

import optionbt
import scalper

NY = "America/New_York"


def occ(sym: str, expiry: pd.Timestamp, side: str, strike: float) -> str:
    return f"{sym}{expiry:%y%m%d}{'C' if side == 'call' else 'P'}{int(round(strike * 1000)):08d}"


def real_bars(cli, contract: str, day: pd.Timestamp) -> pd.DataFrame:
    from alpaca.data.requests import OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = OptionBarsRequest(symbol_or_symbols=contract, timeframe=TimeFrame.Minute,
                            start=(day + pd.Timedelta(hours=9, minutes=30)).tz_convert("UTC").to_pydatetime(),
                            end=(day + pd.Timedelta(hours=16)).tz_convert("UTC").to_pydatetime())
    df = cli.get_option_bars(req).df
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.xs(contract, level=0) if isinstance(df.index, pd.MultiIndex) else df
    d.index = pd.DatetimeIndex(d.index).tz_convert(NY)
    return d


def price_at(bars: pd.DataFrame, t: pd.Timestamp) -> float | None:
    """Last real trade price at or before minute t (bar closes), no older than 5 minutes."""
    if bars.empty:
        return None
    b = bars[(bars.index <= t) & (bars.index > t - pd.Timedelta(minutes=6))]
    return float(b["close"].iloc[-1]) if len(b) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-01-02")
    ap.add_argument("--end", default=pd.Timestamp.now(tz=NY).strftime("%Y-%m-%d"))
    ap.add_argument("--cache", default="/tmp/optionbt_bars.pkl")
    a = ap.parse_args()
    from alpaca.data.historical import OptionHistoricalDataClient

    cli = OptionHistoricalDataClient(os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"])
    cfg, _ = scalper.load_cfg(str(Path(__file__).with_name("config.toml")))
    bars = optionbt.load_bars(cfg["symbols"], a.start, a.end, Path(a.cache))
    vol = optionbt.load_vol(a.start, a.end)
    trades = optionbt.run(("NOW", cfg, bars, vol, 1.0))
    days = sorted({d for s in bars for d in bars[s].index.normalize()})
    rows, missing = [], 0
    for t in trades:
        day = pd.Timestamp(t["day"], tz=NY)
        later = [d for d in days if d > day]
        dte = int(t.get("dte", 0))
        expiry = day if dte == 0 else (later[dte - 1] if len(later) >= dte else None)
        if expiry is None:
            missing += 1
            continue
        con = occ(t["sym"], expiry, t["side"], t["K"])
        try:
            rb = real_bars(cli, con, day)
        except Exception as exc:
            print(f"{con}: {type(exc).__name__}: {str(exc)[:100]}")
            rb = pd.DataFrame()
        e_real = price_at(rb, t["t"] - pd.Timedelta(minutes=1))
        x_real = price_at(rb, t["exit_t"] - pd.Timedelta(minutes=1))
        if e_real is None or x_real is None:
            missing += 1
            continue
        # the model's mid prices at those minutes (undo the spread and fee assumptions it added)
        e_mid, x_mid = t["mid0"], t["mid1"]
        half = lambda p: max(0.02, 0.02 * p) / 2  # noqa: E731
        real_fill = e_real + 0.25 * half(e_real) + 0.004
        real_exit = max(0.01, x_real - half(x_real))
        real_pnl = (real_exit - real_fill) * 100 * t["qty"] - 0.06 * t["qty"]
        rows.append({"day": t["day"], "sym": t["sym"], "side": t["side"], "contract": con, "qty": t["qty"],
                     "model_entry": e_mid, "real_entry": e_real, "model_exit": x_mid, "real_exit": x_real,
                     "model_pnl": t["pnl"], "real_pnl": real_pnl, "reason": t["reason"]})
    df = pd.DataFrame(rows)
    gbp = 0.75
    print(f"\n{len(trades)} backtest trades; {len(df)} matched to real option prices, {missing} without a real price "
          "near entry or exit (left out).\n")
    if df.empty:
        return 1
    ee = (df.model_entry / df.real_entry - 1) * 100
    xe = (df.model_exit / df.real_exit - 1) * 100
    print(f"Entry price: model vs real, median {ee.median():+.1f}%, middle half {ee.quantile(.25):+.1f}% to {ee.quantile(.75):+.1f}%")
    print(f"Exit price:  model vs real, median {xe.median():+.1f}%, middle half {xe.quantile(.25):+.1f}% to {xe.quantile(.75):+.1f}%")
    for name, col in (("MODEL prices", "model_pnl"), ("REAL prices ", "real_pnl")):
        p = df[col]
        w, lo = p[p > 0], p[p <= 0]
        pf = w.sum() / -lo.sum() if lo.sum() < 0 else float("inf")
        print(f"{name}: {len(p)} trades, {len(w) / len(p):.0%} won, avg win £{w.mean() * gbp:.1f}, "
              f"avg loss £{lo.mean() * gbp:.1f}, profit factor {pf:.2f}, total £{p.sum() * gbp:,.0f}")
    print(f"\nSame trade, real minus model: median £{(df.real_pnl - df.model_pnl).median() * gbp:+.1f}, "
          f"total £{(df.real_pnl - df.model_pnl).sum() * gbp:+,.0f}")
    print("\nBy symbol (real prices):")
    for s, g in df.groupby("sym"):
        print(f"  {s}: {len(g)} trades, total £{g.real_pnl.sum() * gbp:,.0f} (model £{g.model_pnl.sum() * gbp:,.0f})")
    df.to_csv("optioncheck_trades.csv", index=False)
    print("\nVerdict: " + ("the model is close enough to trust (entry and exit within about 3%)."
                           if abs(ee.median()) <= 3 and abs(xe.median()) <= 3 else
                           "the model's prices are off by more than 3%: trust the REAL-price line, not the model."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
