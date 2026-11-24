# QQQ Trader replication system: architecture (v1, 24 Nov 2026)

**Paper trading only. Nothing in this package can place a real order: there is no broker code in it at all.**

## What it does

1. **Reads** the QQQ Trader #1 / #2 / #3 messages from an authorised source (see "Message sources").
2. **Parses** each message into a structured event (trader, BOUGHT/SOLD, quantity, strike, CALL/PUT, price, reported P&L,
   time stamp), and **flags** anything incomplete or ambiguous instead of guessing.
3. **Stores** everything in a SQLite database (`state/copytrader/copytrader.db`): the raw message, the parsed event and the
   flags. Raw messages are never altered.
4. **Rebuilds each trader's positions** (scaling in, partial exits, closes). A SELL closes an existing long position; it is
   never treated as opening a short. A SELL with no open position is flagged, not invented.
5. **Measures** each trader separately: win rate, average win and loss, total P&L, maximum drawdown, results by time of day,
   average holding time, and how our recomputed P&L compares with the P&L the trader reports.
6. **Paper-mirrors** each trader (phase 2 only): our own simulated position, kept separate from theirs, priced from our own
   recorded bid/ask where available (buy at the ask, sell at the bid, only on quotes fresh within 60 seconds), with our own
   size and risk limits. Where no recorded price exists, the trader's price is used and the trade is marked "unverified price".
7. **Reports to Telegram**: new trade detected, paper position opened/closed, open positions, realised P&L, daily and weekly
   performance, risk warnings.

## Phases

| Phase | What runs | Copying? |
|---|---|---|
| 1. Observation (first 7 trading days of live messages) | ingest, parse, store, measure, daily report | **No** |
| 2. Paper mirroring | as phase 1 + the paper engine | paper only |
| Real money | not built; would need the user's explicit decision and a separate review | — |

## Message sources (plain English)

- **Authorised Discord bot (preferred):** the server's administrator invites a bot we create (read-only permissions:
  View Channel, Read Message History). The bot token is stored as a GitHub secret (`DISCORD_BOT_TOKEN`), never in the code.
  `copytrader/sources.py` → `DiscordBotSource` uses Discord's official API with that token. Nothing works until the admin
  approves; **no self-bot, no use of your personal login, no scraping.**
- **Official feed / webhook** from the server (if the admin prefers): the same parser reads whatever text it posts.
- **Manual import** (works now): paste messages into a text file and run `python -m copytrader import-text file.txt`;
  or import the trades already transcribed from your screen recordings (`state/discord_trades.csv`, marked as
  "transcribed", 11-20 Nov).
- The Discord plugin connected to Claude in this chat failed to connect ("connection closed"). Even when connected, such a
  plugin only works through a bot that the server admin has invited, so the admin's approval is needed either way.

## Hosting (plain English)

- **GitHub Actions** can run the reader on a schedule, but scheduled runs start at most every 5 minutes, are often delayed by
  several minutes, and a job can last at most 6 hours. It is fine for **observation** (messages read a few minutes late, with
  their original Discord time stamps kept), but it **cannot** react within seconds. Message time stamps are kept to the
  millisecond as Discord provides them; our receipt time is recorded separately, so delays are visible, never hidden.
- Seconds-level mirroring would need an always-on process (your own PC, or a free-tier cloud VM such as Oracle Cloud's
  Always Free tier). Not needed for phase 1; to be decided before phase 2.
- Database: SQLite (free, a single file). Telegram: the existing bot (secrets already in GitHub).
- No paid service is used. Anything that would cost money will be asked first.

## Files

| File | Job |
|---|---|
| `copytrader/parser.py` | message text → events + flags |
| `copytrader/store.py` | SQLite database |
| `copytrader/ledger.py` | each trader's positions and closed trades from his events |
| `copytrader/stats.py` | performance measures |
| `copytrader/paper.py` | our paper mirror (phase 2) |
| `copytrader/notify.py` | Telegram messages |
| `copytrader/sources.py` | message sources (Discord bot, text import, transcribed CSV) |
| `copytrader/__main__.py` | command line |
| `tests/test_copytrader.py` | tests |

## Known limits (stated, not hidden)

- His messages do not include the option's **expiry date**. The parser records it as unknown. The paper engine infers it only
  by matching the trader's price against our recorded quotes for the nearest expiries, and marks it "inferred".
- Messages show the time to the second (e.g. "3:43:54 PM ET"); the Discord API gives milliseconds for when a message was
  posted. Neither tells us exactly when his broker filled the order.
- "Profit" figures in his messages are his; ours are recomputed from his prices and compared.
