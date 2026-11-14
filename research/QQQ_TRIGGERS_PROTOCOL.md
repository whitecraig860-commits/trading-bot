# Study 5: the three one-minute QQQ triggers from the "Scalp City" video. Pre-registered protocol

**Status:** written and committed on 2026-11-12, before any code for this study was written or any result seen. Nothing here changes after results, except dated amendments at the end. This is a backtest only: no orders are placed.

## 1. What is being tested

The bot's owner described its rules in a video the user supplied:
- It trades options with one day to expiry, off a one-minute chart.
- It has three triggers:
  - a candle closes across VWAP;
  - a candle closes across the 50 EMA;
  - price breaks the range of the first 15 minutes.
- Closing above buys a call. Closing below buys a put.

His exact filters, sizes and exits are **not public**. The exits below are my reconstruction from his posted trades of 11 November 2026 (labels `pct_lock`, `atr_stop`, `atr_trail`, `exit_at_cost`; typical win +2% to +3.5% of the option price; typical loss −4.5% to −10%; holds of seconds to 5 minutes). So this tests **his stated entry idea with simple exits**, not his actual bot.

## 2. Data

- **QQQ:** one-minute bars, Alpaca SIP, regular session, 2024-03-01 to 2026-10-31.
- **Options:** real one-minute trade bars from Alpaca for each contract traded. These are trade prices, not bid/ask quotes, which Alpaca does not keep; costs are added separately (§5).
- **Holdout:** 2026-01-01 onward.

## 3. Entries (bar close at minute t; order sent for the next minute)

- **VWAP:** the session's volume-weighted average price, from 09:30.
- **EMA50:** the 50-period exponential average of one-minute closes, carried across days.
- **Opening range:** the high and low of 09:30–09:44.
- **Triggers:**
  - VWAP cross: the previous close is on one side of VWAP and this close is on the other. Up = call, down = put.
  - EMA cross: the same, against EMA50.
  - Range break: the first close above the range high (call) or below the range low (put), at most once per direction per day.
- **Window:** signals from 09:45 to 15:30 New York time.
- **One position at a time.** Signals while in a trade are ignored.
- **Contract:** expiry = the next trading day; strike = the whole-dollar strike nearest the QQQ close at the signal.
- **Entry price:** the open of the contract's first one-minute bar starting in the 3 minutes after the signal bar closes. If there is none, the signal is skipped and counted.

## 4. Exits (checked on each one-minute option bar, starting with the entry bar)

- **Profit lock:** a sell limit at entry × 1.025.
- **Stop:** entry × 0.94. If the bar opens below the stop, the exit is that open.
- **Time stop:** 10 minutes after entry, at that bar's close.
- **End of day:** 15:55, at that bar's close.
- **If the stop and the target are both touched in the same bar,** the stop is assumed to come first (conservative). The opposite assumption is reported as a sensitivity line only.

## 5. Costs

- **Per side:** 0, 1 and 2 cents per share of option price are added on entry and subtracted on exit. The **1-cent case is the base case.**
- **Fees:** $0.03 per contract per side.
- **Size:** one contract.

## 6. What is reported

- Trades, win rate, average win and loss, and profit per trade.
- Profit per day for one contract, in dollars and pounds at 0.76.
- A t-statistic on daily profit (Newey-West, 5 lags).
- Results by trigger, by year, and for the holdout.
- **Sensitivity (reported, never picked):** target 2% and 4%; stop 4% and 10%; time stop 5 and 20 minutes; each trigger alone.

## 7. Pass / fail (base case: all three triggers, 1 cent per side, conservative ordering)

The idea **passes** only if all of these hold:
1. Mean daily profit is above 0 with t ≥ 2.0 over the full period.
2. Mean daily profit is above 0 in the holdout.
3. Mean daily profit is above 0 at 2 cents per side.

- **If it passes:** the next step is a forward test against the recorded bid/ask prices (`tracker/`), under its own protocol, before any paper bot is built.
- **If it fails:** nothing is built on these triggers as stated.

## 8. Limitations

1. The exits and filters are my reconstruction, not the owner's.
2. Option trade bars are not quotes. Real spreads vary through the day and are widest near the open.
3. One-minute bars cannot show what happens inside a minute. His bot exits within seconds.
4. About 2.7 years of data.

## Amendments

(none)
