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
  python bot.py analyse          read the market: trend, momentum, fear, breadth, long or short
  python bot.py pulse --every 5  read gold, SPY, QQQ, IWM, FTSE and Bitcoin every 5 minutes: best approach, signals
  python bot.py insiders         fetch company insiders' share purchases from the SEC (to copy)
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
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import charts
import intraday
import trump

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
    "copy": "Copy the insiders",
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
        "pullback_exit": "bounce",
        "pullback_trail_max_bars": 63,
        "target_r": 2.0,
        "volume_surge": 1.5,
        "adx_trending": 20.0,
        "squeeze_pctile": 0.25,
        "overextended_atr": 3.0,
        "copy_stop_atr": 3.0,
        "copy_max_hold_bars": 63,
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
        "max_daily_swing_pct": 15.0,
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
        "low_confidence_budget_pct": 50.0,
    },
    "charts": {"enabled": True},
    "trump": {"enabled": True, "every_minutes": 5, "max_markets": 4},
    "briefing": {"enabled": True},
    "sizing": {"enabled": True, "low_mult": 0.5, "high_mult": 1.5, "high_points": 3, "low_points": 0, "max_risk_pct": 3.0},
    "analysis": {
        "enabled": True,
        "send_with_scan": True,
        "markets": ["SPY", "QQQ", "IWM", "^FTSE", "BTC-USD", "GC=F"],
        "fear_gauge": "^VIX",
    },
    "pulse": {
        "markets": ["GC=F", "SPY", "QQQ", "IWM", "^FTSE", "BTC-USD"],
        "every_minutes": 5,
        "send_open_brief": True,
        "send_changes": True,
        "confirm_bars": 3,
        "max_changes_per_market": 3,
        "send_signals": True,
        "max_signals_per_market": 4,
        "min_trades": 15,
        "min_edge_r": 0.1,
        "record_every_minutes": 60,
        "cost_pct": 0.02,
        "costs": {"SPY": 0.005, "QQQ": 0.005, "IWM": 0.01, "GC=F": 0.01, "^FTSE": 0.01, "BTC-USD": 0.05},
        "sessions": {},
        "start_scalper": True,
        "run_watch": True,
        "watch_every_minutes": 30,
    },
    "copy": {
        "enabled": True,
        "live": True,
        "live_every_minutes": 10,
        "live_pages": 4,
        "skip_routine": True,
        "sec_user_agent": "",
        "fetch_days": 5,
        "max_filings_per_run": 6000,
        "keep_days": 120,
        "cluster_days": 30,
        "max_signal_age_days": 7,
        "min_buy_usd": 10000,
        "min_total_usd": 50000,
        "big_buy_usd": 100000,
        "big_total_usd": 250000,
        "min_insiders": 2,
        "skip_planned": True,
        "include_big_holders": False,
        "min_price_usd": 5.0,
        "min_dollar_volume": 1000000,
        "max_chase_pct": 15,
        "block_chase_pct": 30,
        "benchmark": "SPY",
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


_NEWS_ERRORS: set = set()


def _news_note(source: str, exc) -> None:
    """Says once per run when a news source fails, instead of quietly reporting 'no news'."""
    if source not in _NEWS_ERRORS:
        _NEWS_ERRORS.add(source)
        print(f"News source {source} failed: {exc}")


def _rss_items(url: str, source: str) -> list[dict]:
    import requests

    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (setup-scanner-bot)"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:
        _news_note(source, exc)
        return []
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        publisher = (src.text or "").strip() if src is not None else source
        if source == "Google News" and " - " in title:  # Google appends " - Publisher" to every title
            title, publisher = title.rsplit(" - ", 1)[0].strip(), title.rsplit(" - ", 1)[1].strip()
        when = None
        try:
            when = pd.Timestamp(it.findtext("pubDate") or "")
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
        except Exception:
            when = None
        out.append({"title": title, "publisher": publisher, "url": link, "when": when, "id": link or title})
    return out


NEWS_JUNK = re.compile(r"(stock|share)s? (price|quote)s?[,:]|stock quote|quote,? (&|and) history|stock forecasts?\b|"
                       r"symbol__|price, news|share chat|stock (price )?today\b", re.I)
COMPANY_NAMES: dict[str, str] = {  # also filled from the movers lists and insider filings, for better news searches
    "AZN.L": "AstraZeneca", "SHEL.L": "Shell", "HSBA.L": "HSBC", "ULVR.L": "Unilever", "RR.L": "Rolls-Royce",
    "BARC.L": "Barclays", "BP.L": "BP", "LLOY.L": "Lloyds", "GSK.L": "GSK", "RIO.L": "Rio Tinto", "VOD.L": "Vodafone",
    "TSCO.L": "Tesco", "BA.L": "BAE Systems", "GLEN.L": "Glencore", "NG.L": "National Grid", "DGE.L": "Diageo",
    "JPM": "JPMorgan", "XOM": "Exxon Mobil", "META": "Meta Platforms", "GOOGL": "Alphabet",
}


def news_query(symbol: str) -> str:
    names = {"^GSPC": "S&P 500", "^FTSE": "FTSE 100", "^NDX": "Nasdaq 100", "GC=F": "gold price", "SI=F": "silver price",
             "BZ=F": "Brent oil", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
             "GBPUSD=X": "pound dollar", "EURUSD=X": "euro dollar", "SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2000"}
    if symbol in names:
        return names[symbol]
    name = COMPANY_NAMES.get(symbol.upper())
    if name:
        name = re.sub(r"\b(inc|corp|corporation|plc|ltd|limited|holdings?|co|company|group|the)\b\.?", "", name, flags=re.I)
        name = re.sub(r"[^\w&' -]", " ", name).strip()
        if len(name) >= 3:
            return f'"{name}" stock' if not symbol.endswith(".L") else f'"{name}" shares'
    if symbol.endswith(".L"):
        return f"{symbol[:-2]} LON shares"
    if len(symbol) <= 3:
        return f'"NYSE:{symbol}" OR "NASDAQ:{symbol}" OR "({symbol})" stock'  # short tickers are common words
    return f"{symbol} stock"


def get_headlines(symbol: str, n: int = 3, max_age_hours: float = 72) -> list[dict]:
    """The newest headlines for one market, newest first, from Yahoo Finance (two ways) and Google News,
    with duplicates removed. If a source fails, the run log says so."""
    if OFFLINE:
        return []
    from urllib.parse import quote_plus

    raw: list[dict] = []
    try:
        import yfinance as yf

        for it in yf.Ticker(symbol).get_news(count=max(10, n)) or []:
            p = _parse_news_item(it)
            if p:
                raw.append(p)
    except Exception as exc:
        _news_note("Yahoo (yfinance)", exc)  # Yahoo often blocks cloud servers like GitHub's
    if len(raw) < n:
        raw += _rss_items(f"https://news.google.com/rss/search?q={quote_plus(news_query(symbol))}+when:3d"
                          "&hl=en-GB&gl=GB&ceid=GB:en", "Google News")
    if len(raw) < n:
        # Yahoo's RSS feed mixes in general market stories: for a share, keep only headlines that name it
        root = symbol.split(".")[0].split("-")[0].upper()
        general = symbol.startswith("^") or "=" in symbol or symbol in {"SPY", "QQQ", "IWM"} or "-USD" in symbol
        for p in _rss_items(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(symbol)}&region=US&lang=en-US",
                            "Yahoo RSS"):
            if general or re.search(rf"\b{re.escape(root)}\b", p["title"]):
                raw.append(p)
    now = pd.Timestamp.now(tz="UTC")
    items, seen = [], set()
    for p in raw:
        if p["when"] is not None and (now - p["when"]).total_seconds() > max_age_hours * 3600:
            continue
        if NEWS_JUNK.search(p["title"]):
            continue  # share-price pages, not news
        k = re.sub(r"[^a-z0-9]", "", p["title"].lower())[:60]
        if k in seen:
            continue
        seen.add(k)
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
# Copy the insiders: directors and bosses buying their own company's shares
# ---------------------------------------------------------------------------
# By US law, company insiders must report every trade in their own company's shares to the SEC
# within two business days (Form 4). What the research says, and what the bot does with it:
#  - Open-market PURCHASES with their own money are the trades worth copying. Sales say much less
#    (people sell for tax, houses and diversification), so sales only count against a share.
#  - "Routine" insiders, who trade in the same month every year, carry no information; the
#    "opportunistic" rest beat the market by about 0.8% a month (Cohen, Malloy & Pomorski, Journal of
#    Finance 2012). The bot checks each buyer's last three years of filings and skips routine ones.
#  - Several insiders buying together, the CEO or CFO buying, big stake increases and buying after a
#    fall are the strongest versions. Trades under pre-arranged 10b5-1 plans are skipped.
#  - Speed matters: the bot reads EDGAR's live feed every few minutes during the day, plus the full
#    daily index each morning so nothing is missed.

SEC_ARCHIVES = "https://www.sec.gov/Archives/"
SEC_LIVE = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include"
            "&start={start}&count=100&output=atom")
_SEC_LAST = [0.0]
TOP_TITLES = re.compile(r"\b(CEO|CFO|COO|PRESIDENT|CHIEF EXECUTIVE|CHIEF FINANCIAL|CHIEF OPERATING|CHAIR)", re.I)


def sec_user_agent(cfg: dict) -> str:
    ua = os.environ.get("SEC_USER_AGENT") or str(cfg.get("copy", {}).get("sec_user_agent", "") or "")
    return ua.strip() or "setup-scanner-bot/1.0 personal-research"


def sec_get(url: str, cfg: dict, timeout: float = 30) -> str:
    """One SEC download, kept under the SEC's limit of 10 requests a second."""
    import requests

    err = None
    for attempt in range(4):
        wait = 0.125 - (time.time() - _SEC_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _SEC_LAST[0] = time.time()
        try:
            r = requests.get(url, headers={"User-Agent": sec_user_agent(cfg)}, timeout=timeout)
        except Exception as exc:
            err = exc
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.text
        if r.status_code == 404:
            raise FileNotFoundError(url)
        if r.status_code == 403:
            raise RuntimeError("the SEC refused the request (403). Put your name and email in copy.sec_user_agent "
                               "or the SEC_USER_AGENT secret, e.g. \"Jane Smith jane@example.com\"")
        err = f"HTTP {r.status_code}"
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"SEC download failed ({err})")


def accession_of(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".txt")


def parse_form_index(text: str) -> list[dict]:
    """EDGAR's daily form index: Form 4 filings only, one row per filing. Each filing is listed twice,
    under the company and under the insider, with different paths, so rows are matched by accession number."""
    out, seen, started = [], set(), False
    for line in text.splitlines():
        if not started:
            started = line.startswith("-----")
            continue
        parts = line.split()
        if len(parts) < 5 or parts[0] != "4":  # "4/A" amendments are skipped
            continue
        acc = accession_of(parts[-1])
        if acc in seen:
            continue
        seen.add(acc)
        out.append({"acc": acc, "cik": parts[-3], "filed": parts[-2], "path": parts[-1]})
    return out


def parse_live_feed(text: str) -> list[dict]:
    """EDGAR's 'latest filings' Atom feed: Form 4s only (the type filter also lets 424B2, 425... through)."""
    out, seen = [], set()
    for entry in re.findall(r"<entry>(.*?)</entry>", text, re.S):
        term = re.search(r'<category[^>]*term="([^"]+)"', entry)
        link = re.search(r"/Archives/edgar/data/(\d+)/(\d{18})/", entry)
        if not term or term.group(1).strip() != "4" or not link:
            continue
        d = link.group(2)
        acc = f"{d[:10]}-{d[10:12]}-{d[12:]}"
        if acc in seen:
            continue
        seen.add(acc)
        when = re.search(r"<updated>(\d{4}-\d{2}-\d{2})", entry)
        filed = when.group(1).replace("-", "") if when else datetime.now(timezone.utc).strftime("%Y%m%d")
        out.append({"acc": acc, "cik": link.group(1), "filed": filed, "path": f"edgar/data/{link.group(1)}/{acc}.txt"})
    return out


def _xv(node, path: str) -> str:
    el = node.find(path) if node is not None else None
    if el is None:
        return ""
    v = el.find("value")
    return ((v.text if v is not None else el.text) or "").strip()


def _truthy(x: str) -> bool:
    return x.strip().lower() in {"1", "true", "yes", "y"}


def _num(x: str) -> float:
    try:
        return float(x.replace(",", ""))
    except Exception:
        return float("nan")


def yahoo_symbol(raw: str) -> str:
    s = re.split(r"[\s,;]+", (raw or "").strip().upper())[0] if raw else ""
    s = s.replace(".", "-").replace("/", "-")
    if s in {"", "NONE", "NA", "N-A"} or not re.fullmatch(r"[A-Z][A-Z0-9-]{0,9}", s):
        return ""
    return s


def parse_form4(text: str, filed: str = "", path: str = "") -> list[dict]:
    """The open-market purchases and sales in one Form 4 filing, each side added up."""
    m = re.search(r"<ownershipDocument>.*?</ownershipDocument>", text, re.S)
    if not m:
        return []
    try:
        root = ET.fromstring(m.group(0))
    except ET.ParseError:
        return []
    sym = yahoo_symbol(_xv(root, "issuer/issuerTradingSymbol"))
    if not sym:
        return []
    sides = {"buy": {"shares": 0.0, "value": 0.0, "after": float("nan"), "dates": []},
             "sell": {"shares": 0.0, "value": 0.0, "after": float("nan"), "dates": []}}
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _xv(t, "transactionCoding/transactionCode")
        if code not in {"P", "S"}:  # P = bought on the open market, S = sold on the open market
            continue
        side = sides["buy" if code == "P" else "sell"]
        n = _num(_xv(t, "transactionAmounts/transactionShares"))
        px = _num(_xv(t, "transactionAmounts/transactionPricePerShare"))
        if not (np.isfinite(n) and np.isfinite(px) and n > 0 and px > 0):
            continue
        side["shares"] += n
        side["value"] += n * px
        own = _num(_xv(t, "postTransactionAmounts/sharesOwnedFollowingTransaction"))
        if np.isfinite(own):
            side["after"] = own  # the last row is the holding after all of that day's trades
        d = _xv(t, "transactionDate")
        if d:
            side["dates"].append(d[:10])
    if sides["buy"]["shares"] <= 0 and sides["sell"]["shares"] <= 0:
        return []
    names, titles = [], []
    director = officer = ten_pct = False
    owner_id = ""
    for o in root.findall("reportingOwner"):
        nm = _xv(o, "reportingOwnerId/rptOwnerName")
        owner_id = owner_id or _xv(o, "reportingOwnerId/rptOwnerCik") or nm
        names.append(nm)
        rel = o.find("reportingOwnerRelationship")
        director |= _truthy(_xv(rel, "isDirector"))
        officer |= _truthy(_xv(rel, "isOfficer"))
        ten_pct |= _truthy(_xv(rel, "isTenPercentOwner"))
        title = _xv(rel, "officerTitle")
        if title:
            titles.append(title)
    if filed and re.fullmatch(r"\d{8}", filed):
        filed = f"{filed[:4]}-{filed[4:6]}-{filed[6:]}"
    base = {
        "symbol": sym,
        "issuer": _xv(root, "issuer/issuerName"),
        "owner": " / ".join(n for n in names if n)[:80],
        "owner_id": owner_id,
        "title": ", ".join(titles)[:60] or ("Director" if director else ("10% owner" if ten_pct else "")),
        "director": director,
        "officer": officer,
        "ten_pct": ten_pct,
        "top": bool(TOP_TITLES.search(" ".join(titles))),
        "plan": _truthy(_xv(root, "aff10b5One")),  # ticked when the trade was pre-arranged under a 10b5-1 plan
        "filed": filed,
        "path": path,
        "acc": accession_of(path) if path else "",
    }
    out = []
    for kind, sd in sides.items():
        if sd["shares"] <= 0:
            continue
        after = sd["after"] if np.isfinite(sd["after"]) else 0.0
        before = after - sd["shares"] if kind == "buy" else after + sd["shares"]
        change = (sd["shares"] / before * 100.0) if before > 0 else 100.0
        out.append(dict(base, kind=kind, shares=sd["shares"], value=sd["value"], avg_price=sd["value"] / sd["shares"],
                        increase_pct=min(change, 1000.0) if kind == "buy" else 0.0,
                        trade_date=min(sd["dates"]) if sd["dates"] else filed))
    return out


def insiders_path() -> Path:
    return STATE_DIR / "insiders.json"


def load_insiders() -> dict:
    p = insiders_path()
    d: dict = {}
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            d = {}
    d.setdefault("days_done", [])
    d.setdefault("seen", {})
    d.setdefault("buys", [])
    d.setdefault("routine", {})
    d.setdefault("alerted", {})
    d.pop("partial", None)
    return d


def save_insiders(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = insiders_path().with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=0)
    tmp.replace(insiders_path())


def worth_checking(b: dict, cfg: dict) -> bool:
    """A purchase that could count towards copying (before the routine-trader check)."""
    cc = cfg["copy"]
    if b.get("kind", "buy") != "buy" or float(b.get("value", 0)) < float(cc.get("min_buy_usd", 10000)):
        return False
    if b.get("plan") and cc.get("skip_planned", True):
        return False
    return bool(b.get("officer") or b.get("director") or (b.get("ten_pct") and cc.get("include_big_holders", False)))


def is_routine(st: dict, cfg: dict, owner_cik: str, month: str) -> bool | None:
    """True if this insider also traded on the open market in the same calendar month in each of the
    last three years: the 'routine' pattern that carries no information. None if it can't be checked."""
    try:
        cik = int(str(owner_cik).strip())
    except ValueError:
        return None
    key = f"{cik}|{month}"
    cache = st.setdefault("routine", {})
    if key in cache:
        return cache[key]
    try:
        data = json.loads(sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", cfg))
    except Exception:
        return None
    rec = data.get("filings", {}).get("recent", {})
    rows = list(zip(rec.get("form", []), rec.get("filingDate", []), rec.get("accessionNumber", [])))
    year, mm = int(month[:4]), month[5:7]
    routine = True
    for back in (1, 2, 3):
        target = f"{year - back}-{mm}"
        traded = False
        for form, day, acc in [r for r in rows if r[0] == "4" and r[1].startswith(target)][:4]:
            try:
                if parse_form4(sec_get(f"{SEC_ARCHIVES}edgar/data/{cik}/{acc}.txt", cfg)):
                    traded = True
                    break
            except Exception:
                continue
        if not traded:
            routine = False
            break
    cache[key] = routine
    return routine


def read_filings(st: dict, cfg: dict, entries: list[dict], budget: int, log=print) -> tuple[list[dict], int]:
    """Downloads and reads Form 4 filings not seen before. Returns (new records, budget left)."""
    new = []
    for n, e in enumerate(entries, 1):
        if e["acc"] in st["seen"]:
            continue
        if budget <= 0:
            break
        budget -= 1
        try:
            recs = parse_form4(sec_get(SEC_ARCHIVES + e["path"], cfg), e["filed"], e["path"])
        except FileNotFoundError:
            recs = []
        except Exception as exc:
            log(f"  stopped early: {exc}")
            return new, 0
        st["seen"][e["acc"]] = e["filed"]
        for r in recs:
            if cfg["copy"].get("skip_routine", True) and worth_checking(r, cfg):
                r["routine"] = is_routine(st, cfg, r["owner_id"], r["trade_date"][:7] or r["filed"][:7])
            if r["kind"] == "buy" or not r.get("plan"):
                new.append(r)
        if n % 250 == 0:
            log(f"  {n} of {len(entries)} read")
    st["buys"].extend(new)
    return new, budget


def tidy_insiders(st: dict, cfg: dict) -> None:
    today = datetime.now(timezone.utc).date()
    cutoff = (today - pd.Timedelta(days=int(cfg["copy"].get("keep_days", 120))).to_pytimedelta()).isoformat()
    seen_cut = (today - pd.Timedelta(days=8).to_pytimedelta()).strftime("%Y%m%d")
    keys, recs = set(), []
    for b in st["buys"]:
        k = (b.get("acc") or b.get("path"), b.get("kind", "buy"))
        if b.get("filed", "") >= cutoff and k not in keys:
            keys.add(k)
            recs.append(b)
    st["buys"] = recs
    st["seen"] = {a: d for a, d in st["seen"].items() if str(d).replace("-", "") >= seen_cut}
    st["days_done"] = sorted(d for d in set(st["days_done"]) if d >= seen_cut)
    a_cut = (today - pd.Timedelta(days=45).to_pytimedelta()).isoformat()
    st["alerted"] = {s: d for s, d in st["alerted"].items() if d >= a_cut}
    st["updated"] = datetime.now(timezone.utc).isoformat()


def update_insiders(cfg: dict, days: int | None = None, log=print) -> dict:
    """Reads every Form 4 filed on recent days that hasn't been read yet (the complete daily indexes)."""
    cc = cfg["copy"]
    st = load_insiders()
    today = datetime.now(timezone.utc).date()
    budget = int(cc.get("max_filings_per_run", 6000))
    done = set(st["days_done"])
    for back in range(int(days or cc.get("fetch_days", 5)), 0, -1):  # oldest first, up to yesterday
        day = today - pd.Timedelta(days=back).to_pytimedelta()
        key = day.strftime("%Y%m%d")
        if day.weekday() >= 5 or key in done or budget <= 0:
            continue
        url = f"{SEC_ARCHIVES}edgar/daily-index/{day.year}/QTR{(day.month - 1) // 3 + 1}/form.{key}.idx"
        try:
            entries = parse_form_index(sec_get(url, cfg))
        except FileNotFoundError:
            if back >= 4:  # a holiday: no filings that day
                done.add(key)
            continue
        todo = [e for e in entries if e["acc"] not in st["seen"]]
        log(f"SEC filings for {day}: {len(entries)} Form 4s, {len(todo)} not read yet")
        _, budget = read_filings(st, cfg, todo, budget, log)
        if all(e["acc"] in st["seen"] for e in entries):
            done.add(key)
    st["days_done"] = sorted(done)
    tidy_insiders(st, cfg)
    save_insiders(st)
    return st


def poll_live_insiders(cfg: dict, st: dict, log=print) -> list[dict]:
    """Reads the newest Form 4s from EDGAR's live feed (seconds to minutes after they're filed)."""
    new_entries = []
    for page in range(int(cfg["copy"].get("live_pages", 4))):
        entries = parse_live_feed(sec_get(SEC_LIVE.format(start=page * 100), cfg))
        fresh = [e for e in entries if e["acc"] not in st["seen"]]
        new_entries += fresh
        if len(fresh) < len(entries) or not entries:
            break  # reached filings already read
    recs, _ = read_filings(st, cfg, new_entries, int(cfg["copy"].get("max_filings_per_run", 6000)), log)
    tidy_insiders(st, cfg)
    return recs


def insider_clusters(buys: list[dict], cfg: dict, now: datetime | None = None) -> dict[str, dict]:
    """Shares that insiders have been buying recently, and whether the buying is strong enough to copy."""
    cc = cfg["copy"]
    now = now or datetime.now(timezone.utc)
    cutoff = (now - pd.Timedelta(days=int(cc.get("cluster_days", 30)))).strftime("%Y-%m-%d")
    by_sym: dict[str, list[dict]] = {}
    sold: dict[str, float] = {}
    routine_skipped: dict[str, int] = {}
    for b in buys:
        if b.get("filed", "") < cutoff:
            continue
        if b.get("kind", "buy") == "sell":
            if (b.get("officer") or b.get("director")) and not b.get("plan"):
                sold[b["symbol"]] = sold.get(b["symbol"], 0.0) + float(b["value"])
            continue
        if not worth_checking(b, cfg):
            continue
        if b.get("routine") and cc.get("skip_routine", True):
            routine_skipped[b["symbol"]] = routine_skipped.get(b["symbol"], 0) + 1
            continue
        by_sym.setdefault(b["symbol"], []).append(b)
    out = {}
    for sym, bs in by_sym.items():
        bs.sort(key=lambda b: (b["filed"], b.get("trade_date", "")))
        who: dict[str, dict] = {}
        total = shares = 0.0
        first_q = None
        for b in bs:
            who.setdefault(b.get("owner_id") or b.get("owner"), b)
            total += float(b["value"])
            shares += float(b["shares"])
            top = any(x.get("top") for x in who.values())
            ok = total >= float(cc.get("min_total_usd", 50000)) and (
                len(who) >= int(cc.get("min_insiders", 2)) or (top and total >= float(cc.get("big_buy_usd", 100000)))
            )
            if ok and first_q is None:
                first_q = b["filed"]
        out[sym] = {
            "symbol": sym,
            "issuer": bs[-1].get("issuer", ""),
            "insiders": len(who),
            "top": any(x.get("top") for x in who.values()),
            "total_value": total,
            "sold_value": sold.get(sym, 0.0),
            "routine_skipped": routine_skipped.get(sym, 0),
            "avg_price": total / shares if shares else float("nan"),
            "max_increase_pct": max(float(b.get("increase_pct", 0)) for b in bs),
            "first_trade": min(b.get("trade_date", b["filed"]) for b in bs),
            "last_filed": bs[-1]["filed"],
            "qualified": first_q is not None,
            "first_qualified": first_q or "",
            "buys": bs,
        }
    return out


def insider_lines(cl: dict, n: int = 4) -> list[str]:
    per: dict[str, dict] = {}
    for b in cl["buys"]:
        k = b.get("owner_id") or b.get("owner")
        if k not in per:
            per[k] = dict(b)
        else:
            per[k]["value"] = float(per[k]["value"]) + float(b["value"])
            per[k]["trade_date"] = max(per[k]["trade_date"], b["trade_date"])
    rows = sorted(per.values(), key=lambda b: float(b["value"]), reverse=True)
    out = [f"• {esc(b['owner'].title())} ({esc(b['title'] or 'insider')}) bought {fmt_money(float(b['value']), 'USD')}"
           f" at about {fmt_price(float(b['avg_price']), 'USD')} on {esc(b['trade_date'])}" for b in rows[:n]]
    if len(rows) > n:
        out.append(f"• and {len(rows) - n} more")
    if cl.get("sold_value"):
        out.append(f"• other insiders sold {fmt_money(cl['sold_value'], 'USD')} in the same 30 days")
    return out


def copy_signal(ind: pd.DataFrame, bench: pd.DataFrame | None, cl: dict, cfg: dict, symbol: str,
                bench_symbol: str, st: dict, now: datetime | None = None):
    """The copy-the-insiders setup for one share: (frame, checks) like compute_signals, or None."""
    cc = cfg["copy"]
    now = now or datetime.now(timezone.utc)
    if not cl.get("qualified"):
        return None
    fresh_from = (now - pd.Timedelta(days=int(cc.get("max_signal_age_days", 7)))).strftime("%Y-%m-%d")
    if cl["first_qualified"] < fresh_from:
        return None  # old news by now
    if any(k.startswith(f"{symbol}|copy|") for k in st.get("sent", {})):
        return None  # already sent this one
    last = ind.iloc[-1]
    price = float(last["Close"])
    dollar_vol = float((ind["Close"] * ind["Volume"]).tail(20).mean())
    if price < float(cc.get("min_price_usd", 5)) or not dollar_vol >= float(cc.get("min_dollar_volume", 1e6)):
        return None  # too cheap or too thinly traded to copy safely
    paid = float(cl["avg_price"])
    chase = (price / paid - 1.0) * 100.0 if paid > 0 else 0.0
    if chase > float(cc.get("block_chase_pct", 30)):
        return None  # the price has already run away from what they paid
    # How far the share had fallen over the 3 months before the first purchase
    before = ind["Close"][ind.index <= pd.Timestamp(cl["first_trade"])]
    fall = float(before.iloc[-1] / before.iloc[-64] - 1.0) * 100.0 if len(before) > 64 else 0.0
    idx = ind.index
    const = lambda flag: pd.Series(bool(flag), index=idx)  # noqa: E731
    trig = pd.Series(False, index=idx)
    trig.iloc[-1] = True
    use_bench = bench is not None and bench_symbol and bench_symbol.upper() != symbol.upper()
    checks = [
        Check("cluster", "3 or more insiders bought" if cl["insiders"] >= 3 else
              f"only {cl['insiders']} insider{'s' if cl['insiders'] != 1 else ''} bought (3+ is stronger)", const(cl["insiders"] >= 3), 15),
        Check("top", "the CEO, CFO, President or Chair bought", const(cl["top"]), 15),
        Check("size", f"they spent {fmt_money(cl['total_value'], 'USD')} of their own money",
              const(cl["total_value"] >= float(cc.get("big_total_usd", 250000))), 10),
        Check("stake", f"raised their own stake by up to {cl['max_increase_pct']:.0f}%", const(cl["max_increase_pct"] >= 10), 10),
        Check("fall", f"bought after a {abs(fall):.0f}% fall" if fall < 0 else "bought after a fall of 10% or more",
              const(fall <= -10), 10),
        Check("trend", "share price above its 200-day average",
              pd.Series(ind["sma200"].notna() & (ind["Close"] > ind["sma200"]), index=idx), 10),
        Check("regime", "{bench} in an uptrend", bench["up"] if use_bench else None, 10),
        Check("chased", f"already {chase:.0f}% above what they paid", const(chase > float(cc.get("max_chase_pct", 15))), 15, True),
        Check("selling", "other insiders sold more than these bought", const(cl.get("sold_value", 0) > cl["total_value"]), 15, True),
        Check("shock", "huge one-day drop: check the news", (-ind["move_atr"] > 3.0), 15, True),
    ]
    return pd.DataFrame({"trig": trig, "score": _score(30, checks, idx)}), checks


def insiders_report(clusters: dict[str, dict], updated: str = "", n: int = 10) -> str:
    good = sorted((c for c in clusters.values() if c["qualified"]), key=lambda c: c["total_value"], reverse=True)
    lines = ["<b>Insider buying worth a look</b> (open-market purchases, last 30 days, from SEC Form 4 filings)"]
    if not good:
        lines.append("No cluster buys right now.")
    for c in good[:n]:
        who = f"{c['insiders']} insider{'s' if c['insiders'] != 1 else ''}" + (" incl. the boss" if c["top"] else "")
        sold = f" · others sold {fmt_money(c['sold_value'], 'USD')}" if c.get("sold_value") else ""
        lines.append(f"<b>{esc(c['symbol'])}</b> {esc(str(c['issuer'])[:28])} · {who} · "
                     f"{fmt_money(c['total_value'], 'USD')} at about {fmt_price(c['avg_price'], 'USD')}{sold} · "
                     f"latest filing {c['last_filed']}")
    if len(good) > n:
        lines.append(f"...and {len(good) - n} more.")
    skipped = sum(c.get("routine_skipped", 0) for c in clusters.values())
    if skipped:
        lines.append(f"Skipped {skipped} purchase{'s' if skipped != 1 else ''} by 'routine' insiders who trade in the same "
                     "month every year (research finds those trades carry no information).")
    if updated:
        lines.append(f"Filings read up to {updated[:16].replace('T', ' ')} UTC.")
    lines.append("<i>Insiders are often early: shares they buy can keep falling for a while. The nightly scan only "
                 "copies the strongest of these, with a stop, and paper-trades them first.</i>")
    return "\n".join(lines)


def new_insider_alerts(st: dict, cfg: dict) -> list[str]:
    """Telegram messages for shares whose insider buying has just become strong enough to copy."""
    out = []
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    fresh_from = (now - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    clusters = insider_clusters(st["buys"], cfg)
    if not st.get("alerts_seeded"):
        # first run: everything already known has been in the nightly scan; only alert on new buying from now on
        for sym, c in clusters.items():
            if c["qualified"]:
                st["alerted"][sym] = today
        st["alerts_seeded"] = True
        return out
    for sym, c in clusters.items():
        if not c["qualified"] or sym in st["alerted"]:
            continue
        st["alerted"][sym] = today
        if c["first_qualified"] < fresh_from:
            continue  # old news
        lines = [f"<b>INSIDERS BUYING: {esc(sym)}</b> · {esc(str(c['issuer'])[:40])}",
                 f"{c['insiders']} insider{'s' if c['insiders'] != 1 else ''} bought {fmt_money(c['total_value'], 'USD')} "
                 f"of their own shares at about {fmt_price(c['avg_price'], 'USD')}:"]
        lines += insider_lines(c)
        lines.append("Tonight's scan checks the chart and scores it as a copy trade (paper first).")
        lines.append("<i>Not advice. Insiders are often early.</i>")
        out.append("\n".join(lines))
    return out


# ---------------------------------------------------------------------------
# Reading the market: trend, momentum, volatility, fear and breadth
# ---------------------------------------------------------------------------


def read_market(sym: str, cfg: dict, csv_dir) -> dict | None:
    try:
        df, meta = get_data(sym, "1d", "2y", csv_dir)
    except Exception:
        return None
    if len(df) < 210:
        return None
    ind = add_indicators(df, cfg)
    last = ind.iloc[-1]
    c, s50, s200 = float(last["Close"]), float(last["sma50"]), float(last["sma200"])
    rising = bool(ind["sma200"].iloc[-1] > ind["sma200"].iloc[-21])
    if c > s200 and s50 > s200:
        trend = "uptrend"
    elif c < s200 and s50 < s200:
        trend = "downtrend"
    else:
        trend = "no clear trend"
    atr_pct = ind["atr"] / ind["Close"] * 100.0
    now_vol = float(atr_pct.iloc[-1])
    usual = float(atr_pct.tail(252).median())
    vol_word = "jumpier than usual" if now_vol > 1.3 * usual else ("calmer than usual" if now_vol < 0.8 * usual else "normal")
    r2 = float(last["rsi2"]) if pd.notna(last["rsi2"]) else 50.0
    if trend == "uptrend" and c < s50:
        trend_note = "uptrend, but pulling back under its 50-day"
    elif trend == "downtrend" and c > s50:
        trend_note = "downtrend, but bouncing above its 50-day"
    else:
        trend_note = trend
    short_term = ""
    if r2 < 10:
        short_term = "sharp dip in the last two days" + (": the kind the pullback setup buys" if trend == "uptrend" else "")
    elif r2 > 90:
        short_term = "sharp jump in the last two days" + (": the kind the pullback setup shorts" if trend == "downtrend" else "")
    return {
        "symbol": sym, "currency": meta.get("currency", "USD"), "price": c, "trend": trend, "trend_note": trend_note,
        "rising200": rising,
        "r1m": float(c / ind["Close"].iloc[-22] - 1.0), "r3m": float(last["ret63"]) if pd.notna(last["ret63"]) else float("nan"),
        "atr_pct": now_vol, "vol_word": vol_word, "short_term": short_term,
        "above20": bool(c > float(last["ema20"])),
    }


def stance_for(trend: str, cfg: dict) -> str:
    mode = shorts_mode(cfg)
    if trend == "uptrend":
        return "favour longs"
    if trend == "downtrend":
        return "favour shorts" if mode != "off" else "stand aside (shorts are switched off)"
    return "no clear edge: be picky, or wait"


def market_read_text(cfg: dict, args, breadth: list[tuple[str, bool, bool]] | None = None,
                     clusters: dict[str, dict] | None = None, compact: bool = False) -> str:
    ac = cfg.get("analysis", {})
    csv_dir = getattr(args, "csv_dir", None)
    if getattr(args, "symbols", None) and not compact:
        markets = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        markets = list(dict.fromkeys(list(ac.get("markets", [])) + [g.get("benchmark", "") for g in cfg.get("groups", {}).values()]))
    rows = [r for r in (read_market(m, cfg, csv_dir) for m in markets if m) if r]
    now = datetime.now(timezone.utc)
    lines = [f"<b>Market read</b> · {now:%d %b %Y}"]
    if not rows:
        return ""
    for r in rows:
        mom = f"{r['r1m']:+.1%} this month, {r['r3m']:+.1%} in 3 months" if r["r3m"] == r["r3m"] else f"{r['r1m']:+.1%} this month"
        line = (f"<b>{esc(r['symbol'])}</b> {r['trend_note']} · {mom} · moves ~{r['atr_pct']:.1f}% a day ({r['vol_word']})"
                f" → {stance_for(r['trend'], cfg)}")
        if r["short_term"] and not compact:
            line += f". Short term: {r['short_term']}"
        lines.append(line)
    fg = ac.get("fear_gauge", "^VIX")
    if fg:
        try:
            vdf, _ = get_data(fg, "1d", "1y", csv_dir)
            v, v50 = float(vdf["Close"].iloc[-1]), float(vdf["Close"].tail(50).mean())
            mood = "calm" if v < 15 else ("normal" if v < 20 else ("nervous" if v < 30 else "fearful: big swings likely"))
            lines.append(f"Fear gauge ({esc(fg)}): {v:.1f}, {'above' if v > v50 else 'below'} its 50-day average of "
                         f"{v50:.1f}: {mood}" + (", and rising" if v > 1.15 * v50 else ""))
        except Exception:
            pass
    if breadth:
        n = len(breadth)
        a200 = sum(1 for _, x, _ in breadth if x)
        a50 = sum(1 for _, _, y in breadth if y)
        health = "strong" if a200 / n >= 0.65 else ("weak" if a200 / n <= 0.35 else "mixed")
        lines.append(f"Breadth: {a200} of {n} watchlist markets above their 200-day ({a200 / n:.0%}), "
                     f"{a50} above their 50-day ({a50 / n:.0%}): {health}")
    ups = sum(1 for r in rows if r["trend"] == "uptrend")
    downs = sum(1 for r in rows if r["trend"] == "downtrend")
    mode = shorts_mode(cfg)
    if ups > downs and ups >= len(rows) / 2:
        overall = "mostly rising markets. The scan leans long"
    elif downs > ups and downs >= len(rows) / 2:
        overall = "mostly falling markets. Longs are harder; " + (
            "the scan looks for shorts" if mode != "off" else "consider allow_shorts = \"auto\" in config.toml")
    else:
        overall = "mixed signals. Fewer, higher-scoring trades are the better bet"
    if mode == "auto":
        falling = [r["symbol"] for r in rows if r["trend"] == "downtrend"]
        overall += ("; shorts are only taken where the market is falling" +
                    (f" (now: {', '.join(falling)})" if falling else " (none right now)"))
    lines.append(f"<b>Overall</b>: {esc(overall)}.")
    if clusters is not None:
        good = sorted((c for c in clusters.values() if c["qualified"]), key=lambda c: c["total_value"], reverse=True)
        if good:
            lines.append("Insiders buying: " + ", ".join(
                f"{esc(c['symbol'])} ({c['insiders']}, {fmt_money(c['total_value'], 'USD')})" for c in good[:6]))
    lines.append("<i>This describes what prices are doing now, not what they will do next.</i>")
    return "\n".join(lines)


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


def min_score_for(setup: str, cfg: dict, which: str = "alert") -> int:
    """The score a setup needs to alert ("alert") or be paper-traded ("paper"). Per-setup values in
    [scan] setup_min_score override both, e.g. breakouts, where the 10-year test found the score didn't help."""
    per = cfg["scan"].get("setup_min_score", {}) or {}
    if setup in per:
        return int(per[setup])
    return int(cfg["scan"]["alert_min_score"] if which == "alert" else cfg["paper"]["min_score"])


def shorts_mode(cfg: dict) -> str:
    """"off", "on" (look for shorts everywhere) or "auto" (only where the wider market is falling)."""
    v = cfg["scan"].get("allow_shorts", False)
    if isinstance(v, str):
        v = v.strip().lower()
        return "auto" if v == "auto" else ("on" if v in {"true", "on", "yes", "1"} else "off")
    return "on" if v else "off"


def compute_signals(ind: pd.DataFrame, bench: pd.DataFrame | None, cfg: dict, symbol: str, bench_symbol: str):
    """Returns {(setup, direction): (DataFrame[trig, score], [Check, ...])}."""
    s = cfg["setups"]
    c = ind["Close"]
    has_vol = bool(ind.attrs.get("has_volume", False))
    use_bench = bench is not None and bench_symbol and bench_symbol.upper() != symbol.upper()
    out = {}
    mode = shorts_mode(cfg)
    directions = ["long", "short"] if mode != "off" else ["long"]
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
        # "auto" shorts: only when the wider market is in a downtrend too (or, with no benchmark,
        # when the market's own 50-day is under a falling 200-day). Shorting a rising market rarely pays.
        gate = None
        if not up and mode == "auto":
            gate = bench["down"].astype(bool) if use_bench else aligned.astype(bool)
        trend_word = "uptrend" if up else "downtrend"
        rs_label = "beating {bench} over 3 months" if up else "weaker than {bench} over 3 months"

        # 1) Trend breakout: a fresh close beyond the N-day high (low for shorts) in the trend's direction
        beyond = (c > ind["don_hi"]) if up else (c < ind["don_lo"])
        trig_bo = above200 & beyond & ~beyond.shift(1, fill_value=False)
        max_day = float(s.get("max_signal_day_atr", 0) or 0)
        if max_day > 0:  # skip signals made by one huge day (earnings gaps, news shocks)
            trig_bo = trig_bo & ~(ind["move_atr"].abs() > max_day)
        if gate is not None:
            trig_bo = trig_bo & gate
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
        if max_day > 0:
            trig_pb = trig_pb & ~(ind["move_atr"].abs() > max_day)
        if gate is not None:
            trig_pb = trig_pb & gate
        deep = (ind["rsi2"] < 5) if up else (ind["rsi2"] > 95)
        holds50 = (c > ind["sma50"]) if up else (c < ind["sma50"])
        shock = (-ind["move_atr"] > 3.0) if up else (ind["move_atr"] > 3.0)
        checks_pb = [
            Check("aligned", f"50-day {'above rising' if up else 'below falling'} 200-day", aligned, 15),
            Check("deep", "very stretched " + ("dip (RSI(2) under 5)" if up else "jump (RSI(2) over 95)"), deep, 15),
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
    if setup == "copy":
        return float(s.get("copy_stop_atr", 3.0))
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
    risk_mult: float = 1.0
    confidence: str = ""
    bars_held: int = 0
    best_price: float = 0.0
    trailing: bool = False
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
    elif pos.setup == "copy":
        # Insiders are usually early, so give it room: trail the stop k x ATR behind the best close,
        # and sell after about three months (when most of the insider-buying effect has shown up).
        best = pos.best_price or pos.entry_price
        best = max(best, c) if long else min(best, c)
        pos.best_price = best
        a = float(row["atr"]) if "atr" in row and np.isfinite(float(row["atr"])) else pos.atr_at_signal
        trail = best - stop_multiple("copy", cfg) * a if long else best + stop_multiple("copy", cfg) * a
        if long and trail > pos.stop:
            pos.stop = trail
        elif (not long) and trail < pos.stop:
            pos.stop = trail
        if pos.bars_held >= int(s.get("copy_max_hold_bars", 63)):
            pos.exit_next_open, pos.exit_reason = True, "time stop (about 3 months)"
    elif pos.trailing:
        # "let it run" pullbacks: once the bounce has come, the stop goes to break-even and then
        # trails under the 20-bar low (high for shorts), like a breakout, for up to ~3 months
        trail = float(row["exit_lo"] if long else row["exit_hi"])
        if np.isfinite(trail):
            if long and trail > pos.stop:
                pos.stop = trail
            elif (not long) and trail < pos.stop:
                pos.stop = trail
        if pos.bars_held >= int(s.get("pullback_trail_max_bars", 63)):
            pos.exit_next_open, pos.exit_reason = True, "time stop (about 3 months)"
    else:
        sma5 = float(row["sma5"])
        if np.isfinite(sma5) and ((long and c > sma5) or ((not long) and c < sma5)):
            if str(s.get("pullback_exit", "bounce")).lower() == "trail":
                pos.trailing = True
                if (long and pos.entry_price > pos.stop) or ((not long) and pos.entry_price < pos.stop):
                    pos.stop = pos.entry_price  # break-even: this trade can no longer lose (bar gaps aside)
            else:
                pos.exit_next_open, pos.exit_reason = True, "bounce done: closed past the 5-day average"
        elif pos.bars_held >= int(s["pullback_max_hold_bars"]):
            pos.exit_next_open, pos.exit_reason = True, "time stop"
    return False


NEWS_GOOD = re.compile(r"\b(upgrade[sd]?|beats?|tops estimates|raises? (its )?(guidance|outlook|forecast)|record (high|revenue|"
                       r"profit|quarter)|buyback|outperform|approv(al|ed|es)|wins? (contract|deal)|surges?|soars?|jumps?|"
                       r"rall(y|ies)|strong (demand|results|growth)|partnership|acquire[sd]? by)\b", re.I)
NEWS_BAD = re.compile(r"\b(downgrade[sd]?|miss(es|ed)?|cuts? (its )?(guidance|outlook|forecast|jobs)|lowers? (guidance|outlook)|"
                      r"lawsuit|sued|probe|investigation|fraud|recall|share offering|dilution|plunges?|slumps?|tumbles?|sinks?|"
                      r"warns?|profit warning|layoffs?|bankruptcy|delist|short seller|halts?)\b", re.I)


def news_tone(items: list[dict]) -> tuple[int, str]:
    """+1 if the headlines lean good, -1 if they lean bad, 0 if mixed or none. Keyword-based: a rough read."""
    good = sum(1 for p in items if NEWS_GOOD.search(p["title"]) and not NEWS_BAD.search(p["title"]))
    bad = sum(1 for p in items if NEWS_BAD.search(p["title"]) and not NEWS_GOOD.search(p["title"]))
    if not items:
        return 0, "no recent headlines"
    if good > bad:
        return 1, f"news leans good ({good} of {len(items)} headlines)"
    if bad > good:
        return -1, f"news leans bad ({bad} of {len(items)} headlines)"
    return 0, f"news is mixed or neutral ({len(items)} headlines)"


def assess_confidence(cfg: dict, direction: str, score: int, regime_ok: bool | None, hist: dict | None,
                      tm: dict | None, tone: int, tone_text: str, warned: bool, insiders: bool, atr_pct: float):
    """How strongly everything agrees, as points, a tier and a risk multiplier.
    Returns (multiplier, tier, [(points, reason), ...])."""
    sz = cfg.get("sizing", {})
    long = direction == "long"
    pts: list[tuple[int, str]] = []
    if score >= 80:
        pts.append((1, f"score {score}/100"))
    elif score < 60:
        pts.append((-1, f"score only {score}/100"))
    if regime_ok is True:
        pts.append((1, "the wider market agrees"))
    elif regime_ok is False:
        pts.append((-1, "the wider market disagrees"))
    if hist and hist.get("trades", 0) >= int(cfg.get("history", {}).get("min_trades", 5)):
        if hist["expectancy"] > 0.1:
            pts.append((1, f"this setup made {hist['expectancy']:+.2f}R a trade on this market before"))
        elif hist["expectancy"] < 0:
            pts.append((-1, f"this setup lost {hist['expectancy']:+.2f}R a trade on this market before"))
    if tm:
        if tm["avg_r"] > 0.1:
            pts.append((1, f"time machine average {tm['avg_r']:+.2f}R"))
        elif tm["avg_r"] < 0:
            pts.append((-1, f"time machine average {tm['avg_r']:+.2f}R"))
    t = tone if long else -tone
    if t > 0:
        pts.append((1, tone_text))
    elif t < 0:
        pts.append((-1, tone_text))
    if warned:
        pts.append((-1, "earnings or a big event is close"))
    if insiders and long:
        pts.append((1, "company insiders are buying"))
    if atr_pct >= 5:
        pts.append((-1, f"very volatile ({atr_pct:.0f}% a day)"))
    total = sum(p for p, _ in pts)
    if not sz.get("enabled", True):
        return 1.0, "NORMAL", pts
    if total >= int(sz.get("high_points", 3)):
        return float(sz.get("high_mult", 1.5)), "HIGH", pts
    if total <= int(sz.get("low_points", 0)):
        return float(sz.get("low_mult", 0.5)), "LOW", pts
    return 1.0, "NORMAL", pts


def size_position(equity: float, cfg: dict, price: float, risk_unit: float, fx: float, crypto: bool, mult: float = 1.0):
    """Units to buy so a stop-out costs risk_per_trade_pct of the account, times the confidence multiplier,
    never more than sizing.max_risk_pct of the account, and never more than max_position_pct in one position."""
    acct = cfg["account"]
    pct = float(acct["risk_per_trade_pct"]) * float(mult or 1.0)
    pct = min(pct, float(cfg.get("sizing", {}).get("max_risk_pct", 3.0)))
    risk_amt = equity * pct / 100.0
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


def redact(text, cfg: dict) -> str:
    """Error messages from web requests can contain the address they called, which has your Telegram key in it.
    This blanks out every secret before anything is printed (GitHub also hides them, but your own computer won't)."""
    out = str(text)
    for secret in (cfg.get("telegram", {}).get("token"), cfg.get("telegram", {}).get("chat_id"),
                   os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET"), os.environ.get("SEC_USER_AGENT")):
        if secret and len(str(secret)) >= 6:
            out = out.replace(str(secret), "***")
    return out


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
                print(redact(f"Telegram error {r.status_code}: {r.text[:200]}", cfg))
        except Exception as exc:
            ok = False
            print(redact(f"Telegram error: {exc}", cfg))
    print("\n" + plain + "\n")
    return ok


TV_SYMBOLS = {"SPY": "AMEX:SPY", "IWM": "AMEX:IWM", "QQQ": "NASDAQ:QQQ", "GC=F": "COMEX:GC1!", "SI=F": "COMEX:SI1!",
              "BZ=F": "ICEEUR:BRN1!", "^FTSE": "TVC:UKX", "^GSPC": "SP:SPX", "^NDX": "NASDAQ:NDX", "^VIX": "TVC:VIX",
              "BTC-USD": "BITSTAMP:BTCUSD", "ETH-USD": "BITSTAMP:ETHUSD", "SOL-USD": "COINBASE:SOLUSD",
              "GBPUSD=X": "FX:GBPUSD", "EURUSD=X": "FX:EURUSD", "RR.L": "LSE:RR."}


def chart_url(symbol: str, minutes: int | None = None) -> str:
    from urllib.parse import quote

    s = symbol.upper()
    tv = TV_SYMBOLS.get(s) or (f"LSE:{s[:-2].replace('.', '_')}" if s.endswith(".L") else s.replace("-", "."))
    return f"https://www.tradingview.com/chart/?symbol={quote(tv, safe=':!.')}" + (f"&interval={minutes}" if minutes else "")


def chart_link(symbol: str, minutes: int | None = None) -> str:
    """A clickable live chart on TradingView (opens the app if you have it). minutes=5 opens the 5-minute chart."""
    return f'<a href="{chart_url(symbol, minutes)}">📈 Live chart</a>'


def send_photo(cfg: dict, png: bytes | None, caption: str, args=None, url: str | None = None) -> bool:
    """Sends a chart picture to Telegram. Without Telegram (or with --no-telegram) it saves the picture to a
    temporary folder and prints where. A missing picture never stops the text alert."""
    if not png:
        return False
    token, chat = cfg["telegram"].get("token"), cfg["telegram"].get("chat_id")
    if (args is not None and getattr(args, "no_telegram", False)) or not token or not chat:
        import tempfile

        folder = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "bot-charts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (re.sub(r"[^A-Za-z0-9]+", "_", to_plain(caption))[:60] + ".png")
        path.write_bytes(png)
        print(f"[chart saved: {path}]")
        return False
    import requests

    try:
        data = {"chat_id": chat, "caption": caption[:1000], "parse_mode": "HTML"}
        if url:  # a tappable button under the picture
            data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": "📈 Live chart", "url": url}]]})
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data,
                          files={"photo": ("chart.png", png, "image/png")}, timeout=30)
        if r.status_code != 200:
            print(redact(f"Telegram photo error {r.status_code}: {r.text[:200]}", cfg))
        return r.status_code == 200
    except Exception as exc:
        print(redact(f"Telegram photo error: {exc}", cfg))
        return False


def deliver(cfg: dict, item, args=None) -> None:
    """A message is either text, or (text, chart picture): the picture goes first, then the text."""
    if isinstance(item, tuple):
        text, png = item
        if png:
            m = re.search(r'href="(https://www\.tradingview\.com/[^"]+)"', text)
            send_photo(cfg, png, text.split("\n")[0], args, html.unescape(m.group(1)) if m else None)
        send_telegram(cfg, text, args)
    else:
        send_telegram(cfg, item, args)


def format_alert(sym, setup, direction, score, checks_desc, plan, cfg, interval, warnings, paper_note,
                 origin: str | None = None, volatility: str | None = None, history: str | None = None,
                 news: list[str] | None = None, insiders: list[str] | None = None) -> str:
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
    lines.append(chart_link(sym) + " (follow it in real time)")
    if origin:
        lines.append(f"Found on today's movers: {esc(origin)}")
    if insiders:
        lines.append("Who bought (their own SEC Form 4 filings):")
        lines.extend(insiders)
    if direction == "short":
        lines.append("Shorting needs a spread bet, CFD or margin account. Losses on a short have no ceiling "
                     "if the price gaps up, so the stop matters even more.")
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
    elif setup == "copy":
        lines.append(
            f"Exit plan: trail the stop {plan['k']:g} x ATR under the best close since you bought; sell after "
            f"{int(s.get('copy_max_hold_bars', 63))} bars (about 3 months) at most; {s['target_r']:g}R is {fmt_price(plan['target'], ccy)}"
        )
    elif str(s.get("pullback_exit", "bounce")).lower() == "trail":
        lines.append(
            f"Exit plan: when it bounces back past the 5-day average, move the stop to break-even, then trail it under the "
            f"{int(s['breakout_exit_lookback'])}-bar {'low' if direction == 'long' else 'high'} to let it run "
            f"(up to {int(s.get('pullback_trail_max_bars', 63))} bars); {s['target_r']:g}R is {fmt_price(plan['target'], ccy)}"
        )
    else:
        lines.append(
            f"Exit plan: close it when price closes back past the 5-day average, or after "
            f"{int(s['pullback_max_hold_bars'])} bars; {s['target_r']:g}R is {fmt_price(plan['target'], ccy)}"
        )
    if plan["units"] > 0:
        intended = plan["equity"] * min(float(cfg["account"]["risk_per_trade_pct"]) * float(plan.get("mult", 1.0)),
                                        float(cfg.get("sizing", {}).get("max_risk_pct", 3.0))) / 100.0
        if plan["risk_amt"] < 0.97 * intended:
            why = f"capped by the {cfg['account']['max_position_pct']:g}% position limit; full risk would be {fmt_money(intended, acct_ccy)}"
        else:
            why = f"{intended / plan['equity'] * 100:g}% of {fmt_money(plan['equity'], acct_ccy)}"
        lines.append(
            f"Size: {plan['units']:g} {plan['unit_name']} ≈ {fmt_money(plan['value'], acct_ccy)}, "
            f"risking {fmt_money(plan['risk_amt'], acct_ccy)} ({why})"
        )
    else:
        lines.append("Size: too small for your risk setting at this price")
    if plan.get("confidence"):
        mult = float(plan.get("mult", 1.0))
        lines.append(f"Confidence: <b>{plan['confidence']}</b>" + (f" ({mult:g}x the normal size)" if mult != 1 else " (normal size)"))
        for pts_, why_ in plan.get("conf_pts", []):
            lines.append(f"   {'➕' if pts_ > 0 else '➖'} {esc(why_)}")
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
        "best_r": float(r.max()),
        "big_wins": int((r >= 3).sum()),
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def manage_paper(st: dict, sym: str, ind: pd.DataFrame, meta: dict, cfg: dict, interval: str, msgs: list[str],
                 photos: list | None = None) -> None:
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
                    float(st["equity"]), cfg, pos.entry_price, pos.risk_per_unit, pos.fx_to_account, bool(meta.get("is_24_7")),
                    pos.risk_mult or 1.0,
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
                    f"<b>Paper trade closed: {esc(sym)} {pos.direction} {'WON' if pos.pnl > 0 else 'LOST'} "
                    f"{fmt_money(pos.pnl, acct_ccy)}</b> ({pos.r_multiple:+.2f}R). "
                    f"In at {fmt_price(pos.entry_price, pos.currency)}, out at {fmt_price(pos.exit_price, pos.currency)} "
                    f"({esc(pos.exit_reason)}) {held}. "
                    f"Paper account {fmt_money(float(st['equity']), acct_ccy)} ({ret:+.1f}%)."
                )
                if photos is not None and cfg.get("charts", {}).get("enabled", True):
                    png = charts.daily_chart(
                        ind[ind.index <= ts], f"{sym} {pos.direction} {pos.setup}: {'WON' if pos.pnl > 0 else 'LOST'} "
                        f"{fmt_money(pos.pnl, acct_ccy)} ({pos.r_multiple:+.2f}R)",
                        entry=pos.entry_price, stop=pos.initial_stop, exit_=pos.exit_price, mark_from=pos.entry_date,
                    )
                    if png:
                        photos.append((f"<b>{esc(sym)}</b>: how the paper trade went, from {pos.entry_date} (shaded) "
                                       f"to {pos.exit_date}", png))
                break
            pos.last_bar = date
        if pos.status in {"pending", "open"}:
            keep.append(asdict(pos))
        elif pos.status == "closed":
            st["closed"].append(asdict(pos))
    st["positions"] = keep


def rescale_open_positions(st: dict, cfg: dict) -> list[str]:
    """When you change risk_per_trade_pct, open paper trades are resized to match (once), so the whole
    account runs at the new size. Paper only: a real broker would need you to buy or sell the difference."""
    pct = float(cfg["account"]["risk_per_trade_pct"])
    if st.get("risk_pct") == pct:
        return []
    st["risk_pct"] = pct
    acct = cfg["account"]["currency"]
    eq = float(st["equity"])
    out = []
    for d in st["positions"]:
        if d.get("status") != "open" or not float(d.get("risk_amount") or 0) or not float(d.get("units") or 0):
            continue
        target = eq * min(pct * float(d.get("risk_mult") or 1.0), float(cfg.get("sizing", {}).get("max_risk_pct", 3.0))) / 100.0
        factor = target / float(d["risk_amount"])
        fx = float(d.get("fx_to_account") or 1.0)
        cap = eq * float(cfg["account"]["max_position_pct"]) / 100.0 / (float(d["entry_price"]) * fx)
        units = round(min(float(d["units"]) * factor, cap), 4)
        if abs(units - float(d["units"])) < 1e-9:
            continue
        old_risk = float(d["risk_amount"])
        d["risk_amount"] = old_risk * units / float(d["units"])
        d["units"] = units
        out.append(f"Resized paper trade {esc(d['symbol'])}: now risking {fmt_money(d['risk_amount'], acct)} "
                   f"(was {fmt_money(old_risk, acct)}), {units:g} units, to match your {pct:g}% risk setting.")
    return out


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
            long = p.get("direction", "long") == "long"
            if p["status"] == "open":
                move = price - float(p["entry_price"]) if long else float(p["entry_price"]) - price
                pnl = move * float(p["units"]) * float(p.get("fx_to_account") or 1)
                lines += [f"{'Bought' if long else 'Sold short'} {p['entry_date']} at {fmt_price(float(p['entry_price']), ccy)}, "
                          f"{float(p['units']):g} units, stop now {fmt_price(float(p['stop']), ccy)}",
                          f"Now {fmt_price(price, ccy)}: {fmt_money(pnl, acct)} so far (not counted until it closes)"]
            else:
                risk = stop_multiple(p["setup"], cfg) * float(p["atr_at_signal"])
                stop = float(p["signal_price"]) - risk if long else float(p["signal_price"]) + risk
                lines.append(f"{'Buys' if long else 'Sells short'} at the next open; stop about {fmt_price(stop, ccy)} "
                             f"({stop_multiple(p['setup'], cfg):g} x ATR {'below' if long else 'above'} the entry)")
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
    paper_on = bool(cfg["paper"]["enabled"])
    acct_ccy = cfg["account"]["currency"]
    news_on = bool(cfg["news"].get("enabled", True))
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    alerts, msgs, errors, log_rows, regimes, vol_rows, photos, candidates = [], [], [], [], [], [], [], []
    checked = movers_checked = movers_passed = 0
    seen = set()
    watch = iter_watchlist(cfg, args)
    on_list = {s for _, syms in watch for s in syms}

    # Today's movers: Yahoo's most active, biggest risers and biggest fallers. They have to pass
    # exactly the same rules as everything else; being on a movers list earns no points.
    movers = [] if getattr(args, "symbols", None) else fetch_movers(cfg)
    mover_info = {}
    for m in movers:
        if m.get("name") and m["name"] != m["symbol"]:
            COMPANY_NAMES[m["symbol"].upper()] = str(m["name"])
        chg = m.get("change_pct")
        mover_info[m["symbol"]] = m["list"] + (f" ({chg:+.1f}% on the day)" if isinstance(chg, (int, float)) else "")
    for bench in sorted({mover_benchmark(m, cfg) for m in movers}):
        syms = [m["symbol"] for m in movers if mover_benchmark(m, cfg) == bench and m["symbol"] not in on_list]
        if syms:
            watch.append((bench, syms))

    # Copy the insiders: shares that company directors and bosses have just bought with their own money
    # (read from SEC filings by "python bot.py insiders"). They get their own setup, with its own score.
    cc = cfg.get("copy", {})
    clusters = {}
    if cc.get("enabled", True) and not getattr(args, "symbols", None) and insiders_path().exists():
        clusters = insider_clusters(load_insiders()["buys"], cfg, now)
    copy_info = {k: v for k, v in clusters.items() if v["qualified"]}
    for k, v in clusters.items():
        if v.get("issuer"):
            COMPANY_NAMES.setdefault(k.upper(), str(v["issuer"]))
    listed = {s for _, syms in watch for s in syms}
    copy_syms = sorted(k for k in copy_info if k not in listed)
    if copy_syms:
        watch.append((cc.get("benchmark", "SPY"), copy_syms))
    breadth = []
    extra = sorted({p["symbol"] for p in st["positions"]} - {s for _, syms in watch for s in syms})
    if extra:
        watch.append(("", extra))  # keep managing paper trades for symbols no longer listed

    warn_days = int(cfg["news"].get("event_warning_days", 2))
    events_soon = upcoming_events(cfg, max(3, warn_days)) if news_on else []
    warn_until = pd.Timestamp.now(tz=cfg["news"].get("timezone", "Europe/London")) + pd.Timedelta(days=warn_days)

    msgs += rescale_open_positions(st, cfg)
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
            quiet = is_mover or (sym in copy_info and sym not in on_list)  # leads: skip errors quietly
            try:
                df, meta = get_data(sym, interval, history, args.csv_dir)
                if len(df) < 210:
                    if not quiet:  # brand-new listings on the movers lists are skipped quietly
                        errors.append(f"{sym} (only {len(df)} bars of history)")
                    continue
                checked += 1
                movers_checked += int(is_mover)
                ind = add_indicators(df, cfg)
                lr = ind.iloc[-1]
                swing = float(lr["atr"]) / float(lr["Close"]) * 100.0 if pd.notna(lr["atr"]) and lr["Close"] > 0 else float("nan")
                if quiet and swing > float(cfg["movers"].get("max_daily_swing_pct", 15)):
                    continue  # a movers-list share swinging 15%+ a day: usually a penny share or bad data
                if swing == swing:
                    vol_rows.append((sym, swing))
                if sym in on_list and pd.notna(lr["sma200"]):
                    breadth.append((sym, bool(lr["Close"] > lr["sma200"]), bool(lr["Close"] > lr["sma50"])))
                bench = align_benchmark(ind, bench_df)
                manage_paper(st, sym, ind, meta, cfg, interval, msgs, photos)
                sigs = compute_signals(ind, bench, cfg, sym, bench_sym)
                if sym in copy_info:
                    cs = copy_signal(ind, bench, copy_info[sym], cfg, sym, bench_sym, st, now)
                    if cs:
                        sigs[("copy", "long")] = cs
                i = len(ind) - 1
                bar = bar_label(ind.index[i], interval)
                for (setup, direction), (frame, checks) in sigs.items():
                    if not bool(frame["trig"].iloc[i]):
                        continue
                    score = int(frame["score"].iloc[i])
                    warnings = []
                    need = min_score_for(setup, cfg)
                    days = next_earnings_days(sym, meta) if score >= need - 10 else None
                    if days is not None and days <= int(cfg["scan"]["earnings_warning_days"]):
                        score = max(0, score - 10)
                        warnings.append(f"Earnings in {days} day{'s' if days != 1 else ''}: prices can jump past any stop")
                    soon = [e for e in events_soon if e["when"] <= warn_until and event_relevant(e, sym)]
                    for ev in soon[:2]:
                        warnings.append(f"Big event soon, {event_text(ev)}: prices can jump on the day")
                    key = f"{sym}|{setup}|{direction}|{bar}"
                    alerted = False
                    if score >= need and key not in st["sent"]:
                        last = ind.iloc[i]
                        price, a = float(last["Close"]), float(last["atr"])
                        k = stop_multiple(setup, cfg)
                        long = direction == "long"
                        risk_unit = k * a
                        fx = fx_rate(meta["currency"], acct_ccy)
                        crypto = bool(meta.get("is_24_7"))
                        # Everything that says how much to trust this trade, before deciding the size
                        tm = time_machine(ind, setup, direction, cfg) if cfg["timemachine"].get("enabled", True) else None
                        hist_stats = None if setup == "copy" else setup_history(sym, setup, direction, cfg, interval, bench_sym, args.csv_dir)
                        head_items = get_headlines(sym, int(cfg["news"].get("headlines", 3)),
                                                   float(cfg["news"].get("max_age_hours", 72))) if news_on else []
                        tone, tone_text = news_tone(head_items)
                        regime_ok = None
                        if bench is not None and bench_sym and bench_sym.upper() != sym.upper():
                            regime_ok = bool(bench["up"].iloc[i]) if long else bool(bench["down"].iloc[i])
                        warned = any(w.startswith(("Earnings in", "Big event soon")) for w in warnings)
                        atr_pct = a / price * 100.0 if price > 0 else 0.0
                        mult, tier, conf_pts = assess_confidence(cfg, direction, score, regime_ok, hist_stats, tm, tone, tone_text,
                                                                 warned, sym in copy_info, atr_pct)
                        units, risk_amt, value = size_position(float(st["equity"]), cfg, price, risk_unit, fx or 1.0, crypto, mult)
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
                            "confidence": tier,
                            "mult": mult,
                            "conf_pts": conf_pts,
                        }
                        open_syms = {p["symbol"] for p in st["positions"]}
                        paper_note = ""
                        ok, why = risk_check(st, cfg, risk_amt)
                        min_r = float(cfg["risk"].get("min_replay_avg_r", -1))
                        if ok and tm and min_r > -1 and tm["avg_r"] < min_r:
                            ok, why = False, f"time machine average {tm['avg_r']:+.2f}R is below your minimum {min_r:+.2f}R"
                        tm_blocked = bool(tm and min_r > -1 and tm["avg_r"] < min_r)
                        if paper_on and score >= min_score_for(setup, cfg, "paper") and sym not in open_syms and not tm_blocked:
                            # decided after the whole scan, so the best signals get the risk budget first
                            warnings.append("Risk check: §RISK§")
                            paper_note = "§PAPER§"
                            candidates.append({
                                "idx": len(alerts), "risk": risk_amt, "tier": tier, "setup": setup, "score": score,
                                "pos": Position(symbol=sym, setup=setup, direction=direction, signal_date=bar,
                                                signal_price=price, atr_at_signal=a, score=score,
                                                currency=meta["currency"], risk_mult=mult, confidence=tier),
                            })
                        else:
                            warnings.append(("Risk check: PASS, " if ok else "Risk check: BLOCK, ") + why)
                            if paper_on and score >= min_score_for(setup, cfg, "paper"):
                                paper_note = ("Paper trading: already holding this one, so no new paper trade." if sym in open_syms
                                              else "Paper trading: blocked by the risk check, so no paper trade.")
                        vol_line = f"Moves about {atr_pct:.1f}% a day" + (
                            ": very volatile, so expect big swings both ways. The size is smaller to keep the risk the same."
                            if atr_pct >= 5.0 else "."
                        )
                        if setup == "copy":
                            hist = ("No 10-year test for this one: the bot only keeps recent insider filings. "
                                    "Studies found insider cluster buys beat the market on average over the next "
                                    "months, but many single trades still lose. The paper account is the real test.")
                        else:
                            hist = history_line(sym, hist_stats, cfg)
                        tml = time_machine_line(tm)
                        if tml:
                            hist = f"{hist}\n{tml}" if hist else tml
                        heads = headline_lines(head_items) if news_on else None
                        desc = describe_checks(checks, i, ind, bench_sym)
                        text = format_alert(
                            sym, setup, direction, score, desc, plan, cfg, interval, warnings, paper_note,
                            origin=mover_info.get(sym) if is_mover else None, volatility=vol_line, history=hist, news=heads,
                            insiders=insider_lines(copy_info[sym]) if setup == "copy" else None,
                        )
                        png = charts.daily_chart(
                            ind.iloc[: i + 1], f"{sym} · {SETUP_TITLES[setup]} · {'BUY' if long else 'SELL SHORT'} · score {score}",
                            entry=price, stop=plan["stop"], target=plan["target"],
                        ) if cfg.get("charts", {}).get("enabled", True) else None
                        alerts.append((text, png))
                        st["sent"][key] = now_iso
                        alerted = True
                        movers_passed += int(is_mover)
                    log_rows.append({
                        "run_utc": now_iso, "bar": bar, "symbol": sym, "setup": setup,
                        "direction": direction, "score": score, "alerted": alerted,
                    })
            except Exception as exc:
                if not quiet:
                    errors.append(f"{sym} ({exc})")

    if not st.get("recap_v1") and st["positions"]:
        recap = recap_positions(st, cfg, args.csv_dir)
        if recap:
            send_telegram(cfg, "<b>Your paper trades so far</b> (resent so you haven't missed any)", args)
            for text in recap:
                send_telegram(cfg, text, args)
    st["recap_v1"] = True
    ac = cfg.get("analysis", {})
    if ac.get("enabled", True) and ac.get("send_with_scan", True) and not getattr(args, "symbols", None):
        try:
            read = market_read_text(cfg, args, breadth, clusters if cc.get("enabled", True) else None, compact=True)
            if read:
                send_telegram(cfg, read, args)
        except Exception as exc:
            errors.append(f"market read ({exc})")
    # Hand out the risk budget: best setups first (breakouts had the strongest 10-year record), then the most
    # confident, then the highest score. Each accepted trade counts against the budget for the next one.
    setup_rank = {"breakout": 0, "copy": 1, "pullback": 2}
    tier_rank = {"HIGH": 0, "NORMAL": 1, "LOW": 2}
    for c in sorted(candidates, key=lambda c: (setup_rank.get(c["setup"], 3), tier_rank.get(c["tier"], 1), -c["score"])):
        ok, why = risk_check(st, cfg, c["risk"], c["tier"])
        if ok:
            st["positions"].append(asdict(c["pos"]))
            note = "Paper trading: the bot will open this at the next open and manage it for you."
        else:
            note = "Paper trading: blocked by the risk check, so no paper trade."
        text, png = alerts[c["idx"]]
        text = text.replace("§RISK§", esc(("PASS, " if ok else "BLOCK, ") + why)).replace("§PAPER§", esc(note))
        alerts[c["idx"]] = (text, png)
    for item in alerts:
        deliver(cfg, item, args)
    for caption, png in photos:
        m = re.search(r"<b>([^<]+)</b>", caption)
        send_photo(cfg, png, caption, args, chart_url(html.unescape(m.group(1))) if m else None)
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
        if cc.get("enabled", True):
            if insiders_path().exists():
                lines.append(f"Insider buying: {len(copy_info)} share{'s' if len(copy_info) != 1 else ''} with strong "
                             "buying in the last 30 days, checked as copy trades")
            else:
                lines.append("Insider buying: no SEC filings read yet (run python bot.py insiders)")
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
        for tier in ("HIGH", "NORMAL", "LOW"):
            rs = [c for c in st["closed"] if c.get("confidence") == tier]
            if rs:
                t = summarise_r([c["r_multiple"] for c in rs])
                lines.append(f"  {tier} confidence: {t['trades']} trades, {t['win_rate']:.0%} won, {t['expectancy']:+.2f}R a trade, "
                             f"{fmt_money(sum(float(c['pnl']) for c in rs), acct_ccy)}")
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
    cols = ["Open", "High", "Low", "Close", "sma5", "exit_lo", "exit_hi", "atr"]  # step_bar reads these
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
    if direction != "long" or setup not in {"breakout", "pullback"} or len(ind) < 120:
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
    trailing = np.zeros(n, bool)
    trail_mode = setup == "pullback" and str(s.get("pullback_exit", "bounce")).lower() == "trail"
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
        elif trail_mode:
            bounced = alive & ~trailing & (c > closes.mean(axis=1))
            trailing |= bounced
            stop = np.where(bounced, np.maximum(stop, entry), stop)
            stop = np.where(alive & trailing, np.maximum(stop, lows.min(axis=1)), stop)
            flag |= alive & ~trailing & (bars >= int(s["pullback_max_hold_bars"]))
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


def position_risk(p: dict, st: dict, cfg: dict) -> float:
    """What a trade can still lose: from where it is held to its CURRENT stop (a trade whose stop has moved up to
    break-even or beyond risks nothing more). Trades waiting to open count at their planned risk."""
    eq = float(st["equity"])
    if p.get("status") == "open" and float(p.get("units") or 0) > 0:
        long = p.get("direction", "long") == "long"
        gap = (float(p["entry_price"]) - float(p["stop"])) if long else (float(p["stop"]) - float(p["entry_price"]))
        return max(0.0, gap) * float(p["units"]) * float(p.get("fx_to_account") or 1.0)
    pct = min(float(cfg["account"]["risk_per_trade_pct"]) * float(p.get("risk_mult") or 1.0),
              float(cfg.get("sizing", {}).get("max_risk_pct", 3.0)))
    return eq * pct / 100


def risk_check(st: dict, cfg: dict, new_risk: float, tier: str | None = None) -> tuple[bool, str]:
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
    open_risk = sum(position_risk(p, st, cfg) for p in st["positions"])
    cap = eq * float(rc.get("max_open_risk_pct", 5)) / 100
    if open_risk + new_risk > cap + 1e-9:
        return False, (f"too much already at risk ({fmt_money(open_risk, cfg['account']['currency'])} in open trades, "
                       f"limit {fmt_money(cap, cfg['account']['currency'])})")
    low_share = float(rc.get("low_confidence_budget_pct", 50))
    if tier == "LOW" and open_risk + new_risk > cap * low_share / 100 + 1e-9:
        return False, (f"LOW confidence trades only use the first {low_share:g}% of the risk budget, "
                       "keeping room for stronger ones")
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
        return [label, "0", "-", "-", "-", "-", "-", "-", "-", "-"]
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
        f"{st['best_r']:+.1f}",
        str(st["big_wins"]),
    ]


def portfolio_sim(trades: list, cfg: dict, risk_pct: float, heat_pct: float, max_open: int,
                  start_equity: float = 5000.0) -> dict:
    """Runs the whole paper account through history: each day's new signals are ranked (breakouts first,
    then higher score), taken while total open risk stays under heat_pct, sized at risk_pct of the account
    at the time, and paid out in R when they close. Open risk counts from the entry stop (no credit for
    trailed stops), so this is on the cautious side."""
    setup_rank = {"breakout": 0, "copy": 1, "pullback": 2}
    ts = [t for t in trades if t.entry_date and t.exit_date and t.exit_reason != "still open at the end of the data"]
    ts.sort(key=lambda t: (t.entry_date, setup_rank.get(t.setup, 3), -t.score))
    eq, peak, max_dd = start_equity, start_equity, 0.0
    open_: list = []  # (exit_date, risk_amount, r)
    taken = skipped = 0
    curve = []
    for t in ts:
        still = []
        for ex, risk, r in sorted(open_):
            if ex <= t.entry_date:
                eq += risk * r
                peak = max(peak, eq)
                max_dd = max(max_dd, 1 - eq / peak)
            else:
                still.append((ex, risk, r))
        open_ = still
        risk_amt = eq * risk_pct / 100
        heat = sum(r for _, r, _ in open_)
        if heat + risk_amt > eq * heat_pct / 100 + 1e-9 or len(open_) >= max_open or eq <= 0:
            skipped += 1
            continue
        taken += 1
        open_.append((t.exit_date, risk_amt, t.r_multiple))
        curve.append((t.entry_date, eq))
    for ex, risk, r in sorted(open_):
        eq += risk * r
        peak = max(peak, eq)
        max_dd = max(max_dd, 1 - eq / peak)
    years = 1.0
    if ts:
        years = max(0.5, (pd.Timestamp(ts[-1].exit_date) - pd.Timestamp(ts[0].entry_date)).days / 365.25)
    cagr = (eq / start_equity) ** (1 / years) - 1 if eq > 0 else -1.0
    return {"risk": risk_pct, "heat": heat_pct, "taken": taken, "skipped": skipped, "final": eq,
            "cagr": cagr, "max_dd": max_dd, "years": years}


def portfolio_report(trades: list, cfg: dict) -> None:
    max_open = int(cfg["paper"]["max_open_positions"])
    print("\nWhole-account simulation (every signal that passes your paper rules, ranked each day, £5,000 start,")
    print(f"at most {max_open} trades open, open risk counted from the entry stop):\n")
    rows = []
    for risk in (1.0, 2.0):
        for heat in (6, 12, 18, 24, 36):
            r = portfolio_sim(trades, cfg, risk, heat, max_open)
            rows.append([f"{risk:g}%", f"{heat}%", f"{r['taken']}/{r['taken'] + r['skipped']}",
                         f"£{r['final']:,.0f}", f"{r['cagr']:+.1%}", f"{r['max_dd']:.0%}",
                         f"{r['cagr'] / r['max_dd']:.2f}" if r["max_dd"] > 0 else "-"])
    print(_table(["Risk/trade", "Risk cap", "Trades taken", "End balance", "A year", "Worst fall", "Year/fall"], rows))
    print("Year/fall = yearly growth divided by the worst fall: higher means more growth for each bit of pain.")


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
    headers = ["Group", "Trades", "Won", "Avg win R", "Avg loss R", "Expectancy R", "Profit factor", "Worst run R",
               "Best R", "3R+ wins"]
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
    if getattr(args, "portfolio", False):
        paper_trades = [t for t in all_trades if t.score >= min_score_for(t.setup, cfg, "paper")]
        portfolio_report(paper_trades, cfg)
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
                    if score >= min_score_for(setup, cfg) and key not in ws["sent"]:
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
                        f"With real money, this is where your stop order would have {'sold' if long else 'bought it back'}."
                    )
                    ws["sent"][key] = stamp

            # 4) Fresh headlines on anything the paper account holds
            if wc.get("held_news", True) and news_on and sym in held:
                fresh = [p for p in get_headlines(sym, 5, 12) if f"news|{p['id']}" not in ws["sent"]]
                if fresh:
                    msgs.append("\n".join([f"<b>News on {esc(sym)}</b> (in your paper account):"] + headline_lines(fresh[:3])))
                    for p in fresh:
                        ws["sent"][f"news|{p['id']}"] = stamp

            # 5) Earnings coming up on something the paper account holds: the share can gap past the stop
            if sym in held:
                days = next_earnings_days(sym, meta)
                key = f"earn|{sym}|{(pd.Timestamp(day) + pd.Timedelta(days=days or 0)):%Y-%m-%d}"
                if days is not None and days <= int(wc.get("earnings_days", 3)) and key not in ws["sent"]:
                    pos = held[sym]
                    msgs.append(
                        f"<b>Earnings soon: {esc(sym)}</b> reports in {days} day{'s' if days != 1 else ''}. You hold it in the paper "
                        f"account ({pos['direction']}, stop {fmt_price(float(pos['stop']), ccy)}). Results can make a share jump "
                        "straight past a stop. With real money, many traders take some or all of the profit off first."
                    )
                    ws["sent"][key] = stamp
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


# ---------------------------------------------------------------------------
# Pulse: read gold, the S&P 500, Nasdaq, Russell, FTSE and Bitcoin every 5 minutes
# ---------------------------------------------------------------------------


def pulse_path() -> Path:
    return STATE_DIR / "pulse.json"


def load_pulse() -> dict:
    d: dict = {}
    if pulse_path().exists():
        try:
            d = json.loads(pulse_path().read_text(encoding="utf-8"))
        except Exception:
            d = {}
    d.setdefault("markets", {})
    d.setdefault("trades", [])
    d.setdefault("closed", [])
    return d


def save_pulse(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    d["closed"] = d["closed"][-500:]
    tmp = pulse_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    tmp.replace(pulse_path())


def pulse_risk(cfg: dict) -> float:
    """Money at risk on each paper intraday trade (so R can be shown as pounds won or lost)."""
    return float(cfg["account"]["size"]) * float(cfg["account"]["risk_per_trade_pct"]) / 100.0


def intraday_frame(sym: str, period: str, cfg: dict, csv_dir):
    df, meta = get_data(sym, "5m", period, csv_dir)
    spec = intraday.spec_for(sym, cfg["pulse"].get("sessions", {}).get(sym))
    return intraday.add_intraday(intraday.prepare(df, spec), spec), spec, meta


def record_line(record: dict) -> str:
    parts = []
    for a, name in intraday.APPROACHES.items():
        r = record.get(a, {})
        if r.get("trades"):
            parts.append(f"{name} {r['avg_r']:+.2f}R a trade ({r['trades']} trades, {r['win_rate']:.0%} won)")
        else:
            parts.append(f"{name}: no trades")
    n = max((r.get("sessions", 0) for r in record.values()), default=0)
    return f"Lately here ({n} sessions of 5-min bars, after costs): " + " · ".join(parts)


def won_lost(r: float, cfg: dict) -> str:
    money = r * pulse_risk(cfg)
    acct = cfg["account"]["currency"]
    return f"{'WON' if money > 0 else 'LOST'} {fmt_money(money, acct)} ({r:+.2f}R)"


def pulse_market_text(sym, spec, ind, m, ccy, cfg, head: str) -> str:
    row = ind.iloc[-1]
    d, k = row["direction"], row["kind"]
    best = intraday.best_approach(d, k, m.get("record", {}), int(cfg["pulse"].get("min_trades", 15)),
                                  float(cfg["pulse"].get("min_edge_r", 0.1)))
    tz = cfg["news"].get("timezone", "Europe/London")
    when = ind.index[-1].tz_convert(tz) + pd.Timedelta(minutes=5)
    vw_dir = "rising" if row["vwap_slope"] > 0 else "falling"
    h1 = "up" if row["h1_up"] else ("down" if row["h1_down"] else "flat")
    lines = [f"<b>{head}{esc(spec['name'])} · {intraday.describe(d, k)}</b> · {when:%H:%M} UK",
             f"Price {fmt_price(float(row['Close']), ccy)} · VWAP {fmt_price(float(row['vwap']), ccy)} ({vw_dir}) · "
             f"1-hour trend {h1} · today {(row['Close'] / row['sess_open'] - 1) * 100:+.2f}%",
             f"Best approach now: {esc(intraday.advice(d, k, best))}"]
    if np.isfinite(row["or_high"]):
        lines.append(f"Opening range {fmt_price(float(row['or_low']), ccy)} to {fmt_price(float(row['or_high']), ccy)} · "
                     f"VWAP bands {fmt_price(float(row['vwap'] - 2 * row['vwap_sd']), ccy)} to "
                     f"{fmt_price(float(row['vwap'] + 2 * row['vwap_sd']), ccy)}")
    if m.get("record"):
        lines.append(esc(record_line(m["record"])))
    return "\n".join(lines)


def manage_pulse_trades(ps: dict, sym: str, ind, spec, ccy, cfg) -> list[str]:
    msgs, keep = [], []
    cost = market_cost(cfg, sym)
    pos = {str(t): i for i, t in enumerate(ind.index)}
    for t in ps["trades"]:
        if t["symbol"] != sym:
            keep.append(t)
            continue
        i = pos.get(t["signal_time"])
        if i is None:
            if pd.Timestamp(t["signal_time"]) < ind.index[0]:
                continue  # too old to follow any more
            keep.append(t)
            continue
        res = intraday.follow(ind, i, t["approach"], t["side"], cost)
        if res is None:
            msgs.append(f"Paper intraday trade skipped: {esc(spec['name'])} {t['side']} (couldn't be taken at the next open).")
            continue
        if res.get("status") != "closed":
            if res.get("status") == "open" and not t.get("opened_said"):
                t.update(entry=res["entry"], stop=res["stop"], target=res["target"], opened_said=True)
            keep.append(t)
            continue
        t.update(res)
        t["money"] = t["r"] * pulse_risk(cfg)
        ps["closed"].append(t)
        today = [c for c in ps["closed"] if str(c.get("exit_time", ""))[:10] == str(res["exit_time"])[:10]]
        day_r = sum(c["r"] for c in today)
        text = (
            f"<b>{esc(spec['name'])} {intraday.APPROACHES[t['approach']]} {t['side'].upper()}: {won_lost(t['r'], cfg)}</b>\n"
            f"{'Bought' if t['side'] == 'long' else 'Sold'} at {fmt_price(res['entry'], ccy)}, out at {fmt_price(res['exit'], ccy)} "
            f"({esc(res['reason'])}). Paper only.\n"
            f"Today's intraday paper trades: {len(today)}, {won_lost(day_r, cfg)}"
        )
        png = charts.intraday_chart(ind, f"{spec['name']} {t['side']}: {won_lost(t['r'], cfg)}", entry=res["entry"],
                                    stop=res["stop"], target=None if t["approach"] == "late" else res["target"],
                                    exit_=res["exit"]) if cfg.get("charts", {}).get("enabled", True) else None
        msgs.append((text, png) if png else text)
    ps["trades"] = keep
    return msgs


def market_cost(cfg: dict, sym: str) -> float:
    """Spread + slippage each way for this market, in %."""
    pc = cfg["pulse"]
    return float(pc.get("costs", {}).get(sym, pc.get("cost_pct", 0.02)))


def pulse_once(cfg: dict, args, ps: dict) -> list[str]:
    pc = cfg["pulse"]
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    msgs = []
    for sym in pc.get("markets", []):
        m = ps["markets"].setdefault(sym, {})
        stale = not m.get("record_at") or (now - pd.Timestamp(m["record_at"])).total_seconds() > 60 * float(pc.get("record_every_minutes", 60))
        try:
            ind, spec, meta = intraday_frame(sym, "60d" if stale else "5d", cfg, args.csv_dir)
        except Exception as exc:
            print(f"{sym}: {exc}")
            continue
        if len(ind) < 80:
            continue
        ccy = meta.get("currency", "USD")
        cost = market_cost(cfg, sym)
        if stale:
            m["record"] = intraday.recent_record(ind, cost)
            m["record_at"] = now.isoformat()
        msgs += manage_pulse_trades(ps, sym, ind, spec, ccy, cfg)
        last_ts = ind.index[-1]
        live = OFFLINE or (now - last_ts.tz_convert("UTC")).total_seconds() <= 20 * 60
        if not live or m.get("last_bar") == str(last_ts):
            continue  # market closed, or no new bar yet
        m["last_bar"] = str(last_ts)
        row = ind.iloc[-1]
        d, k = row["direction"], row["kind"]
        best = intraday.best_approach(d, k, m.get("record", {}), int(pc.get("min_trades", 15)), float(pc.get("min_edge_r", 0.1)))
        key = f"{d}|{k}|{best}"
        if m.get("brief_day") != today:
            if pc.get("send_open_brief", True):
                msgs.append(pulse_market_text(sym, spec, ind, m, ccy, cfg, "OPEN: "))
            m.update(brief_day=today, stance=key, pending=None, pending_n=0, alerts={})
        elif key != m.get("stance"):
            m["pending_n"] = m.get("pending_n", 0) + 1 if m.get("pending") == key else 1
            m["pending"] = key
            if m["pending_n"] >= int(pc.get("confirm_bars", 3)):
                old = m.get("stance", "none|mixed|None").split("|")
                n_ch = m.setdefault("changes", {}).get(today, 0)
                if pc.get("send_changes", True) and n_ch < int(pc.get("max_changes_per_market", 3)):
                    msgs.append(pulse_market_text(sym, spec, ind, m, ccy, cfg, "CHANGE: ") +
                                f"\n(was {intraday.describe(old[0], old[1]).lower()})")
                    m["changes"] = {today: n_ch + 1}
                m.update(stance=key, pending=None, pending_n=0)
        else:
            m.update(pending=None, pending_n=0)
        if best and pc.get("send_signals", True):
            side = intraday.signal_now(ind, best, d)
            n_today = m.setdefault("alerts", {}).get(today, 0)
            if side and n_today < int(pc.get("max_signals_per_market", 4)):
                m["alerts"] = {today: n_today + 1}
                price = float(row["Close"])
                stop = float(row[f"{best}_{'l' if side == 'long' else 's'}stop"])
                risk = max(abs(price - stop), intraday.MIN_RISK_ATR * float(row["atr"]))  # same rules as the record
                stop = price - risk if side == "long" else price + risk
                if best == "fade":
                    target = float(row["vwap"])
                elif best == "late":
                    target = float("nan")  # held to the close
                else:
                    target = price + 2 * risk if side == "long" else price - 2 * risk
                rec = m.get("record", {}).get(best, {})
                text = (
                    f"<b>SIGNAL: {esc(spec['name'])} {'BUY (long)' if side == 'long' else 'SELL (short)'}</b> · "
                    f"{intraday.APPROACHES[best]} · 5-min chart · {chart_link(sym, 5)}\n"
                    f"Entry about {fmt_price(price, ccy)} now · stop {fmt_price(stop, ccy)} · "
                    f"{'sell at the close' if best == 'late' else 'target ' + fmt_price(target, ccy)}\n"
                    f"Why: {esc(intraday.describe(d, k).lower())}; {esc(intraday.HOW[(best, side)])}\n"
                    f"This approach has made {rec.get('avg_r', 0):+.2f}R a trade on this market lately "
                    f"({rec.get('trades', 0)} trades). At {fmt_money(pulse_risk(cfg), cfg['account']['currency'])} risk, "
                    f"the stop costs {fmt_money(-pulse_risk(cfg), cfg['account']['currency'])} and the target makes about "
                    f"{fmt_money(pulse_risk(cfg) * (abs(target - price) / risk if risk and target == target else 2), cfg['account']['currency'])}"
                    f"{' (if it runs 2R by the close)' if best == 'late' else ''}.\n"
                    "The bot paper-trades it and tells you how it ends.\n<i>Not advice. Check your broker's live price.</i>"
                )
                png = charts.intraday_chart(ind, f"{spec['name']} · {'BUY' if side == 'long' else 'SELL'} · {intraday.APPROACHES[best]}",
                                            entry=price, stop=stop, target=target) if cfg.get("charts", {}).get("enabled", True) else None
                msgs.append((text, png) if png else text)
                ps["trades"].append({"symbol": sym, "approach": best, "side": side, "signal_time": str(last_ts), "signal_price": price})
    # End-of-day results, once, after the US close
    if now.hour >= 21 and ps.get("summary_day") != today:
        todays = [c for c in ps["closed"] if str(c.get("exit_time", ""))[:10] == today]
        if todays:
            lines = [f"<b>Intraday paper results · {today}</b>"]
            for c in todays:
                lines.append(f"{esc(intraday.spec_for(c['symbol'])['name'])} {intraday.APPROACHES[c['approach']]} {c['side']}: "
                             f"{won_lost(c['r'], cfg)}")
            lines.append(f"Today: {won_lost(sum(c['r'] for c in todays), cfg)}")
            allr = [c["r"] for c in ps["closed"]]
            lines.append(f"All intraday paper trades so far: {len(allr)}, {np.mean([r > 0 for r in allr]):.0%} won, "
                         f"{won_lost(sum(allr), cfg)}")
            for a, name in intraday.APPROACHES.items():
                rs = [c["r"] for c in ps["closed"] if c["approach"] == a]
                if rs:
                    lines.append(f"  {name}: {len(rs)} trades, {won_lost(sum(rs), cfg)}")
            msgs.append("\n".join(lines))
        ps["summary_day"] = today
    return msgs


def dispatch_workflow(name: str) -> bool:
    """Starts another GitHub workflow now (GitHub's own schedules can start hours late)."""
    import subprocess

    if not (os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_ACTIONS")):
        return False
    try:
        r = subprocess.run(["gh", "workflow", "run", name, "--ref", os.environ.get("GITHUB_REF_NAME", "main")],
                           capture_output=True, text=True, timeout=60)
        print(f"Started {name}: {r.returncode} {r.stdout.strip()} {r.stderr.strip()}")
        return r.returncode == 0
    except Exception as exc:
        print(f"Couldn't start {name}: {exc}")
        return False


def live_price(sym: str, args) -> tuple[float | None, bool]:
    """(latest price, market open?) from 5-minute bars."""
    try:
        df, _ = get_data(sym, "5m", "5d", getattr(args, "csv_dir", None))
        last = pd.Timestamp(df.index[-1]).tz_localize("UTC") if pd.Timestamp(df.index[-1]).tzinfo is None else pd.Timestamp(df.index[-1])
        return float(df["Close"].iloc[-1]), OFFLINE or (pd.Timestamp.now(tz="UTC") - last).total_seconds() < 25 * 60
    except Exception:
        return None, False


def trump_chores(cfg: dict, args, ps: dict) -> list[str]:
    """New Trump posts that could move markets, and the 30/120-minute checks of what really happened."""
    tc = cfg.get("trump", {})
    msgs: list[str] = []
    now = pd.Timestamp.now(tz="UTC")
    seen = ps.setdefault("trump_seen", [])
    checks = ps.setdefault("trump_checks", [])
    try:
        import requests

        r = requests.get(trump.FEED, timeout=20, headers={"User-Agent": "Mozilla/5.0 (setup-scanner-bot)"})
        r.raise_for_status()
        posts = trump.parse_feed(r.text)
    except Exception as exc:
        _news_note("Trump posts", exc)
        posts = []
    first_run = not ps.get("trump_seeded")
    ps["trump_seeded"] = True
    for post in reversed(posts):  # oldest first
        if post["id"] in seen:
            continue
        seen.append(post["id"])
        if first_run or (post["when"] is not None and (now - post["when"]).total_seconds() > 90 * 60):
            continue  # old posts aren't news any more
        effects = trump.read_post(post["text"])
        if not effects:
            continue
        lines = [f"🇺🇸 <b>TRUMP POST</b> · {ago(post['when'])}",
                 f"“{esc(post['text'][:450])}{'…' if len(post['text']) > 450 else ''}”", "", "<b>Could move:</b>"]
        markets = []
        for h in effects[: int(tc.get("max_markets", 4))]:
            px, open_ = live_price(h["market"], args)
            arrow = "⬆ up" if h["direction"] > 0 else "⬇ down"
            lines.append(f"{esc(h['market'])} {arrow}: {esc(h['why'])} (topic: {esc(h['topic'])}) · {chart_link(h['market'], 5)}"
                         + ("" if open_ else " · market closed now"))
            if px:
                markets.append({"market": h["market"], "direction": h["direction"], "p0": px, "open": open_, "topic": h["topic"]})
        lines += ["", "The bot checks what really happened 30 and 120 minutes from now (paper only).",
                  "<i>A free feed is minutes late: fast traders move first. Not advice.</i>"]
        if post["url"]:
            lines.append(f'<a href="{html.escape(post["url"], quote=True)}">The post</a>')
        msgs.append("\n".join(lines))
        checks.append({"id": post["id"], "text": post["text"][:80], "at": now.isoformat(), "markets": markets, "done": []})
    ps["trump_seen"] = seen[-400:]
    # Follow-ups
    keep = []
    for c in checks:
        age = (now - pd.Timestamp(c["at"])).total_seconds() / 60
        for mins in (30, 120):
            if age >= mins and mins not in c["done"]:
                c["done"].append(mins)
                res = []
                for m in c["markets"]:
                    if not m.get("open"):
                        continue
                    px, _ = live_price(m["market"], args)
                    if not px:
                        continue
                    move = (px / m["p0"] - 1) * 100
                    right = move * m["direction"] > 0.05
                    wrong = move * m["direction"] < -0.05
                    res.append(f"{esc(m['market'])} {move:+.2f}% {'✅ as expected' if right else ('❌ the other way' if wrong else '➖ barely moved')}")
                    if mins == 120:
                        rec = ps.setdefault("trump_record", {}).setdefault(m["topic"], [0, 0])
                        rec[0] += int(right)
                        rec[1] += 1
                if res:
                    msgs.append(f"🇺🇸 <b>{mins} minutes after Trump's post</b> “{esc(c['text'])}…”\n" + "\n".join(res))
        if len(c["done"]) < 2 and age < 24 * 60:
            keep.append(c)
    ps["trump_checks"] = keep
    return msgs


def morning_briefing(cfg: dict, args) -> str:
    """A daily global briefing: top headlines, then commodities, crypto, currencies and indexes, green or red."""
    groups = [("Indexes", ["^GSPC", "^NDX", "^FTSE", "^VIX"]), ("Commodities", ["GC=F", "SI=F", "BZ=F"]),
              ("Crypto", ["BTC-USD", "ETH-USD", "SOL-USD"]), ("Currencies", ["GBPUSD=X", "EURUSD=X"])]
    names = {"^GSPC": "S&P 500", "^NDX": "Nasdaq 100", "^FTSE": "FTSE 100", "^VIX": "VIX (fear)", "GC=F": "Gold",
             "SI=F": "Silver", "BZ=F": "Brent oil", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
             "GBPUSD=X": "£/$", "EURUSD=X": "€/$"}
    tz = cfg["news"].get("timezone", "Europe/London")
    lines = [f"☀️ <b>Morning briefing</b> · {pd.Timestamp.now(tz=tz):%a %d %b}"]
    heads = market_headlines(5, 18)
    if heads:
        lines += ["", "<b>Top news</b>"] + headline_lines(heads)
    for title, syms in groups:
        rows = []
        for sym in syms:
            try:
                df, meta = get_data(sym, "1d", "1mo", getattr(args, "csv_dir", None))
                c, pc = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
                chg = (c / pc - 1) * 100
                rows.append(f"{'🟢' if chg >= 0 else '🔴'} {names.get(sym, sym)} {fmt_price(c, meta.get('currency', 'USD'))} ({chg:+.2f}%)")
            except Exception:
                continue
        if rows:
            lines += ["", f"<b>{title}</b>"] + rows
    evs = upcoming_events(cfg, 1)
    if evs:
        lines += ["", "<b>Coming up</b>"] + [esc(event_text(e)) for e in evs]
    return "\n".join(lines)


def pulse_chores(cfg: dict, args, ps: dict, state: dict) -> list[str]:
    """Jobs the all-day pulse does so they don't depend on GitHub's unreliable schedules."""
    pc, cc = cfg["pulse"], cfg.get("copy", {})
    msgs: list[str] = []
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    ny = pd.Timestamp.now(tz="America/New_York")
    # 1) Start the 0DTE scalper just before the US open (once a day, weekdays)
    if pc.get("start_scalper", True) and ny.weekday() < 5 and ps.get("scalper_day") != today:
        mins = ny.hour * 60 + ny.minute
        if 9 * 60 + 15 <= mins <= 9 * 60 + 40:
            if dispatch_workflow("scalper.yml") or not os.environ.get("GITHUB_ACTIONS"):
                ps["scalper_day"] = today
    # 2) The daily insider catch-up (every filing from the previous days), once a day
    if cc.get("enabled", True) and not OFFLINE and ps.get("insiders_day") != today:
        try:
            update_insiders(cfg, log=print)
            ps["insiders_day"] = today
        except Exception as exc:
            print(f"Insider catch-up: {exc}")
    # 3) EDGAR's live insider feed every few minutes
    if (cc.get("enabled", True) and cc.get("live", True) and not OFFLINE
            and time.time() - state.get("insider_poll", 0) >= 60 * float(cc.get("live_every_minutes", 10))):
        state["insider_poll"] = time.time()
        try:
            ist = load_insiders()
            poll_live_insiders(cfg, ist, log=print)
            msgs += new_insider_alerts(ist, cfg)
            save_insiders(ist)
        except Exception as exc:
            print(f"Insider feed: {exc}")
    # 5) Trump's posts, every few minutes
    if cfg.get("trump", {}).get("enabled", True) and not OFFLINE and \
            time.time() - state.get("trump", 0) >= 60 * float(cfg.get("trump", {}).get("every_minutes", 5)):
        state["trump"] = time.time()
        try:
            msgs += trump_chores(cfg, args, ps)
        except Exception as exc:
            print(f"Trump posts: {exc}")
    # 6) The morning briefing, once a day from 06:30 UK time
    uk = pd.Timestamp.now(tz=cfg["news"].get("timezone", "Europe/London"))
    if cfg.get("briefing", {}).get("enabled", True) and ps.get("briefing_day") != today and uk.weekday() < 5 and \
            uk.hour * 60 + uk.minute >= 6 * 60 + 30:
        ps["briefing_day"] = today
        try:
            msgs.append(morning_briefing(cfg, args))
        except Exception as exc:
            print(f"Morning briefing: {exc}")
    # 4) The watchlist check (big moves, breakouts in progress, paper stops, news) every 30 minutes
    if pc.get("run_watch", True) and time.time() - state.get("watch", 0) >= 60 * float(pc.get("watch_every_minutes", 30)):
        state["watch"] = time.time()
        try:
            watch_once(cfg, args)
        except Exception as exc:
            print(f"Watch check failed: {exc}")
    return msgs


def cmd_pulse(cfg: dict, args) -> int:
    """Reads each market every few minutes. --every 5 keeps going; --until 21:35 (UTC) or --for 340 (minutes) stops it."""
    every = float(getattr(args, "every", 0) or 0)
    started = time.time()
    until = getattr(args, "until", "") or ""
    for_min = float(getattr(args, "for_minutes", 0) or 0)
    if every > 0 and until and datetime.now(timezone.utc).strftime("%H:%M") >= until:
        print(f"After {until} UTC: nothing to do until tomorrow.")
        return 0
    ps = load_pulse()
    state: dict = {}
    while True:
        _DATA_CACHE.clear()
        try:
            msgs = pulse_once(cfg, args, ps)
        except Exception as exc:
            msgs = []
            print(f"Pulse check failed: {exc}")
        try:
            msgs += pulse_chores(cfg, args, ps, state)
        except Exception as exc:
            print(f"Pulse chores failed: {exc}")
        for item in msgs:
            deliver(cfg, item, args)
        save_pulse(ps)
        if not msgs:
            print(f"Pulse {datetime.now(timezone.utc):%H:%M} UTC: nothing new.")
        if every <= 0:
            return 0
        now = datetime.now(timezone.utc)
        if until and now.strftime("%H:%M") >= until:
            return 0
        if for_min and (time.time() - started) / 60 >= for_min:
            return 0
        # wake just after the next bar finishes (bars close on the 5-minute mark; Yahoo needs a moment)
        step = every * 60
        wait = step - (time.time() % step) + 40
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            return 0


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


def cmd_analyse(cfg: dict, args) -> int:
    """Reads the market: each market's trend, momentum and volatility, the fear gauge, breadth, insider
    buying, and whether that favours going long or short. With --symbols, reads those markets and
    says which setups (long or short) are live on each."""
    breadth = []
    if not getattr(args, "symbols", None):
        for _, symbols in iter_watchlist(cfg, args):
            for sym in symbols:
                try:
                    df, _ = get_data(sym, "1d", cfg["scan"]["history"], args.csv_dir)
                    ind = add_indicators(df, cfg)
                    lr = ind.iloc[-1]
                    if pd.notna(lr["sma200"]):
                        breadth.append((sym, bool(lr["Close"] > lr["sma200"]), bool(lr["Close"] > lr["sma50"])))
                except Exception:
                    continue
    clusters = None
    if cfg.get("copy", {}).get("enabled", True) and insiders_path().exists():
        clusters = insider_clusters(load_insiders()["buys"], cfg)
    text = market_read_text(cfg, args, breadth, clusters)
    if not text:
        print("No price data available right now.")
        return 1
    if getattr(args, "symbols", None):
        extra = []
        bench_sym = getattr(args, "benchmark", "") or ""
        bench_df = None
        if bench_sym:
            try:
                bench_df, _ = get_data(bench_sym, "1d", cfg["scan"]["history"], args.csv_dir)
            except Exception:
                bench_df = None
        both = dict(cfg, scan=dict(cfg["scan"], allow_shorts=cfg["scan"].get("allow_shorts") or "auto"))
        for sym in [x.strip() for x in args.symbols.split(",") if x.strip()]:
            try:
                df, _ = get_data(sym, "1d", cfg["scan"]["history"], args.csv_dir)
                ind = add_indicators(df, cfg)
                sigs = compute_signals(ind, align_benchmark(ind, bench_df), both, sym, bench_sym)
            except Exception:
                continue
            live = [f"{SETUP_TITLES[st_]} {d} {int(fr['score'].iloc[-1])}/100"
                    for (st_, d), (fr, _c) in sigs.items() if bool(fr["trig"].iloc[-1])]
            extra.append(f"{esc(sym)} setups today: " + (", ".join(live) if live else "none"))
            if clusters and sym.upper() in clusters:
                c = clusters[sym.upper()]
                extra.append(f"{esc(sym)} insiders: {c['insiders']} bought {fmt_money(c['total_value'], 'USD')} in the last 30 days"
                             + ("" if c["qualified"] else " (not enough to copy)"))
        if extra:
            text = text.replace("\n<i>This describes", "\n" + "\n".join(extra) + "\n<i>This describes")
    output(cfg, text, args)
    return 0


def cmd_insiders(cfg: dict, args) -> int:
    """Reads new SEC Form 4 filings (insiders buying their own company's shares) and lists the strongest."""
    if not cfg.get("copy", {}).get("enabled", True):
        print("Copying insiders is switched off ([copy] enabled = false in config.toml).")
        return 0
    if not getattr(args, "no_fetch", False):
        try:
            update_insiders(cfg, int(getattr(args, "days", 0) or 0) or None)
        except Exception as exc:
            print(f"Couldn't read the SEC filings: {exc}")
            if not insiders_path().exists():
                return 1
    st = load_insiders()
    text = insiders_report(insider_clusters(st["buys"], cfg), st.get("updated", ""))
    output(cfg, text, args)
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
    parser.add_argument("command", choices=["scan", "watch", "movers", "volatile", "news", "events", "analyse", "analyze",
                                            "market", "insiders", "pulse", "timemachine", "resend", "backtest", "status",
                                            "leaders", "test-telegram"])
    parser.add_argument("--config", default=str(BASE_DIR / "config.toml"), help="settings file (default: config.toml)")
    parser.add_argument("--symbols", help="comma-separated symbols to use instead of the watchlist")
    parser.add_argument("--benchmark", default="", help="benchmark symbol to use with --symbols")
    parser.add_argument("--csv-dir", default=None, help="read prices from CSV files in this folder instead of downloading")
    parser.add_argument("--no-telegram", action="store_true", help="print messages here instead of sending them")
    parser.add_argument("--telegram", action="store_true", help="send the report to Telegram as well (status, movers, volatile, news, events)")
    parser.add_argument("--every", type=float, default=0, help="watch: keep checking every this many minutes")
    parser.add_argument("--until", default="", help="pulse: stop at this UTC time, e.g. 21:35")
    parser.add_argument("--for", dest="for_minutes", type=float, default=0, help="pulse: stop after this many minutes")
    parser.add_argument("--days", type=int, default=0, help="insiders: how many days of SEC filings to read")
    parser.add_argument("--portfolio", action="store_true", help="backtest: also simulate the whole account at different risk caps")
    parser.add_argument("--no-fetch", action="store_true", help="insiders: list what's already saved, without downloading")
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
        "analyse": cmd_analyse,
        "analyze": cmd_analyse,
        "market": cmd_analyse,
        "insiders": cmd_insiders,
        "pulse": cmd_pulse,
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
