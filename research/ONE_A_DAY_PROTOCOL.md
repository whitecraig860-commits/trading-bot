# Study 6: the "one trade a day" QQQ bot. Pre-registered protocol

**Status:** written and committed on 2026-11-13, before any code for this study was written or any result seen. Nothing changes after results except dated amendments at the end. Backtest only: no orders.

## 1. What is being tested

The bot's owner posted its rules on 13 November 2026:
- It marks the 09:30 to 09:45 high and low.
- From 10am to 2pm it checks every 10 minutes.
- It buys calls when a 1-minute candle closes above the range high plus 0.3 ATR (5-minute), above the noise band and above VWAP.
- It buys puts when the candle closes below all three.
- The option is about $2 in the money, expiring in 1 to 3 trading days.
- One trade a day; some days none.
- Once price moves 4 ATR its way, it sells if it gives back half.
- Safety stop at 10 ATR; otherwise out at 3:45.

## 2. My reading of the parts he did not define (fixed now)

- **ATR:** the average true range of the last 14 completed 5-minute QQQ candles, at the check time. It is frozen at entry for the exits.
- **Noise band:** today's open × (1 ± the average absolute move from the open to this minute of the day, over the previous 14 trading days). This is the "noise area" of Zarattini, Aziz and Barbon (2024), which the wording suggests.
- **VWAP:** the session's volume-weighted average price from 09:30.
- **Check times:** the 1-minute candles closing at 10:00, 10:10, and so on to 14:00.
- **Entry:** at the first check where every condition for one side holds. The order goes in the next minute. No further trades that day.
- **Option:** expiry two trading days ahead (the middle of his range). Strike: for a call, the nearest whole strike to price minus $2; for a put, price plus $2.
- **Exits, measured on QQQ's 1-minute closes from the entry price:**
  - **Safety stop:** an adverse move of 10 ATR.
  - **Trail:** once the best favourable move has reached 4 ATR, exit when the favourable move falls to half of its best.
  - **Time:** the candle closing at 15:45.

## 3. Data

- QQQ 1-minute bars, Alpaca SIP, 2024-03-01 to 2026-10-31. The first 14 trading days only build the noise band.
- Real 1-minute option trade bars from Alpaca for the contract traded.
- **Option fills:** entry at the open of the contract's first bar in the 5 minutes after the signal; exit at the close of its last bar at or before the exit minute (no more than 10 minutes old). A trade with no usable option price is counted separately and scored on the shares only.
- **Holdout:** 2026-01-01 onward.

## 4. Costs

- Options: 0, 2 and 5 cents per share per side. **2 cents is the base case.** Fees of $0.03 per contract per side. One contract.
- Shares (reported alongside, to separate the signal from the option): 100 shares, 1 cent per share per side.

## 5. What is reported

- Trades, days with no trade, win rate, average win and loss, profit per trade and per day (dollars, and pounds at 0.76).
- A t-statistic on daily profit (Newey-West, 5 lags).
- By side, by year, by exit reason, and the holdout.
- The largest single-day loss and the worst losing run.
- **Sensitivity (reported, never picked):** expiry 1 and 3 days; at-the-money strike; trail at 3 and 5 ATR; no noise-band condition; no 0.3 ATR buffer.

## 6. Pass / fail (options, 2 cents per side)

The idea passes only if all hold:
1. Mean daily profit above 0 with t ≥ 2.0 over the full period.
2. Mean daily profit above 0 in the holdout.
3. Mean daily profit above 0 at 5 cents per side.
4. The shares version is also profitable over the full period (so the result is not an accident of option pricing).

- **If it passes:** a forward paper test at recorded bid/ask prices, under its own short protocol.
- **If it fails:** it is not built.

## 7. Limitations

1. Section 2 is my reading, not his code.
2. Option trade bars are not quotes; in-the-money options trade less often, so some fills are stale by minutes.
3. About 2.7 years, one trade a day at most: a few hundred trades.
4. The published noise-band strategy was tested on SPY to early 2024; this period is mostly after that.

## Amendments

(none)
