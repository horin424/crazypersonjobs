import re


def normalize_text(value: str | None) -> str:
    """Trim and collapse Unicode whitespace without altering meaningful characters."""
    return re.sub(r"\s+", " ", value or "").strip()

