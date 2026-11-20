# Definitive bot register (20 Nov 2026)

Detailed rules, history and change log for each: `audit/baseline_<bot>.md`, `audit/logs/<bot>.md`, `audit/CHANGES.md`.

## Shared code: these are NOT independent strategies

- **Family 1, "one-minute crosses" (11 bots).** Main, original, trail, trail+trend, his style, skip weak, combo, picks like
  him, his clone and brakes all use the same signal code (`PaperBot._signal` in `tracker/qqqbot.py`): one-minute VWAP and
  EMA50 crosses plus the first 15-minute range break. They differ only in filters (which signals they skip) and exits. The
  5-minute bot uses the same crosses on 5-minute candles. Their results are strongly correlated: they buy at the same moments.
- **Family 2, "one-a-day breakout" (2 bots).** The shares bot (`tracker/sharesbot.py`) and the one-a-day options bot (which
  copies the shares bot's entry and exit) are one strategy in two instruments.
- **Opening move** (one bot) is a separate rule but uses the same option engine as family 1.

## Register

| # | Bot (id) | Family | Entry | Exit (target / stop / time) | Indicators | Size | Trades/day | History per day (1c) | Paper (recorded) | Status | Rating |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Main, stop after 2 (`options`) | 1 | 1-min VWAP/EMA50 cross or range break, 09:45-15:30 | +2.5% / −6% / 10 min; stop the day after 2 losses | VWAP, EMA50, 15-min range | 1 contract | ~10 | −$38.25 | +$55 (−$118 without frozen-price trades), 6 days | live paper, benchmark | E |
| 2 | Original (`original`) | 1 | same | +2.5% / −6% / 10 min | same | 1 contract | ~27 | −$95.19 | −$770, 5 days | live paper, benchmark | E |
| 3 | Trail (`trail`) | 1 | same | trail 1.5% from +2.5% / −6% / 15 min | same | 1 | ~5.5 | −$10.07 | −$171, 4 days | live paper | E |
| 4 | Trail + trend (`trailtrend`) | 1 | same, with the day's direction only | as trail | + day open | 1 | ~5.4 | −$6.42 | −$446, 4 days | live paper | E |
| 5 | His style (`his`) | 1 | same | trail / −12% / 15 min | same | 1 | ~7 | −$19.48 | −$170, 4 days | live paper | E |
| 6 | Skip weak (`skipweak`) | 1 | same, skip crosses < $0.10 | as main | same | 1 | ~8 | −$31.57 | −$273, 2 days | live paper | E |
| 7 | Combo (`combo`) | 1 | skip weak + from 09:31 + in the money | as main | same | 1 | ~8.6 | −$34.58 | −$275, 2 days | live paper | E |
| 8 | Picks like him (`picks`) | 1 | + EMA9/20 agree, strong candle, before 12:00 | as main | + EMA9, EMA20 | 1 | ~3.4 | −$11.69 | +$5, 2 days | live paper | E |
| 9 | His clone (`clone`) | 1 | as picks | +3.5% / −10% / 6 min | same | 1 | ~3.4 | −$11.15 | −$207, 2 days | live paper | E |
| 10 | Brakes (`brakes`) | 1 | as main | as main + stop at +$50 / −$100 | same | 1 | ~9 | −$35.39 | none | pending PR #39 | E |
| 11 | 5-minute (`five`) | 1 | 5-min VWAP/EMA50 crosses | +5% / −10% / 30 min | same on 5-min | 1 | ~5.4 | −$16.46 | none | pending PR #39 | E |
| 12 | Opening move (`open30`) | separate | 10:00, QQQ ±0.25% from open | +10% / −10% / 60 min | open | 1 | ~0.5 | −$2.46 | none | pending PR #39 | E |
| 13 | One-a-day options (`oneaday`) | 2 | copies the shares bot | sells when the shares bot does | as shares bot | 1 contract, ATM next-day | ~0.7 | +$14.12 | none | pending PR #39 | C |
| 14 | Shares one-a-day (`shares`) | 2 | 09:30-09:45 range ± 0.3 ATR(5-min), beyond VWAP and the noise band; checks every 10 min 10:00-14:00 | trail at 4 ATR giving back half / 10 ATR stop / 15:45 | range, ATR, VWAP, 14-day noise band | ~£1,000 fractional | ~0.75 | +$35.68 (100 sh, 2024-26); +0.035% a trade 2016-26 | +$67.59, 5 trades | live paper | B (regime-dependent) |

Older components (not part of this audit's strategies): the swing scanner and the scalper were retired on 11 Nov (e7230da,
switches kept); the market "pulse" and other alert jobs send messages but do not trade.
