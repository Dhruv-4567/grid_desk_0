"""Official announcements: notice pages of CEA, MNRE and Grid-India, plus PIB, CERC, SECI and others
through Google News' index of those sites.

Government sites rarely offer feeds, so notice pages are read directly. The reader is generic:
it tries table rows, then dated list items, then <article> cards, and from each takes a title-like
text, the first real date and the first real link. Cosmetic redesigns don't break it; if a page
stops yielding anything, the Official section says so rather than failing.

Design rule: fetch_official always returns (items, errors) and never raises.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import (
    OFFICIAL_KINDS, OFFICIAL_MAX_AGE_DAYS, OFFICIAL_MAX_ITEMS, OFFICIAL_NOISE, OFFICIAL_OTHER,
    Feed, OfficialPage,
)
from .net import download, run_all
from .news import parse_feed
from .textutil import IST, clean_text, dedupe_key, has_phrase, safe_link

log = logging.getLogger(__name__)

MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DMY = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
_D_MON_Y = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]{3,9})[,\s-]+(\d{4})\b")
_MON_D_Y = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
_SIZE_SUFFIX = re.compile(r"\s*\((?:[^()]*\b(?:kb|mb)\b[^()]*)\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Announcement:
    title: str
    link: str
    body: str                    # CEA, MNRE, Ministry of Power, ...
    published: date | None
    kind: str                    # one of config.OFFICIAL_KINDS ids, or "other"


# ---------------------------------------------------------------- helpers

def _make_date(y: int, m: int, d: int) -> date | None:
    try:
        result = date(y, m, d)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if 2000 <= result.year <= 2100 else None


def find_date(text: Any) -> date | None:
    """Earliest-positioned valid date in the text, in any format Indian government sites use."""
    if not isinstance(text, str) or not text:
        return None
    found: list[tuple[int, date]] = []
    for m in _ISO.finditer(text):
        if (d := _make_date(int(m[1]), int(m[2]), int(m[3]))):
            found.append((m.start(), d))
    for m in _DMY.finditer(text):
        if (d := _make_date(int(m[3]), int(m[2]), int(m[1]))):
            found.append((m.start(), d))
    for m in _D_MON_Y.finditer(text):
        month = MONTHS.get(m[2][:3].lower())
        if month and (d := _make_date(int(m[3]), month, int(m[1]))):
            found.append((m.start(), d))
    for m in _MON_D_Y.finditer(text):
        month = MONTHS.get(m[1][:3].lower())
        if month and (d := _make_date(int(m[3]), month, int(m[2]))):
            found.append((m.start(), d))
    return min(found)[1] if found else None


def classify_official(title: Any) -> str:
    for kid, _label, words in OFFICIAL_KINDS:
        if has_phrase(title, words):
            return kid
    return OFFICIAL_OTHER[0]


def is_noise(title: Any) -> bool:
    return has_phrase(title, OFFICIAL_NOISE)


def _date_only(text: str) -> bool:
    rest = text
    for rx in (_ISO, _DMY, _D_MON_Y, _MON_D_Y):
        rest = rx.sub(" ", rest)
    return len(re.sub(r"[\W_]+", "", rest)) < 5


def _looks_like_title(text: str) -> bool:
    if len(text) < 15 or not re.search(r"[A-Za-z]{3}", text):
        return False
    return not text.lower().startswith(("http://", "https://", "view", "download", "read more"))


def _resolve_link(href: Any, base_url: str) -> str:
    if not isinstance(href, str):
        return ""
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    try:
        absolute = urljoin(base_url, href)
    except ValueError:
        return ""
    return safe_link(absolute.replace(" ", "%20"))


# ---------------------------------------------------------------- parsing a notice page

def _from_rows(rows, base_url: str, body: str, require_date: bool) -> list[Announcement]:
    items: list[Announcement] = []
    for row in rows:
        cells = row.find_all("td")
        if cells:
            texts = [clean_text(c.get_text(" "), 500) for c in cells]
        else:   # a list item or card: prefer its heading or link text as the title, the rest for the date
            heading = row.find(["h1", "h2", "h3", "h4", "h5"]) or next(
                (a for a in row.find_all("a") if _looks_like_title(clean_text(a.get_text(" ")))), None)
            texts = [clean_text(heading.get_text(" "), 500)] if heading else []
            texts.append(clean_text(row.get_text(" "), 500))
        idx = next((i for i, t in enumerate(texts) if _looks_like_title(t) and not _date_only(t)), None)
        if idx is None:
            continue
        title = _SIZE_SUFFIX.sub("", texts[idx]).strip()
        if not _looks_like_title(title) or is_noise(title):
            continue
        published = find_date(" ".join(t for i, t in enumerate(texts) if i != idx)) or find_date(title)
        if require_date and published is None:
            continue
        link = next((l for a in row.find_all("a", href=True) if (l := _resolve_link(a.get("href"), base_url))), "")
        if not link:
            continue
        items.append(Announcement(clean_text(title, 300), link, body, published, classify_official(title)))
    return items


def parse_listing(content: bytes, base_url: str, body: str) -> list[Announcement]:
    """Notices from a government page: tables first, then dated list items, then article cards."""
    try:
        soup = BeautifulSoup(content or b"", "html.parser")
    except Exception as exc:
        log.warning("Could not parse %s: %r", body, exc)
        return []
    table_rows = [r for r in soup.find_all("tr") if r.find("td")]
    if table_rows and (items := _from_rows(table_rows, base_url, body, require_date=False)):
        return items
    if (items := _from_rows(soup.find_all("li"), base_url, body, require_date=True)):   # dated only: skips menus
        return items
    return _from_rows(soup.find_all("article"), base_url, body, require_date=False)


def _from_feed(content: bytes, feed: Feed) -> list[Announcement]:
    out = []
    for n in parse_feed(content, feed.name, ()):
        if is_noise(n.title):
            continue
        published = n.published.astimezone(IST).date() if n.published else None
        out.append(Announcement(n.title, n.link, feed.name, published, classify_official(n.title)))
    return out


# ---------------------------------------------------------------- fetching

def fetch_official(
    pages: Iterable[OfficialPage],
    feeds: Iterable[Feed],
    session: Any = None,
    today: date | None = None,
) -> tuple[list[Announcement], list[str]]:
    jobs: list[Any] = [*pages, *feeds]
    today = today or datetime.now(timezone.utc).astimezone(IST).date()
    cutoff = today - timedelta(days=OFFICIAL_MAX_AGE_DAYS)

    def worker(sess: Any, src: Any):
        name = src.name if isinstance(src, Feed) else src.body
        try:
            content = download(sess, src.url)
            if isinstance(src, Feed):
                return _from_feed(content, src), None
            items = parse_listing(content, src.url, src.body)
            if not items:
                return [], f"{name}: page loaded but no notices were found (the layout may have changed)"
            return items, None
        except Exception as exc:
            log.warning("Official source %s failed: %r", name, exc)
            return [], f"{name}: {type(exc).__name__}"

    results = run_all(jobs, worker, session)
    errors = [e for _, e in results if e]
    seen: set[str] = set()
    merged: list[Announcement] = []
    for batch, _ in results:
        for a in batch:
            key = dedupe_key(a.title)
            if not key or key in seen:
                continue
            if a.published and (a.published < cutoff or a.published > today + timedelta(days=2)):
                continue
            seen.add(key)
            merged.append(a)
    merged.sort(key=lambda a: a.published or date.min, reverse=True)
    return merged[:OFFICIAL_MAX_ITEMS], errors


def filter_official(items: Iterable[Announcement], bodies=None, kinds=None, query: str = "") -> list[Announcement]:
    bodies, kinds = set(bodies or ()), set(kinds or ())
    q = (query or "").strip().lower()
    return [a for a in items
            if (not bodies or a.body in bodies) and (not kinds or a.kind in kinds) and (not q or q in a.title.lower())]
