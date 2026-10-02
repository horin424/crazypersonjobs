from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now_jst_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def display_jst(iso_timestamp: str) -> str:
    parsed = datetime.fromisoformat(iso_timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S JST")

