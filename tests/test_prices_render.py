from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from powerdesk import charts, render
from powerdesk.config import COMPANIES, Company
from powerdesk.news import NewsItem
from powerdesk.official import Announcement
from powerdesk.prices import Quote, build_quotes, fetch_closes, market_status, rebased
from powerdesk.textutil import IST
from tests.fixtures import fake_download, price_frame

A = Company("AAA", "Alpha", "Transmission")
B = Company("BBB", "Beta", "Transmission")


def closes_for(companies, **kw):
    return fetch_closes(companies, period="2y", download=fake_download, **kw)


# ---------------------------------------------------------------- prices

def test_fetch_closes_both_column_layouts():
    frame = price_frame(["AAA.NS", "BBB.NS"])
    swapped = frame.swaplevel(axis=1)
    for f in (frame, swapped):
        series, err = fetch_closes([A, B], "1y", download=lambda *a, **k: f)
        assert err is None and set(series) == {"AAA", "BBB"} and len(series["AAA"]) == 500


def test_bad_values_cleaned_and_missing_ticker_absent():
    idx = pd.bdate_range("2026-01-01", periods=6)
    frame = pd.DataFrame({("AAA.NS", "Close"): [np.nan, 0, -5, 101, np.inf, 102]}, index=idx)
    series, _ = fetch_closes([A, B], "1y", download=lambda *a, **k: frame)
    assert list(series["AAA"]) == [101.0, 102.0] and "BBB" not in series


@pytest.mark.parametrize("result", [None, pd.DataFrame(), "garbage", 42])
def test_weird_download_results(result):
    assert fetch_closes([A, B], "1y", download=lambda *a, **k: result) == ({}, None)


def test_download_exception_never_raises():
    def boom(*a, **k):
        raise ConnectionError("rate limited")
    series, err = fetch_closes(COMPANIES, "1y", download=boom)
    assert series == {} and "ConnectionError" in err
    quotes = build_quotes(COMPANIES, {}, {}, err)
    assert len(quotes) == len(COMPANIES) and all(q.error and q.last is None for q in quotes.values())


def test_flat_frame_only_for_single_ticker():
    frame = pd.DataFrame({"Close": [10.0, 11.0]}, index=pd.bdate_range("2026-01-01", periods=2))
    assert fetch_closes([A], "1y", download=lambda *a, **k: frame)[0]["AAA"].iloc[-1] == 11.0
    assert fetch_closes([A, B], "1y", download=lambda *a, **k: frame)[0] == {}


def test_build_quotes_merges_live_over_history():
    hist, _ = closes_for([A, B])
    live = {"AAA": hist["AAA"].tail(2) * 1.0}
    live["AAA"].iloc[-1] = 999.0
    q = build_quotes([A, B], hist, live)
    assert q["AAA"].last == 999.0 and q["AAA"].high_52w == 999.0          # live price extends the 52-week range
    assert q["AAA"].prev_close == pytest.approx(float(hist["AAA"].iloc[-2]))
    assert q["BBB"].last == pytest.approx(float(hist["BBB"].iloc[-1]))  # falls back to history
    assert q["AAA"].ret_1y is not None and 0 <= (q["BBB"].range_position or 0) <= 1


def test_quote_edge_cases():
    q = build_quotes([A], {}, {"AAA": pd.Series([50.0])})["AAA"]
    assert q.last == 50 and q.prev_close is None and q.change_pct is None and q.as_of is None
    assert Quote("X", last=10, prev_close=0).change_pct is None
    assert Quote("X", last=10, high_52w=10, low_52w=10).range_position is None
    assert build_quotes([], {}, {}) == {}


def test_rebased():
    hist, _ = closes_for([A, B])
    df = rebased(hist, ["AAA", "BBB", "ZZZ"], 91)
    assert set(df["symbol"]) == {"AAA", "BBB"}
    assert df.groupby("symbol")["value"].first().round(6).eq(100).all()
    assert rebased({}, ["AAA"], 30).empty


@pytest.mark.parametrize("when,bar,expected", [
    (datetime(2026, 10, 6, 11, 0, tzinfo=IST), date(2026, 10, 6), "open"),
    (datetime(2026, 10, 6, 11, 0, tzinfo=IST), date(2026, 10, 5), "closed"),   # holiday: no bar today
    (datetime(2026, 10, 6, 8, 0, tzinfo=IST), date(2026, 10, 5), "pre-open"),
    (datetime(2026, 10, 6, 16, 0, tzinfo=IST), date(2026, 10, 6), "closed"),
    (datetime(2026, 10, 4, 11, 0, tzinfo=IST), date(2026, 10, 2), "closed"),   # Sunday
    (datetime(2026, 10, 6, 5, 0, tzinfo=timezone.utc), date(2026, 10, 6), "open"),  # 10:30 IST given in UTC
])
def test_market_status(when, bar, expected):
    assert market_status(when, bar) == expected


# ---------------------------------------------------------------- rendering safety

EVIL = NewsItem(
    title='Profit *up* [click](javascript:x) $x^2$ <script>alert(1)</script> "quoted" _u_ `c`',
    link="https://ok.com/a_(1)?q=$5",
    source="<b>Src</b>", published=datetime(2026, 10, 6, 6, tzinfo=timezone.utc),
    summary="Line one\n    indented line that could become code", category="tender", tickers=("NTPC",))


def test_story_html_is_escaped_and_single_line():
    out = render.story(EVIL)
    assert "<script>" not in out and "&lt;script&gt;" in out
    for raw in ("$", "*up*", "[click]", "`c`", "_u_"):
        assert raw not in out.split('href="')[0] + out.split('">', 2)[-1]
    assert "\n" not in out
    assert 'href="https://ok.com/a_(1)?q=%245"' in out and 'rel="noopener noreferrer"' in out


def test_bad_links_are_dropped():
    bad = NewsItem("T", "javascript:alert(1)", "S", None, "", "other", ())
    assert "<a " not in render.story(bad)
    assert render.href('https://a.com/"onmouseover=x') == ""


def test_numbers_and_tones():
    assert render.fmt_price(1234.5) == "₹1,234.50" and render.fmt_price(None) == "—"
    assert render.fmt_pct(1.234) == "+1.23%" and render.fmt_pct(-0.5, 1) == "-0.5%"
    assert render.fmt_pct(-0.001) == "0.00%"
    assert (render.tone(1), render.tone(-1), render.tone(0), render.tone(None)) == ("up", "down", "flat", "flat")


def test_components_render_without_data():
    co = COMPANIES[0]
    assert "Price unavailable" in render.quote_box(co, None)
    assert "loading or unavailable" in render.ticker(COMPANIES, {})
    assert "quiet" in render.lead(None)
    assert "Pick at least one segment" in render.market_table([], {}, {}, [], co.symbol)
    assert "No official" in render.gazette([], date(2026, 10, 6))
    html = render.masthead(date(2026, 10, 6), None, "open", co, None, 0)
    assert "NSE open" in html and "Tuesday, 6 October 2026" in html


def test_market_table_and_gazette():
    hist, _ = closes_for([A, B])
    quotes = build_quotes([A, B], hist, {})
    html = render.market_table([A, B], quotes, {"AAA": 3}, ["Transmission"], "AAA")
    assert 'class="gd-home"' in html and html.count("<tr") == 4 and ">3</td>" in html
    ann = [Announcement("New CEA report", "https://cea.nic.in/r.pdf", "CEA", date(2026, 10, 5), "report"),
           Announcement("Old notice <x>", "https://cea.nic.in/o.pdf", "CEA", date(2026, 8, 1), "other")]
    g = render.gazette(ann, date(2026, 10, 6))
    assert g.count("gd-new") == 1 and "&lt;x&gt;" in g


def test_charts_build_or_decline():
    hist, _ = closes_for([A, B])
    assert charts.price_line(hist["AAA"], "t") is not None
    assert charts.price_line(None, "t") is None
    assert charts.price_line(pd.Series([1.0]), "t") is None
    intraday = price_frame(["AAA.NS"], intraday=True)[("AAA.NS", "Close")]
    assert charts.price_line(intraday, "t", prev_close=100.0, intraday=True) is not None
    assert charts.relative_performance(rebased(hist, ["AAA", "BBB"], 91), "AAA") is not None
    assert charts.relative_performance(pd.DataFrame(columns=["date", "symbol", "value"]), "AAA") is None
    charts.relative_performance(rebased(hist, ["AAA", "BBB"], 91), "AAA").to_dict()   # serialises cleanly
