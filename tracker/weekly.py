"""
Weekly check: ranks every paper bot by its real results and sends one Telegram message. Reads the saved state files
only; changes nothing and places no orders. Run by .github/workflows/weekly.yml on Friday after the US close.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqqbot  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "state"
BOTS = [("options", "qqqbot", "Stop after 2 losses"), ("original", "qqqbot_original", "Original")]
BOTS += [(k, v[0], v[1][:1].upper() + v[1][1:]) for k, v in qqqbot.EXTRA_BOTS.items()]
BOTS += [("shares", "sharesbot", "Shares one-a-day")]


def days(folder: str, key: str) -> dict:
    out = {}
    for f in sorted((ROOT / folder).glob("20??-??-??.json")) if (ROOT / folder).is_dir() else []:
        try:
            st = json.loads(f.read_text())
            if key == "shares":
                out[f.stem] = float((st.get("trade") or {}).get("pnl_usd", 0) or 0)
            else:
                out[f.stem] = sum(float(t["pnl"]) for t in st.get("trades", []))
        except Exception:
            pass
    return out


def trades(folder: str) -> list:
    out = []
    for f in sorted((ROOT / folder).glob("20??-??-??.json")) if (ROOT / folder).is_dir() else []:
        try:
            out += json.loads(f.read_text()).get("trades", [])
        except Exception:
            pass
    return out


def lessons(name: str, tr: list) -> list:
    """What worked and what didn't for one options bot, from all its trades so far. Ideas only: nothing is changed."""
    if len(tr) < 10:
        return [(f"<b>{name}</b>: no trades yet." if not tr else f"<b>{name}</b>: only {len(tr)} trades so far, too few to say what works.")]

    def tod(t):
        h = t["t"][11:16]
        return "09:45-10:30" if h < "10:30" else "10:30-12:00" if h < "12:00" else "12:00-14:00" if h < "14:00" else "14:00-15:30"

    groups = {}
    for t in tr:
        for label in (f"{t['trigger']} signals", "calls" if t["type"] == "C" else "puts", f"trades at {tod(t)}",
                      f"exits by {t.get('why', '?')}"):
            g = groups.setdefault(label, [0, 0, 0.0])
            g[0] += 1
            g[1] += t["pnl"] > 0
            g[2] += t["pnl"]
    ranked = sorted(((v[2], k, v) for k, v in groups.items() if v[0] >= 5 and not k.startswith("exits")), reverse=True)
    total = sum(t["pnl"] for t in tr)
    wins = [t["pnl"] for t in tr if t["pnl"] > 0]
    losses = [t["pnl"] for t in tr if t["pnl"] <= 0]
    lines = [f"<b>{name}</b>: {len(tr)} trades, {len(wins) / len(tr):.0%} won, {total:+,.0f} USD. "
             f"Average win {sum(wins) / max(len(wins), 1):+.0f}, average loss {sum(losses) / max(len(losses), 1):+.0f}."]
    if ranked:
        best, worst = ranked[0], ranked[-1]
        lines.append(f"  ✅ Worked best: {best[1]} ({best[2][0]} trades, {best[0]:+,.0f})")
        if worst[0] < 0:
            lines.append(f"  ❌ Worked worst: {worst[1]} ({worst[2][0]} trades, {worst[0]:+,.0f})")
            lines.append(f"  💡 Would test: skipping {worst[1]} (an idea to check on 2.7 years of history first, not a change)")
    stops = groups.get("exits by stop")
    if stops and stops[0] >= 5:
        lines.append(f"  Stops hit: {stops[0]} times, {stops[2]:+,.0f} in all.")
    return lines


def report(today: date) -> str:
    since = (today - timedelta(days=today.weekday())).isoformat()  # Monday of this week
    rows = []
    for key, folder, name in BOTS:
        d = days(folder, key)
        wk = {k: v for k, v in d.items() if k >= since}
        rows.append((name, sum(wk.values()), len(wk), sum(v > 0 for v in wk.values()), sum(d.values()), len(d)))
    rows.sort(key=lambda r: (r[2] == 0, -r[1]))
    g = qqqbot.GBP
    lines = [f"📅 <b>Weekly check</b> (week of {date.fromisoformat(since):%d %b})", "<b>This week</b>, best first:"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, wk, n, up, tot, nd) in enumerate(rows):
        tag = medals[i] if i < 3 and n else "•"
        lines.append(f"{tag} {name}: <b>{wk:+,.0f} USD</b> (£{wk * g:+,.0f}) · {up}/{n} day{'s' if n != 1 else ''} up" if n else f"• {name}: no days yet")
    lines.append("")
    lines.append("<b>All time</b> (since each bot started):")
    for name, wk, n, up, tot, nd in sorted(rows, key=lambda r: -r[4]):
        if nd:
            lines.append(f"{name}: {tot:+,.0f} USD over {nd} day{'s' if nd != 1 else ''}" + (" ✔ 20+ days" if nd >= 20 else ""))
    lines.append("")
    lines.append("<b>What each bot has learned</b> (all its trades so far):")
    for key, folder, name in BOTS:
        if key != "shares":
            lines += lessons(name, trades(folder))
    live = [r for r in rows if r[5] >= 20]
    lines.append("")
    lines.append("<i>Paper only. One week is too short to judge: a bot needs about 20+ days before its lead means much. "
                 + ("Bots with 20+ days are marked ✔." if live else "No bot has 20 days yet.")
                 + " Ideas are only tested, never applied automatically; you decide.</i>")
    return "\n".join(lines)


if __name__ == "__main__":
    text = report(date.today())
    print(text)
    if "--send" in sys.argv:
        sys.exit(0 if qqqbot.send_telegram(text) else 1)
