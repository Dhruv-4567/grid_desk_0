"""Whole-app checks with every network call failing: the page must still load, and a section
that hits a bug must show a note instead of taking the site down."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import powerdesk.news as news
import powerdesk.official as official
import powerdesk.prices as prices
import powerdesk.render as render

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise ConnectionError("network disabled in tests")
    original = prices.fetch_closes
    monkeypatch.setattr(prices, "fetch_closes", lambda companies, period, interval="1d", download=None:
                        original(companies, period, interval, download=refuse))
    monkeypatch.setattr(news, "download", refuse)
    monkeypatch.setattr(official, "download", refuse)


def run_app():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def test_app_loads_with_everything_down():
    at = run_app()
    assert not at.exception and not at.error
    assert [t.label for t in at.tabs] == ["Front Page", "Markets", "Companies", "Official Gazette", "Archive"]
    html = " ".join(m.value for m in at.markdown)
    assert "The Grid Desk" in html and "Price unavailable" in html and "Source status" not in html


def test_section_failure_is_contained(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("simulated bug")
    monkeypatch.setattr(render, "market_table", broken)
    at = run_app()
    assert not at.exception
    assert any("markets section hit an unexpected problem" in m.value for m in at.markdown)
    assert any("gd-lead" in m.value or "gd-empty" in m.value for m in at.markdown)   # other sections still render
