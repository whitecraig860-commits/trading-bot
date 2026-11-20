# Complete record of what has been changed (from git, 11-20 Nov 2026)

Source: `git log` of `main` (what actually ran) and of the branch `claude/affectionate-edison-9wfyzd` (pending in PR #39).
"Live" means it is in `main` and the recorder runs it. Nothing is changed automatically: every change below was a commit
made by me and merged by the user's pull-request merge. No production change has been made since the user's instruction
to stop (20 Nov); everything after that is research and audit files on the branch.

## Changes that affect several bots

| Date | Commit / PR | Change | Status |
|---|---|---|---|
| 11 Nov | e7230da (PR #21) | Older scalper and swing-breakout trading retired (reversible switches; code kept) | live |
| 12 Nov | 5176a49, d775048, 2aeb927 (PR #24, #26) | Option bid/ask recorder every 5 s, keyed on quote time | live |
| 12 Nov | 4d8f439 (PR #27) | QQQ-only alerts | live |
| 14 Nov | 0ae2a91, 4f395e7 | Live web page (reads files; no trading effect) | live |
| 16 Nov | 635f209 (PR #33) | Live page v2 (display only) | live |
| 17 Nov | 3a48482 (PR #34, #35) | Calendar on the live page (display only) | live |
| 17 Nov | PR #36, #37 | Weekly Telegram check and "what each bot has learned" (reads files only) | live |
| pending | PR #39, CC-001 | Fresh-quote guard: options bots buy and sell only on quotes stamped within 60 s | **pending approval** |
| pending | PR #39, CC-002 | Recorder holiday decision: stop only if QQQ shares are not trading | **pending approval** |
| pending | PR #39, CC-004 | Daily validation log and daily Telegram check | **pending approval** |

## Per bot

| Bot | Original version | Changes since (date, commit) | Entry / exit / stop / target / indicators now | Deployment |
|---|---|---|---|---|
| Main options ("stop after 2") | 12 Nov, 4d8f439: Study 5 rules. 1-min VWAP and EMA50 crosses + first 15-min range break, 09:45-15:30; nearest strike, next-day expiry, 1 contract; sell at +2.5%, −6% or 10 min; bought at the ask, sold at the bid | 12 Nov 27a1b69: BOUGHT/SOLD Telegram messages (no trading effect). 12 Nov baf3d4c: no error line before the first candle (no trading effect). **14 Nov 8f6ca7e: stop for the day after 2 losses in a row** (Study 7: paired t +20.1). 17 Nov e133ef9: summary text now states the exit rule and lists the comparison bots (messages only). 17 Nov 01e0ef4 made it use a trailing exit, **reverted by e133ef9 before it was merged**: both arrived together in PR #19, so the trailing exit never ran live. Pending: CC-001 | Same entry, exits and indicators as the original; + stop after 2 losses | live (paper) |
| Original | 14 Nov, 68bd0de: the main bot's rules without the loss stop, for comparison | none | as created | live (paper) |
| Trail | 17 Nov (PR #19) | none since creation | main + keep winners from +2.5%, sell 1.5% below best, 15-min limit | live (paper) |
| Trail + trend | 17 Nov (PR #19) | none since creation | trail, calls only above the open, puts only below | live (paper) |
| His style | 17 Nov: first committed as "trend + trail + 12% stop" (2ec6a13), changed to "12% stop + trail, no trend filter" (143f551) **before merging** | none since merge | trail + 12% stop | live (paper) |
| Skip weak | 18 Nov (PR #38) | none | main, skip crosses < $0.10 | live (paper) |
| Combo | 18 Nov (PR #38) | none | skip weak + signals from 09:31 + strike in the money | live (paper) |
| Picks like him | 18 Nov (PR #38) | none | EMA9/20 agree + strong candle + before 12:00 + not weak | live (paper) |
| His clone | 18 Nov (PR #38) | none | picks + 3.5% / −10% / 6 min | live (paper) |
| Brakes | created on the branch 19 Nov | — | main + stop at +$50 / −$100 for the day | **pending (PR #39)** |
| 5-minute crosses | created on the branch 19 Nov | — | 5-min VWAP/EMA50 crosses, +5% / −10% / 30 min | **pending (PR #39)** |
| Opening move | created on the branch 19 Nov | — | 10:00 call/put on a 0.25% opening move, +10% / −10% / 60 min | **pending (PR #39)** |
| One-a-day options | created on the branch 19 Nov | CC-003 (keep the option through a recorder restart) on the branch | follows the shares bot; next-day at-the-money option | **pending (PR #39)** |
| Shares one-a-day | 13 Nov, d60ae57: Study 6 rule on paper, about £1,000 fractional shares | none | 09:30-09:45 range; checks 10:00-14:00 every 10 min; range ± 0.3 ATR(5-min), beyond VWAP and the noise band; trail at 4 ATR giving back half; 10 ATR stop; out 15:45 | live (paper) |

Position sizing has never changed: 1 option contract per trade; the shares bot about £1,000 notional.

## Changes made but not recorded properly at the time (now recorded)

1. The 17 Nov trailing exit on the main bot (01e0ef4) was made and reverted the same day; it never went live, but it was not
   in an experiment log until this audit.
2. The 17 Nov change to the main bot's summary text (messages only) was in a commit message but not in an experiment log.
3. I edited the description of PR #38 after it had been merged and kept pushing to its branch, so the later commits (now PR
   #39) did not go live while I reported them as merged-pending. Recorded in `audit/README.md`; corrected by opening PR #39.
4. The history tests' cost assumption (1 cent a side) was never measured against reality until the audit; it is about 4-5
   times too low for options (`audit/cost_breakdown.md`).

## Reverted changes

- Main bot trailing exit (01e0ef4 → reverted by e133ef9, 17 Nov): reverted at the user's request to keep existing bots unchanged.
- "Trend + trail" fourth bot definition (2ec6a13 → 143f551, 17 Nov): changed before merging, because his trades showed no trend filter.

## Performance impact of the changes that went live

| Change | Evidence before → after |
|---|---|
| Stop after 2 losses (main bot) | History (Study 7): −$95.19 → −$38.25 a day (both still losing). Paper: not separable (only one version ran each day; the original bot runs alongside as the control: original −$770 vs main +$55 recorded over the same days). |
| Everything else that went live | Display, messages, new comparison bots: no effect on existing bots (verified by replays: identical trades). |
