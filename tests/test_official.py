from datetime import date

import pytest
import requests

from powerdesk.config import Feed, OfficialPage
from powerdesk.official import classify_official, fetch_official, filter_official, find_date, is_noise, parse_listing
from tests.fixtures import CEA_HTML, GRID_INDIA_HTML, MNRE_HTML, NOW, FakeResponse, FakeSession, rss, sample_headlines

TODAY = NOW.date()


def titles(items):
    return [a.title for a in items]


def test_cea_table():
    items = parse_listing(CEA_HTML, "https://cea.nic.in/whats-new/?lang=en", "CEA")
    t = titles(items)
    cap = items[t.index("Monthly Installed Capacity Report as on 30.06.2026")]
    assert cap.published == date(2026, 7, 15) and cap.kind == "report" and cap.link.endswith("Website_June.pdf")
    draft = next(a for a in items if a.title.startswith("Draft CEA"))
    assert draft.kind == "regulation"
    assert draft.link == "https://cea.nic.in/wp-content/uploads/notification/2026/08/Draft%20Grid.pdf"
    for hidden in ("Vacancy", "NPC Meeting", "General Review", "Profiles of Chairperson"):
        assert not any(hidden in x for x in t)


def test_mnre_table():
    almm, seabed = parse_listing(MNRE_HTML, "https://mnre.gov.in/en/past-notices/current-notices/", "MNRE")
    assert almm.title == "Updated (05.06.2025) List-I under ALMM order for Solar PV Modules"
    assert almm.published == date(2026, 8, 18) and almm.link == "https://mnre.gov.in/files/almm.pdf"
    assert seabed.kind == "tender"


def test_article_cards_fallback():
    items = parse_listing(GRID_INDIA_HTML, "https://grid-india.in/press-release/", "Grid-India")
    assert items[0].title == "Grid-India meets all-time peak demand of 250 GW successfully"
    assert items[0].published == date(2026, 9, 18) and items[0].link == "https://grid-india.in/press/gi-peak.pdf"
    assert items[1].kind == "report"


def test_dated_list_fallback_skips_menus():
    html = b'<ul><li><a href="/m">Some long navigation menu entry</a></li><li>Guidelines for BESS fire safety audit, 12 Sep 2026 <a href="/b.pdf">PDF</a></li></ul>'
    items = parse_listing(html, "https://x.gov.in/", "X")
    assert len(items) == 1 and items[0].published == date(2026, 9, 12)
    assert items[0].title.startswith("Guidelines for BESS fire safety audit")


@pytest.mark.parametrize("content", [b"", b"<<<>>>", b"\xff\xfe\x00garbage", b"<html><body>No notices</body></html>", None])
def test_garbage_pages(content):
    assert parse_listing(content, "https://x.gov.in/", "X") == []


@pytest.mark.parametrize("text,expected", [
    ("2026-07-15", date(2026, 7, 15)), ("as on 30.06.2026", date(2026, 6, 30)),
    ("18/08/2026 to 18/09/2026", date(2026, 8, 18)), ("held on 12th September 2026", date(2026, 9, 12)),
    ("Sep 21, 2026", date(2026, 9, 21)), ("31/02/2026", None), ("99-99-9999", None),
    ("version 1.2.3", None), (None, None), (42, None),
])
def test_find_date(text, expected):
    assert find_date(text) == expected


def test_classify_and_noise():
    assert classify_official("Invitation for RFP on GeM portal") == "tender"
    assert classify_official("Minutes of the 20th Meeting of NCT") == "meeting"
    assert classify_official("Advisory on use of Ester Oil in Transformers") == "scheme"
    assert classify_official("Chairperson addresses") == "other"
    assert is_noise("Notice of Result for Canteen Attendant") and not is_noise("Draft Cyber Security Regulations")


def test_fetch_official_isolation_and_filters():
    routes = {
        "https://cea.nic.in/w/": FakeResponse(CEA_HTML),
        "https://mnre.gov.in/n/": requests.exceptions.SSLError("bad certificate"),
        "https://new.gov.in/": FakeResponse(b"<html>redesigned</html>"),
        "pib": FakeResponse(rss(sample_headlines(NOW)[:3])),
    }
    pages = [OfficialPage("CEA", "https://cea.nic.in/w/"), OfficialPage("MNRE", "https://mnre.gov.in/n/"),
             OfficialPage("New", "https://new.gov.in/")]
    items, errors = fetch_official(pages, [Feed("Ministry of Power", "pib")], session=FakeSession(routes), today=TODAY)
    assert any("MNRE" in e and "SSLError" in e for e in errors)
    assert any("New" in e and "layout" in e for e in errors)
    assert {a.body for a in items} == {"CEA", "Ministry of Power"}
    assert not any(a.published and a.published.year == 2019 for a in items)
    dated = [a.published for a in items if a.published]
    assert dated == sorted(dated, reverse=True)
    assert filter_official(items, bodies=["CEA"], kinds=["report"])[0].title.startswith("Monthly Installed")
    assert filter_official(items, query="GRID")[0].kind == "regulation"
    assert fetch_official([], [], today=TODAY) == ([], [])
