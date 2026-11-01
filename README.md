# Setup Scanner Bot

Reads the market, checks your watchlist and the day's biggest movers every night, copies company insiders who are buying their own shares, scores three evidence-based setups from 0 to 100, and sends your phone a Telegram message when one scores 70 or more. During market hours it also does a quick check every 30 minutes for big moves, breakouts in progress and news. Every strong alert is paper-traded automatically (no real money), so you can see whether it actually works before you risk any.

**The setups**

- **Trend breakout**: a fresh close above the 55-day high while price is above its 200-day average.
- **Pullback in a trend**: a sharp two-day dip (RSI(2) under 10) while price is above its 200-day average.
- **Copy the insiders**: several directors, or the CEO or CFO, have just bought their own company's shares with their own money (see below).

**Long and short.** With `allow_shorts = "auto"` (the default now) the bot also looks for the mirror image of the first two setups: a break below the 55-day low, or a sharp two-day jump, in a falling market. It only goes short when the wider market (the group's benchmark) is in a downtrend too, because shorting rising markets rarely pays. `true` looks for shorts everywhere, `false` turns them off. Shorts need a spread bet, CFD or margin account, and a short's loss has no ceiling if the price gaps up.

**Reading the market.** `python bot.py analyse` (also sent with every nightly scan) shows, for each main market: the trend, this month's and the last 3 months' returns, how jumpy it is compared with normal, and whether that favours longs or shorts. It also shows the VIX "fear gauge", how many of your watchlist markets are above their 200-day average (breadth), and which shares insiders are buying. `--symbols AAPL,TSLA` reads those instead and says which long or short setups are live on each.

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

- **Insider buying**: every morning at 05:41 UTC, Tuesday to Saturday (reads the previous US business day's SEC filings).
- **Setup scanner**: every night at 00:23 UTC (the market read and the full scan; alerts are waiting before the London open).
- **Market watch**: every 30 minutes on weekdays from 07:07 to 21:37 UTC (the quick check).

Use the Actions tab to run either one now. Together they use well under the 2,000 free minutes a month GitHub gives private repositories.

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
