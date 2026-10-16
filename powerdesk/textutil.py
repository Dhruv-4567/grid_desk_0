"""Small, pure text helpers shared by every module. None of these raise on bad input."""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))   # fixed offset: needs no time-zone database

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LINK_RE = re.compile(r"^https?://[^\s<>\"'`\\]+$", re.IGNORECASE)


def clean_text(value: Any, limit: int = 400) -> str:
    """Strip HTML tags and entities, collapse whitespace, trim to `limit` characters."""
    if not isinstance(value, str):
        return ""
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value))).strip()
    if len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut) + "…"


def safe_link(value: Any) -> str:
    """Return the URL only if it is a plain http(s) link; otherwise ''."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if _LINK_RE.match(value) else ""


@lru_cache(maxsize=512)
def phrase_pattern(terms: tuple[str, ...]) -> re.Pattern[str] | None:
    """Whole-phrase matcher: 'iex' matches 'IEX shares' but not 'Sciex'."""
    cleaned = tuple(t.lower().strip() for t in terms if isinstance(t, str) and t.strip())
    if not cleaned:
        return None
    alts = "|".join(re.escape(t) for t in sorted(set(cleaned), key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9])(?:{alts})(?![a-z0-9])")


def has_phrase(text: Any, terms: tuple[str, ...]) -> bool:
    pattern = phrase_pattern(tuple(terms))
    return bool(pattern and isinstance(text, str) and pattern.search(text.lower()))


def dedupe_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())[:80]


def now_ist() -> datetime:
    return datetime.now(IST)


def to_ist(dt: datetime | None) -> datetime | None:
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def ist_date(value: datetime | date | None) -> date | None:
    if isinstance(value, datetime):
        local = to_ist(value)
        return local.date() if local else None
    if isinstance(value, date):
        return value
    return None


def relative_day(value: datetime | date | None, today: date | None = None) -> str:
    d = ist_date(value)
    if d is None:
        return "Undated"
    today = today or now_ist().date()
    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"
    return d.strftime("%a %d %b %Y")


def time_label(value: datetime | None) -> str:
    local = to_ist(value)
    return local.strftime("%H:%M IST") if local else ""


def long_date(d: date) -> str:
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"
