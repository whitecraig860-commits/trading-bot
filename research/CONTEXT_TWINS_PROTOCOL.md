# "+context" twin bots. Pre-registered 25 Nov 2026, before any twin has traded

**Approval.** On 25 Nov 2026 the owner asked for a copy of every bot that uses the dashboard's shared data to decide
entries, with the original kept unchanged ("Change entries too, but make that another bot").

**Rule (fixed now).** A twin takes exactly the signals its original would take. In addition, it opens a trade only when
the shared context (`tracker/context.py`, the same numbers shown on the live page as "what the bots see") agrees:
1. **Trend agrees with the side.** A call or long needs a **Bullish** trend, and a put or short needs a **Bearish** one.
   - Bullish = EMA 9 > EMA 20 > EMA 50 and EMA 20 has risen over 10 minutes; Bearish is the mirror image.
2. **Not choppy.** The trend is not Sideways, and there have been fewer than 4 closes across EMA 20 in the last 30 minutes.
3. **Context available.** With fewer than 15 bars, or any error, the twin does not trade (safe default).
4. **Unchanged from the original:** exits, the loss stop and the brakes, the pause switch and the fresh-quote rule.

**Not used (reasons).**
- **News:** we only have free headlines, with no sentiment and no summaries, so there is no honest signal to use.
- **Economic calendar:** there is no free source with times, forecasts and actual figures.
- These would only be added as a new, separately registered rule.

**Twins.** One for each live bot:
- options_ctx
- skipweak_ctx, combo_ctx, picks_ctx, clone_ctx, brakes_ctx, five_ctx, open30_ctx, oneaday_ctx
- shares_ctx

Twins send no Telegram messages; they appear on the live page.

**How it will be judged.** Each twin is compared with its original over the same days:
- difference per day in dollars;
- trades taken;
- win rate;
- worst day.

A twin "helps" only if:
- it beats its original by more than costs over at least 30 trades of the twin AND at least 20 trading days;
- AND the same rule also helps on history. A backtest with the existing study harness will be registered separately
  before it is run.

Until then the results are only observations. No original bot is changed because of a twin's result without a new
change-control entry and the owner's approval.

**Expected effect (written before results).** Fewer trades, mostly in trending hours. Whether that is better is unknown:
- Study 8 found "trade with the day's direction" helped a little on history.
- Study 10 found that trading less helps by itself, even at random.
- So a twin beating its original could just be fewer trades. Compare per trade as well as per day.
