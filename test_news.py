from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from powerdesk.config import COMPANIES, Feed
from powerdesk.news import (
    archive_query, archive_windows, classify, fetch_archive, fetch_company_news, fetch_news,
    filter_news, mention_counts, parse_feed, tag_companies,
)
from powerdesk.textutil import dedupe_key
from tests.fixtures import NOW, FakeResponse, FakeSession, rss, sample_headlines

BY = {c.symbol: c for c in COMPANIES}
PSU = {c.symbol for c in COMPANIES if c.psu}
FEED = rss(sample_headlines(NOW) + [
    ("No link here", "", NOW, ""),
    ("Bad scheme story", "javascript:alert(1)", NOW, ""),
    ("Undated story about a 50 MW solar plant", "https://example.com/u", None, ""),
    ("Ancient story about a 10 MW plant", "https://example.com/old", NOW - timedelta(days=400), ""),
])


def test_parse_feed_cleans_and_tags():
    items = parse_feed(FEED, "Test", COMPANIES)
    by_title = {i.title: i for i in items}
    first = by_title["NTPC REL invites bids for 1,200 MW wind-solar hybrid project in Andhra Pradesh"]  # publisher removed
    assert first.category == "tender" and {"NTPC", "NTPCGREEN"} <= set(first.tickers)
    assert "No link here" not in by_title and "Bad scheme story" not in by_title
    tata = by_title["Tata Power commissions 300 MW solar capacity in Bikaner for captive customers"]
    assert tata.tickers == ("TATAPOWER",) and tata.category == "private"
    assert by_title["NHPC signs MoU with Maharashtra government for 7,350 MW pumped storage projects"].category == "govt"
    assert all(i.published is None or i.published.tzinfo for i in items)


@pytest.mark.parametrize("content", [b"", b"<<not xml", b"\xff\xfe\x00", b"<rss><channel></channel></rss>"])
def test_parse_feed_garbage(content):
    assert parse_feed(content, "X", COMPANIES) == []


@pytest.mark.parametrize("text,tickers,expected", [
    ("SECI issues tender for 2 GW solar", (), "tender"),
    ("CERC proposes grid code amendments", (), "policy"),
    ("Power Grid shares rise 3%", ("POWERGRID",), "markets"),
    ("NTPC commissions 660 MW unit", ("NTPC",), "govt"),
    ("Cabinet clears hydro push for the northeast", (), "govt"),
    ("Adani Green operationalises 750 MW at Khavda", ("ADANIGREEN",), "private"),
    ("Monsoon lifts hydro generation", (), "other"),
    (None, (), "other"),
])
def test_classify(text, tickers, expected):
    assert classify(text, tickers, PSU) == expected


def test_tagging_is_whole_word():
    assert tag_companies("IEX volumes jump", COMPANIES) == ("IEX",)
    assert tag_companies("Sciex launches a lab device", COMPANIES) == ()
    assert "POWERGRID" in tag_companies("POWERGRID to raise bonds", COMPANIES)
    assert tag_companies(None, COMPANIES) == ()
    assert "TATAPOWER" not in tag_companies("Tata Steel results", COMPANIES)


def test_fetch_news_isolates_failures_dedupes_and_sorts():
    routes = {"u1": FakeResponse(FEED), "u2": FakeResponse(FEED),
              "u3": requests.ConnectionError("down"), "u4": FakeResponse(status=503)}
    feeds = [Feed(n, n) for n in routes]
    items, errors = fetch_news(feeds, COMPANIES, session=FakeSession(routes), now=NOW)
    assert len(errors) == 2 and any("u3" in e for e in errors) and any("u4" in e for e in errors)
    keys = [dedupe_key(i.title) for i in items]
    assert len(keys) == len(set(keys))
    assert not any("Ancient" in i.title for i in items)
    dated = [i.published for i in items if i.published]
    assert dated == sorted(dated, reverse=True) and items[-1].published is None


def test_fetch_news_total_failure_and_empty():
    items, errors = fetch_news([Feed("A", "a")], COMPANIES, session=FakeSession({"a": TimeoutError()}), now=NOW)
    assert items == [] and len(errors) == 1
    assert fetch_news([], COMPANIES, now=NOW) == ([], [])


def test_oversized_feed_rejected():
    items, errors = fetch_news([Feed("Big", "b")], COMPANIES,
                               session=FakeSession({"b": FakeResponse(b"x" * 6_000_000)}), now=NOW)
    assert items == [] and "Big" in errors[0]


def test_company_news_uses_dedicated_search():
    company = BY["TORNTPOWER"]
    seen = {}

    class Spy(FakeSession):
        def get(self, url, **kw):
            seen["url"] = url
            return FakeResponse(FEED)
    items, errors = fetch_company_news(company, COMPANIES, session=Spy({}))
    assert "Torrent+Power" in seen["url"] and not errors and items


def test_archive_windows_cover_range_exactly():
    s, e = date(2012, 1, 1), date(2026, 9, 30)
    w = archive_windows(s, e)
    assert len(w) == 12 and w[0][0] == s and w[-1][1] == e
    for (a1, b1), (a2, _) in zip(w, w[1:]):
        assert a1 <= b1 and a2 == b1 + timedelta(days=1)
    assert archive_windows(date(2026, 9, 1), date(2026, 9, 3)) == [(date(2026, 9, 1), date(2026, 9, 3))]
    assert archive_windows(e, s)[0][0] == s                       # reversed input is fixed
    assert archive_windows(None, e) == []


def test_archive_query_and_fetch():
    assert archive_query(None) == "(power OR electricity) India"
    assert archive_query(BY["NTPC"], "tender OR bid", "Rajasthan") == '"NTPC" (tender OR bid) Rajasthan'
    feed = rss([("NTPC floats tender in Rajasthan", "https://e.com/a", datetime(2020, 3, 5, tzinfo=timezone.utc), ""),
                ("Out of range NTPC story", "https://e.com/b", datetime(2024, 1, 1, tzinfo=timezone.utc), ""),
                ("Undated NTPC story", "https://e.com/c", None, "")])

    class Any(FakeSession):
        def get(self, url, **kw):
            assert "after%3A" in url and "before%3A" in url
            return FakeResponse(feed)
    items, errors = fetch_archive(date(2020, 1, 1), date(2020, 6, 30), COMPANIES, BY["NTPC"], session=Any({}))
    assert [i.title for i in items] == ["NTPC floats tender in Rajasthan"] and not errors


def test_filter_and_mentions():
    items = parse_feed(FEED, "T", COMPANIES)
    assert filter_news(items) == items
    assert all(i.category == "policy" for i in filter_news(items, ["policy"]))
    assert all("TATAPOWER" in i.tickers for i in filter_news(items, symbols=["TATAPOWER"]))
    assert len(filter_news(items, query="KHAVDA")) == 1
    counts = mention_counts(items, COMPANIES)
    assert counts["TATAPOWER"] == 1 and counts["SUZLON"] == 0
