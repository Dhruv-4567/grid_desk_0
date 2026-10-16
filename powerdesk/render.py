"""HTML for the newspaper layout. Pure functions: data in, one-line HTML string out.

Safety rules, enforced here and nowhere else:
  * every piece of outside text goes through esc(), which also neutralises Markdown/LaTeX characters
    ($ * _ ` ~ [ ]) so st.markdown can't reinterpret a headline;
  * every link goes through href(), which only lets plain http(s) URLs through;
  * output is a single line, so Markdown never turns indentation into code blocks.
"""
from __future__ import annotations

import html
from datetime import date, datetime
from itertools import groupby
from typing import Iterable, Mapping, Sequence

from .config import CATEGORIES, OFFICIAL_KINDS, OFFICIAL_OTHER, Company
from .news import NewsItem
from .official import Announcement
from .prices import Quote
from .textutil import long_date, relative_day, safe_link, time_label

CATEGORY_LABELS = dict(CATEGORIES)
OFFICIAL_LABELS = {k: label for k, label, _ in OFFICIAL_KINDS} | {OFFICIAL_OTHER[0]: OFFICIAL_OTHER[1]}
_MD_ENTITIES = str.maketrans({"$": "&#36;", "*": "&#42;", "_": "&#95;", "`": "&#96;", "~": "&#126;",
                              "[": "&#91;", "]": "&#93;", "\\": "&#92;", "\n": " ", "\r": " ", "|": "&#124;"})


def esc(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True).translate(_MD_ENTITIES)


def href(url: object) -> str:
    link = safe_link(url)
    return html.escape(link, quote=True).replace("$", "%24") if link else ""


def _a(text: str, url: object) -> str:
    h = href(url)
    return f'<a href="{h}" target="_blank" rel="noopener noreferrer">{esc(text)}</a>' if h else esc(text)


# ---------------------------------------------------------------- numbers

def fmt_price(x: float | None) -> str:
    return "—" if x is None else f"₹{x:,.2f}"


def fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    x = round(x, digits)
    return f"{0:.{digits}f}%" if x == 0 else f"{x:+.{digits}f}%"


def tone(x: float | None) -> str:
    if x is None or abs(x) < 0.005:
        return "flat"
    return "up" if x > 0 else "down"


def arrow(x: float | None) -> str:
    return {"up": "▲", "down": "▼"}.get(tone(x), "■")


# ---------------------------------------------------------------- masthead

def masthead(today: date, updated: datetime | None, status: str, home: Company, home_quote: Quote | None,
             story_count: int) -> str:
    status_html = {
        "open": '<span class="gd-live">● NSE open</span>',
        "pre-open": '<span class="gd-closed">NSE opens 9:15 IST</span>',
    }.get(status, '<span class="gd-closed">NSE closed</span>')
    q = home_quote or Quote(home.symbol)
    left = (f'<div class="gd-ear">{esc(home.name)}<br><b>{esc(fmt_price(q.last))}</b> '
            f'<span class="{tone(q.change_pct)}">{arrow(q.change_pct)} {esc(fmt_pct(q.change_pct))}</span></div>')
    right = f'<div class="gd-ear right">On the wire<br><b>{story_count} stories</b> · 14 days</div>'
    stamp = f"Edition updated {updated.strftime('%H:%M')} IST" if updated else "Edition updating"
    return (
        '<div class="gd-mast">'
        f'<div class="gd-ears">{left}<div></div>{right}</div>'
        '<div class="gd-name">The Grid Desk</div>'
        '<div class="gd-motto">Power, markets &amp; policy, for the investor relations desk</div>'
        '<div class="gd-dateline">'
        f'<span>Mumbai</span><span>{esc(long_date(today))}</span><span>{status_html}</span><span>{esc(stamp)}</span>'
        '</div></div>'
    )


def ticker(companies: Iterable[Company], quotes: Mapping[str, Quote]) -> str:
    parts = []
    for c in companies:
        q = quotes.get(c.symbol)
        if not q or q.last is None:
            continue
        parts.append(f'<span class="gd-tick"><b>{esc(c.symbol)}</b>{esc(f"{q.last:,.2f}")} '
                     f'<span class="{tone(q.change_pct)}">{arrow(q.change_pct)} {esc(fmt_pct(q.change_pct))}</span></span>')
    if not parts:
        return '<div class="gd-ticker"><span class="gd-tick">Prices are loading or unavailable right now.</span></div>'
    track = "".join(parts)
    return f'<div class="gd-ticker"><div class="gd-ticker-track">{track}{track}</div></div>'


def section(title: str, note: str = "") -> str:
    return f'<div class="gd-section"><div class="gd-h2">{esc(title)}</div><span>{esc(note)}</span></div>'


def empty(text: str) -> str:
    return f'<div class="gd-empty">{esc(text)}</div>'


# ---------------------------------------------------------------- stories

def _byline(item: NewsItem, show_day: bool = True) -> str:
    bits = [item.source]
    if item.published:
        bits.append(f"{relative_day(item.published)}, {time_label(item.published)}" if show_day else time_label(item.published))
    tags = "".join(f'<span class="gd-tag">{esc(t)}</span>' for t in item.tickers[:4])
    return f'<div class="gd-byline">{esc(" · ".join(b for b in bits if b))}{tags}</div>'


def story(item: NewsItem, show_kicker: bool = True, show_day: bool = True) -> str:
    kicker = f'<div class="gd-kicker">{esc(CATEGORY_LABELS.get(item.category, item.category))}</div>' if show_kicker else ""
    dek = f'<div class="gd-dek">{esc(item.summary)}</div>' if item.summary else ""
    return f'<div class="gd-story">{kicker}<div class="gd-h3">{_a(item.title, item.link)}</div>{dek}{_byline(item, show_day)}</div>'


def lead(item: NewsItem | None) -> str:
    if item is None:
        return empty("The wire is quiet. Stories will appear here as soon as the feeds respond.")
    dek = f'<div class="gd-dek">{esc(item.summary)}</div>' if item.summary else ""
    return (f'<div class="gd-lead"><div class="gd-kicker">Lead · {esc(CATEGORY_LABELS.get(item.category, item.category))}</div>'
            f'<div class="gd-h1">{_a(item.title, item.link)}</div>{dek}{_byline(item)}</div>')


def column(items: Sequence[NewsItem], empty_text: str = "Nothing new in this section.") -> str:
    if not items:
        return empty(empty_text)
    return "<div>" + "".join(story(i, show_kicker=False) for i in items) + "</div>"


def _month(item: NewsItem) -> str:
    return item.published.strftime("%B %Y") if item.published else "Undated"


def wire(items: Iterable[NewsItem], today: date | None = None, by_month: bool = False) -> str:
    """Stories grouped under day (or month) headings."""
    out = []
    key = _month if by_month else (lambda i: relative_day(i.published, today))
    for day, group in groupby(items, key=key):
        out.append(f'<div class="gd-day">{esc(day)}</div>')
        out.extend(story(i, show_day=by_month) for i in group)
    return "<div>" + "".join(out) + "</div>" if out else empty("No stories match these filters.")


# ---------------------------------------------------------------- quotes and tables

def _range_bar(q: Quote) -> str:
    pos = q.range_position
    if pos is None:
        return ""
    return ('<div class="gd-range">52-week range'
            f'<div class="gd-range-bar"><span class="gd-range-dot" style="left:calc({pos * 100:.1f}% - 1px)"></span></div>'
            f'<div class="gd-range-ends"><span>{esc(fmt_price(q.low_52w))}</span><span>{esc(fmt_price(q.high_52w))}</span></div></div>')


def quote_box(company: Company, q: Quote | None) -> str:
    q = q or Quote(company.symbol, error="No price data")
    as_of = f" · as of {q.as_of:%d %b}" if q.as_of else ""
    if q.last is None:
        body = empty(f"Price unavailable right now ({q.error or 'no data'}). It retries automatically.")
    else:
        chg = q.change
        chg_txt = "—" if chg is None else f"{chg:+,.2f}"
        body = (
            f'<div class="gd-qprice">{esc(fmt_price(q.last))}</div>'
            f'<div class="gd-qchg {tone(q.change_pct)}">{arrow(q.change_pct)} {esc(chg_txt)} ({esc(fmt_pct(q.change_pct))}) today</div>'
            '<div class="gd-qgrid">'
            f'<div>1 month<b class="{tone(q.ret_1m)}">{esc(fmt_pct(q.ret_1m, 1))}</b></div>'
            f'<div>3 months<b class="{tone(q.ret_3m)}">{esc(fmt_pct(q.ret_3m, 1))}</b></div>'
            f'<div>1 year<b class="{tone(q.ret_1y)}">{esc(fmt_pct(q.ret_1y, 1))}</b></div>'
            f'</div>{_range_bar(q)}'
        )
    return (f'<div class="gd-quote"><div class="gd-qname">{esc(company.name)}</div>'
            f'<div class="gd-qsym">NSE: {esc(company.symbol)} · {esc(company.segment)}{esc(as_of)}</div>{body}</div>')


def market_table(companies: Sequence[Company], quotes: Mapping[str, Quote], mentions: Mapping[str, int],
                 segments: Sequence[str], home_symbol: str) -> str:
    head = ("<tr><th>Company</th><th>Price</th><th>Day</th><th>1M</th><th>1Y</th>"
            "<th>52-week range</th><th>News, 14d</th></tr>")
    rows = []
    for seg in segments:
        members = [c for c in companies if c.segment == seg]
        if not members:
            continue
        rows.append(f'<tr class="gd-seg"><td colspan="7">{esc(seg)}</td></tr>')
        for c in members:
            q = quotes.get(c.symbol) or Quote(c.symbol, error="No price data")
            pos = q.range_position
            bar = (f'<span class="gd-minirange" title="{esc(fmt_price(q.low_52w))} – {esc(fmt_price(q.high_52w))}">'
                   f'<i style="left:{pos * 100:.0f}%"></i></span>') if pos is not None else "—"
            price = esc(fmt_price(q.last)) if q.last is not None else f'<span class="flat" title="{esc(q.error)}">n/a</span>'
            cls = ' class="gd-home"' if c.symbol == home_symbol else ""
            rows.append(
                f'<tr{cls}><td class="gd-co">{esc(c.name)}<small>{esc(c.symbol)}</small></td>'
                f'<td>{price}</td>'
                f'<td class="{tone(q.change_pct)}">{esc(fmt_pct(q.change_pct))}</td>'
                f'<td class="{tone(q.ret_1m)}">{esc(fmt_pct(q.ret_1m, 1))}</td>'
                f'<td class="{tone(q.ret_1y)}">{esc(fmt_pct(q.ret_1y, 1))}</td>'
                f'<td>{bar}</td><td>{int(mentions.get(c.symbol, 0))}</td></tr>'
            )
    if not rows:
        return empty("Pick at least one segment.")
    return f'<div class="gd-table-wrap"><table class="gd-table"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


# ---------------------------------------------------------------- official gazette

def gazette(items: Iterable[Announcement], today: date, new_days: int = 7) -> str:
    out = []
    for day, group in groupby(items, key=lambda a: relative_day(a.published, today)):
        out.append(f'<div class="gd-day">{esc(day)}</div>')
        for a in group:
            new = '<span class="gd-new">NEW</span>' if a.published and 0 <= (today - a.published).days <= new_days else ""
            out.append(f'<div class="gd-gazette"><div class="gd-kicker">{esc(a.body)} · {esc(OFFICIAL_LABELS.get(a.kind, a.kind))}</div>'
                       f'<div class="gd-gtitle">{new}{_a(a.title, a.link)}</div></div>')
    return "<div>" + "".join(out) + "</div>" if out else empty("No official notices match these filters.")


def gazette_brief(items: Sequence[Announcement]) -> str:
    if not items:
        return empty("No official notices loaded yet.")
    return "<div>" + "".join(
        f'<div class="gd-gazette"><div class="gd-kicker">{esc(a.body)}</div>'
        f'<div class="gd-gtitle">{_a(a.title, a.link)}</div>'
        f'<div class="gd-byline">{esc(relative_day(a.published))}</div></div>' for a in items) + "</div>"


def footer(errors: Sequence[str]) -> str:
    note = f"{len(errors)} source(s) did not respond this round; everything else is current." if errors else "All sources responded."
    return (f'<div class="gd-footer">Prices: Yahoo Finance (NSE), may lag the exchange by a few minutes. '
            f'News: Google News, Mercom India, Power Peak Digest. Official: CEA, MNRE, Grid-India, PIB, CERC, SECI. {esc(note)}</div>')
