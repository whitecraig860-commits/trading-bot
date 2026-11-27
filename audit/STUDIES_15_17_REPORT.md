# Studies 15–17: news bot, SPY one-a-day, meme coins (27 Nov 2026)

The rules were pre-registered before any real data was run (research/NEWS_BOT_PROTOCOL.md, SPY_ONEADAY_PROTOCOL.md,
MEME_COIN_PROTOCOL.md). The raw outputs are in audit/study15_output.txt, study16_output.txt and study17_output.txt.

## Study 15: news bot (free word scorer + chart trend): INCONCLUSIVE
- **Data.** Alpaca's free news history for our symbols only starts on **29 Apr 2026**: 3,108 headlines, about 7
  months, not the planned 2.7 years.
  - A first run fetched only one page a month (a paging bug); it was void and re-run with explicit paging.
- **Result.** 7 signals and 6 priced trades. At 5 cents a side: −$0.09 a day, t −0.61. It beat 13 of 20 random-minute
  placebos.
- **Verdict.** The pre-registered pass mark is not met. With 6 trades nothing can be concluded either way.
- **What follows.** The bot runs on paper as the owner asked, labelled "history test: too little data". Its live
  record is the evidence.

## Study 16: shares one-a-day rule on SPY: PASS
- **2022–2026:** +$29.99 a day per 100 shares, t +3.09, positive in all 5 years, 2026 +$26.89 a day.
- **2016–2021:** −$3.20 a day (t −0.72), the same pattern as QQQ: the rule worked from 2022, not before.
- **Placebo:** the rule beat all 20 random-side placebos (best placebo +$21.66).
- **Scale.** 100 SPY shares is about $60,000. The paper bot trades a £1,000 account (about 2 shares), so expect about
  1/45 of these dollar figures.
- **What follows.** A new paper bot `shares_spy`, with no Telegram messages, on the live page. Same caution as QQQ:
  the edge is regime-dependent.

## Study 17: meme coins: NO strategy passed
- **Costs:** 0.6% a round trip. Data: 15-minute bars, 2023 to Oct 2026.
- **Momentum and breakout buys** (M1, M2, M4) lost money on DOGE, BTC and TRUMP.
- **SHIB and PEPE breakout results** of +24% to +420% a trade are price-data errors (very small prices / bad bars),
  not real; they are ignored.
- **Closest: DOGE dip-buy (M3).** Buy after a fall of more than 8% in 4 hours; +1.23% a trade after costs, 90 trades,
  67% won, positive every year 2023–2026, beat 20/20 placebos. But t 2.71, against the 3.0 bar set for 16 combinations.
  "Promising, not proven".
- **Holding:** SHIB −59%, PEPE −61% and TRUMP −96% over their histories.
- **What follows.** The owner asked to try the DOGE dip-buy on paper: `tracker/dogebot.py`, every 15 minutes, the
  ledger on the live-data branch, shown on the live page. No other coins.
