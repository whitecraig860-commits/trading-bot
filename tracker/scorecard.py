"""
Honest scorecard for the Discord group's posted QQQ option trades
=================================================================
Reads the trades as posted (state/discord_trades.csv) and the recorded bid/ask history (state/quotes), and re-prices
every trade the way a real order would fill: BUY at the ask, SELL at the bid, using the recorded quote nearest to
the posted time (no more than 15 seconds away). The free quote feed is Alpaca's 'indicative' one: close to,
but not exactly, the real exchange quotes, and the scorecard says which feed each price came from. Trades on days with no recorded quotes are counted, not guessed.

  python tracker/scorecard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FEE = 0.03  # dollars per contract per side (regulatory and exchange fees; commission is zero)


def quotes_for(day: str) -> pd.DataFrame | None:
    files = sorted((ROOT / "state" / "quotes").glob(f"{day}-*.csv.gz"))
    if not files:
        return None
    q = pd.concat([pd.read_csv(f) for f in files])
    # 'when' is the time the quote was made, not when we fetched it (free quotes can arrive 15 minutes late)
    q["when"] = pd.to_datetime(q["quote_time"])
    return q.dropna(subset=["when", "bid", "ask"]).drop_duplicates(["contract", "when"])


def fill(q: pd.DataFrame, expiry_hint, typ: str, strike: float, when: pd.Timestamp, side: str):
    """The recorded quote nearest in time to the posted fill, no more than 15 seconds away."""
    c = q[(q["type"] == typ) & (q["strike"] == strike) & ((q["when"] - when).abs() <= pd.Timedelta(seconds=15))]
    if expiry_hint:
        c = c[c["expiry"] == expiry_hint]
    if c.empty:
        return None
    c = c.assign(gap=(c["when"] - when).abs())
    first = c[c["gap"] == c["gap"].min()]
    return first, ("ask" if side == "buy" else "bid")


def main() -> int:
    path = ROOT / "state" / "discord_trades.csv"
    t = pd.read_csv(path, dtype={"expiry": str, "trader": str}).fillna({"expiry": "", "trader": ""})
    rows = []
    for _, r in t.iterrows():
        posted = (r.sell - r.buy) * 100 * r.qty
        row = {"date": r.date, "trade": f"{int(r.qty)}x {int(r.strike)}{r.type} {r.buy_time}", "posted": posted,
               "realistic": None, "note": ""}
        q = quotes_for(r.date)
        if q is None:
            row["note"] = "no recorded quotes that day"
        else:
            b = fill(q, r.expiry, r.type, float(r.strike), pd.Timestamp(f"{r.date} {r.buy_time}"), "buy")
            s = fill(q, r.expiry, r.type, float(r.strike), pd.Timestamp(f"{r.date} {r.sell_time}"), "sell")
            if not b or not s:
                row["note"] = "no quote within 15 seconds"
            else:
                # if the expiry isn't known, use the one whose mid price is closest to the posted buy price
                bq, sq = b[0], s[0]
                if not r.expiry:
                    bq = bq.assign(d=((bq.bid + bq.ask) / 2 - r.buy).abs()).sort_values("d").head(1)
                    sq = sq[sq.expiry == bq.expiry.iloc[0]]
                if sq.empty:
                    row["note"] = "no matching sell quote"
                else:
                    ask, bid = float(bq.ask.iloc[0]), float(sq.bid.iloc[0])
                    row["realistic"] = (bid - ask) * 100 * r.qty - 2 * FEE * r.qty
                    row["note"] = f"ask {ask:.2f} (posted {r.buy:.2f}), bid {bid:.2f} (posted {r.sell:.2f}), feed {bq.feed.iloc[0]}"
        rows.append(row)
    df = pd.DataFrame(rows)
    for day, g in df.groupby("date"):
        print(f"\n{day}: {len(g)} trades, posted total ${g.posted.sum():+,.0f}")
        for _, x in g.iterrows():
            real = "      n/a" if x.realistic is None or pd.isna(x.realistic) else f"${x.realistic:+8,.0f}"
            print(f"   {x.trade:28s} posted ${x.posted:+7,.0f}   realistic {real}   {x.note}")
    done = df.dropna(subset=["realistic"])
    print(f"\nALL DAYS: {len(df)} trades posted, total ${df.posted.sum():+,.0f}, "
          f"{(df.posted > 0).mean():.0%} winners as posted.")
    if len(done):
        print(f"Re-priced at real bid/ask: {len(done)} trades, posted ${done.posted.sum():+,.0f} -> realistic "
              f"${done.realistic.sum():+,.0f}; {(done.realistic > 0).mean():.0%} winners; "
              f"average cost of real fills ${(done.posted - done.realistic).mean():,.0f} per trade.")
    else:
        print("No trades could be re-priced yet: the price recorder has to be running on the days they trade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
