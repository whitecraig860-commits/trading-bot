# Independent audit of every bot: baseline (20 Nov 2026)

Nothing was changed to produce this. It measures each bot as it is. Detailed reports: `audit/baseline_<bot>.md`.
Paper record: `audit/paper_results.md`. Every change from now on is logged first in `audit/logs/<bot>.md`.

**Data used:** QQQ one-minute bars (SIP) and real one-minute option trade bars from Alpaca, Mar 2024 to Oct 2026 (670 days);
QQQ shares back to Jan 2016 for the shares bot; our own recorded 5-second option bid/ask since 13 Nov 2026.
Out of sample = 2026 (the rules were designed on earlier data or on his trades, not on 2026).

## 1. Every bot, its rules and its results

One contract per trade for options bots; history at 1 cent a side + fees (the realistic cost is higher, see section 3).

| # | Bot | Rules (short) | History per day | t | PF | Max DD | 2026 (out of sample) | At 5 cents a side | Paper so far |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Stop after 2 losses (main) | 1-min VWAP/EMA50 cross + range break; +2.5% / −6% / 10 min; stop after 2 losses | −$38.25 | −32.1 | 0.48 | −$25,592 | −$42.52 | −$44.03 | +$55, 6 days |
| 2 | Original | as main, no loss stop | −$95.19 | −28.2 | 0.50 | −$63,706 | −$105.10 | −$312.52 | −$770, 5 days |
| 3 | Trailing exit | main + trail 1.5% from +2.5% | −$10.07 | −6.1 | 0.79 | −$6,747 | −$10.86 | −$31.80 | −$171, 4 days |
| 4 | Trailing exit + trend | trail, with the day's direction only | −$6.42 | −3.1 | 0.86 | −$4,353 | −$5.29 | −$29.91 | −$446, 4 days |
| 5 | His style | trail + 12% stop | −$19.48 | −8.4 | 0.75 | −$13,088 | −$23.85 | −$40.90 | −$170, 4 days |
| 6 | Skip weak crosses | main, skip crosses < $0.10 | −$31.57 | −24.7 | 0.51 | −$21,112 | −$35.85 | −$40.42 | −$273, 2 days |
| 7 | Skip weak + 9:31 + ITM | | −$34.58 | −24.0 | 0.52 | −$23,138 | −$39.26 | −$47.40 | −$275, 2 days |
| 8 | Picks like him | EMA9/20 + strong candle + before 12 + not weak | −$11.69 | −11.0 | 0.54 | −$7,864 | −$16.50 | −$25.23 | +$5, 2 days |
| 9 | His clone | picks + 3.5% / −10% / 6 min | −$11.15 | −7.2 | 0.66 | −$7,507 | −$17.15 | −$30.46 | −$207, 2 days |
| 10 | Brakes | main + stop at +$50 / −$100 | −$35.39 | −28.3 | 0.48 | −$23,679 | −$38.21 | −$39.73 | not live yet |
| 11 | 5-minute crosses | +5% / −10% / 30 min | −$16.46 | −7.3 | 0.74 | −$11,003 | −$14.03 | −$52.62 | not live yet |
| 12 | Opening move 10:00 | +10% / −10% / 60 min | −$2.46 | −2.3 | 0.76 | −$1,676 | −$6.91 | −$6.48 | not live yet |
| 13 | **One-a-day options** | shares bot's breakout, next-day ATM option | **+$14.12** | **+1.73** | **1.27** | −$3,317 | **+$16.17** | **+$8.39** | not live yet |
| 14 | **Shares one-a-day** (100 shares) | breakout of the 9:30-9:45 range, noise band, VWAP; trail 4 ATR; stop 10 ATR | **+$35.68** | **+2.71** | **1.39** | −$6,084 | **+$38.77** | **+$29.89** | +$21, 4 days (about £1,000 size) |
| 14b | Shares one-a-day, **2016-2026** | same | +$13.46 | +2.96 | 1.21 | −$7,878 | | +$7.42 | |

## 2. Ratings

| Bot | Rating | Why |
|---|---|---|
| 1-12 (all one-minute and 5-minute scalpers, opening move) | **E. DISCONTINUE** | No edge. The entry is a coin flip (Study 12: QQQ goes the signal's way 49% of the time; 5-minute: 49-50%). Every one loses in every year, in the out-of-sample year, and at realistic costs. Monte Carlo: 97-100% chance of a losing year. Filters only reduce the number of trades (Study 11 placebo). |
| 13 One-a-day options | **B. PROMISING** | Positive every year, beats 20 of 20 random-direction placebos, positive out of sample (+$16.17/day), survives 5 cents a side (+$8.39). But t 1.73 (below 2.0), **76% of its profit came from its 5 biggest trades** (without them: +$2,245 over 2.7 years), 11 losses in a row happened, and it only works on volatile days (top-10% range days +$263/day; trending months −$11/day). Not live yet. |
| 14 Shares one-a-day | **B. PROMISING** | The only bot with t above 2 in both samples (2.71 on 2024-26, 2.96 on 2016-26), positive out of sample, survives 10 cents a share a side on 2024-26, profit not dependent on a few trades (top 5 = 39%; 26% over 2016-26). But **it lost money in 2016, 2017 and 2020 (−$2,998 in the COVID crash)** and only became strongly profitable from 2022: the edge may depend on the market regime. Only 4 paper days. |

No bot is rated A (STRONG). None is approved for real money.

## 3. Findings that apply to all bots

1. **Real costs are higher than the history assumed.** Our paper trades paid $7.33 to $14.86 per round trip in bid-ask
   spread (measured on 316 trades from the recorded quotes), against $2.06 assumed in the history tests. That is about
   4-7 cents a side, so the "5 cents a side" history figures are the realistic ones.
2. **Two technical faults found and fixed, but the fixes are not live** (PR #39 not merged): trading on stale quotes
   (a fake −$147 trade on 19 Nov) and the recorder treating a data outage as a holiday (missed 9:30-10:30 on 19 Nov).
3. **Account size.** Monte Carlo (5,000 simulated years) for the two promising bots at one contract / 100 shares: on a
   $2,000 account, a 50% drawdown is near-certain; on $5,000, 47% (options) / 70% (shares 2016-26); on $25,000, 0%.
   With a small account the size must be much smaller than one contract / 100 shares (the live shares bot trades ~£1,000).

## 4. What has been tested, and what has not

| Test | Done? |
|---|---|
| Longest history | Options: Mar 2024 to Oct 2026 (Alpaca has no older option bars). Shares: 2016 to 2026. |
| Bull / bear / high and low volatility / trending / choppy / big-range days / gap opens | Yes, every bot (report section "Market conditions") |
| Named crashes | Aug 2024 spike, Apr 2025 tariff crash, Dec 2024 Fed day (all bots); Dec 2018, COVID 2020, 2022 bear (shares only: no option data) |
| Out of sample | 2026 for every bot |
| Higher costs (2, 3, 5, 10 cents a side) | Yes |
| Late fills (1 and 2 minutes) | Yes (options bots 1-12) |
| Rejected orders (10%) | Yes (bots 1-12) |
| Connection outage (one random hour every day, bot blind, acts after) | Yes (bots 1-12) |
| Settings wobbled ±20% (target, stop) | Yes (bots 1-12) |
| Monte Carlo, 5,000 runs, random order + random extra slippage, 3 account sizes, drawdown and ruin odds | Yes, every bot |
| Dependence on the biggest trades | Yes ("top5 share", "net without top 5") |
| Live vs history: same signals and trades | Main bot: replay of recorded prices reproduces its real trades on 17 and 18 Nov. 5-minute bot: live signals = history signals (test data). Others: not yet. |
| Partial fills, minimum order size | Not meaningful for one contract; needed before sizing up |
| Real-broker order rejection, duplicate orders, reconnection | **Not possible** without a broker paper account connected; code review only: each bot holds one position at a time and closes it at a restart |
| Late fills, outage, rejections for bots 13-14 | **Not yet** (they use a different engine; next step) |
| Real flash-crash behaviour of options | **Not possible**: no option data before 2024 |

## 5. Plan, in priority order

1. **Merge PR #39** so the two data fixes and bots 10-13 go live (bot 13 has no paper record until then).
2. **Stop spending effort on bots 1-12** (rated E). Suggest keeping only bots 1 and 2 on the page as controls and retiring
   the rest, with the user's agreement.
3. **Finish the stress programme for bots 13 and 14:** late fills, outages, rejected orders, parameter wobble (noise band,
   0.3 ATR buffer, 4 ATR trail), and the regime question: why the shares edge was absent in 2016-2021.
4. **Paper validation for bots 13 and 14 before any real money:** at least 60 trading days and 40 trades each; live
   signals compared day by day with the history engine on the same day; actual fills vs expected; costs measured.
5. **Position sizing study** for a small account (fractional shares; options are 100-share contracts, too big for £1,000).
6. Every change: logged in `audit/logs/<bot>.md` first, tested against the unchanged bot on identical data, then on
   out-of-sample data, by market condition, one variable at a time.
