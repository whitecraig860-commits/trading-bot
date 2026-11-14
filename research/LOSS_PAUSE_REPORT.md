# Study 7: pausing after a loss. Results

**Run:** 2026-11-14, 670 days (2024-03 to 2026-10). Rules: `research/LOSS_PAUSE_PROTOCOL.md`, committed (d8ba8f7) before any code. Output: `research/study7_output.txt`.

| Rule | Per day at 1 cent (one contract) | Improvement on BASE | Paired t |
|---|---|---|---|
| BASE (as the bot ran) | −$95 | — | — |
| Wait 10 min after a loss | −$64 | +$31 | 14.0 |
| Wait 20 min after a loss | −$53 | +$43 | 18.5 |
| **Stop for the day after 2 losses in a row** | **−$38** | **+$57** | **20.1** |
| Stop after 3 losses in a row | −$65 | +$30 | 13.1 |

- **All four rules passed every adoption line,** including the holdout and 2 cents per side.
- **"Stop after 2 losses in a row" improved the most, so it is adopted in the live paper bot,** with an off switch.
- **The bot still loses money with it.** The rule mostly helps by trading less on choppy days. It is an improvement, not a fix: Study 5's verdict (fails) stands.
