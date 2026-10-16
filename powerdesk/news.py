"""Power-sector news from RSS feeds: the live wire, company deep-dives, and the dated archive.

Design rule: one broken feed never breaks the page. Every fetch_* function returns
(items, errors), where errors holds one readable line per source that failed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

import feedparser

from .config import (
    ARCHIVE_MAX_ITEMS, ARCHIVE_MAX_WINDOWS, GOVT_WORDS, NEWS_MAX_AGE_DAYS, NEWS_MAX_ITEMS,
    PROJECT_WORDS, TOPIC_RULES, Company, Feed, google_news,
)
from .net import download, run_all
from .textutil import IST, clean_text, dedupe_key, has_phrase, phrase_pattern, safe_link

log = logging.getLogger(__name__)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str                  # publisher, e.g. "Mercom India"
    published: datetime | None   # always timezone-aware (UTC) when present
    summary: str
    category: str                # one of config.CATEGORIES ids
    tickers: tuple[str, ...]     # NSE symbols mentioned


# ---------------------------------------------------------------- tagging

def tag_companies(text: str, companies: Iterable[Company]) -> tuple[str, ...]:
    if not isinstance(text, str) or not text:
        return ()
    low = text.lower()
    found = []
    for c in companies:
        pattern = phrase_pattern(c.match_terms)
        if pattern and pattern.search(low):
            found.append(c.symbol)
    return tuple(found)


def classify(text: str, tickers: Iterable[str] = (), psu_symbols: Iterable[str] = ()) -> str:
    """Topic first (tender / policy / markets); otherwise who is behind it (government / private)."""
    if not isinstance(text, str):
        return "other"
    for cid, words in TOPIC_RULES:
        if has_phrase(text, words):
            return cid
    tickers, psu = set(tickers), set(psu_symbols)
    if tickers & psu or has_phrase(text, GOVT_WORDS):
        return "govt"
    if (tickers - psu) or has_phrase(text, PROJECT_WORDS):
        return "private"
    return "other"


# ---------------------------------------------------------------- parsing

def _published(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime(*tuple(value)[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def parse_feed(content: bytes, feed_name: str, companies: Iterable[Company]) -> list[NewsItem]:
    companies = list(companies)
    psu = {c.symbol for c in companies if c.psu}
    try:
        parsed = feedparser.parse(content or b"")
    except Exception as exc:     # feedparser is tolerant, but never let a parser bug escape
        log.warning("Could not parse %s: %r", feed_name, exc)
        return []
    items: list[NewsItem] = []
    for entry in parsed.get("entries") or []:
        if not hasattr(entry, "get"):
            continue
        title = clean_text(entry.get("title"), 300)
        link = safe_link(entry.get("link"))
        if not title or not link:
            continue
        meta = entry.get("source")
        source = clean_text(meta.get("title"), 80) if hasattr(meta, "get") else ""
        source = source or feed_name
        suffix = f" - {source}"
        if title.endswith(suffix) and len(title) > len(suffix):   # Google News appends the publisher
            title = title[: -len(suffix)].strip()
        summary = clean_text(entry.get("summary"))
        s_low, t_low = summary.lower(), title.lower()
        if summary and (t_low.startswith(s_low[:60]) or s_low.startswith(t_low[:40])):
            summary = ""         # Google News summaries usually just repeat the headline
        text = f"{title} {summary}"
        tickers = tag_companies(text, companies)
        items.append(NewsItem(title, link, source, _published(entry), summary,
                              classify(text, tickers, psu), tickers))
    return items


def merge(batches: Iterable[Iterable[NewsItem]], keep=lambda item: True, limit: int = NEWS_MAX_ITEMS) -> list[NewsItem]:
    """De-duplicate by headline, apply `keep`, sort newest first (undated last), cap at `limit`."""
    seen: set[str] = set()
    out: list[NewsItem] = []
    for batch in batches:
        for item in batch:
            key = dedupe_key(item.title)
            if not key or key in seen or not keep(item):
                continue
            seen.add(key)
            out.append(item)
    out.sort(key=lambda i: i.published or _EPOCH, reverse=True)
    return out[:limit]


def _fetch_feeds(feeds: list[Feed], companies: list[Company], session: Any):
    def worker(sess: Any, feed: Feed):
        try:
            return parse_feed(download(sess, feed.url), feed.name, companies), None
        except Exception as exc:
            log.warning("Feed %s failed: %r", feed.name, exc)
            return [], f"{feed.name}: {type(exc).__name__}"
    results = run_all(feeds, worker, session)
    return [r[0] for r in results], [r[1] for r in results if r[1]]


# ---------------------------------------------------------------- public fetchers

def fetch_news(
    feeds: Iterable[Feed],
    companies: Iterable[Company],
    session: Any = None,
    now: datetime | None = None,
) -> tuple[list[NewsItem], list[str]]:
    """The live wire: every feed, last NEWS_MAX_AGE_DAYS days, newest first."""
    feeds, companies = list(feeds), list(companies)
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=NEWS_MAX_AGE_DAYS)
    batches, errors = _fetch_feeds(feeds, companies, session)
    items = merge(batches, keep=lambda i: i.published is None or i.published >= cutoff)
    return items, errors


def fetch_company_news(
    company: Company,
    companies: Iterable[Company],
    session: Any = None,
    days: int = 30,
) -> tuple[list[NewsItem], list[str]]:
    """A dedicated search for one company, so its page goes deeper than the shared wire."""
    feed = Feed(f"{company.name} search", google_news(company.search_query, days=days))
    batches, errors = _fetch_feeds([feed], list(companies), session)
    return merge(batches), errors


def archive_windows(start: date, end: date, max_windows: int = ARCHIVE_MAX_WINDOWS) -> list[tuple[date, date]]:
    """Split [start, end] into up to `max_windows` contiguous, non-overlapping slices (inclusive)."""
    if not isinstance(start, date) or not isinstance(end, date):
        return []
    if end < start:
        start, end = end, start
    total = (end - start).days + 1
    n = max(1, min(max_windows, total // 7 or 1))
    step = total / n
    windows, cursor = [], start
    for i in range(n):
        stop = start + timedelta(days=round(step * (i + 1)) - 1) if i < n - 1 else end
        if stop < cursor:
            continue
        windows.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return windows


def archive_query(company: Company | None, topic_terms: str = "", extra: str = "") -> str:
    base = company.search_query if company else "(power OR electricity) India"
    parts = [base]
    if topic_terms.strip():
        parts.append(f"({topic_terms.strip()})")
    if extra.strip():
        parts.append(extra.strip()[:120])
    return " ".join(parts)


def fetch_archive(
    start: date,
    end: date,
    companies: Iterable[Company],
    company: Company | None = None,
    topic_terms: str = "",
    extra: str = "",
    session: Any = None,
) -> tuple[list[NewsItem], list[str]]:
    """Dated search across any past range (Google News index), split into slices for depth."""
    companies = list(companies)
    windows = archive_windows(start, end)
    if not windows:
        return [], []
    q = archive_query(company, topic_terms, extra)
    feeds = [
        Feed(f"{a:%d %b %Y}–{b:%d %b %Y}",
             google_news(f"{q} after:{(a - timedelta(days=1)).isoformat()} before:{(b + timedelta(days=1)).isoformat()}", days=None))
        for a, b in windows
    ]
    lo, hi = windows[0][0] - timedelta(days=1), windows[-1][1] + timedelta(days=1)

    def in_range(item: NewsItem) -> bool:
        if item.published is None:
            return False
        d = item.published.astimezone(IST).date()
        return lo <= d <= hi

    batches, errors = _fetch_feeds(feeds, companies, session)
    return merge(batches, keep=in_range, limit=ARCHIVE_MAX_ITEMS), errors


# ---------------------------------------------------------------- filtering (pure)

def filter_news(
    items: Iterable[NewsItem],
    categories: Iterable[str] | None = None,
    symbols: Iterable[str] | None = None,
    query: str = "",
) -> list[NewsItem]:
    cats, syms = set(categories or ()), set(symbols or ())
    q = (query or "").strip().lower()
    return [
        i for i in items
        if (not cats or i.category in cats)
        and (not syms or syms & set(i.tickers))
        and (not q or q in f"{i.title} {i.summary} {i.source}".lower())
    ]


def mention_counts(items: Iterable[NewsItem], companies: Iterable[Company]) -> Mapping[str, int]:
    counts = {c.symbol: 0 for c in companies}
    for i in items:
        for t in i.tickers:
            if t in counts:
                counts[t] += 1
    return counts
