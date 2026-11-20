# Study 13 results: three different kinds of entry

Protocol: `research/NEW_ENTRIES_PROTOCOL.md` (committed before code or results). Script: `research/new_entries_study.py`.
Output: `research/study13_output.txt`. 670 days of real option bars; one contract; 1 cent a side unless stated.

| | 5-minute crosses (FIVE) | Opening move (OPEN30) | **One-a-day breakout, options (ONEADAY)** |
|---|---|---|---|
| QQQ moves the right way after the signal (15 / 30 min) | 49% / 50% | 51% / 54% | **55% / 56%** |
| Per day at 1 / 2 / 3 / 5 cents | −$16.46 / −27.30 / −37.95 / −52.62 | −$2.46 / −3.47 / −4.47 / −6.48 | **+$14.44 / +12.98 / +11.51 / +8.58** |
| Own t | −7.31 | −2.32 | **+1.73** (needs 2.0) |
| Every year | lost every year | lost every year | **+$14.01 / +13.28 / +16.25 (2024/25/26)** |
| Against 20 placebos | beats 16 | beats 5 | **beats all 20** (random direction: −$5.94) |
| 1,000 resamples positive | 0% | 0.7% | **96.7%** |
| Calm / busy / up / down days | all negative | all negative | −$26.85 / **+$55.87** / +$7.77 / +$22.06 |
| Verdict | not profitable | not profitable | **passes every line except significance (t 1.73 < 2.0)** |

## What it means

- **FIVE:** the same crosses on 5-minute candles are still a coin flip. Slower candles are not the answer.
- **OPEN30:** the opening move predicts a little (54% at 30 minutes) but not enough to pay for the options.
- **ONEADAY:** the first entry in thirteen studies with real predictive power on the options. It made money in every year,
  beat every random-direction placebo, and was positive in 96.7% of resamples, even at 5 cents a side. It falls just short
  of the pre-set significance line (t 1.73 vs 2.0), so it is **not called profitable**. All its money is made on busy days;
  on calm days it loses. Testing "busy days only" would be a new idea and needs its own pre-registered test.

All three run as paper bots (`five`, `open30`, `oneaday` in `EXTRA_BOTS`); the daily Telegram check reports them every day.
