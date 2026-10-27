# Setup Scanner Bot

Checks your watchlist and the day's biggest movers every night, scores two evidence-based setups from 0 to 100, and sends your phone a Telegram message when one scores 70 or more. During market hours it also does a quick check every 30 minutes for big moves, breakouts in progress and news. Every strong alert is paper-traded automatically (no real money), so you can see whether it actually works before you risk any.

**The two setups**

- **Trend breakout**: a fresh close above the 55-day high while price is above its 200-day average.
- **Pullback in a trend**: a sharp two-day dip (RSI(2) under 10) while price is above its 200-day average.

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
| `python bot.py news` | Market headlines and big events in the next 7 days; add `--symbols AAPL,RR.L` for one market |
| `python bot.py events` | Big scheduled events for the next 14 days |
| `python bot.py backtest` | Test both setups on 10 years of prices, with costs |
| `python bot.py status` | The paper-trading account |
| `python bot.py leaders` | The watchlist ranked by 12-month momentum |
| `python bot.py test-telegram` | Send a test message |

`scan` and `watch` send to Telegram. The other commands print in the terminal; add `--telegram` to send them too. Add `--no-telegram` to anything to print instead of sending. `--symbols AAPL,MSFT --benchmark SPY` tries other markets without editing the settings.

## Run it automatically

**Free, in the cloud (GitHub Actions)**: create a free GitHub account, make a new **private** repository, and upload all these files (including the `.github` folder). In the repository, go to Settings, Secrets and variables, Actions, and add `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`. Leave them empty in `config.toml`. Two schedules then run themselves, even with your computer off:

- **Setup scanner**: every night at 00:23 UTC (the full scan; alerts are waiting before the London open).
- **Market watch**: every 30 minutes on weekdays from 07:07 to 21:37 UTC (the quick check).

Use the Actions tab to run either one now. Together they use well under the 2,000 free minutes a month GitHub gives private repositories.

**On your own computer**: schedule `python bot.py scan` once a night (Windows Task Scheduler, or `crontab -e` on a Mac or Linux), and leave `python bot.py watch --every 10` running during market hours for faster checks. The computer has to be on.

If Yahoo Finance blocks the cloud server (it sometimes rate-limits them), run the bot on your own computer instead.

## How "real time" it is

The quick check sees prices as Yahoo Finance publishes them. Yahoo lists Nasdaq shares, crypto and currencies as real time, London shares as 20 minutes delayed and COMEX gold futures as 30 minutes delayed. That's fine for alerts, but check your broker's live price before placing anything. The setups themselves are judged on closing prices each night, because that's what the backtest and the paper trades use.

## Files

- `bot.py`: the bot.
- `config.toml`: every setting, with notes, including the movers lists, news, event dates and the watchlist.
- `state/`: created on first run. `paper.json` holds the paper account (delete it to start again); `watch.json` remembers what the quick check already sent; `scan_log.csv` records every signal; `backtest_trades.csv` every backtest trade.
- `tradingview/setup_score.pine`: the same scoring as a TradingView indicator (paste it into the Pine Editor, add it to a chart, then create an alert on "Any alert() function call").
- `.github/workflows/`: the nightly scan and the market watch schedules.

## Before you use real money

Run `python bot.py backtest`, then paper-trade until you have at least 30 closed trades (with the default watchlist that's likely three to four months). Only consider small real positions if both show positive expectancy after costs. Set `backtest.min_score = 70` to test exactly what the alerts would have done. Set realistic costs for your markets: about 0.1% a side is sensible for shares, much less for major currency pairs, and more for small coins.

Movers lists and big moves are leads, not signals. A share that's on a movers list must pass exactly the same rules as anything else, and research has found that shares which grab attention or swing wildly have tended to do worse afterwards, on average.
