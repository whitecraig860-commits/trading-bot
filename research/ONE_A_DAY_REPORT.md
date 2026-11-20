# Study 6: the "one trade a day" QQQ bot. Results

**Run:** 2026-11-13, on data from 2024-03-01 to 2026-10-30 (654 trading days). Rules: `research/ONE_A_DAY_PROTOCOL.md`, committed (20add7e) before any code. Full output: `research/study6_output.txt`. No orders were placed.

## Verdict: FAILS (3 of 4 lines passed; the main significance line failed)

| | Trades | Win rate | Per trade | Per day | t |
|---|---|---|---|---|---|
| Options, 2 cents per side (base) | 437 | 45% | +$10.9 | +$7.29 | 0.90 |
| Options, 5 cents per side | 437 | 44% | +$4.9 | +$3.28 | 0.41 |
| Options, holdout 2026 | 151 | 45% | +$5.1 | +$3.74 | 0.22 |
| **100 QQQ shares, 1 cent per side** | 485 | **59%** | **+$49.3** | **+$36.56** | **2.72** |

## What it shows

1. **The signal is real on the shares.**
   - Buying or shorting 100 QQQ shares on his rules made money in every year (2024, 2025 and 2026), with t = 2.7.
   - It also held up under every sensitivity setting.
   - This is the first entry signal in these studies with a statistically clear edge.
2. **The options throw most of it away.**
   - The same trades in one-contract options won only 45% of the time, against 59% on the shares.
   - Holding an option for about 5½ hours (the median) costs time decay, and the in-the-money options trade thinly, so fills are worse.
   - The result was positive but not statistically clear, and it was almost entirely made by 43 trades that reached the trailing exit.
3. **The noise band matters.** Without it, the shares edge roughly halved and the options lost money. That matches the published research the rule resembles (Zarattini, Aziz and Barbon, 2024).

## Size, honestly

- **The shares result needs a full position.** 100 QQQ shares is about $67,000. The +$49 per trade is about 0.07% of that.
- **On a £1,000 account,** the same idea is worth roughly 50–70p per trade.
- **Better options choices** (1-day expiry, or at-the-money) looked better. They were reported but not picked, as the protocol requires, so they need their own forward test.

## Next step (not authorised by this protocol)

- The options version is not built, by the pre-registered rules.
- The shares signal is worth a separate forward paper test, under its own protocol. That test should include position sizing a small account can actually use.
