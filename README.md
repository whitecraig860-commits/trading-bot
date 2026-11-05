# Setup Scanner Bot

Reads the market, checks your watchlist and the day's biggest movers every night, copies company insiders who are buying their own shares, scores three evidence-based setups from 0 to 100, and sends your phone a Telegram message when one scores 70 or more. During market hours it also does a quick check every 30 minutes for big moves, breakouts in progress and news. Every strong alert is paper-traded automatically (no real money), so you can see whether it actually works before you risk any.

**The setups**

- **Trend breakout**: a fresh close above the 55-day high while price is above its 200-day average.
- **Pullback in a trend**: a sharp two-day dip (RSI(2) under 10) while price is above its 200-day average. When it bounces, the stop moves to break-even and then trails under the 20-day low to let the winner run (`pullback_exit = "trail"`).
- **Copy the insiders**: several directors, or the CEO or CFO, have just bought their own company's shares with their own money (see below).

**What 10 years of real prices said** (29 markets, `python bot.py backtest`, costs included):
- **Trend breakouts (long) are the money-maker**: +0.79R a trade over 652 trades, 40% won, average win 3.4R, best +61.8R, with 89 trades making 3R or more. Positive in both the earlier and the later half of the test. Most trades lose a little; a few win big. At £100 risk, that's a £90 loss or a £340+ win, sometimes £1,000s.
- **Pullbacks that sell on the first bounce had no edge** (-0.01R: lots of small wins like +£2, and losses that cancel them out). **Letting them run** turned that into +0.12R a trade with a best of +13.7R, so that's the default now.
- **The score didn't help breakouts**: those scoring 50-69 did as well as 70+, so breakouts alert from 50 (`setup_min_score`).
- **Daily shorts lost money** (breakouts -0.27R, pullbacks -0.04R a trade), even only shorting falling markets, so `allow_shorts = false` for the nightly scan. Shorting still happens in the 5-minute pulse and the scalper's puts. `"auto"` (short only when the market's falling) and `true` are still there if you want them; shorts need a spread bet, CFD or margin account.

**Reading the market.** `python bot.py analyse` (also sent with every nightly scan) shows, for each main market: the trend, this month's and the last 3 months' returns, how jumpy it is compared with normal, and whether that favours longs or shorts. It also shows the VIX "fear gauge", how many of your watchlist markets are above their 200-day average (breadth), and which shares insiders are buying. `--symbols AAPL,TSLA` reads those instead and says which long or short setups are live on each.

**How much each trade risks (confidence sizing).** The normal risk is `risk_per_trade_pct` of the account (2% = £100 on £5,000). Before each trade the bot adds up what agrees and what doesn't: the score, whether the wider market agrees, this setup's own 10-year record on that market, the time machine, whether the news headlines lean good or bad, earnings or big events close by, insider buying, and very high volatility. 3+ points is **HIGH** confidence and risks 1.5x (£150); 0 or less is **LOW** and risks 0.5x (£50). Each alert lists every reason. Nothing ever risks more than `sizing.max_risk_pct` (3%), because the 10-year test's worst losing run for breakouts was 26.7R: at 20% a trade that would have emptied the account. `python bot.py status` shows how HIGH, NORMAL and LOW trades have really done, so you can see whether the bigger bets earn their size. Change `risk_per_trade_pct` and the next scan resizes the open paper trades to match.

**News.** Headlines come from Yahoo Finance, Google News and Yahoo's RSS feed, newest first, with duplicates and share-price pages removed. Yahoo's main news service often blocks cloud servers like GitHub's (that's why alerts used to say "no headlines"), so the other two fill in, and the run log says when a source fails. Searches use the company's name when the bot knows it (from the movers lists and SEC filings), so short tickers like IT (Gartner) don't pick up other companies' news. Studies disagree on whether trading on news mood works, so the tone of the headlines only nudges the confidence; it never makes a trade on its own.

**Trump's posts.** While the pulse runs, it reads Donald Trump's Truth Social posts every 5 minutes (through the trumpstruth.org archive, because Truth Social blocks automated readers). A post about tariffs, China, the Fed, oil or Iran, crypto, the stock market or a named company gets an alert listing the markets it could move and which way, with live-chart links. 30 and 120 minutes later the bot reports what really happened (✅ as expected, ❌ the other way). Posts with nothing market-related are ignored. It's paper only, and a free feed is minutes late, so fast traders move first: the follow-up checks are the honest test of whether anything is left to catch.

**Morning briefing.** On weekdays from 06:30 UK time: the top market headlines, then the S&P 500, Nasdaq, FTSE, VIX, gold, silver, oil, Bitcoin, Ethereum, Solana and the pound and euro, each green or red, and the big events coming up.

**Chart pictures.** Every alert comes with a chart of what the market looked like: daily candles with the 20, 50 and 200-day averages and the entry, stop and target lines. Every closed paper trade gets one showing how it went. The 5-minute pulse's signals and results, and the scalper's buys and sells, come with a 5-minute chart with VWAP, its bands and the opening range. Turn them off with `[charts] enabled = false`.

**Every 5 minutes: gold, the S&P 500, Nasdaq, Russell 2000, FTSE 100 and Bitcoin.** `python bot.py pulse --every 5` (GitHub runs it on weekdays from 07:00 to 21:35 UTC) reads each market on 5-minute bars and works out:
- whether it's **trending up, trending down or choppy**, from VWAP and its slope, the 9/21/50 EMAs, the 1-hour trend, the opening range and the day's open
- **which approach has actually made money on that market over the last 60 days**, after realistic costs for that market, by testing five of them: buying dips in a trend, opening-range breakouts, fading stretches back to VWAP, plain VWAP crosses (what the old scalper did), and last-half-hour momentum (Gao, Han, Li & Zhou, 2018)
- whether the approach that fits today's market, and has been working, has a **signal right now**

You get a brief when each market opens, a message when one changes character (at most 3 a day each), signals with entry, stop and target, and a **WON/LOST £** message when each paper trade ends. After the US close you get the day's results by approach. Each paper trade risks `risk_per_trade_pct` of `account.size` (£100 now), so the money figures are what you'd have made or lost at that size.

**Expect it to say "sit out" a lot.** On real 5-minute data from the last 60 days, none of the five approaches made money after costs on any of the six markets (before costs most were close to break-even, which matches the research on day trading). The pulse only sends a signal when an approach has made at least +0.1R a trade lately (`min_edge_r`), so when nothing is working it tells you so instead of guessing. The market reading (trend or chop, levels, what's working) is still there every time.

**The 0DTE scalper now trades with the trend.** It used to buy calls on any one-minute tick above VWAP, even while the market was falling. Now it judges its triggers on 5-minute bars and checks the same trend reading as the pulse. It only buys calls when the trend is up, puts when it's down, and nothing when the market is choppy. It also stops a symbol for the day after 2 losses, waits 30 minutes after any loss, and records the price the option actually sold for. `python scalper.py backtest` prints the old rules and the new rules side by side: on the last ~20 days of real 1-minute prices the new rules made +0.10R a trade on the share price (old rules: 0.00R), with the VWAP trigger best and the opening-range trigger losing, so that trigger is off. It now bids just above the middle of the bid/ask spread instead of paying the asking price: research on retail 0DTE traders ([Beckmeyer et al.](https://www.bnnbloomberg.ca/day-traders-lose-358-000-per-day-gambling-on-zero-day-options-1.1910634)) found most of their losses came from trading costs. Even so, 0DTE options are the riskiest part of this bot: keep them on paper.

**Copying other people's trades: the insiders.** US company directors and officers must report every trade in their own company's shares to the SEC within two business days (Form 4). Of all the "copy someone's trades" ideas, their open-market *purchases* have the best research behind them: they have tended to beat the market over the following months, most clearly when several insiders buy together, when the CEO or CFO buys, and when the trade isn't part of a pre-arranged 10b5-1 plan. The bot reads every Form 4 from the SEC each morning, keeps only those purchases, and the nightly scan copies the strongest as a long trade at the next open. It sets a 3 x ATR trailing stop, sells after about 3 months at most, and skips any share whose price has already run 30% past what the insiders paid. Insider *sales* are ignored, because people sell for tax, houses and diversification. Two other ideas were left out on purpose. Politicians' trades are reported up to 45 days late, and studies have mostly found no edge in copying them. Copy-trading apps like eToro have no way for a bot to copy them.

**The score** gives points for trend alignment, heavy volume, a quiet squeeze first, trend strength, beating the market and the market's own trend. It takes points off for chasing a stretched move, a news-sized one-day drop, or earnings within a week.

**Every alert also shows**

- the entry, stop, exit plan and position size (1% risk)
- how volatile the market is, and that the size is smaller for volatile ones
- warnings for big events in the next 2 days (rate decisions, inflation, jobs, the Budget)
- the setup's own past record on that market over 10 years: how often it fired, how often it won, the average result
- the latest headlines, with links
- which movers list it came from, if any

Education and tooling only. Not financial advice. Any setup can lose.

## Quick start (your own computer)

1. **Telegram bot**: in Telegram, message `@BotFather`, send `/newbot`, follow the prompts and copy the token. Send your new bot any message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy the number after `"chat":{"id":`. That is your chat ID. Keep the token secret.
2. **Python**: install Python 3.11 or newer from python.org (tick "Add Python to PATH" on Windows).
3. **Install**: open a terminal in this folder and run `python -m pip install -r requirements.txt` (on a Mac, use `python3` in every command).
4. **Settings**: open `config.toml`, set your account size and currency, paste the token and chat ID, and edit the watchlist.
5. **Test**: `python bot.py test-telegram`, then `python bot.py backtest`, then `python bot.py scan`.

## Commands

| Command | What it does |
| --- | --- |
| `python bot.py scan` | The nightly check: watchlist plus today's movers, alerts, paper trades, a summary |
| `python bot.py watch` | Quick check during market hours: big moves, breakouts in progress, paper stops hit, new headlines on what the paper account holds |
| `python bot.py watch --every 10` | Keeps checking every 10 minutes until you press Ctrl+C |
| `python bot.py movers` | Today's most active, biggest risers and biggest fallers (US and UK), each checked against the rules |
| `python bot.py volatile` | The most volatile markets right now, with their trend |
| `python bot.py pulse --every 5` | Read gold, SPY, QQQ, IWM, FTSE and Bitcoin every 5 minutes: trend or chop, the approach that's working, signals, WON/LOST paper trades (add `--until 21:35` to stop at a UTC time) |
| `python bot.py analyse` | Read the market: trend, momentum, volatility, fear gauge, breadth, insider buying, long or short |
| `python bot.py insiders` | Read new SEC insider filings and list the strongest insider buying (`--days 10` reads further back, `--no-fetch` lists what's saved) |
| `python bot.py news` | Market headlines and big events in the next 7 days; add `--symbols AAPL,RR.L` for one market |
| `python bot.py events` | Big scheduled events for the next 14 days |
| `python bot.py backtest` | Test both setups on 10 years of prices, with costs |
| `python bot.py status` | The paper-trading account |
| `python bot.py leaders` | The watchlist ranked by 12-month momentum |
| `python bot.py test-telegram` | Send a test message |

`scan` and `watch` send to Telegram. The other commands print in the terminal; add `--telegram` to send them too. Add `--no-telegram` to anything to print instead of sending. `--symbols AAPL,MSFT --benchmark SPY` tries other markets without editing the settings.

## Run it automatically

**Free, in the cloud (GitHub Actions)**: create a free GitHub account, make a new **private** repository, and upload all these files (including the `.github` folder). In the repository, go to Settings, Secrets and variables, Actions, and add `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`. Leave them empty in `config.toml`. Also add `SEC_USER_AGENT` set to your name and email (for example `Jane Smith jane@example.com`): the SEC asks everyone who downloads its filings to identify themselves, and may refuse requests that don't. These schedules then run themselves, even with your computer off:

- **Market pulse**: every 5 minutes on weekdays, about 06:07 to 21:35 UTC. It also does the jobs that need good timing: it **starts the 0DTE scalper** just before the US open, runs the **market watch** every 30 minutes, does the **daily insider catch-up**, and reads the SEC's **live insider feed** every 10 minutes. GitHub often starts scheduled runs late or skips them when it's busy (the scalper's own schedule once started at 22:22 UTC, after the US close), so the pulse asks to start every hour; only one runs at a time and an extra start waits to take over the next shift. You'll see some grey "cancelled" runs in the Actions tab: that's those spare starts, and it's normal. This runs about 15 hours a day, which is only free on a **public** repository.
- **Setup scanner**: every night at 00:23 UTC (the market read and the full scan; alerts are waiting before the London open). GitHub sometimes starts it a few hours late; it still works.
- **0DTE scalper**: started by the pulse at the US open (its own schedule is a backup).
- **Market watch** and **Insider buying**: run inside the pulse now; use the Actions tab to run either by hand.

Use the Actions tab to run any of them now. On a public repository GitHub's standard runners are free; on a private one the pulse alone would use far more than the 2,000 free minutes a month.

**On your own computer**: schedule `python bot.py scan` once a night (Windows Task Scheduler, or `crontab -e` on a Mac or Linux), and leave `python bot.py watch --every 10` running during market hours for faster checks. The computer has to be on.

If Yahoo Finance blocks the cloud server (it sometimes rate-limits them), run the bot on your own computer instead.

## How "real time" it is

The quick check sees prices as Yahoo Finance publishes them. Yahoo lists Nasdaq shares, crypto and currencies as real time, London shares as 20 minutes delayed and COMEX gold futures as 30 minutes delayed. That's fine for alerts, but check your broker's live price before placing anything. The setups themselves are judged on closing prices each night, because that's what the backtest and the paper trades use.

## Files

- `bot.py`: the bot.
- `config.toml`: every setting, with notes, including the movers lists, news, event dates and the watchlist.
- `state/`: created on first run. `paper.json` holds the paper account (delete it to start again); `insiders.json` the insider purchases read from the SEC; `watch.json` remembers what the quick check already sent; `scan_log.csv` records every signal; `backtest_trades.csv` every backtest trade.
- `tradingview/setup_score.pine`: the same scoring as a TradingView indicator (paste it into the Pine Editor, add it to a chart, then create an alert on "Any alert() function call").
- `.github/workflows/`: the nightly scan, market watch, insider buying and scalper schedules.

## Before you use real money

The copy-the-insiders setup can't be backtested (the bot only keeps recent filings), so the paper account is its only test. Shorts are in the backtest: compare the long and short tables. Run `python bot.py backtest`, then paper-trade until you have at least 30 closed trades (with the default watchlist that's likely three to four months). Only consider small real positions if both show positive expectancy after costs. Set `backtest.min_score = 70` to test exactly what the alerts would have done. Set realistic costs for your markets: about 0.1% a side is sensible for shares, much less for major currency pairs, and more for small coins.

Movers lists and big moves are leads, not signals. A share that's on a movers list must pass exactly the same rules as anything else, and research has found that shares which grab attention or swing wildly have tended to do worse afterwards, on average.
