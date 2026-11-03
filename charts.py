"""
Chart pictures for Telegram: what the market looked like when the bot decided to trade.

  daily_chart(...)     the last ~6 months of daily candles with the 20/50/200-day averages and the
                       entry, stop and target lines (used by the nightly scan's alerts and closed trades)
  intraday_chart(...)  today's 5-minute candles with VWAP, its bands and the opening range, plus the
                       entry, stop and target lines (used by the pulse's signals and the scalper)

Both return PNG bytes, or None if matplotlib isn't installed or anything goes wrong: a missing picture
must never stop an alert from being sent.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

UP, DOWN, BG, GRID, TEXT = "#26a69a", "#ef5350", "#131722", "#2a2e39", "#d1d4dc"


def _candles(ax, df: pd.DataFrame) -> None:
    x = np.arange(len(df))
    o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    colour = np.where(c >= o, UP, DOWN)
    ax.vlines(x, l, h, colors=colour, linewidth=0.8)
    body_lo, body_hi = np.minimum(o, c), np.maximum(o, c)
    ax.bar(x, np.maximum(body_hi - body_lo, (h - l).max() * 0.002), bottom=body_lo, color=colour, width=0.7, linewidth=0)


def _style(fig, ax, title: str) -> None:
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.grid(color=GRID, linewidth=0.5)
    ax.set_title(title, color=TEXT, fontsize=11, loc="left")
    ax.yaxis.tick_right()


def _levels(ax, n: int, entry=None, stop=None, target=None, exit_=None) -> None:
    for y, label, col, style in ((entry, "entry", "#2962ff", "-"), (stop, "stop", DOWN, "--"),
                                 (target, "target", UP, "--"), (exit_, "exit", "#ff9800", "-")):
        if y is not None and np.isfinite(y):
            ax.axhline(y, color=col, linestyle=style, linewidth=1.1)
            ax.text(n + 0.5, y, f"{label} {y:,.2f}", color=col, fontsize=8, va="center", ha="left",
                    bbox={"facecolor": BG, "edgecolor": "none", "pad": 1})
    ax.set_xlim(-1, n + max(14, n * 0.16))  # room on the right for the labels


def _xlabels(ax, idx: pd.DatetimeIndex, fmt: str, every: int) -> None:
    ticks = list(range(0, len(idx), max(1, every)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([idx[i].strftime(fmt) for i in ticks], rotation=0)


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
    import matplotlib.pyplot as plt

    plt.close(fig)
    return buf.getvalue()


def daily_chart(ind: pd.DataFrame, title: str, entry=None, stop=None, target=None, exit_=None,
                bars: int = 130, mark_from: str | None = None) -> bytes | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = ind.tail(bars)
        fig, ax = plt.subplots(figsize=(9, 4.8))
        _candles(ax, df)
        x = np.arange(len(df))
        for col, name, colour in (("ema20", "20-day", "#f7c948"), ("sma50", "50-day", "#ab47bc"), ("sma200", "200-day", "#90a4ae")):
            if col in df and df[col].notna().any():
                ax.plot(x, df[col].to_numpy(float), color=colour, linewidth=1, label=name)
        if mark_from:
            pos = int(np.searchsorted(df.index.to_numpy(), np.datetime64(pd.Timestamp(mark_from))))
            if 0 <= pos < len(df):
                ax.axvspan(pos - 0.5, len(df) - 0.5, color="#2962ff", alpha=0.08)
        _levels(ax, len(df), entry, stop, target, exit_)
        _style(fig, ax, title)
        _xlabels(ax, df.index, "%d %b", len(df) // 6)
        ax.legend(loc="upper left", fontsize=7, facecolor=BG, labelcolor=TEXT, edgecolor=GRID)
        return _png(fig)
    except Exception:
        return None


def intraday_chart(ind: pd.DataFrame, title: str, entry=None, stop=None, target=None, exit_=None,
                   sessions: int = 1) -> bytes | None:
    """ind: 5-minute bars from intraday.add_intraday (or plain OHLC bars with an optional 'vwap' column)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = ind
        if "session" in ind:
            keep = list(dict.fromkeys(ind["session"]))[-sessions:]
            df = ind[ind["session"].isin(keep)]
        df = df.tail(160)
        fig, ax = plt.subplots(figsize=(9, 4.8))
        _candles(ax, df)
        x = np.arange(len(df))
        if "vwap" in df:
            ax.plot(x, df["vwap"].to_numpy(float), color="#f7c948", linewidth=1.2, label="VWAP")
            if "vwap_sd" in df:
                for k in (-2, 2):
                    ax.plot(x, (df["vwap"] + k * df["vwap_sd"]).to_numpy(float), color="#f7c948", linewidth=0.6,
                            linestyle=":", label="VWAP bands" if k == 2 else None)
        if "ema21" in df:
            ax.plot(x, df["ema21"].to_numpy(float), color="#ab47bc", linewidth=0.9, label="21 EMA")
        for col, colour in (("or_high", "#90a4ae"), ("or_low", "#90a4ae")):
            if col in df and df[col].notna().any():
                ax.plot(x, df[col].to_numpy(float), color=colour, linewidth=0.8, linestyle="-.",
                        label="opening range" if col == "or_high" else None)
        _levels(ax, len(df), entry, stop, target, exit_)
        _style(fig, ax, title)
        _xlabels(ax, df.index, "%H:%M", len(df) // 7)
        ax.legend(loc="upper left", fontsize=7, facecolor=BG, labelcolor=TEXT, edgecolor=GRID)
        return _png(fig)
    except Exception:
        return None
