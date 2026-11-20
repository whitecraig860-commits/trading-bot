"""
Study 1 (see PROTOCOL.md): does the intraday trend signal predict the SHARE, before any option is involved?

Same signal and exits as the trend worker (trend_snapshot.py = trendworker.py from PR #19, unchanged), traded on the
share with a small realistic cost. Plus forward returns after each signal vs two baselines:
  - "trend only": every 5-minute bar where the trend filter alone says up (or down), same direction
  - "all bars": every 5-minute bar, in the direction of the day so far
If the share result is negative too, the problem is the signal, not the options.

  python research/trend_signal_check.py --symbols QQQ,SPY,IWM,GLD,NVDA,TSLA --start 2024-03-01 --end 2026-11-10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optionbt  # noqa: E402
import scalper  # noqa: E402
import trend_snapshot as tw  # noqa: E402

COST = {"NVDA": 0.0005, "TSLA": 0.0005}  # per side; ETFs 0.0002


def run(sym: str, bars: pd.DataFrame, cfg: dict) -> tuple[list[dict], list[dict]]:
    cfg = {**tw.DEFAULTS, **cfg}
    cost = COST.get(sym, 0.0002)
    rth = bars.between_time("09:30", "15:59")
    trades, fwd = [], []
    for day in sorted(set(rth.index.normalize())):
        d1 = rth[(rth.index >= day) & (rth.index < day + pd.Timedelta(days=1))]
        if len(d1) < 300:
            continue
        ind = scalper.session_indicators(scalper.to_bars(d1, 5), {**scalper.DEFAULTS, "signal_minutes": 5})
        close = d1["Close"]
        open_t, last_exit = None, None
        n_tr = n_loss = 0
        for i in range(12, len(ind)):
            now = ind.index[i] + pd.Timedelta(minutes=5)
            # forward returns for the baselines (every bar) and for signals
            st = tw.trend_state(ind, i, cfg)
            day_dir = 1 if float(ind["Close"].iloc[i]) >= float(ind["Open"].iloc[0]) else -1
            fut = close[close.index >= now]
            if len(fut) > 60:
                p0 = float(d1["Open"].get(now, fut.iloc[0]))
                r30 = float(fut.iloc[29]) / p0 - 1
                r60 = float(fut.iloc[59]) / p0 - 1
                sig = tw.signal(ind, i, cfg)
                fwd.append({"day": day.strftime("%Y-%m-%d"), "trend": st, "day_dir": day_dir, "r30": r30, "r60": r60,
                            "sig": 0 if not sig else (1 if sig[0] == "call" else -1)})
            # the trade simulation on the share
            if open_t is None and n_tr < cfg["tw_max_trades"] and n_loss < cfg["tw_max_losses"] and \
                    (last_exit is None or (now - last_exit).total_seconds() / 60 >= cfg["tw_cooldown_minutes"]):
                sig = tw.signal(ind, i, cfg)
                if sig and now in d1.index:
                    side, stop, why = sig
                    entry = float(d1.at[now, "Open"])
                    want = 1 if side == "call" else -1
                    risk = abs(float(ind["Close"].iloc[i]) - stop)
                    open_t = {"day": day.strftime("%Y-%m-%d"), "want": want, "entry": entry, "u_ref": float(ind["Close"].iloc[i]),
                              "risk": risk, "best": 0.0, "t": now}
                    n_tr += 1
            if open_t is None:
                continue
            for m in d1.index[(d1.index >= now) & (d1.index < now + pd.Timedelta(minutes=5))]:
                t = open_t
                S = float(d1.at[m, "Close"])
                u_r = (S - t["u_ref"]) * t["want"] / t["risk"]
                t["best"] = max(t["best"], u_r)
                fl = tw.floor_r(t["best"], cfg)
                t_now = m + pd.Timedelta(minutes=1)
                reason = None
                if t_now.hour * 60 + t_now.minute >= 15 * 60 + 50:
                    reason = "end of day"
                elif u_r >= cfg["tw_target_r"]:
                    reason = "target"
                elif u_r <= -1:
                    reason = "stop"
                elif fl is not None and u_r <= fl:
                    reason = "trail/break-even"
                if reason:
                    gross = (S - t["entry"]) * t["want"]
                    net = gross - cost * (S + t["entry"])
                    trades.append({"day": t["day"], "R": net / t["risk"], "reason": reason, "mins": (t_now - t["t"]).total_seconds() / 60})
                    open_t, last_exit = None, t_now
                    if net < 0:
                        n_loss += 1
                    break
    return trades, fwd


def summary(sym: str, t: pd.DataFrame, f: pd.DataFrame) -> None:
    if t.empty:
        print(f"{sym}: no trades")
        return
    w, lo = t[t.R > 0], t[t.R <= 0]
    pf = w.R.sum() / -lo.R.sum() if lo.R.sum() < 0 else float("inf")
    print(f"{sym}: SHARE trades {len(t)}, {len(w) / len(t):.0%} won, avg win {w.R.mean():+.2f}R, avg loss {lo.R.mean():+.2f}R, "
          f"expectancy {t.R.mean():+.3f}R (t = {t.R.mean() / (t.R.std(ddof=1) / np.sqrt(len(t))):+.2f}), profit factor {pf:.2f}")
    for per, g in (("2024-25", t[t.day < "2026-01-01"]), ("2026", t[t.day >= "2026-01-01"])):
        if len(g):
            print(f"    {per}: {len(g)} trades, expectancy {g.R.mean():+.3f}R")
    sig = f[f.sig != 0]
    tr = f[f.trend != 0]
    for h in ("r30", "r60"):
        s_ret = (sig[h] * sig.sig).mean() * 1e4
        t_ret = (tr[h] * tr.trend).mean() * 1e4
        a_ret = (f[h] * f.day_dir).mean() * 1e4
        print(f"    {h[1:]}-min forward return in the signal's direction: signals {s_ret:+.1f} bp ({len(sig)}), "
              f"trend filter alone {t_ret:+.1f} bp ({len(tr)}), any bar with the day's direction {a_ret:+.1f} bp ({len(f)})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="QQQ,SPY,IWM,GLD,NVDA,TSLA")
    ap.add_argument("--start", default="2024-03-01")
    ap.add_argument("--end", default="2026-11-10")
    ap.add_argument("--cache", default="/tmp/tw_cache")
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    cfg = {"tw_min_day_move_pct": 0.6}
    allt = []
    for sym in a.symbols.split(","):
        bars = optionbt.load_bars([sym], a.start, a.end, cache / f"{sym}.pkl")[sym]
        t, f = run(sym, bars, cfg)
        summary(sym, pd.DataFrame(t), pd.DataFrame(f))
        allt += [dict(x, sym=sym) for x in t]
    t = pd.DataFrame(allt)
    if len(t):
        print(f"\nALL SIX on the share: {len(t)} trades, expectancy {t.R.mean():+.3f}R, "
              f"t = {t.R.mean() / (t.R.std(ddof=1) / np.sqrt(len(t))):+.2f}, won {(t.R > 0).mean():.0%}")
        t.to_csv("research_trend_share_trades.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
