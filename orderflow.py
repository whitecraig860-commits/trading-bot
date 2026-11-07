"""
Order flow, as far as the data honestly allows
==============================================
Candles can't show what happens inside them. Alpaca does give the scalper real trades and quotes for SPY, QQQ and
IWM, but with its free data that's only the IEX exchange: roughly 2-3% of all US trading in these funds. Alpaca has
NO order book (depth) for US shares at all. So this reads a real but small sample, and says so every time:

  - buying vs selling volume: each IEX trade is matched to the quote at that moment. At or above the ask = a buyer
    lifted the offer, at or below the bid = a seller hit the bid, in between = whichever side of the middle it was.
  - spread widening: the spread now vs its normal over the last few minutes
  - quote sizes: bid size vs ask size at the top of the IEX book (the only depth there is)
  - absorption: a minute with much more volume than usual but hardly any price movement, i.e. one side's heavy
    buying or selling being soaked up by the other
  - liquidity pulled: quote sizes collapsing and the spread widening at the same time

It is shown in the scalper's explanation and doesn't decide trades: there's no history of it to test it on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NOTE = "IEX sample, about 2-3% of all trading; no order book is available"


def classify(trades: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    """trades: index time, columns price, size. quotes: index time, bid_price, ask_price, bid_size, ask_size.
    Adds 'side' (+1 buy, -1 sell, 0 unknown) using the quote at the time of each trade."""
    t = trades.sort_index().copy()
    q = quotes.sort_index()[["bid_price", "ask_price"]]
    m = pd.merge_asof(t.reset_index(), q.reset_index(), left_on=t.index.name or "timestamp",
                      right_on=q.index.name or "timestamp", direction="backward")
    mid = (m["bid_price"] + m["ask_price"]) / 2
    side = np.where(m["price"] >= m["ask_price"], 1, np.where(m["price"] <= m["bid_price"], -1,
                    np.where(m["price"] > mid, 1, np.where(m["price"] < mid, -1, 0))))
    # tick rule for the rest: up from the last trade = buy, down = sell
    tick = np.sign(m["price"].diff().fillna(0).to_numpy())
    side = np.where(side == 0, tick, side)
    t["side"] = side.astype(int)
    return t


def analyse(trades: pd.DataFrame, quotes: pd.DataFrame, atr: float | None = None) -> dict | None:
    if trades is None or quotes is None or len(trades) < 20 or len(quotes) < 20:
        return None
    t = classify(trades, quotes)
    buy = float(t.loc[t.side > 0, "size"].sum())
    sell = float(t.loc[t.side < 0, "size"].sum())
    tot = buy + sell
    imb = (buy - sell) / tot if tot else 0.0
    q = quotes.sort_index()
    spread = (q["ask_price"] - q["bid_price"]).clip(lower=0)
    now_spread = float(spread.iloc[-20:].median())
    norm_spread = float(spread.median())
    widening = now_spread > max(2 * norm_spread, norm_spread + 0.01)
    bs_ = float(q["bid_size"].iloc[-50:].mean())
    as_ = float(q["ask_size"].iloc[-50:].mean())
    size_now = float((q["bid_size"] + q["ask_size"]).iloc[-20:].mean())
    size_norm = float((q["bid_size"] + q["ask_size"]).median())
    pulled = size_norm > 0 and size_now < 0.3 * size_norm and widening
    # absorption: per minute volume vs price range
    per = t.resample("1min").agg({"price": ["max", "min"], "size": "sum"})
    per.columns = ["hi", "lo", "vol"]
    per = per[per.vol > 0]
    absorb = None
    if len(per) >= 3:
        last = per.iloc[-1]
        med = float(per["vol"].median())
        rng = float(last.hi - last.lo)
        scale = atr / 5 if atr else float((per.hi - per.lo).median()) or 0.01
        if last.vol >= 2 * med and rng <= 0.3 * max(scale, 1e-6):
            lt = t[t.index >= per.index[-1]]
            lb, ls = float(lt.loc[lt.side > 0, "size"].sum()), float(lt.loc[lt.side < 0, "size"].sum())
            absorb = 1 if ls > lb else -1  # heavy selling soaked up = buyers holding the price (bullish), and back
    return {"buy": buy, "sell": sell, "imbalance": imb, "spread": now_spread, "spread_norm": norm_spread,
            "widening": widening, "bid_size": bs_, "ask_size": as_, "pulled": pulled, "absorb": absorb,
            "trades": len(t)}


def lines(of: dict | None, side: str) -> list[tuple[int, str]]:
    """(sign for this trade, text) for the explanation. Never scored: shown so you can judge it."""
    if not of:
        return [(0, f"order flow: not enough IEX trades to read ({NOTE})")]
    want = 1 if side == "call" else -1
    out = []
    lean = of["imbalance"] * want
    out.append((1 if lean > 0.2 else -1 if lean < -0.2 else 0,
                f"order flow: {of['buy'] / max(of['buy'] + of['sell'], 1):.0%} of the last 5 minutes' volume was buyers "
                f"lifting the offer ({of['trades']} trades; {NOTE})"))
    if of["absorb"] is not None:
        out.append((1 if of["absorb"] == want else -1,
                    "absorption: heavy " + ("selling" if of["absorb"] > 0 else "buying")
                    + " in the last minute but the price barely moved (the other side soaked it up)"))
    if of["pulled"]:
        out.append((-1, "liquidity pulled: quote sizes collapsed and the spread widened"))
    elif of["widening"]:
        out.append((-1, f"spread widening: {of['spread']:.3f} vs {of['spread_norm']:.3f} normally"))
    tilt = (of["bid_size"] - of["ask_size"]) / max(of["bid_size"] + of["ask_size"], 1)
    if abs(tilt) > 0.3:
        out.append((1 if tilt * want > 0 else -1, f"IEX top of book leans to the {'bid' if tilt > 0 else 'ask'} "
                                                  f"({of['bid_size']:.0f} vs {of['ask_size']:.0f})"))
    return out


def fetch(stock_client, sym: str, minutes: int = 5) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Last few minutes of IEX trades and quotes from Alpaca (the free feed)."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockQuotesRequest, StockTradesRequest

    end = pd.Timestamp.now(tz="UTC")
    start = end - pd.Timedelta(minutes=minutes)
    tr = stock_client.get_stock_trades(StockTradesRequest(symbol_or_symbols=sym, start=start.to_pydatetime(),
                                                          end=end.to_pydatetime(), feed=DataFeed.IEX, limit=10000)).df
    qu = stock_client.get_stock_quotes(StockQuotesRequest(symbol_or_symbols=sym, start=start.to_pydatetime(),
                                                          end=end.to_pydatetime(), feed=DataFeed.IEX, limit=10000)).df
    if tr is None or qu is None or tr.empty or qu.empty:
        return None, None
    tr = tr.xs(sym, level=0) if isinstance(tr.index, pd.MultiIndex) else tr
    qu = qu.xs(sym, level=0) if isinstance(qu.index, pd.MultiIndex) else qu
    tr.index.name = qu.index.name = "timestamp"
    return tr[["price", "size"]].astype(float), qu[["bid_price", "ask_price", "bid_size", "ask_size"]].astype(float)
