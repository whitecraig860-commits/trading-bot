#!/usr/bin/env python3
"""
Setup Scanner Bot
=================
Checks your watchlist, scores trading setups from 0 to 100, messages your
phone on Telegram when a strong one lines up, and paper-trades every strong
setup automatically so you can see whether it works before risking money.

  python bot.py scan             check the watchlist and today's movers (alerts + paper trades)
  python bot.py watch            quick check during market hours: big moves, breakouts, news
  python bot.py watch --every 10 keep checking every 10 minutes (leave it running)
  python bot.py movers           today's most active, biggest risers and fallers, checked
  python bot.py volatile         the most volatile markets right now
  python bot.py news             market headlines and big events coming up (--symbols for one)
  python bot.py events           big scheduled events: rate decisions, inflation, jobs
  python bot.py timemachine --symbols AAPL   replay a trade 10,000 times from its own bars
  python bot.py backtest         test the setups on years of past prices
  python bot.py status           show the paper-trading account
  python bot.py leaders          rank the watchlist by momentum
  python bot.py test-telegram    send a test message to your phone

scan and watch send to Telegram; the other commands print here unless you add
--telegram. Add --no-telegram to any command to print instead of sending.

Education and tooling only. This is not financial advice, and any setup can lose.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - older Pythons
    import tomli as tomllib  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"

DAILY_OR_LONGER = {"1d", "5d", "1wk", "1mo", "3mo"}
INTRADAY = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h"}

SETUP_TITLES = {
    "breakout": "Trend breakout",
    "pullback": "Pullback in a trend",
}

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

DEFAULTS: dict = {
    "account": {
        "size": 5000.0,
        "currency": "GBP",
        "risk_per_trade_pct": 1.0,
        "max_position_pct": 25.0,
        "fractional_units": True,
    },
    "scan": {
        "interval": "1d",
        "history": "2y",
        "alert_min_score": 70,
        "strong_score": 80,
        "allow_shorts": False,
        "earnings_warning_days": 7,
        "daily_summary": True,
    },
    "setups": {
        "breakout_lookback": 55,
        "breakout_exit_lookback": 20,
        "breakout_stop_atr": 2.0,
        "pullback_rsi2_entry": 10.0,
        "pullback_stop_atr": 2.5,
        "pullback_max_hold_bars": 10,
        "target_r": 2.0,
        "volume_surge": 1.5,
        "adx_trending": 20.0,
        "squeeze_pctile": 0.25,
        "overextended_atr": 3.0,
    },
    "paper": {
        "enabled": True,
        "min_score": 70,
        "max_open_positions": 8,
    },
    "backtest": {
        "history": "10y",
        "cost_per_side_pct": 0.1,
        "min_score": 0,
        "in_sample_share": 0.7,
    },
    "telegram": {"token": "", "chat_id": ""},
    "leaders": {"top_n": 5, "send_on_weekday": 0},
    "movers": {
        "enabled": True,
        "us_lists": ["most_actives", "day_gainers", "day_losers"],
        "uk": True,
        "per_list": 10,
        "min_price_usd": 5.0,
        "us_benchmark": "SPY",
        "uk_benchmark": "^FTSE",
    },
    "news": {
        "enabled": True,
        "headlines": 3,
        "max_age_hours": 72,
        "event_warning_days": 2,
        "yahoo_calendar": True,
        "timezone": "Europe/London",
        "crypto_news": True,
        "crypto_symbols": ["BTC-USD", "ETH-USD", "SOL-USD"],
        "events": [],
    },
    "watch": {
        "big_move_pct": 3.0,
        "big_move_atr": 2.5,
        "breakouts_in_progress": True,
        "stop_warnings": True,
        "held_news": True,
    },
    "history": {"enabled": True, "period": "10y", "min_trades": 5},
    "timemachine": {"enabled": True, "replays": 10000, "horizon_bars": 60, "lookback_bars": 504, "seed": 19},
    "risk": {
        "daily_loss_limit_pct": 2.0,
        "weekly_loss_limit_pct": 5.0,
        "max_open_risk_pct": 5.0,
        "max_new_trades_per_day": 3,
        "min_replay_avg_r": -1.0,
    },
    "groups": {
        "us": {"benchmark": "SPY", "symbols": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]},
    },
}


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if k == "groups":
            out[k] = v  # your watchlist replaces the default one
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str) -> dict:
    p = Path(path)
    cfg = DEFAULTS
    if p.exists():
        with open(p, "rb") as fh:
            cfg = deep_merge(DEFAULTS, tomllib.load(fh))
    else:
        print(f"Note: {p} not found, using built-in defaults.")
    # Secrets can come from environment variables (used by GitHub Actions).
    tg = cfg.setdefault("telegram", {})
    tg["token"] = os.environ.get("TELEGRAM_TOKEN") or tg.get("token", "")
    tg["chat_id"] = os.environ.get("TELEGRAM_CHAT_ID") or str(tg.get("chat_id", ""))
    return cfg


def iter_watchlist(cfg: dict, args) -> list[tuple[str, list[str]]]:
    """Returns [(benchmark, [symbols])]."""
    if getattr(args, "symbols", None):
        syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
        return [(getattr(args, "benchmark", "") or "", syms)]
    out = []
    for _, g in cfg.get("groups", {}).items():
        out.append((g.get("benchmark", "") or "", list(g.get("symbols", []))))
    return out


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

_DATA_CACHE: dict = {}
_FX_CACHE: dict = {}
OFFLINE = False  # True when prices come from CSV files: no currency or earnings look-ups


def safe_name(symbol: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in symbol)


def guess_currency(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith(".L"):
        return "GBp"  # London prices on Yahoo are in pence
    if s.endswith("=X") and len(s) >= 8:
        return s[3:6]  # GBPUSD=X is priced in USD
    if "-" in s:
        q = s.rsplit("-", 1)[1]
        if q in {"USD", "GBP", "EUR", "USDT", "USDC"}:
            return "USD" if q in {"USDT", "USDC"} else q
    if s in {"^FTSE", "^FTMC"}:
        return "GBP"
    return "USD"


def period_to_bars(period: str, per_year: int) -> int:
    p = period.strip().lower()
    if p == "max":
        return per_year * 30
    num = float("".join(ch for ch in p if ch.isdigit() or ch == ".") or 1)
    if p.endswith("y"):
        return int(num * per_year)
    if p.endswith("mo"):
        return int(num * per_year / 12)
    if p.endswith("d"):
        return int(num)
    return per_year * 2


def cap_intraday_period(period: str, interval: str) -> str:
    if interval in {"1h", "60m", "90m"} and period in {"2y", "5y", "10y", "max"}:
        return "730d"
    if interval in {"1m", "2m", "5m", "15m", "30m"}:
        return "60d"
    return period


def _yf_history(symbol: str, interval: str, period: str):
    import yfinance as yf

    period = cap_intraday_period(period, interval)
    last_err = None
    for attempt in range(3):
        try:
            t = yf.Ticker(symbol)
            df = t.history(period=period, interval=interval, auto_adjust=True, actions=False)
            if df is None or df.empty:
                raise ValueError("no prices returned")
            meta: dict = {}
            try:
                md = t.history_metadata
                meta["currency"] = md.get("currency")
                meta["type"] = str(md.get("instrumentType") or "").upper()
                meta["tz"] = md.get("exchangeTimezoneName")
                ctp = md.get("currentTradingPeriod") or {}
                reg = ctp.get("regular") if isinstance(ctp, dict) else None
                if isinstance(reg, dict) and isinstance(reg.get("end"), pd.Timestamp):
                    meta["regular_end"] = reg["end"]
            except Exception:
                pass
            return df, meta
        except Exception as exc:  # network hiccups, rate limits
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed ({last_err})")


def _ccxt_history(spec: str, interval: str, period: str):
    try:
        import ccxt  # optional dependency
    except ImportError as exc:
        raise RuntimeError("install ccxt to use exchange symbols (pip install ccxt)") from exc
    exch_id, market = spec.split(":", 1)
    ex = getattr(ccxt, exch_id.strip().lower())({"enableRateLimit": True})
    tf = {"1wk": "1w", "60m": "1h"}.get(interval, interval)
    tf_ms = ex.parse_timeframe(tf) * 1000
    bars = period_to_bars(period, 365 if tf == "1d" else 365 * 24)
    since = ex.milliseconds() - bars * tf_ms
    rows: list = []
    for _ in range(25):
        batch = ex.fetch_ohlcv(market, timeframe=tf, since=since, limit=720)
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1][0] + tf_ms
        if since > ex.milliseconds() or len(batch) < 2:
            break
    if not rows:
        raise RuntimeError("no prices returned")
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df.index = pd.to_datetime(df["ts"], unit="ms")
    quote = market.split("/")[1].split(":")[0].upper() if "/" in market else "USD"
    if quote in {"USDT", "USDC", "DAI"}:
        quote = "USD"
    meta = {"currency": quote, "type": "CRYPTOCURRENCY", "tz": "UTC", "is_24_7": True}
    return df.drop(columns=["ts"]), meta


def _csv_history(symbol: str, csv_dir: str):
    path = Path(csv_dir) / f"{safe_name(symbol)}.csv"
    if not path.exists():
        raise RuntimeError(f"no file {path}")
    df = pd.read_csv(path)
    cols = {str(c).lower().strip(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("datetime") or cols.get("timestamp") or df.columns[0]
    df.index = pd.to_datetime(df[date_col])
    rename = {}
    for want in ("open", "high", "low", "close", "volume", "adj close"):
        if want in cols:
            rename[cols[want]] = want.title()
    df = df.rename(columns=rename)
    if "Adj Close" in df.columns and "Close" in df.columns:
        factor = df["Adj Close"] / df["Close"]
        for c in ("Open", "High", "Low", "Close"):
            df[c] = df[c] * factor
    return df, {}


def _normalise(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip().title())
    for c in ("Open", "High", "Low", "Close"):
        if c not in df.columns:
            raise RuntimeError(f"price column {c} missing")
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        if interval in DAILY_OR_LONGER:
            idx = idx.tz_localize(None)  # keep the exchange's own calendar date
        else:
            idx = idx.tz_convert("UTC").tz_localize(None)
    if interval in DAILY_OR_LONGER:
        idx = idx.normalize()
    df.index = idx
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df["Volume"] = df["Volume"].fillna(0.0)
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def drop_incomplete_bar(df: pd.DataFrame, meta: dict, interval: str) -> pd.DataFrame:
    """Signals must only use finished bars. Drops today's bar if the market is still open."""
    if df.empty:
        return df
    now = pd.Timestamp.now(tz="UTC")
    last = df.index[-1]
    try:
        if interval in DAILY_OR_LONGER:
            if meta.get("is_24_7"):
                if last.date() >= now.date():
                    return df.iloc[:-1]
            elif meta.get("tz"):
                local_now = now.tz_convert(meta["tz"])
                end = meta.get("regular_end")
                if (
                    end is not None
                    and last.date() == local_now.date()
                    and end.tz_convert(meta["tz"]).date() == local_now.date()
                    and local_now < end + pd.Timedelta(minutes=20)
                ):
                    return df.iloc[:-1]  # today's session is still running
        else:
            step = pd.Timedelta(interval.replace("m", "min")) if interval.endswith("m") else pd.Timedelta(interval)
            if last + step > now.tz_localize(None):
                return df.iloc[:-1]
    except Exception:
        pass
    return df


def get_data(symbol: str, interval: str, period: str, csv_dir: str | None = None, live: bool = False):
    """Prices for one market. live=True keeps today's unfinished bar (used by the watch check)."""
    key = (symbol, interval, period, csv_dir, live)
    if key in _DATA_CACHE:
        return _DATA_CACHE[key]
    if csv_dir:
        df, meta = _csv_history(symbol, csv_dir)
    elif ":" in symbol:
        df, meta = _ccxt_history(symbol, interval, period)
    else:
        df, meta = _yf_history(symbol, interval, period)
    df = _normalise(df, interval)
    meta = dict(meta)
    if not meta.get("currency"):
        meta["currency"] = guess_currency(symbol)
    upper = symbol.upper()
    meta["is_24_7"] = bool(
        meta.get("is_24_7")
        or meta.get("type") == "CRYPTOCURRENCY"
        or upper.endswith(("-USD", "-GBP", "-EUR", "-USDT", "-USDC"))
    )
    if not csv_dir and not live:
        df = drop_incomplete_bar(df, meta, interval)
    _DATA_CACHE[key] = (df, meta)
    return df, meta


def traded_today(df: pd.DataFrame, meta: dict) -> bool:
    """True if the market's latest daily bar is today's (in the exchange's own time zone)."""
    if df.empty:
        return False
    tz = "UTC" if meta.get("is_24_7") else (meta.get("tz") or "UTC")
    try:
        return df.index[-1].date() == pd.Timestamp.now(tz=tz).date()
    except Exception:
        return False


def fx_rate(frm: str, to: str) -> float | None:
    """How many units of `to` one unit of `frm` is worth. None if unknown."""
    if not frm or not to or frm == to:
        return 1.0
    if OFFLINE:
        return None
    if frm == "GBp":
        r = fx_rate("GBP", to)
        return None if r is None else 0.01 * r
    if to == "GBp":
        r = fx_rate(frm, "GBP")
        return None if r is None else 100.0 * r
    key = (frm, to)
    if key in _FX_CACHE:
        return _FX_CACHE[key]
    rate = None
    try:
        import yfinance as yf

        for sym, invert in ((f"{frm}{to}=X", False), (f"{to}{frm}=X", True)):
            try:
                hist = yf.Ticker(sym).history(period="5d", interval="1d")
                px = float(hist["Close"].dropna().iloc[-1])
                if px > 0:
                    rate = 1.0 / px if invert else px
                    break
            except Exception:
                continue
    except Exception:
        rate = None
    _FX_CACHE[key] = rate
    return rate


def next_earnings_days(symbol: str, meta: dict) -> int | None:
    """Days until the next earnings date for a share, if Yahoo knows it."""
    if OFFLINE or meta.get("type") not in {"EQUITY", ""} or ":" in symbol or "=" in symbol or symbol.startswith("^"):
        return None
    try:
        import yfinance as yf

        cal = yf.Ticker(symbol).calendar or {}
        dates = cal.get("Earnings Date") or []
        today = datetime.now(timezone.utc).date()
        future = sorted(d for d in dates if d >= today)
        if future:
            return (future[0] - today).days
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Today's movers, news headlines and big scheduled events
# ---------------------------------------------------------------------------

MOVER_LABELS = {
    "most_actives": "US most active",
    "day_gainers": "US biggest risers",
    "day_losers": "US biggest fallers",
    "small_cap_gainers": "US small-cap risers",
    "most_shorted_stocks": "US most shorted",
}


def fetch_movers(cfg: dict) -> list[dict]:
    """Yahoo Finance's lists of the day's most traded shares, biggest risers and biggest fallers."""
    mv = cfg.get("movers", {})
    if OFFLINE or not mv.get("enabled"):
        return []
    try:
        import yfinance as yf
    except ImportError:
        return []
    n = int(mv.get("per_list", 10))
    out: list[dict] = []
    seen: set = set()

    def add(q: dict, label: str, region: str) -> None:
        sym = q.get("symbol")
        if not sym or sym in seen:
            return
        price = q.get("regularMarketPrice")
        if region == "us" and isinstance(price, (int, float)) and price < float(mv.get("min_price_usd", 5)):
            return  # skip penny stocks
        seen.add(sym)
        out.append({
            "symbol": sym,
            "name": q.get("shortName") or q.get("longName") or sym,
            "change_pct": q.get("regularMarketChangePercent"),
            "price": price,
            "list": label,
            "region": region,
        })

    for name in mv.get("us_lists", []):
        try:
            res = yf.screen(name, count=n)
            for q in (res or {}).get("quotes", []):
                add(q, MOVER_LABELS.get(name, name), "us")
        except Exception as exc:
            print(f"Movers list {name}: {exc}")
    if mv.get("uk"):
        try:
            from yfinance import EquityQuery

            base = EquityQuery("and", [
                EquityQuery("eq", ["region", "gb"]),
                EquityQuery("gte", ["intradaymarketcap", 1_000_000_000]),
                EquityQuery("gt", ["dayvolume", 100_000]),
            ])
            for label, field, ascending in (
                ("UK most active", "dayvolume", False),
                ("UK biggest risers", "percentchange", False),
                ("UK biggest fallers", "percentchange", True),
            ):
                res = yf.screen(base, sortField=field, sortAsc=ascending, size=n)
                for q in (res or {}).get("quotes", []):
                    add(q, label, "gb")
        except Exception as exc:
            print(f"UK movers: {exc}")
    return out


def mover_benchmark(m: dict, cfg: dict) -> str:
    mv = cfg.get("movers", {})
    return mv.get("uk_benchmark", "^FTSE") if m.get("region") == "gb" else mv.get("us_benchmark", "SPY")


def _parse_news_item(item) -> dict | None:
    """Reads either of Yahoo's two news formats. A silent format change has broken other people's bots."""
    if not isinstance(item, dict):
        return None
    c = item.get("content") if isinstance(item.get("content"), dict) else item
    title = str(c.get("title") or "").strip()
    if not title:
        return None
    prov = c.get("provider")
    publisher = prov.get("displayName", "") if isinstance(prov, dict) else str(c.get("publisher") or "")
    url = ""
    for k in ("clickThroughUrl", "canonicalUrl"):
        v = c.get(k)
        if isinstance(v, dict) and v.get("url"):
            url = str(v["url"])
            break
    url = url or str(c.get("link") or "")
    ts = c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime")
    when = None
    try:
        if isinstance(ts, (int, float)):
            when = pd.Timestamp(ts, unit="s", tz="UTC")
        elif ts:
            when = pd.Timestamp(ts)
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
    except Exception:
        when = None
    key = str(item.get("id") or c.get("id") or c.get("uuid") or url or title)
    return {"title": title, "publisher": publisher, "url": url, "when": when, "id": key}


def get_headlines(symbol: str, n: int = 3, max_age_hours: float = 72) -> list[dict]:
    """The newest headlines Yahoo Finance has for one market, newest first."""
    if OFFLINE:
        return []
    try:
        import yfinance as yf

        raw = yf.Ticker(symbol).get_news(count=max(10, n))
    except Exception:
        return []
    now = pd.Timestamp.now(tz="UTC")
    items = []
    for it in raw or []:
        p = _parse_news_item(it)
        if not p:
            continue
        if p["when"] is not None and (now - p["when"]).total_seconds() > max_age_hours * 3600:
            continue
        items.append(p)
    items.sort(key=lambda p: p["when"] if p["when"] is not None else pd.Timestamp(0, tz="UTC"), reverse=True)
    return items[:n]


def market_headlines(n: int = 6, max_age_hours: float = 24) -> list[dict]:
    seen, out = set(), []
    for sym in ("^GSPC", "^FTSE"):
        for p in get_headlines(sym, n=10, max_age_hours=max_age_hours):
            k = p["title"].lower()
            if k not in seen:
                seen.add(k)
                out.append(p)
    out.sort(key=lambda p: p["when"] if p["when"] is not None else pd.Timestamp(0, tz="UTC"), reverse=True)
    return out[:n]


def ago(when) -> str:
    if when is None:
        return ""
    secs = (pd.Timestamp.now(tz="UTC") - when).total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def headline_lines(items: list[dict]) -> list[str]:
    lines = []
    for p in items:
        title = esc(p["title"])
        link = f'<a href="{html.escape(p["url"], quote=True)}">{title}</a>' if p["url"].startswith("http") else title
        extra = ", ".join(x for x in (esc(p["publisher"]), ago(p["when"])) if x)
        lines.append(f"• {link}" + (f" ({extra})" if extra else ""))
    return lines


EVENT_CATEGORIES = (
    ("budget", ("budget",)),
    ("election", ("election",)),
    ("rates", ("interest rate", "rate decision", "fed funds", "fomc", "bank rate", "monetary policy", "bank of england")),
    ("inflation", ("cpi", "consumer price", "inflation")),
    ("jobs", ("nonfarm", "non-farm", "non farm", "payroll", "unemployment", "jobs report", "claimant", "employment change")),
    ("gdp", ("gdp",)),
    ("retail", ("retail sales",)),
    ("pce", ("pce",)),
)
_EVENTS_CACHE: list | None = None


def event_category(name: str) -> str | None:
    low = name.lower()
    for cat, words in EVENT_CATEGORIES:
        if any(w in low for w in words):
            return cat
    return None


def _yahoo_events(tzname: str, days: int) -> list[dict]:
    """Big US and UK releases from Yahoo Finance's economic calendar."""
    try:
        import yfinance as yf

        start = pd.Timestamp.now(tz="UTC")
        cal = yf.Calendars(start=start.strftime("%Y-%m-%d"), end=(start + pd.Timedelta(days=days)).strftime("%Y-%m-%d"))
        frames = []
        for page in range(5):
            df = cal.get_economic_events_calendar(limit=100, offset=page * 100, force=True)
            if df is None or len(df) == 0:
                break
            frames.append(df.reset_index())
            if len(df) < 100:
                break
        if not frames:
            return []
        df = pd.concat(frames, ignore_index=True)
    except Exception as exc:
        print(f"Economic calendar: {exc}")
        return []
    name_col = "Event" if "Event" in df.columns else df.columns[0]
    out = []
    for _, r in df.iterrows():
        region = str(r.get("Region", "") or "").upper()
        if region not in {"US", "GB", "UK"}:
            continue
        name = str(r.get(name_col, "") or "").strip()
        cat = event_category(name)
        if not cat:
            continue
        try:
            when = pd.Timestamp(r.get("Event Time"))
            when = (when.tz_localize("UTC") if when.tzinfo is None else when).tz_convert(tzname)
        except Exception:
            continue
        uk = region in {"GB", "UK"}
        out.append({"when": when, "name": f"{'UK' if uk else 'US'} {name}", "region": "GB" if uk else "US",
                    "has_time": True, "source": "yahoo", "cat": cat})
    return out


def upcoming_events(cfg: dict, days: int = 7) -> list[dict]:
    """Big scheduled events from your settings plus Yahoo's economic calendar, in your time zone."""
    global _EVENTS_CACHE
    ncfg = cfg.get("news", {})
    tzname = ncfg.get("timezone", "Europe/London")
    if _EVENTS_CACHE is None:
        events = []
        for e in ncfg.get("events", []) or []:
            try:
                d = str(e.get("date", "")).strip()
                t = str(e.get("time", "") or "").strip()
                name = str(e.get("name", "")).strip()
                if not d or not name:
                    continue
                when = pd.Timestamp(f"{d} {t}" if t else d).tz_localize(tzname)
                low = name.lower()
                region = str(e.get("region") or ("GB" if ("uk" in low.split() or "bank of england" in low or "budget" in low) else "US")).upper()
                events.append({"when": when, "name": name, "region": region, "has_time": bool(t),
                               "source": "settings", "cat": event_category(name) or low})
            except Exception:
                continue
        if ncfg.get("yahoo_calendar", True) and not OFFLINE:
            events.extend(_yahoo_events(tzname, 14))
        seen, unique = set(), []
        for ev in sorted(events, key=lambda e: (e["source"] != "settings", e["when"])):
            k = (ev["when"].date(), ev["region"], ev["cat"])
            if k not in seen:
                seen.add(k)
                unique.append(ev)
        _EVENTS_CACHE = sorted(unique, key=lambda e: e["when"])
    start = pd.Timestamp.now(tz=tzname).normalize()
    end = start + pd.Timedelta(days=days + 1)
    return [e for e in _EVENTS_CACHE if start <= e["when"] < end]


def event_text(ev: dict) -> str:
    w = ev["when"]
    t = f" {w:%H:%M}" if ev.get("has_time") and (w.hour or w.minute) else ""
    return f"{w:%a} {w.day} {w:%b}{t}: {ev['name']}"


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.where(avg_loss != 0.0, 100.0).where(avg_gain.notna())


def true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    return true_range(h, l, c).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def adx(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    a = atr(h, l, c, n)
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / a
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / a
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def add_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    s = cfg["setups"]
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = df.copy()
    out["sma5"] = c.rolling(5, min_periods=5).mean()
    out["ema20"] = c.ewm(span=20, adjust=False, min_periods=20).mean()
    out["sma50"] = c.rolling(50, min_periods=50).mean()
    out["sma200"] = c.rolling(200, min_periods=200).mean()
    out["rsi2"] = rsi(c, 2)
    out["atr"] = atr(h, l, c, 14)
    out["adx"] = adx(h, l, c, 14)
    mid = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std(ddof=0)
    out["bb_width"] = 4.0 * sd / mid
    out["bb_pctile"] = out["bb_width"].rolling(126, min_periods=60).rank(pct=True)
    n = int(s["breakout_lookback"])
    out["don_hi"] = h.rolling(n, min_periods=n).max().shift(1)
    out["don_lo"] = l.rolling(n, min_periods=n).min().shift(1)
    m = int(s["breakout_exit_lookback"])
    out["exit_lo"] = l.rolling(m, min_periods=m).min()
    out["exit_hi"] = h.rolling(m, min_periods=m).max()
    has_volume = bool((v.tail(60) > 0).sum() >= 40)
    if has_volume:
        out["vol_ratio"] = v / v.rolling(20, min_periods=20).mean().shift(1)
    else:
        out["vol_ratio"] = np.nan
    out["ret63"] = c / c.shift(63) - 1.0
    out["mom_12_1"] = c.shift(21) / c.shift(252) - 1.0
    out["move_atr"] = (c - c.shift(1)) / out["atr"].shift(1)  # today's move in ATRs
    out.attrs["has_volume"] = has_volume
    return out


def align_benchmark(ind: pd.DataFrame, bench_df: pd.DataFrame | None) -> pd.DataFrame | None:
    if bench_df is None or bench_df.empty:
        return None
    b = bench_df["Close"]
    b200 = b.rolling(200, min_periods=200).mean()
    b63 = b / b.shift(63) - 1.0
    frame = pd.DataFrame({"close": b, "sma200": b200, "ret63": b63})
    union = frame.index.union(ind.index)
    frame = frame.reindex(union).ffill().reindex(ind.index)
    frame["up"] = frame["sma200"].notna() & (frame["close"] > frame["sma200"])
    frame["down"] = frame["sma200"].notna() & (frame["close"] < frame["sma200"])
    return frame


# ---------------------------------------------------------------------------
# Setups and scoring
# ---------------------------------------------------------------------------


@dataclass
class Check:
    key: str
    label: str  # may contain {vol_ratio}, {adx}, {bench}
    series: pd.Series | None  # None = not available for this market
    weight: int
    penalty: bool = False


def _score(base: int, checks: list[Check], index) -> pd.Series:
    earned = pd.Series(float(base), index=index)
    available = float(base)
    for ch in checks:
        if ch.series is None:
            continue
        hit = ch.series.astype(bool).astype(float)
        if ch.penalty:
            earned = earned - hit * ch.weight
        else:
            available += ch.weight
            earned = earned + hit * ch.weight
    return (100.0 * earned / available).clip(0, 100).round()


def compute_signals(ind: pd.DataFrame, bench: pd.DataFrame | None, cfg: dict, symbol: str, bench_symbol: str):
    """Returns {(setup, direction): (DataFrame[trig, score], [Check, ...])}."""
    s = cfg["setups"]
    c = ind["Close"]
    has_vol = bool(ind.attrs.get("has_volume", False))
    use_bench = bench is not None and bench_symbol and bench_symbol.upper() != symbol.upper()
    out = {}
    directions = ["long", "short"] if cfg["scan"].get("allow_shorts") else ["long"]
    for d in directions:
        up = d == "long"
        above200 = ind["sma200"].notna() & ((c > ind["sma200"]) if up else (c < ind["sma200"]))
        sma200_slope = ind["sma200"] > ind["sma200"].shift(20)
        if up:
            aligned = (ind["sma50"] > ind["sma200"]) & sma200_slope
        else:
            aligned = (ind["sma50"] < ind["sma200"]) & ~sma200_slope & ind["sma200"].shift(20).notna()
        adx_ok = ind["adx"] >= float(s["adx_trending"])
        rs = None
        regime = None
        if use_bench:
            rs = (ind["ret63"] > bench["ret63"]) if up else (ind["ret63"] < bench["ret63"])
            regime = bench["up"] if up else bench["down"]
        trend_word = "uptrend" if up else "downtrend"
        rs_label = "beating {bench} over 3 months" if up else "weaker than {bench} over 3 months"

        # 1) Trend breakout: a fresh close beyond the N-day high (low for shorts) in the trend's direction
        beyond = (c > ind["don_hi"]) if up else (c < ind["don_lo"])
        trig_bo = above200 & beyond & ~beyond.shift(1, fill_value=False)
        vol_ok = (ind["vol_ratio"] >= float(s["volume_surge"])) if has_vol else None
        stretch = ((c - ind["ema20"]) / ind["atr"]) if up else ((ind["ema20"] - c) / ind["atr"])
        squeeze = ind["bb_pctile"].shift(1).rolling(10, min_periods=5).min() <= float(s["squeeze_pctile"])
        checks_bo = [
            Check("aligned", f"50-day {'above rising' if up else 'below falling'} 200-day", aligned, 15),
            Check("volume", "volume {vol_ratio:.1f}x normal", vol_ok, 15),
            Check("squeeze", "quiet squeeze before the break", squeeze, 15),
            Check("adx", "strong trend (ADX {adx:.0f})", adx_ok, 10),
            Check("rs", rs_label, rs, 10),
            Check("regime", "{bench} in an " + trend_word if up else "{bench} in a " + trend_word, regime, 10),
            Check("stretched", "already stretched far from the 20-day average", stretch > float(s["overextended_atr"]), 15, True),
        ]
        out[("breakout", d)] = (pd.DataFrame({"trig": trig_bo, "score": _score(30, checks_bo, ind.index)}), checks_bo)

        # 2) Pullback in a trend: a sharp 2-day dip (RSI(2)) while the long-term trend holds
        entry = float(s["pullback_rsi2_entry"])
        dipped = (ind["rsi2"] < entry) if up else (ind["rsi2"] > 100.0 - entry)
        trig_pb = above200 & dipped & ~dipped.shift(1, fill_value=False)
        deep = (ind["rsi2"] < 5) if up else (ind["rsi2"] > 95)
        holds50 = (c > ind["sma50"]) if up else (c < ind["sma50"])
        shock = (-ind["move_atr"] > 3.0) if up else (ind["move_atr"] > 3.0)
        checks_pb = [
            Check("aligned", f"50-day {'above rising' if up else 'below falling'} 200-day", aligned, 15),
            Check("deep", "very stretched dip (RSI(2) " + ("under 5)" if up else "over 95)"), deep, 15),
            Check("holds50", f"still {'above' if up else 'below'} the 50-day average", holds50, 10),
            Check("adx", "strong trend (ADX {adx:.0f})", adx_ok, 10),
            Check("rs", rs_label, rs, 10),
            Check("regime", "{bench} in an " + trend_word if up else "{bench} in a " + trend_word, regime, 10),
            Check("shock", "huge one-day move: check the news", shock, 15, True),
        ]
        out[("pullback", d)] = (pd.DataFrame({"trig": trig_pb, "score": _score(30, checks_pb, ind.index)}), checks_pb)
    return out


def stop_multiple(setup: str, cfg: dict) -> float:
    s = cfg["setups"]
    return float(s["breakout_stop_atr"] if setup == "breakout" else s["pullback_stop_atr"])


def describe_checks(checks: list[Check], i: int, ind: pd.DataFrame, bench_symbol: str) -> list[tuple[bool, str, bool]]:
    """[(passed, text, is_penalty)] for bar i, skipping checks that do not apply."""
    row = ind.iloc[i]
    vals = {
        "vol_ratio": float(row["vol_ratio"]) if pd.notna(row["vol_ratio"]) else 0.0,
        "adx": float(row["adx"]) if pd.notna(row["adx"]) else 0.0,
        "bench": bench_symbol,
    }
    out = []
    for ch in checks:
        if ch.series is None:
            continue
        passed = bool(ch.series.iloc[i])
        if ch.penalty and not passed:
            continue
        try:
            text = ch.label.format(**vals)
        except Exception:
            text = ch.label
        out.append((passed, text, ch.penalty))
    return out


# ---------------------------------------------------------------------------
# Trades: entries, stops, exits (shared by backtest and paper trading)
# ---------------------------------------------------------------------------


@dataclass
class Position:
    symbol: str
    setup: str
    direction: str
    signal_date: str
    signal_price: float
    atr_at_signal: float
    score: int
    currency: str = "USD"
    status: str = "pending"  # pending -> open -> closed (or cancelled)
    entry_date: str = ""
    entry_price: float = 0.0
    stop: float = 0.0
    initial_stop: float = 0.0
    risk_per_unit: float = 0.0
    units: float = 1.0
    fx_to_account: float = 1.0
    risk_amount: float = 0.0
    bars_held: int = 0
    last_bar: str = ""
    exit_next_open: bool = False
    exit_reason: str = ""
    exit_date: str = ""
    exit_price: float = 0.0
    r_multiple: float = 0.0
    pnl: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


def bar_label(ts: pd.Timestamp, interval: str) -> str:
    return ts.strftime("%Y-%m-%d") if interval in DAILY_OR_LONGER else ts.strftime("%Y-%m-%d %H:%M")


def try_fill(pos: Position, date: str, row, cfg: dict) -> bool:
    """Fill a pending entry at this bar's open. Returns False if cancelled."""
    o = float(row["Open"])
    risk = stop_multiple(pos.setup, cfg) * float(pos.atr_at_signal)
    long = pos.direction == "long"
    if not (np.isfinite(o) and risk > 0):
        pos.status, pos.exit_reason = "cancelled", "no valid price"
        return False
    planned_stop = pos.signal_price - risk if long else pos.signal_price + risk
    if (long and o <= planned_stop) or ((not long) and o >= planned_stop):
        pos.status, pos.exit_reason = "cancelled", "opened beyond the stop"
        return False
    pos.entry_date, pos.entry_price = date, o
    pos.risk_per_unit = risk
    pos.stop = pos.initial_stop = (o - risk) if long else (o + risk)
    pos.status, pos.bars_held = "open", 0
    return True


def close_position(pos: Position, date: str, price: float, reason: str, cost: float) -> bool:
    long = pos.direction == "long"
    entry_eff = pos.entry_price * (1 + cost if long else 1 - cost)
    exit_eff = price * (1 - cost if long else 1 + cost)
    per_unit = (exit_eff - entry_eff) if long else (entry_eff - exit_eff)
    pos.r_multiple = per_unit / pos.risk_per_unit if pos.risk_per_unit else 0.0
    pos.pnl = per_unit * pos.units * pos.fx_to_account
    pos.exit_date, pos.exit_price, pos.exit_reason = date, float(price), reason
    pos.status = "closed"
    return True


def step_bar(pos: Position, date: str, row, cfg: dict, cost: float) -> bool:
    """Process one finished bar for an open position. Returns True if it closed."""
    s = cfg["setups"]
    long = pos.direction == "long"
    o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
    first_bar = date == pos.entry_date
    if pos.exit_next_open and not first_bar:
        return close_position(pos, date, o, pos.exit_reason, cost)
    if long:
        if not first_bar and o <= pos.stop:
            return close_position(pos, date, o, "stop (gapped through)", cost)
        if l <= pos.stop:
            return close_position(pos, date, pos.stop, "stop" if pos.stop <= pos.initial_stop else "trailing stop", cost)
    else:
        if not first_bar and o >= pos.stop:
            return close_position(pos, date, o, "stop (gapped through)", cost)
        if h >= pos.stop:
            return close_position(pos, date, pos.stop, "stop" if pos.stop >= pos.initial_stop else "trailing stop", cost)
    pos.bars_held += 1
    pos.last_bar = date
    if pos.setup == "breakout":
        trail = float(row["exit_lo"] if long else row["exit_hi"])
        if np.isfinite(trail):
            if long and trail > pos.stop:
                pos.stop = trail
            elif (not long) and trail < pos.stop:
                pos.stop = trail
    else:
        sma5 = float(row["sma5"])
        if np.isfinite(sma5) and ((long and c > sma5) or ((not long) and c < sma5)):
            pos.exit_next_open, pos.exit_reason = True, "bounce done: closed past the 5-day average"
        elif pos.bars_held >= int(s["pullback_max_hold_bars"]):
            pos.exit_next_open, pos.exit_reason = True, "time stop"
    return False


def size_position(equity: float, cfg: dict, price: float, risk_unit: float, fx: float, crypto: bool):
    acct = cfg["account"]
    risk_amt = equity * float(acct["risk_per_trade_pct"]) / 100.0
    units = risk_amt / (risk_unit * fx) if risk_unit > 0 else 0.0
    max_units = (equity * float(acct["max_position_pct"]) / 100.0) / (price * fx) if price > 0 else 0.0
    units = min(units, max_units)
    step = 0.0001 if crypto else (0.01 if acct.get("fractional_units", True) else 1.0)
    units = math.floor(units / step) * step
    units = round(units, 4)
    return units, units * risk_unit * fx, units * price * fx


# ---------------------------------------------------------------------------
# Telegram and formatting
# ---------------------------------------------------------------------------


def esc(x) -> str:
    return html.escape(str(x), quote=False)


def fmt_price(x: float, ccy: str) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    if ccy == "GBp":
        return f"{x:,.1f}p"
    ax = abs(x)
    digits = 2 if ax >= 1 else (4 if ax >= 0.01 else 6)
    symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(ccy)
    return f"{symbol}{x:,.{digits}f}" if symbol else f"{x:,.{digits}f} {ccy}"


def fmt_money(x: float, ccy: str) -> str:
    symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(ccy)
    sign = "-" if x < 0 else ""
    return f"{sign}{symbol}{abs(x):,.0f}" if symbol else f"{sign}{abs(x):,.0f} {ccy}"


def to_plain(text: str) -> str:
    """Telegram HTML to plain text for the console."""
    text = re.sub(r'<a href="([^"]*)">(.*?)</a>', lambda m: f"{m.group(2)} [{html.unescape(m.group(1))}]", text)
    text = re.sub(r"</?(b|i)>", "", text)
    return html.unescape(text)


def output(cfg: dict, text: str, args) -> None:
    """Commands that report (movers, volatile, news, events, status) print unless you add --telegram."""
    send_telegram(cfg, text, args if getattr(args, "telegram", False) else argparse.Namespace(no_telegram=True))


def send_telegram(cfg: dict, text: str, args=None) -> bool:
    token, chat = cfg["telegram"].get("token"), cfg["telegram"].get("chat_id")
    plain = to_plain(text)
    if (args is not None and getattr(args, "no_telegram", False)) or not token or not chat:
        print("\n" + plain + "\n")
        return False
    import requests

    ok = True
    chunks, current = [], ""
    for line in text.split("\n"):  # split on line breaks so no HTML tag is cut in half
        if len(current) + len(line) + 1 > 3900 and current:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    for chunk in chunks:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=20,
            )
            if r.status_code != 200:
                ok = False
                print(f"Telegram error {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            ok = False
            print(f"Telegram error: {exc}")
    print("\n" + plain + "\n")
    return ok


def format_alert(sym, setup, direction, score, checks_desc, plan, cfg, interval, warnings, paper_note,
                 origin: str | None = None, volatility: str | None = None, history: str | None = None,
                 news: list[str] | None = None) -> str:
    strong = score >= int(cfg["scan"]["strong_score"])
    ccy, acct_ccy = plan["currency"], cfg["account"]["currency"]
    unit_word = {"shares": "a share", "coins": "a coin"}.get(plan["unit_name"], "a unit")
    s = cfg["setups"]
    head = "STRONG SETUP" if strong else "GOOD SETUP"
    tf = {"1d": "daily chart", "1h": "hourly chart", "1wk": "weekly chart"}.get(interval, f"{interval} chart")
    lines = [
        f"<b>{head}: {esc(sym)}</b> · score {score}/100",
        f"{SETUP_TITLES[setup]} · {'buy (long)' if direction == 'long' else 'sell short'} · {tf}",
    ]
    if origin:
        lines.append(f"Found on today's movers: {esc(origin)}")
    lines += [
        "",
        f"Entry: about {fmt_price(plan['price'], ccy)} at the next open",
        f"Stop: {fmt_price(plan['stop'], ccy)} ({plan['k']:g} x ATR, {fmt_price(plan['risk_unit'], ccy)} {unit_word})",
    ]
    if setup == "breakout":
        lines.append(
            f"Exit plan: trail the stop under the {int(s['breakout_exit_lookback'])}-bar "
            f"{'low' if direction == 'long' else 'high'}; {s['target_r']:g}R is {fmt_price(plan['target'], ccy)}"
        )
    else:
        lines.append(
            f"Exit plan: close it when price closes back past the 5-day average, or after "
            f"{int(s['pullback_max_hold_bars'])} bars; {s['target_r']:g}R is {fmt_price(plan['target'], ccy)}"
        )
    if plan["units"] > 0:
        intended = plan["equity"] * float(cfg["account"]["risk_per_trade_pct"]) / 100.0
        if plan["risk_amt"] < 0.97 * intended:
            why = f"capped by the {cfg['account']['max_position_pct']:g}% position limit; full risk would be {fmt_money(intended, acct_ccy)}"
        else:
            why = f"{cfg['account']['risk_per_trade_pct']:g}% of {fmt_money(plan['equity'], acct_ccy)}"
        lines.append(
            f"Size: {plan['units']:g} {plan['unit_name']} ≈ {fmt_money(plan['value'], acct_ccy)}, "
            f"risking {fmt_money(plan['risk_amt'], acct_ccy)} ({why})"
        )
    else:
        lines.append("Size: too small for your risk setting at this price")
    if plan.get("fx_missing"):
        lines.append(f"(Could not get the {ccy} to {acct_ccy} rate, so size assumes 1 to 1. Check it.)")
    if volatility:
        lines.append(esc(volatility))
    lines.append("")
    ticks = []
    for passed, text, penalty in checks_desc:
        mark = "⚠️" if penalty else ("✅" if passed else "❌")
        ticks.append(f"{mark} {esc(text)}")
    lines.extend(ticks)
    for w in warnings:
        lines.append(f"⚠️ {esc(w)}")
    if history:
        lines.append("")
        lines.append(esc(history))
    if news is not None:
        lines.append("")
        if news:
            lines.append("Latest news:")
            lines.extend(news)
        else:
            lines.append("No headlines in the last few days.")
    if paper_note:
        lines.append("")
        lines.append(esc(paper_note))
    lines.append("")
    lines.append("<i>Not advice. Check the chart and the news before acting.</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State (paper trading, alerts already sent)
# ---------------------------------------------------------------------------


def state_path() -> Path:
    return STATE_DIR / "paper.json"


def load_state(cfg: dict) -> dict:
    p = state_path()
    if p.exists():
        with open(p, "r", encoding="utf-8") as fh:
            st = json.load(fh)
    else:
        size = float(cfg["account"]["size"])
        st = {"version": 1, "start_equity": size, "equity": size, "positions": [], "closed": [], "sent": {}, "leaders_week": ""}
    st.setdefault("sent", {})
    st.setdefault("closed", [])
    st.setdefault("positions", [])
    return st


def save_state(st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.now(timezone.utc) - pd.Timedelta(days=45)).isoformat()
    st["sent"] = {k: v for k, v in st.get("sent", {}).items() if v >= cutoff}
    tmp = state_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, default=float)
    tmp.replace(state_path())


def append_log(rows: list[dict]) -> None:
    if not rows:
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / "scan_log.csv"
    new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        w.writerows(rows)


def summarise_r(rs: list[float]) -> dict:
    if not rs:
        return {"trades": 0}
    r = np.array(rs, dtype=float)
    wins, losses = r[r > 0], r[r <= 0]
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    gross_loss = abs(losses.sum())
    return {
        "trades": int(len(r)),
        "win_rate": float(len(wins) / len(r)),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "expectancy": float(r.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else float("inf"),
        "total_r": float(r.sum()),
        "max_dd_r": float((peak - eq).max()) if len(eq) else 0.0,
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def manage_paper(st: dict, sym: str, ind: pd.DataFrame, meta: dict, cfg: dict, interval: str, msgs: list[str]) -> None:
    cost = float(cfg["backtest"]["cost_per_side_pct"]) / 100.0
    acct_ccy = cfg["account"]["currency"]
    keep = []
    for d in st["positions"]:
        pos = Position.from_dict(d)
        if pos.symbol != sym or pos.status not in {"pending", "open"}:
            keep.append(asdict(pos))
            continue
        after = pd.Timestamp(pos.last_bar or pos.signal_date)
        new_bars = ind[ind.index > after]
        for ts, row in new_bars.iterrows():
            date = bar_label(ts, interval)
            if pos.status == "pending":
                if not try_fill(pos, date, row, cfg):
                    msgs.append(f"Paper trade skipped: {esc(sym)} {pos.setup} ({pos.exit_reason}).")
                    break
                fx = fx_rate(pos.currency, acct_ccy)
                pos.fx_to_account = fx if fx else 1.0
                units, risk_amt, value = size_position(
                    float(st["equity"]), cfg, pos.entry_price, pos.risk_per_unit, pos.fx_to_account, bool(meta.get("is_24_7"))
                )
                if units <= 0:
                    pos.status, pos.exit_reason = "cancelled", "position too small"
                    msgs.append(f"Paper trade skipped: {esc(sym)} (position too small for the risk setting).")
                    break
                pos.units, pos.risk_amount = units, risk_amt
                msgs.append(
                    f"<b>Paper trade opened</b>: {esc(sym)} {pos.direction} at {fmt_price(pos.entry_price, pos.currency)}, "
                    f"stop {fmt_price(pos.stop, pos.currency)}, {units:g} units, risking {fmt_money(risk_amt, acct_ccy)}."
                )
            if pos.status == "open" and step_bar(pos, date, row, cfg, cost):
                st["equity"] = float(st["equity"]) + pos.pnl
                ret = (float(st["equity"]) / float(st["start_equity"]) - 1.0) * 100.0
                held = "on its first bar" if pos.bars_held == 0 else f"after {pos.bars_held} bar{'s' if pos.bars_held != 1 else ''}"
                msgs.append(
                    f"<b>Paper trade closed</b>: {esc(sym)} {pos.r_multiple:+.2f}R ({fmt_money(pos.pnl, acct_ccy)}), "
                    f"{esc(pos.exit_reason)} at {fmt_price(pos.exit_price, pos.currency)} {held}. "
                    f"Paper account {fmt_money(float(st['equity']), acct_ccy)} ({ret:+.1f}%)."
                )
                break
            pos.last_bar = date
        if pos.status in {"pending", "open"}:
            keep.append(asdict(pos))
        elif pos.status == "closed":
            st["closed"].append(asdict(pos))
    st["positions"] = keep


def crypto_headlines(cfg: dict, n: int = 4) -> list[dict]:
    """Newest crypto headlines from Yahoo Finance's Bitcoin, Ethereum and Solana news feeds."""
    seen, out = set(), []
    for sym in cfg["news"].get("crypto_symbols", ["BTC-USD", "ETH-USD"]):
        for p in get_headlines(sym, n=8, max_age_hours=24):
            k = p["title"].lower()
            if k not in seen:
                seen.add(k)
                out.append(p)
    out.sort(key=lambda p: p["when"] if p["when"] is not None else pd.Timestamp(0, tz="UTC"), reverse=True)
    return out[:n]


def recap_positions(st: dict, cfg: dict, csv_dir) -> list[str]:
    """Rebuilds the alert for every paper trade waiting or open, so nothing is missed."""
    out = []
    acct = cfg["account"]["currency"]
    for p in st["positions"]:
        try:
            sym = p["symbol"]
            df, meta = get_data(sym, cfg["scan"]["interval"], cfg["scan"]["history"], csv_dir)
            ind = add_indicators(df, cfg)
            ccy = p.get("currency") or meta["currency"]
            price = float(ind["Close"].iloc[-1])
            lines = [f"<b>{'OPEN' if p['status'] == 'open' else 'WAITING TO OPEN'}: {esc(sym)}</b> · "
                     f"{SETUP_TITLES.get(p['setup'], p['setup'])} · score {p['score']}/100",
                     f"Signal on {p['signal_date']} at {fmt_price(float(p['signal_price']), ccy)}"]
            if p["status"] == "open":
                pnl = (price - float(p["entry_price"])) * float(p["units"]) * float(p.get("fx_to_account") or 1)
                lines += [f"Bought {p['entry_date']} at {fmt_price(float(p['entry_price']), ccy)}, "
                          f"{float(p['units']):g} units, stop now {fmt_price(float(p['stop']), ccy)}",
                          f"Now {fmt_price(price, ccy)}: {fmt_money(pnl, acct)} so far (not counted until it closes)"]
            else:
                risk = stop_multiple(p["setup"], cfg) * float(p["atr_at_signal"])
                lines.append(f"Buys at the next open; stop about {fmt_price(float(p['signal_price']) - risk, ccy)} "
                             f"({stop_multiple(p['setup'], cfg):g} x ATR below the entry)")
            heads = headline_lines(get_headlines(sym, 2, 72)) if cfg["news"].get("enabled", True) else []
            if heads:
                lines += ["Latest news:"] + heads
            out.append("\n".join(lines))
        except Exception as exc:
            out.append(f"{esc(p.get('symbol', '?'))}: couldn't rebuild this alert ({esc(exc)})")
    return out


def event_relevant(ev: dict, sym: str) -> bool:
    """US events move every market; UK events mainly move UK shares and the pound."""
    if ev.get("region") != "GB":
        return True
    s = sym.upper()
    return s.endswith(".L") or "GBP" in s or s.startswith("^FT")


def cmd_scan(cfg: dict, args) -> int:
    interval = cfg["scan"]["interval"]
    history = cfg["scan"]["history"]
    st = load_state(cfg)
    alert_min = int(cfg["scan"]["alert_min_score"])
    paper_on = bool(cfg["paper"]["enabled"])
    acct_ccy = cfg["account"]["currency"]
    news_on = bool(cfg["news"].get("enabled", True))
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    alerts, msgs, errors, log_rows, regimes, vol_rows = [], [], [], [], [], []
    checked = movers_checked = movers_passed = 0
    seen = set()
    watch = iter_watchlist(cfg, args)
    on_list = {s for _, syms in watch for s in syms}

    # Today's movers: Yahoo's most active, biggest risers and biggest fallers. They have to pass
    # exactly the same rules as everything else; being on a movers list earns no points.
    movers = [] if getattr(args, "symbols", None) else fetch_movers(cfg)
    mover_info = {}
    for m in movers:
        chg = m.get("change_pct")
        mover_info[m["symbol"]] = m["list"] + (f" ({chg:+.1f}% on the day)" if isinstance(chg, (int, float)) else "")
    for bench in sorted({mover_benchmark(m, cfg) for m in movers}):
        syms = [m["symbol"] for m in movers if mover_benchmark(m, cfg) == bench and m["symbol"] not in on_list]
        if syms:
            watch.append((bench, syms))
    extra = sorted({p["symbol"] for p in st["positions"]} - {s for _, syms in watch for s in syms})
    if extra:
        watch.append(("", extra))  # keep managing paper trades for symbols no longer listed

    warn_days = int(cfg["news"].get("event_warning_days", 2))
    events_soon = upcoming_events(cfg, max(3, warn_days)) if news_on else []
    warn_until = pd.Timestamp.now(tz=cfg["news"].get("timezone", "Europe/London")) + pd.Timedelta(days=warn_days)

    for bench_sym, symbols in watch:
        bench_df = None
        if bench_sym:
            try:
                bench_df, _ = get_data(bench_sym, interval, history, args.csv_dir)
                bind = add_indicators(bench_df, cfg)
                last = bind.iloc[-1]
                label = f"{bench_sym} {'uptrend' if last['Close'] > last['sma200'] else 'downtrend'}"
                if pd.notna(last["sma200"]) and label not in regimes:
                    regimes.append(label)
            except Exception as exc:
                errors.append(f"{bench_sym} ({exc})")
        for sym in symbols:
            if sym in seen:
                continue
            seen.add(sym)
            is_mover = sym in mover_info and sym not in on_list
            try:
                df, meta = get_data(sym, interval, history, args.csv_dir)
                if len(df) < 210:
                    if not is_mover:  # brand-new listings on the movers lists are skipped quietly
                        errors.append(f"{sym} (only {len(df)} bars of history)")
                    continue
                checked += 1
                movers_checked += int(is_mover)
                ind = add_indicators(df, cfg)
                lr = ind.iloc[-1]
                if pd.notna(lr["atr"]) and lr["Close"] > 0:
                    vol_rows.append((sym, float(lr["atr"]) / float(lr["Close"]) * 100.0))
                bench = align_benchmark(ind, bench_df)
                manage_paper(st, sym, ind, meta, cfg, interval, msgs)
                sigs = compute_signals(ind, bench, cfg, sym, bench_sym)
                i = len(ind) - 1
                bar = bar_label(ind.index[i], interval)
                for (setup, direction), (frame, checks) in sigs.items():
                    if not bool(frame["trig"].iloc[i]):
                        continue
                    score = int(frame["score"].iloc[i])
                    warnings = []
                    days = next_earnings_days(sym, meta) if score >= alert_min - 10 else None
                    if days is not None and days <= int(cfg["scan"]["earnings_warning_days"]):
                        score = max(0, score - 10)
                        warnings.append(f"Earnings in {days} day{'s' if days != 1 else ''}: prices can jump past any stop")
                    soon = [e for e in events_soon if e["when"] <= warn_until and event_relevant(e, sym)]
                    for ev in soon[:2]:
                        warnings.append(f"Big event soon, {event_text(ev)}: prices can jump on the day")
                    key = f"{sym}|{setup}|{direction}|{bar}"
                    alerted = False
                    if score >= alert_min and key not in st["sent"]:
                        last = ind.iloc[i]
                        price, a = float(last["Close"]), float(last["atr"])
                        k = stop_multiple(setup, cfg)
                        long = direction == "long"
                        risk_unit = k * a
                        fx = fx_rate(meta["currency"], acct_ccy)
                        crypto = bool(meta.get("is_24_7"))
                        units, risk_amt, value = size_position(float(st["equity"]), cfg, price, risk_unit, fx or 1.0, crypto)
                        plan = {
                            "price": price,
                            "stop": price - risk_unit if long else price + risk_unit,
                            "target": price + (risk_unit if long else -risk_unit) * float(cfg["setups"]["target_r"]),
                            "risk_unit": risk_unit,
                            "k": k,
                            "units": units,
                            "risk_amt": risk_amt,
                            "value": value,
                            "equity": float(st["equity"]),
                            "currency": meta["currency"],
                            "crypto": crypto,
                            "unit_name": "coins" if crypto else (
                                "shares" if (meta.get("type") or "") in {"EQUITY", "ETF", ""} and "=" not in sym and not sym.startswith("^")
                                else "units"
                            ),
                            "fx_missing": fx is None,
                        }
                        open_syms = {p["symbol"] for p in st["positions"]}
                        paper_note = ""
                        tm = time_machine(ind, setup, direction, cfg) if cfg["timemachine"].get("enabled", True) else None
                        ok, why = risk_check(st, cfg, risk_amt)
                        min_r = float(cfg["risk"].get("min_replay_avg_r", -1))
                        if ok and tm and min_r > -1 and tm["avg_r"] < min_r:
                            ok, why = False, f"time machine average {tm['avg_r']:+.2f}R is below your minimum {min_r:+.2f}R"
                        warnings.append(("Risk check: PASS, " if ok else "Risk check: BLOCK, ") + why)
                        if paper_on and score >= int(cfg["paper"]["min_score"]):
                            if sym in open_syms:
                                paper_note = "Paper trading: already holding this one, so no new paper trade."
                            elif not ok:
                                paper_note = "Paper trading: blocked by the risk check, so no paper trade."
                            else:
                                pos = Position(
                                    symbol=sym, setup=setup, direction=direction, signal_date=bar,
                                    signal_price=price, atr_at_signal=a, score=score, currency=meta["currency"],
                                )
                                st["positions"].append(asdict(pos))
                                paper_note = "Paper trading: the bot will open this at the next open and manage it for you."
                        atr_pct = a / price * 100.0 if price > 0 else 0.0
                        vol_line = f"Moves about {atr_pct:.1f}% a day" + (
                            ": very volatile, so expect big swings both ways. The size is smaller to keep the risk the same."
                            if atr_pct >= 5.0 else "."
                        )
                        hist = history_line(sym, setup_history(sym, setup, direction, cfg, interval, bench_sym, args.csv_dir), cfg)
                        tml = time_machine_line(tm)
                        if tml:
                            hist = f"{hist}\n{tml}" if hist else tml
                        heads = None
                        if news_on:
                            heads = headline_lines(get_headlines(
                                sym, int(cfg["news"].get("headlines", 3)), float(cfg["news"].get("max_age_hours", 72))
                            ))
                        desc = describe_checks(checks, i, ind, bench_sym)
                        alerts.append(format_alert(
                            sym, setup, direction, score, desc, plan, cfg, interval, warnings, paper_note,
                            origin=mover_info.get(sym) if is_mover else None, volatility=vol_line, history=hist, news=heads,
                        ))
                        st["sent"][key] = now_iso
                        alerted = True
                        movers_passed += int(is_mover)
                    log_rows.append({
                        "run_utc": now_iso, "bar": bar, "symbol": sym, "setup": setup,
                        "direction": direction, "score": score, "alerted": alerted,
                    })
            except Exception as exc:
                if not is_mover:
                    errors.append(f"{sym} ({exc})")

    if not st.get("recap_v1") and st["positions"]:
        recap = recap_positions(st, cfg, args.csv_dir)
        if recap:
            send_telegram(cfg, "<b>Your paper trades so far</b> (resent so you haven't missed any)", args)
            for text in recap:
                send_telegram(cfg, text, args)
    st["recap_v1"] = True
    for text in alerts:
        send_telegram(cfg, text, args)
    if msgs:
        send_telegram(cfg, "\n".join(msgs), args)
    if news_on and cfg["news"].get("crypto_news", True) and not getattr(args, "symbols", None):
        ch = crypto_headlines(cfg, 4)
        if ch:
            send_telegram(cfg, "\n".join(["<b>Crypto news</b> (last 24 hours)"] + headline_lines(ch)), args)

    # Weekly momentum leaders
    wd = int(cfg["leaders"].get("send_on_weekday", 0))
    week = now.strftime("%G-W%V")
    if wd >= 0 and now.weekday() == wd and st.get("leaders_week") != week:
        text = leaders_text(cfg, args)
        if text:
            send_telegram(cfg, text, args)
            st["leaders_week"] = week

    if cfg["scan"].get("daily_summary", True):
        closed = st["closed"]
        stats = summarise_r([c["r_multiple"] for c in closed])
        n_open = sum(1 for p in st["positions"] if p["status"] == "open")
        n_pend = sum(1 for p in st["positions"] if p["status"] == "pending")
        ret = (float(st["equity"]) / float(st["start_equity"]) - 1.0) * 100.0
        lines = [
            f"<b>Scan done</b> · {now:%d %b %Y %H:%M} UTC",
            f"Checked {checked} market{'s' if checked != 1 else ''} · {len(alerts)} new alert{'s' if len(alerts) != 1 else ''}",
        ]
        if movers:
            lines.append(f"Today's movers: {movers_checked} checked, {movers_passed} passed the rules")
        if regimes:
            lines.append("Market trend: " + " · ".join(esc(r) for r in regimes))
        if vol_rows:
            top = sorted(vol_rows, key=lambda r: r[1], reverse=True)[:3]
            lines.append("Most volatile: " + " · ".join(f"{esc(s)} {v:.1f}% a day" for s, v in top))
        if events_soon:
            lines.append("Coming up: " + "; ".join(esc(event_text(e)) for e in events_soon[:4]))
        if paper_on:
            pstats = f"Paper account: {fmt_money(float(st['equity']), acct_ccy)} ({ret:+.1f}%) · {n_open} open"
            if n_pend:
                pstats += f" · {n_pend} waiting to open"
            if stats["trades"]:
                pstats += f" · {stats['trades']} closed, {stats['win_rate']:.0%} won, {stats['total_r']:+.1f}R"
            lines.append(pstats)
        if errors:
            lines.append("Could not check: " + "; ".join(esc(e) for e in errors[:8]))
        send_telegram(cfg, "\n".join(lines), args)

    append_log(log_rows)
    save_state(st)
    return 0


def leaders_text(cfg: dict, args) -> str:
    interval = cfg["scan"]["interval"]
    rows = []
    for _, symbols in iter_watchlist(cfg, args):
        for sym in symbols:
            try:
                df, _ = get_data(sym, interval, cfg["scan"]["history"], args.csv_dir)
                ind = add_indicators(df, cfg)
                last = ind.iloc[-1]
                mom = last["mom_12_1"] if pd.notna(last["mom_12_1"]) else last["ret63"]
                if pd.notna(mom) and pd.notna(last["sma200"]) and last["Close"] > last["sma200"]:
                    rows.append((sym, float(mom)))
            except Exception:
                continue
    if not rows:
        return ""
    rows.sort(key=lambda r: r[1], reverse=True)
    top = rows[: int(cfg["leaders"].get("top_n", 5))]
    lines = ["<b>Momentum leaders</b> (12-month return, skipping the latest month; only markets above their 200-day)"]
    lines += [f"{n}. {esc(sym)} {mom:+.0%}" for n, (sym, mom) in enumerate(top, 1)]
    lines.append("<i>Momentum works on average over many holdings, and can reverse sharply after a market fall.</i>")
    return "\n".join(lines)


def cmd_leaders(cfg: dict, args) -> int:
    text = leaders_text(cfg, args)
    if not text:
        print("No markets above their 200-day average right now, or no data.")
        return 0
    send_telegram(cfg, text, args)
    return 0


def cmd_status(cfg: dict, args) -> int:
    st = load_state(cfg)
    acct_ccy = cfg["account"]["currency"]
    ret = (float(st["equity"]) / float(st["start_equity"]) - 1.0) * 100.0
    lines = [f"<b>Paper account</b>: {fmt_money(float(st['equity']), acct_ccy)} ({ret:+.1f}% since start)"]
    for p in st["positions"]:
        if p["status"] == "open":
            lines.append(
                f"Open: {esc(p['symbol'])} {p['direction']} {p['setup']} from {p['entry_date']} at "
                f"{fmt_price(p['entry_price'], p['currency'])}, stop {fmt_price(p['stop'], p['currency'])}, {p['bars_held']} bars"
            )
        else:
            lines.append(f"Waiting to open: {esc(p['symbol'])} {p['setup']} (signal {p['signal_date']})")
    stats = summarise_r([c["r_multiple"] for c in st["closed"]])
    if stats["trades"]:
        lines.append(
            f"Closed: {stats['trades']} trades · {stats['win_rate']:.0%} won · average win {stats['avg_win']:+.2f}R · "
            f"average loss {stats['avg_loss']:+.2f}R · expectancy {stats['expectancy']:+.2f}R per trade · "
            f"worst run {stats['max_dd_r']:.1f}R"
        )
        for c in st["closed"][-5:]:
            lines.append(f"  {esc(c['symbol'])} {c['setup']} {c['r_multiple']:+.2f}R ({esc(c['exit_reason'])}, {c['exit_date']})")
    else:
        lines.append("No closed paper trades yet.")
    send_telegram(cfg, "\n".join(lines), args if getattr(args, "telegram", False) else argparse.Namespace(no_telegram=True))
    return 0


def run_backtest_symbol(ind, sigs, cfg, sym, interval, cost, min_score) -> list[Position]:
    trades: list[Position] = []
    idx = ind.index
    n = len(ind)
    cols = ["Open", "High", "Low", "Close", "sma5", "exit_lo", "exit_hi", "atr"]
    arr = {c: ind[c].to_numpy(dtype=float) for c in cols}
    for (setup, direction), (frame, _) in sigs.items():
        trig = frame["trig"].to_numpy(dtype=bool)
        score = frame["score"].to_numpy(dtype=float)
        pos: Position | None = None
        for i in range(n):
            date = bar_label(idx[i], interval)
            row = None
            if pos is not None:
                row = {c: arr[c][i] for c in cols}
                if pos.status == "pending" and not try_fill(pos, date, row, cfg):
                    pos = None
                if pos is not None and pos.status == "open" and step_bar(pos, date, row, cfg, cost):
                    trades.append(pos)
                    pos = None
            if pos is None and i < n - 1 and trig[i] and score[i] >= min_score and np.isfinite(arr["atr"][i]):
                pos = Position(
                    symbol=sym, setup=setup, direction=direction, signal_date=date,
                    signal_price=arr["Close"][i], atr_at_signal=arr["atr"][i], score=int(score[i]),
                )
        if pos is not None and pos.status == "open":
            close_position(pos, bar_label(idx[-1], interval), arr["Close"][-1], "still open at the end of the data", cost)
            trades.append(pos)
    return trades


def time_machine(ind: pd.DataFrame, setup: str, direction: str, cfg: dict, replays: int | None = None) -> dict | None:
    """Replays the trade thousands of times. Each replay builds the next bars by drawing real daily bars
    (open, high, low and close as ratios to the previous close) from this market's own recent history,
    then runs the exact same stop and exit rules. A simulation, not a prediction."""
    tc = cfg.get("timemachine", {})
    if direction != "long" or len(ind) < 120:
        return None
    n = int(replays or tc.get("replays", 10000))
    horizon = int(tc.get("horizon_bars", 60))
    hist = ind.tail(int(tc.get("lookback_bars", 504)) + 1)
    pc = hist["Close"].shift(1)
    ratios = np.column_stack([(hist[c] / pc).to_numpy() for c in ("Open", "High", "Low", "Close")])[1:]
    ratios = ratios[np.isfinite(ratios).all(axis=1)]
    if len(ratios) < 60:
        return None
    s = cfg["setups"]
    cost = float(cfg["backtest"]["cost_per_side_pct"]) / 100.0
    rng = np.random.default_rng(int(tc.get("seed", 19)))
    pick = ratios[rng.integers(0, len(ratios), size=(n, horizon))]
    last_close = float(ind["Close"].iloc[-1])
    risk = stop_multiple(setup, cfg) * float(ind["atr"].iloc[-1])
    if not (risk > 0):
        return None
    m = int(s["breakout_exit_lookback"])
    lows = np.tile(ind["Low"].tail(m).to_numpy(), (n, 1))
    closes = np.tile(ind["Close"].tail(5).to_numpy(), (n, 1))
    prev = np.full(n, last_close)
    entry = prev * pick[:, 0, 0]
    stop = entry - risk
    init_stop = stop.copy()
    alive = np.ones(n, bool)
    flag = np.zeros(n, bool)
    exit_px = np.full(n, np.nan)
    stopped = np.zeros(n, bool)
    bars = np.zeros(n, int)
    for t in range(horizon):
        r = pick[:, t, :]
        o, c = prev * r[:, 0], prev * r[:, 3]

        lo = np.minimum(prev * r[:, 2], np.minimum(o, c))
        if t == 0:
            o = entry
        go = alive & flag
        exit_px[go] = o[go]
        alive &= ~go
        gap = alive & (t > 0) & (o <= stop)
        exit_px[gap] = o[gap]
        stopped |= gap & (stop <= init_stop)
        alive &= ~gap
        hit = alive & (lo <= stop)
        exit_px[hit] = stop[hit]
        stopped |= hit & (stop <= init_stop)
        alive &= ~hit
        bars[alive] += 1
        lows = np.column_stack([lows[:, 1:], lo])
        closes = np.column_stack([closes[:, 1:], c])
        if setup == "breakout":
            stop = np.where(alive, np.maximum(stop, lows.min(axis=1)), stop)
        else:
            flag |= alive & ((c > closes.mean(axis=1)) | (bars >= int(s["pullback_max_hold_bars"])))
        prev = c
        if not alive.any():
            break
    exit_px[alive] = prev[alive]
    rmult = (exit_px * (1 - cost) - entry * (1 + cost)) / risk
    return {
        "replays": n, "horizon": horizon, "profit": float((rmult > 0).mean()), "stopped": float(stopped.mean()),
        "open_at_end": float(alive.mean()), "avg_r": float(rmult.mean()), "median_r": float(np.median(rmult)),
        "p10": float(np.percentile(rmult, 10)), "p90": float(np.percentile(rmult, 90)), "avg_bars": float(bars.mean()),
    }


def time_machine_line(tm: dict | None) -> str | None:
    if not tm:
        return None
    return (f"Time machine ({tm['replays']:,} replays from this market's own recent bars): "
            f"{tm['profit']:.0%} ended in profit, {tm['stopped']:.0%} hit the first stop, average {tm['avg_r']:+.2f}R, "
            f"worst 10% {tm['p10']:+.1f}R or less, best 10% {tm['p90']:+.1f}R or more. A simulation, not a promise.")


def risk_check(st: dict, cfg: dict, new_risk: float) -> tuple[bool, str]:
    """PASS or BLOCK for a new trade, against your limits. Uses the paper account."""
    rc = cfg.get("risk", {})
    eq = float(st["equity"])
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    week_start = (now - pd.Timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    closed = st.get("closed", [])
    day_pnl = sum(float(c.get("pnl", 0)) for c in closed if str(c.get("exit_date", ""))[:10] == today)
    week_pnl = sum(float(c.get("pnl", 0)) for c in closed if str(c.get("exit_date", ""))[:10] >= week_start)
    if day_pnl <= -eq * float(rc.get("daily_loss_limit_pct", 2)) / 100:
        return False, f"daily loss limit reached ({fmt_money(day_pnl, cfg['account']['currency'])} today)"
    if week_pnl <= -eq * float(rc.get("weekly_loss_limit_pct", 5)) / 100:
        return False, f"weekly loss limit reached ({fmt_money(week_pnl, cfg['account']['currency'])} this week)"
    pend_risk = eq * float(cfg["account"]["risk_per_trade_pct"]) / 100
    open_risk = sum(float(p.get("risk_amount") or pend_risk) for p in st["positions"])
    if open_risk + new_risk > eq * float(rc.get("max_open_risk_pct", 5)) / 100 + 1e-9:
        return False, f"too much already at risk ({fmt_money(open_risk, cfg['account']['currency'])} in open trades)"
    new_today = sum(1 for p in st["positions"] if p.get("status") == "pending")
    if new_today >= int(rc.get("max_new_trades_per_day", 3)):
        return False, "already at the maximum new trades for today"
    if len(st["positions"]) >= int(cfg["paper"]["max_open_positions"]):
        return False, "at the maximum number of open trades"
    return True, "within all your limits"


def setup_history(sym, setup, direction, cfg, interval, bench_sym, csv_dir) -> dict | None:
    """How this exact setup (at the alert score) has done on this market before: the honest-odds check."""
    hc = cfg.get("history", {})
    if not hc.get("enabled", True):
        return None
    try:
        period = hc.get("period", "10y")
        df, _ = get_data(sym, interval, period, csv_dir)
        if len(df) < 300:
            return None
        ind = add_indicators(df, cfg)
        bench_df = None
        if bench_sym:
            try:
                bench_df, _ = get_data(bench_sym, interval, period, csv_dir)
            except Exception:
                bench_df = None
        sigs = compute_signals(ind, align_benchmark(ind, bench_df), cfg, sym, bench_sym)
        if (setup, direction) not in sigs:
            return None
        cost = float(cfg["backtest"]["cost_per_side_pct"]) / 100.0
        trades = run_backtest_symbol(ind, {(setup, direction): sigs[(setup, direction)]}, cfg, sym, interval,
                                     cost, float(cfg["scan"]["alert_min_score"]))
        closed = [t for t in trades if t.exit_reason != "still open at the end of the data"]
        out = summarise_r([t.r_multiple for t in closed])
        out["years"] = (ind.index[-1] - ind.index[0]).days / 365.25
        return out
    except Exception:
        return None


def history_line(sym: str, st: dict | None, cfg: dict) -> str | None:
    if not st:
        return None
    yrs = max(1, round(st.get("years", 0)))
    n = st.get("trades", 0)
    if n < int(cfg.get("history", {}).get("min_trades", 5)):
        return f"Past record on {sym}: only {n} similar signal{'s' if n != 1 else ''} in {yrs} years, too few to judge."
    return (
        f"Past record on {sym}: {n} similar signals (score {cfg['scan']['alert_min_score']}+) in {yrs} years, "
        f"{st['win_rate']:.0%} won, average {st['expectancy']:+.2f}R a trade after costs. A reality check, not a promise."
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    for r in rows:
        out.append("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    return "\n".join(out)


def _stats_row(label: str, st: dict) -> list[str]:
    if not st.get("trades"):
        return [label, "0", "-", "-", "-", "-", "-", "-"]
    pf = st["profit_factor"]
    return [
        label,
        str(st["trades"]),
        f"{st['win_rate']:.0%}",
        f"{st['avg_win']:+.2f}",
        f"{st['avg_loss']:+.2f}",
        f"{st['expectancy']:+.3f}",
        "inf" if pf == float("inf") else f"{pf:.2f}",
        f"{st['max_dd_r']:.1f}",
    ]


def cmd_backtest(cfg: dict, args) -> int:
    interval = cfg["scan"]["interval"]
    history = cfg["backtest"]["history"]
    cost = float(cfg["backtest"]["cost_per_side_pct"]) / 100.0
    min_score = float(cfg["backtest"]["min_score"])
    all_trades: list[Position] = []
    bh_rows = []
    first_dates, last_dates = [], []
    for bench_sym, symbols in iter_watchlist(cfg, args):
        bench_df = None
        if bench_sym:
            try:
                bench_df, _ = get_data(bench_sym, interval, history, args.csv_dir)
            except Exception as exc:
                print(f"Benchmark {bench_sym}: {exc}")
        for sym in symbols:
            try:
                df, meta = get_data(sym, interval, history, args.csv_dir)
            except Exception as exc:
                print(f"{sym}: {exc}")
                continue
            if len(df) < 260:
                print(f"{sym}: only {len(df)} bars, skipped")
                continue
            ind = add_indicators(df, cfg)
            bench = align_benchmark(ind, bench_df)
            sigs = compute_signals(ind, bench, cfg, sym, bench_sym)
            trades = run_backtest_symbol(ind, sigs, cfg, sym, interval, cost, min_score)
            all_trades.extend(trades)
            start = ind.index[200] if len(ind) > 200 else ind.index[0]
            c = ind["Close"].loc[start:]
            dd = float((c / c.cummax() - 1.0).min())
            bh_rows.append([sym, f"{c.index[0]:%Y-%m-%d}", f"{c.index[-1]:%Y-%m-%d}", f"{(c.iloc[-1] / c.iloc[0] - 1.0):+.0%}", f"{dd:.0%}", str(len(trades))])
            first_dates.append(c.index[0])
            last_dates.append(c.index[-1])
    if not all_trades:
        print("No trades were generated. Try more symbols or a longer history.")
        return 1

    cut = None
    if first_dates:
        t0, t1 = min(first_dates), max(last_dates)
        cut = t0 + (t1 - t0) * float(cfg["backtest"]["in_sample_share"])
    risk_pct = float(cfg["account"]["risk_per_trade_pct"])
    headers = ["Group", "Trades", "Won", "Avg win R", "Avg loss R", "Expectancy R", "Profit factor", "Worst run R"]
    print(f"\nBacktest: {len(bh_rows)} markets, {interval} bars, costs {cost * 100:.2f}% each way, "
          f"entries at the next open after the signal.\n")
    for (setup, direction) in sorted({(t.setup, t.direction) for t in all_trades}):
        ts = [t for t in all_trades if t.setup == setup and t.direction == direction]
        ts.sort(key=lambda t: t.exit_date)
        rows = [_stats_row("All signals", summarise_r([t.r_multiple for t in ts]))]
        for lo, hi, lab in ((0, 50, "Score under 50"), (50, 70, "Score 50 to 69"), (70, 80, "Score 70 to 79"), (80, 101, "Score 80+")):
            rows.append(_stats_row(lab, summarise_r([t.r_multiple for t in ts if lo <= t.score < hi])))
        if cut is not None:
            ins = [t.r_multiple for t in ts if pd.Timestamp(t.signal_date) < cut]
            outs = [t.r_multiple for t in ts if pd.Timestamp(t.signal_date) >= cut]
            rows.append(_stats_row(f"Signals before {cut:%b %Y}", summarise_r(ins)))
            rows.append(_stats_row(f"Signals from {cut:%b %Y}", summarise_r(outs)))
        total = summarise_r([t.r_multiple for t in ts])
        print(f"== {SETUP_TITLES[setup]} ({direction}) ==")
        print(_table(headers, rows))
        print(f"Taking every signal at {risk_pct:g}% risk would have changed the account by about "
              f"{total['total_r'] * risk_pct:+.0f}% over the period (simple sum, before compounding and overlap).\n")
    print("Buy and hold over the same period, for comparison:")
    print(_table(["Market", "From", "To", "Return", "Worst fall", "Trades"], bh_rows))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    out = STATE_DIR / "backtest_trades.csv"
    pd.DataFrame([asdict(t) for t in all_trades]).to_csv(out, index=False)
    print(f"\nEvery trade is saved in {out.relative_to(BASE_DIR) if out.is_relative_to(BASE_DIR) else out}")
    print("How to read this: look for positive expectancy after costs in BOTH periods, from at least 100 trades,")
    print("and higher scores doing better than lower ones. If you change settings to improve these numbers,")
    print("judge the change on the later period only. Past results do not guarantee future ones.")
    return 0


def cmd_test_telegram(cfg: dict, args) -> int:
    if not cfg["telegram"].get("token") or not cfg["telegram"].get("chat_id"):
        print("Telegram is not set up yet: add your token and chat ID to config.toml (or as environment variables).")
        return 1
    ok = send_telegram(cfg, "<b>Setup scanner</b>: test message. If you can read this, alerts will reach your phone.", args)
    print("Sent." if ok else "Sending failed: check the token and chat ID.")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Faster checks during market hours, movers, volatility, news and events
# ---------------------------------------------------------------------------


def watch_state_path() -> Path:
    return STATE_DIR / "watch.json"


def load_watch_state() -> dict:
    p = watch_state_path()
    d: dict = {}
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            d = {}
    d.setdefault("sent", {})
    return d


def save_watch_state(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.now(timezone.utc) - pd.Timedelta(days=4)).isoformat()
    d["sent"] = {k: v for k, v in d.get("sent", {}).items() if v >= cutoff}
    tmp = watch_state_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    tmp.replace(watch_state_path())


def watch_once(cfg: dict, args) -> int:
    """One quick pass: big moves today, breakouts in progress, paper stops hit, fresh news on what you hold."""
    st = load_state(cfg)
    ws = load_watch_state()
    wc = cfg["watch"]
    news_on = bool(cfg["news"].get("enabled", True))
    alert_min = int(cfg["scan"]["alert_min_score"])
    now = datetime.now(timezone.utc)
    stamp, day = now.isoformat(), now.strftime("%Y-%m-%d")
    held = {p["symbol"]: p for p in st["positions"] if p["status"] == "open"}
    watch = iter_watchlist(cfg, args)
    extra = sorted(set(held) - {s for _, syms in watch for s in syms})
    if extra:
        watch.append(("", extra))
    msgs, checked, seen = [], 0, set()
    for bench_sym, symbols in watch:
        bench_live = None
        if bench_sym:
            try:
                bench_live, _ = get_data(bench_sym, "1d", "2y", args.csv_dir, live=True)
            except Exception:
                bench_live = None
        for sym in symbols:
            if sym in seen:
                continue
            seen.add(sym)
            try:
                df, meta = get_data(sym, "1d", "2y", args.csv_dir, live=True)
            except Exception:
                continue
            if len(df) < 60 or not traded_today(df, meta):
                continue  # that market hasn't traded yet today
            checked += 1
            ind = add_indicators(df, cfg)
            last, prev = ind.iloc[-1], ind.iloc[-2]
            price, prev_close = float(last["Close"]), float(prev["Close"])
            if prev_close <= 0:
                continue
            ccy = meta["currency"]
            chg = (price / prev_close - 1.0) * 100.0
            atr_prev = float(prev["atr"]) if pd.notna(prev["atr"]) else 0.0
            in_atrs = abs(price - prev_close) / atr_prev if atr_prev > 0 else 0.0

            # 1) A big move today (the bot's version of a "most volatile" or "top movers" list)
            big = abs(chg) >= float(wc["big_move_pct"]) or (in_atrs >= float(wc["big_move_atr"]) and abs(chg) >= 1.0)
            key = f"move|{sym}|{day}"
            if big and key not in ws["sent"]:
                lines = [f"<b>BIG MOVE: {esc(sym)} {chg:+.1f}% today</b>, now {fmt_price(price, ccy)}"]
                if in_atrs:
                    lines.append(f"That's about {in_atrs:.1f}x a normal day's move for this market.")
                heads = get_headlines(sym, 3, 24) if news_on else []
                if heads:
                    lines.append("Latest news:")
                    lines.extend(headline_lines(heads))
                elif news_on:
                    lines.append("No headlines in the last 24 hours. A move with no news is worth checking too.")
                if sym in held:
                    lines.append("You hold this in the paper account.")
                lines.append("<i>Not a buy or sell signal on its own: big moves often reverse.</i>")
                msgs.append("\n".join(lines))
                ws["sent"][key] = stamp

            # 2) A breakout happening right now (only confirmed if it closes there)
            if wc.get("breakouts_in_progress", True) and sym not in held:
                sigs = compute_signals(ind, align_benchmark(ind, bench_live), cfg, sym, bench_sym)
                i = len(ind) - 1
                for (setup, direction), (frame, _) in sigs.items():
                    if setup != "breakout" or not bool(frame["trig"].iloc[i]):
                        continue
                    score = int(frame["score"].iloc[i])
                    key = f"bo|{sym}|{direction}|{day}"
                    if score >= alert_min and key not in ws["sent"]:
                        side = "high" if direction == "long" else "low"
                        msgs.append(
                            f"<b>Breakout in progress: {esc(sym)}</b> is through its "
                            f"{int(cfg['setups']['breakout_lookback'])}-day {side} at {fmt_price(price, ccy)} "
                            f"({chg:+.1f}% today), scoring {score}/100 so far.\n"
                            "It only counts if it closes there: tonight's scan confirms it and sends the full alert. "
                            "Volume is still building, so the score can change."
                        )
                        ws["sent"][key] = stamp

            # 3) A paper trade's stop hit during the day
            if wc.get("stop_warnings", True) and sym in held:
                pos = held[sym]
                long = pos["direction"] == "long"
                extreme = float(last["Low"]) if long else float(last["High"])
                hit = extreme <= float(pos["stop"]) if long else extreme >= float(pos["stop"])
                key = f"stop|{sym}|{day}"
                if hit and key not in ws["sent"]:
                    msgs.append(
                        f"<b>Stop hit: {esc(sym)}</b> traded at {fmt_price(extreme, ccy)}, through the paper stop at "
                        f"{fmt_price(float(pos['stop']), ccy)}. Tonight's scan records the exit. "
                        "With real money, this is where your stop order would have sold."
                    )
                    ws["sent"][key] = stamp

            # 4) Fresh headlines on anything the paper account holds
            if wc.get("held_news", True) and news_on and sym in held:
                fresh = [p for p in get_headlines(sym, 5, 12) if f"news|{p['id']}" not in ws["sent"]]
                if fresh:
                    msgs.append("\n".join([f"<b>News on {esc(sym)}</b> (in your paper account):"] + headline_lines(fresh[:3])))
                    for p in fresh:
                        ws["sent"][f"news|{p['id']}"] = stamp
    for m in msgs:
        send_telegram(cfg, m, args)
    if not msgs:
        print(f"Watch check {now:%H:%M} UTC: {checked} market{'s' if checked != 1 else ''} open today, nothing new.")
    save_watch_state(ws)
    return len(msgs)


def cmd_watch(cfg: dict, args) -> int:
    global _EVENTS_CACHE
    every = float(getattr(args, "every", 0) or 0)
    while True:
        try:
            watch_once(cfg, args)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"Watch check failed: {exc}")
        if every <= 0:
            return 0
        print(f"Next check in {every:g} minutes. Press Ctrl+C to stop.")
        try:
            time.sleep(every * 60)
        except KeyboardInterrupt:
            return 0
        _DATA_CACHE.clear()  # fresh prices for the next pass
        _EVENTS_CACHE = None


def cmd_movers(cfg: dict, args) -> int:
    movers = fetch_movers(dict(cfg, movers=dict(cfg["movers"], enabled=True)))
    if not movers:
        print("Couldn't get today's movers from Yahoo Finance just now. Try again in a minute.")
        return 1
    alert_min = int(cfg["scan"]["alert_min_score"])
    bench_cache: dict = {}
    lines = ["<b>Today's movers, checked against the bot's rules</b>"]
    passed = 0
    current = None
    for m in movers:
        if m["list"] != current:
            current = m["list"]
            lines += ["", f"<b>{esc(current)}</b>"]
        sym, bench_sym = m["symbol"], mover_benchmark(m, cfg)
        try:
            df, _ = get_data(sym, "1d", cfg["scan"]["history"])
            if len(df) < 210:
                status = "too new to judge"
            else:
                if bench_sym not in bench_cache:
                    try:
                        bench_cache[bench_sym] = get_data(bench_sym, "1d", cfg["scan"]["history"])[0]
                    except Exception:
                        bench_cache[bench_sym] = None
                ind = add_indicators(df, cfg)
                sigs = compute_signals(ind, align_benchmark(ind, bench_cache[bench_sym]), cfg, sym, bench_sym)
                lr = ind.iloc[-1]
                trend = "uptrend" if pd.notna(lr["sma200"]) and lr["Close"] > lr["sma200"] else "below its 200-day"
                swing = float(lr["atr"]) / float(lr["Close"]) * 100.0 if lr["Close"] > 0 else 0.0
                live = [(SETUP_TITLES[s].lower(), int(fr["score"].iloc[-1])) for (s, _d), (fr, _c) in sigs.items() if bool(fr["trig"].iloc[-1])]
                status = f"{trend}, swings ~{swing:.1f}% a day, "
                status += ("setup: " + ", ".join(f"{n} {sc}/100" for n, sc in live)) if live else "no setup"
                if any(sc >= alert_min for _, sc in live):
                    passed += 1
        except Exception:
            status = "no data"
        chg = m.get("change_pct")
        chg_txt = f"{chg:+.1f}%" if isinstance(chg, (int, float)) else ""
        lines.append(f"{esc(sym)} {chg_txt} · {esc(str(m['name'])[:26])} · {esc(status)}")
    lines += ["", f"{passed} of {len(movers)} pass the rules right now.",
              "<i>Most big movers don't. Research finds shares that grab attention or swing wildly "
              "have tended to do worse afterwards, on average.</i>"]
    output(cfg, "\n".join(lines), args)
    return 0


def cmd_volatile(cfg: dict, args) -> int:
    pairs = [(b, s) for b, syms in iter_watchlist(cfg, args) for s in syms]
    if not getattr(args, "symbols", None):
        pairs += [(mover_benchmark(m, cfg), m["symbol"]) for m in fetch_movers(cfg)]
    rows, seen = [], set()
    for _, sym in pairs:
        if sym in seen:
            continue
        seen.add(sym)
        try:
            df, _ = get_data(sym, "1d", "1y", args.csv_dir)
            if len(df) < 30:
                continue
            ind = add_indicators(df, cfg)
            lr = ind.iloc[-1]
            if not (pd.notna(lr["atr"]) and lr["Close"] > 0):
                continue
            month = float(lr["Close"] / ind["Close"].iloc[-22] - 1.0) * 100.0 if len(ind) > 22 else float("nan")
            trend = "uptrend" if pd.notna(lr["sma200"]) and lr["Close"] > lr["sma200"] else "downtrend"
            rows.append((sym, float(lr["atr"]) / float(lr["Close"]) * 100.0, month, trend))
        except Exception:
            continue
    if not rows:
        print("No price data available right now.")
        return 1
    rows.sort(key=lambda r: r[1], reverse=True)
    lines = ["<b>Most volatile right now</b> (average daily swing, last 14 days)"]
    for n, (sym, swing, month, trend) in enumerate(rows[:12], 1):
        mtxt = f"{int(round(month)):+d}% this month" if month == month else ""
        lines.append(f"{n}. {esc(sym)} ~{swing:.1f}% a day · {mtxt} · {trend}")
    lines.append("<i>Higher means bigger swings both ways, not better odds. The bot buys fewer shares of volatile "
                 "markets so a stop-out still costs about the same.</i>")
    output(cfg, "\n".join(lines), args)
    return 0


def cmd_news(cfg: dict, args) -> int:
    lines = []
    if getattr(args, "symbols", None):
        for sym in [s.strip() for s in args.symbols.split(",") if s.strip()]:
            heads = get_headlines(sym, 6, float(cfg["news"].get("max_age_hours", 72)))
            lines += [f"<b>{esc(sym)}</b>"] + (headline_lines(heads) or ["No headlines in the last few days."]) + [""]
    else:
        lines.append("<b>Market headlines</b> (last 24 hours)")
        lines += headline_lines(market_headlines(6, 24)) or ["None found just now."]
        lines += ["", "<b>Crypto news</b> (last 24 hours)"]
        lines += headline_lines(crypto_headlines(cfg, 5)) or ["None found just now."]
        lines += ["", "<b>Big events, next 7 days</b> (UK time)"]
        lines += [esc(event_text(e)) for e in upcoming_events(cfg, 7)] or ["None found."]
    output(cfg, "\n".join(lines).strip(), args)
    return 0


def cmd_events(cfg: dict, args) -> int:
    evs = upcoming_events(cfg, 14)
    lines = ["<b>Big scheduled events, next 14 days</b> (UK time)"]
    lines += [esc(event_text(e)) for e in evs] or ["None found."]
    lines.append("<i>Prices can jump on these days. Alerts warn you when one is close.</i>")
    output(cfg, "\n".join(lines), args)
    return 0


def cmd_resend(cfg: dict, args) -> int:
    st = load_state(cfg)
    texts = recap_positions(st, cfg, args.csv_dir)
    if not texts:
        print("No paper trades waiting or open.")
        return 0
    for t in texts:
        send_telegram(cfg, t, args)
    return 0


def cmd_timemachine(cfg: dict, args) -> int:
    if not getattr(args, "symbols", None):
        print("Say which market: python bot.py timemachine --symbols AAPL")
        return 1
    for sym in [x.strip() for x in args.symbols.split(",") if x.strip()]:
        try:
            df, _ = get_data(sym, "1d", cfg["scan"]["history"], args.csv_dir)
            ind = add_indicators(df, cfg)
        except Exception as exc:
            print(f"{sym}: {exc}")
            continue
        lines = [f"<b>Time machine: {esc(sym)}</b>, if you bought at the next open today"]
        for setup in ("breakout", "pullback"):
            tm = time_machine(ind, setup, "long", cfg)
            if tm:
                lines.append(f"{SETUP_TITLES[setup]} rules: {tm['profit']:.0%} in profit, {tm['stopped']:.0%} stopped, "
                             f"average {tm['avg_r']:+.2f}R, median {tm['median_r']:+.2f}R, "
                             f"10th to 90th percentile {tm['p10']:+.1f}R to {tm['p90']:+.1f}R, held {tm['avg_bars']:.0f} bars on average")
        lines.append("<i>Built from this market's own last two years of daily bars. A reality check, not a prediction.</i>")
        output(cfg, "\n".join(lines), args)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for trading setups, send alerts, paper-trade, backtest.")
    parser.add_argument("command", choices=["scan", "watch", "movers", "volatile", "news", "events",
                                            "timemachine", "resend", "backtest", "status", "leaders", "test-telegram"])
    parser.add_argument("--config", default=str(BASE_DIR / "config.toml"), help="settings file (default: config.toml)")
    parser.add_argument("--symbols", help="comma-separated symbols to use instead of the watchlist")
    parser.add_argument("--benchmark", default="", help="benchmark symbol to use with --symbols")
    parser.add_argument("--csv-dir", default=None, help="read prices from CSV files in this folder instead of downloading")
    parser.add_argument("--no-telegram", action="store_true", help="print messages here instead of sending them")
    parser.add_argument("--telegram", action="store_true", help="send the report to Telegram as well (status, movers, volatile, news, events)")
    parser.add_argument("--every", type=float, default=0, help="watch: keep checking every this many minutes")
    args = parser.parse_args(argv)
    global OFFLINE
    OFFLINE = bool(args.csv_dir)
    cfg = load_config(args.config)
    commands = {
        "scan": cmd_scan,
        "watch": cmd_watch,
        "movers": cmd_movers,
        "volatile": cmd_volatile,
        "news": cmd_news,
        "events": cmd_events,
        "timemachine": cmd_timemachine,
        "resend": cmd_resend,
        "backtest": cmd_backtest,
        "status": cmd_status,
        "leaders": cmd_leaders,
        "test-telegram": cmd_test_telegram,
    }
    return commands[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
