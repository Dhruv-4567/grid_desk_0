"""The Grid Desk — a newspaper for the power sector.

Run locally:  streamlit run app.py
Everything you'd want to change (companies, feeds, sources, timings) is in powerdesk/config.py.
"""
from __future__ import annotations

import functools
import logging
from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from powerdesk import charts, config, render, theme
from powerdesk.news import fetch_archive, fetch_company_news, fetch_news, filter_news, merge, mention_counts
from powerdesk.official import fetch_official, filter_official
from powerdesk.prices import build_quotes, fetch_closes, market_status, rebased
from powerdesk.textutil import has_phrase, now_ist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("griddesk")

st.set_page_config(page_title="The Grid Desk", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
st.markdown(theme.CSS, unsafe_allow_html=True)

BY_SYMBOL = {c.symbol: c for c in config.COMPANIES}
HOME = BY_SYMBOL[config.HOME_SYMBOL]
CORE = [c for c in config.COMPANIES if c.segment in config.CORE_SEGMENTS]


def show(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def company_label(symbol: str) -> str:
    c = BY_SYMBOL.get(symbol)
    return f"{c.name} ({symbol})" if c else symbol


# ================================================================ data (cached; the fetchers never raise)

@st.cache_data(ttl=config.HISTORY_TTL_SECONDS, show_spinner=False)
def load_history():
    return fetch_closes(config.COMPANIES, period="2y")   # 2y so 1-year returns always have a base


@st.cache_data(ttl=config.LIVE_TTL_SECONDS, show_spinner=False)
def load_live():
    return fetch_closes(config.COMPANIES, period="5d")


@st.cache_data(ttl=config.LIVE_TTL_SECONDS, show_spinner=False)
def load_intraday(symbol: str):
    company = BY_SYMBOL.get(symbol)
    if company is None:
        return None
    series, _ = fetch_closes([company], period="1d", interval="5m")
    return series.get(symbol)


@st.cache_data(ttl=config.NEWS_TTL_SECONDS, show_spinner=False)
def load_news():
    return fetch_news(config.NEWS_FEEDS, config.COMPANIES)


@st.cache_data(ttl=config.COMPANY_NEWS_TTL_SECONDS, show_spinner=False)
def load_company_news(symbol: str):
    company = BY_SYMBOL.get(symbol)
    return fetch_company_news(company, config.COMPANIES) if company else ([], [])


@st.cache_data(ttl=config.OFFICIAL_TTL_SECONDS, show_spinner=False)
def load_official():
    return fetch_official(config.OFFICIAL_PAGES, config.OFFICIAL_FEEDS)


@st.cache_data(ttl=config.ARCHIVE_TTL_SECONDS, show_spinner=False, max_entries=50)
def load_archive(start: date, end: date, symbol: str | None, topic_terms: str, extra: str):
    return fetch_archive(start, end, config.COMPANIES, BY_SYMBOL.get(symbol) if symbol else None, topic_terms, extra)


def fresh(loader, *args):
    """Call a cached loader; if it came back empty with errors, forget it so the next refresh retries."""
    data, errors = loader(*args)
    if errors and not data:
        loader.clear()
    return data, errors


def quotes_now():
    history, herr = fresh(load_history)
    live, lerr = fresh(load_live)
    return build_quotes(config.COMPANIES, history, live, lerr or herr), history, live


def last_year(series):
    if series is None or not isinstance(series.index, pd.DatetimeIndex) or series.empty:
        return series
    return series[series.index >= series.index[-1] - pd.Timedelta(days=365)]


def current_status(live) -> str:
    s = live.get(HOME.symbol)
    last_bar = s.index[-1].date() if s is not None and len(s) and isinstance(s.index, pd.DatetimeIndex) else None
    return market_status(now_ist(), last_bar)


def guarded(title: str):
    """Last line of defence: a section that hits something unexpected shows a note, not a crash."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                log.exception("%s failed", title)
                show(render.empty(f"The {title} section hit an unexpected problem and will retry on the next refresh. "
                                  "Press “Refresh” to try now."))
        return inner
    return wrap


def source_status(errors) -> None:
    if errors:
        with st.expander(f"Source status · {len(errors)} did not respond this round"):
            for e in errors:
                st.text(e)


# ================================================================ masthead (refreshes every minute)

@st.fragment(run_every=config.LIVE_TTL_SECONDS)
@guarded("masthead")
def masthead():
    quotes, _, live = quotes_now()
    items, _ = fresh(load_news)
    show(render.masthead(now_ist().date(), now_ist(), current_status(live), HOME, quotes.get(HOME.symbol), len(items)))
    show(render.ticker(CORE, quotes))


masthead()
_, refresh_col = st.columns([5, 1])
if refresh_col.button("↻ Refresh", type="tertiary", width="stretch", help="Fetch everything again now"):
    st.cache_data.clear()
    st.rerun()

front_tab, markets_tab, companies_tab, gazette_tab, archive_tab = st.tabs(
    ["Front Page", "Markets", "Companies", "Official Gazette", "Archive"])


# ================================================================ front page

def pick_lead(items):
    for i in items:
        if i.tickers and i.category in ("tender", "govt", "private", "policy"):
            return i
    return items[0] if items else None


@st.fragment(run_every=config.NEWS_TTL_SECONDS)
@guarded("front page")
def front_page():
    with st.spinner("Collecting the latest from the wire…"):
        items, errors = fresh(load_news)
        official, oerrors = fresh(load_official)
        quotes, _, _ = quotes_now()

    lead = pick_lead(items)
    rest = [i for i in items if i is not lead]
    main, rail = st.columns([2.1, 1], gap="large")
    with main:
        show(render.lead(lead))
        seconds = [i for i in rest if i.category != (lead.category if lead else None)][:2]
        a, b = st.columns(2, gap="medium")
        for col, item in zip((a, b), seconds):
            with col:
                show(render.story(item))
    with rail:
        show(render.quote_box(HOME, quotes.get(HOME.symbol)))
        show(render.section(f"{HOME.name} desk"))
        show(render.column(filter_news(items, symbols=[HOME.symbol])[:4], f"No {HOME.name} stories in the last two weeks."))

    used = {id(lead), *(id(i) for i in seconds)} if lead else set()
    rest = [i for i in rest if id(i) not in used]

    def row(cats_titles):
        cols = st.columns(len(cats_titles), gap="large")
        for col, (cid, title) in zip(cols, cats_titles):
            with col:
                show(render.section(title))
                if cid == "official":
                    show(render.gazette_brief(official[:6]))
                else:
                    show(render.column([i for i in rest if i.category == cid][:6]))

    row([("tender", "Tenders & Orders"), ("govt", "Government & PSU"), ("private", "Private Sector")])
    row([("policy", "Policy & Regulation"), ("markets", "Markets & Deals"), ("official", "From the Gazette")])

    show(render.section("The Wire", "every story, newest first · filter by section or company"))
    cats = st.pills("Sections", [c for c, _ in config.CATEGORIES], selection_mode="multi",
                    format_func=lambda c: render.CATEGORY_LABELS.get(c, c), key="wire_cats") or []
    f2, f3 = st.columns([2, 1.2])
    syms = f2.multiselect("Companies", [c.symbol for c in config.COMPANIES], format_func=company_label,
                          key="wire_syms", placeholder="All companies")
    q = f3.text_input("Search", key="wire_q", placeholder="MW, state, scheme…")
    shown = filter_news(items, cats, syms, q)
    st.caption(f"{len(shown)} of {len(items)} stories from the last {config.NEWS_MAX_AGE_DAYS} days.")
    show(render.wire(shown[:200]))
    show(render.footer(errors + oerrors))
    source_status(errors + oerrors)


with front_tab:
    front_page()


# ================================================================ markets (refreshes every minute)

SORTS = {"By segment": None, "Day change": "change_pct", "1-month return": "ret_1m",
         "1-year return": "ret_1y", "Most in the news": "mentions"}


@st.fragment(run_every=config.LIVE_TTL_SECONDS)
@guarded("markets")
def markets():
    quotes, history, live = quotes_now()
    items, _ = fresh(load_news)
    status = current_status(live)

    show(render.section("Market Report", {"open": "NSE open · updates every minute",
                                          "pre-open": "NSE opens 9:15 IST"}.get(status, "NSE closed · last close shown")))
    left, right = st.columns([1, 1.7], gap="large")
    with left:
        show(render.quote_box(HOME, quotes.get(HOME.symbol)))
    with right:
        intraday = load_intraday(HOME.symbol)
        chart = charts.price_line(intraday, f"{HOME.name} · today, 5-minute", quotes[HOME.symbol].prev_close, intraday=True)
        if chart is None:
            chart = charts.price_line(last_year(history.get(HOME.symbol)), f"{HOME.name} · one year")
        if chart is None:
            show(render.empty("Chart unavailable right now; it retries automatically."))
        else:
            st.altair_chart(chart, width="stretch")

    show(render.section("Power Sector Peers", "generation · transmission · distribution"))
    segs = st.pills("Segments", list(config.SEGMENTS), selection_mode="multi",
                    default=list(config.CORE_SEGMENTS), key="mkt_segs") or []
    c2, _ = st.columns([1, 2.5])
    sort_label = c2.selectbox("Order", list(SORTS), key="mkt_sort")
    mentions = mention_counts(items, config.COMPANIES)
    chosen = [c for c in config.COMPANIES if c.segment in segs]
    key = SORTS[sort_label]
    if key:
        def sort_value(c):
            v = mentions.get(c.symbol, 0) if key == "mentions" else getattr(quotes.get(c.symbol), key, None)
            return (v is None, -(v or 0))
        chosen = [replace(c, segment=f"All selected · {sort_label.lower()}") for c in sorted(chosen, key=sort_value)]
        seg_order = [chosen[0].segment] if chosen else []
    else:
        seg_order = [s for s in config.SEGMENTS if s in segs]
    show(render.market_table(chosen, quotes, mentions, seg_order, HOME.symbol))
    missing = [c.symbol for c in chosen if quotes.get(c.symbol) is None or quotes[c.symbol].last is None]
    if missing:
        st.caption(f"No price right now for: {', '.join(missing)}. These retry automatically.")

    show(render.section("Relative Performance", "rebased to 100 at the start of the window"))
    p1, p2 = st.columns([3, 1.2])
    default_peers = [s for s in ("TATAPOWER", "NTPC", "ADANIPOWER", "JSWENERGY", "TORNTPOWER", "POWERGRID") if s in BY_SYMBOL]
    peers = p1.multiselect("Compare", [c.symbol for c in config.COMPANIES], default=default_peers,
                           format_func=company_label, key="perf_peers", max_selections=8)
    window = p2.segmented_control("Window", ["1M", "3M", "6M", "1Y"], default="6M", required=True, key="perf_win") or "6M"
    days = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365}[window]
    perf = charts.relative_performance(rebased(history, peers, days), HOME.symbol)
    if perf is None:
        show(render.empty("Pick at least one company with price history to compare."))
    else:
        st.altair_chart(perf, width="stretch")

    with st.expander("Sortable table and download"):
        frame = pd.DataFrame([{
            "Symbol": c.symbol, "Company": c.name, "Segment": c.segment, "Price (₹)": q.last,
            "Day %": q.change_pct, "1M %": q.ret_1m, "3M %": q.ret_3m, "1Y %": q.ret_1y,
            "52W high": q.high_52w, "52W low": q.low_52w, "News (14d)": mentions.get(c.symbol, 0),
            "As of": q.as_of, "Status": q.error or "OK",
        } for c in config.COMPANIES if (q := quotes.get(c.symbol))])
        st.dataframe(frame, hide_index=True, width="stretch", column_config={
            col: st.column_config.NumberColumn(format="%.2f") for col in ("Price (₹)", "Day %", "1M %", "3M %", "1Y %", "52W high", "52W low")})
        st.download_button("Download CSV", frame.to_csv(index=False).encode("utf-8"),
                           file_name=f"power-peers-{now_ist():%Y%m%d-%H%M}.csv", mime="text/csv")


with markets_tab:
    markets()


# ================================================================ companies

@st.fragment
@guarded("companies")
def companies():
    symbols = [c.symbol for c in config.COMPANIES]
    sym = st.selectbox("Company", symbols, index=symbols.index(HOME.symbol), format_func=company_label, key="co_sym")
    company = BY_SYMBOL[sym]
    quotes, history, _ = quotes_now()

    left, right = st.columns([1, 1.7], gap="large")
    with left:
        show(render.quote_box(company, quotes.get(sym)))
    with right:
        chart = charts.price_line(last_year(history.get(sym)), f"{company.name} · one year")
        if chart is None:
            show(render.empty("Price history unavailable right now."))
        else:
            st.altair_chart(chart, width="stretch")

    with st.spinner(f"Searching the wire for {company.name}…"):
        wire_items, _ = fresh(load_news)
        own_items, errors = fresh(load_company_news, sym)
        official, _ = fresh(load_official)
    stories = merge([filter_news(wire_items, symbols=[sym]), [i for i in own_items if sym in i.tickers] or own_items])

    news_col, gazette_col = st.columns([2, 1], gap="large")
    with news_col:
        show(render.section(f"{company.name} in the news", "last 30 days"))
        cats = st.pills("Sections", [c for c, _ in config.CATEGORIES], selection_mode="multi",
                        format_func=lambda c: render.CATEGORY_LABELS.get(c, c), key="co_cats") or []
        shown = filter_news(stories, cats)
        st.caption(f"{len(shown)} {'story' if len(shown) == 1 else 'stories'}.")
        show(render.wire(shown[:150]))
    with gazette_col:
        show(render.section("Official mentions"))
        mentions = [a for a in official if has_phrase(a.title, company.match_terms)]
        show(render.gazette_brief(mentions[:10]) if mentions else render.empty(f"No official notices name {company.name} recently."))
    source_status(errors)


with companies_tab:
    companies()


# ================================================================ official gazette

@st.fragment(run_every=config.OFFICIAL_TTL_SECONDS)
@guarded("official gazette")
def gazette():
    with st.spinner("Checking CEA, MNRE, Grid-India, PIB, CERC and SECI…"):
        items, errors = fresh(load_official)
    show(render.section("Official Gazette", f"notices from the last {config.OFFICIAL_MAX_AGE_DAYS} days · checked every 3 hours"))
    bodies = list(dict.fromkeys([p.body for p in config.OFFICIAL_PAGES] + [f.name for f in config.OFFICIAL_FEEDS]))
    picked_bodies = st.pills("Source", bodies, selection_mode="multi", key="gz_bodies") or []
    picked_kinds = st.pills("Type", list(render.OFFICIAL_LABELS), selection_mode="multi", key="gz_kinds",
                            format_func=lambda k: render.OFFICIAL_LABELS.get(k, k)) or []
    q = st.text_input("Search notices", key="gz_q", placeholder="Regulation, ALMM, BESS, capacity report…")
    shown = filter_official(items, picked_bodies, picked_kinds, q)
    st.caption(f"{len(shown)} of {len(items)} notices. NEW = last 7 days.")
    show(render.gazette(shown[:300], now_ist().date()))
    source_status(errors)


with gazette_tab:
    gazette()


# ================================================================ archive

@st.fragment
@guarded("archive")
def archive():
    show(render.section("The Archive", f"search any period since {config.ARCHIVE_EARLIEST_YEAR}"))
    today = now_ist().date()
    earliest = date(config.ARCHIVE_EARLIEST_YEAR, 1, 1)
    topics = dict(config.ARCHIVE_TOPICS)
    with st.form("archive_form", border=False):
        a1, a2, a3, a4 = st.columns([1, 1, 1.4, 1.4])
        start = a1.date_input("From", value=today - timedelta(days=90), min_value=earliest, max_value=today, key="ar_from")
        end = a2.date_input("To", value=today, min_value=earliest, max_value=today, key="ar_to")
        sym = a3.selectbox("Company", ["__all__"] + [c.symbol for c in config.COMPANIES], key="ar_sym",
                           format_func=lambda s: "Whole sector" if s == "__all__" else company_label(s))
        topic = a4.selectbox("Topic", list(topics), key="ar_topic")
        extra = st.text_input("Keywords (optional)", key="ar_kw", placeholder="e.g. Rajasthan, pumped storage, Mundra")
        submitted = st.form_submit_button("Search the archive")
    if submitted:
        st.session_state["ar_params"] = (min(start, end), max(start, end), None if sym == "__all__" else sym,
                                         topics.get(topic, ""), extra.strip()[:120])
    params = st.session_state.get("ar_params")
    if not params:
        show(render.empty("Choose a period and press “Search the archive”. Long periods are split into slices "
                          "so older years still return plenty of stories."))
        return
    with st.spinner("Searching the archive…"):
        items, errors = fresh(load_archive, *params)
    s, e, _, _, _ = params
    st.caption(f"{len(items)} stories between {s:%d %b %Y} and {e:%d %b %Y}. Coverage of very old years is thinner.")
    if items:
        frame = pd.DataFrame([{"Date": i.published.date() if i.published else None, "Headline": i.title,
                               "Source": i.source, "Section": render.CATEGORY_LABELS.get(i.category, i.category),
                               "Companies": ", ".join(i.tickers), "Link": i.link} for i in items])
        st.download_button("Download results (CSV)", frame.to_csv(index=False).encode("utf-8"),
                           file_name=f"power-archive-{s:%Y%m%d}-{e:%Y%m%d}.csv", mime="text/csv")
    show(render.wire(items[:400], by_month=True))
    source_status(errors)


with archive_tab:
    archive()
