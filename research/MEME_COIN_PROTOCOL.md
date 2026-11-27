# Study 17: meme-coin strategies (research only, no bot). Pre-registered 27 Nov 2026

**Coins.** The meme coins Alpaca lists (DOGE/USD, SHIB/USD, and PEPE/USD or TRUMP/USD if listed), plus BTC/USD as a
comparison. 15-minute bars, 2023-01 to 2026-10, 24/7.

**Costs.** Alpaca crypto fees 0.25% per side (taker) plus 0.05% slippage per side: 0.6% a round trip.

**Strategies (fixed now; each long only, since Alpaca crypto has no shorting).**
- **M1, volume-spike momentum:** buy when a bar's volume is over 5× its 24-hour average and the bar is up over 2%.
  Exit after 4 hours, at +6%, or at −3%.
- **M2, breakout:** buy on a close above the 48-hour high. Exit when the price falls 5% below its highest point
  since entry (trailing stop), or after 24 hours.
- **M3, dip buy:** buy after a drop of more than 8% in 4 hours. Exit at +5%, at −5%, or after 12 hours.
- **M4, trend filter:** M2, only while the price is above its 7-day average.

**Judged, per coin and strategy.**
- Average per trade after costs > 0 with t ≥ 2, positive in 2025 and in 2026.
- Beats 19 of 20 random-entry placebos (same number of trades, same holding rules).
- Only 16 combinations are tested, so the bar is high: t ≥ 3 to count after multiple testing.

**Output.** A report only. No crypto bot is built unless something passes and you approve it.
