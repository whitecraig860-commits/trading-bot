"""Send a Telegram message with the existing bot (tracker/qqqbot.send_telegram; secrets from the environment)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tracker"))


def send(text: str) -> bool:
    import qqqbot
    return qqqbot.send_telegram(text)
