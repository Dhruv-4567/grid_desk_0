"""Shared fake data and fake network for tests (and for previewing the layout offline)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import numpy as np
import pandas as pd
import requests

from powerdesk.config import COMPANIES


class FakeResponse:
    def __init__(self, content: bytes = b"", status: int = 200):
        self.content, self.status = content, status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))

    def iter_content(self, size):
        for i in range(0, len(self.content), size):
            yield self.content[i:i + size]


class FakeSession:
    """Maps URL -> FakeResponse or Exception. Unknown URLs raise ConnectionError."""

    def __init__(self, routes):
        self.routes = routes

    def get(self, url, **kwargs):
        result = self.routes.get(url, requests.ConnectionError(f"no route for {url}"))
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        pass


def rss(items: list[tuple[str, str, datetime | None, str]]) -> bytes:
    """items: (title, link, published, summary)"""
    out = ['<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>']
    for title, link, published, summary in items:
        date_tag = f"<pubDate>{format_datetime(published)}</pubDate>" if published else ""
        source = f'<source url="https://pub.example">{title.rsplit(" - ", 1)[1]}</source>' if " - " in title else ""
        out.append(f"<item><title>{title}</title><link>{link}</link>{date_tag}{source}<description>{summary}</description></item>")
    out.append("</channel></rss>")
    return "".join(out).encode()


def sample_headlines(now: datetime) -> list[tuple[str, str, datetime | None, str]]:
    h = lambda hours: now - timedelta(hours=hours)
    return [
        ("NTPC REL invites bids for 1,200 MW wind-solar hybrid project in Andhra Pradesh - Mercom India",
         "https://example.com/1", h(2), "Tender includes 600 MWh of co-located storage."),
        ("Tata Power commissions 300 MW solar capacity in Bikaner for captive customers",
         "https://example.com/2", h(5), "Takes the company's renewable portfolio past 7 GW."),
        ("CERC issues draft amendments to the Indian Electricity Grid Code; comments invited",
         "https://example.com/3", h(8), "Changes cover scheduling, congestion management and ancillary services."),
        ("Power Grid Corporation shares rise 3% after board approves Rs 5,000 crore bond issue",
         "https://example.com/4", h(20), ""),
        ("Adani Green Energy operationalises 750 MW at Khavda renewable park",
         "https://example.com/5", h(26), "Khavda is set to be the world's largest single-site renewable plant."),
        ("NHPC signs MoU with Maharashtra government for 7,350 MW pumped storage projects",
         "https://example.com/6", h(30), ""),
        ("JSW Energy acquires 1.6 GW thermal asset; stake purchase valued at $1.1 billion",
         "https://example.com/7", h(40), "Deal adds to the company's *contracted* capacity."),
        ("Discoms in Uttar Pradesh face rising dues as summer peak demand eases",
         "https://example.com/8", h(50), ""),
        ("Torrent Power wins 1,500 MW pumped storage order from MSEDCL",
         "https://example.com/9", h(60), ""),
        ("Ministry of Power notifies Electricity (Amendment) Rules on late payment surcharge",
         "https://example.com/10", h(75), ""),
        ("CESC posts higher Q2 profit on Rajasthan distribution gains",
         "https://example.com/11", h(90), ""),
        ("Monsoon lifts hydro generation to a three-year high", "https://example.com/12", h(100), ""),
    ]


CEA_HTML = b"""<html><body><nav><ul><li><a href="/about">Profiles of Chairperson and Members</a></li></ul></nav>
<table><tr><th>Sl. No.</th><th>Title</th><th>Date</th><th>Download</th></tr>
<tr><td>1</td><td>Monthly Installed Capacity Report as on 30.06.2026</td><td>2026-07-15</td>
    <td><a href="https://cea.nic.in/wp-content/uploads/installed/2026/06/Website_June.pdf">file</a> <a href="#">#</a></td></tr>
<tr><td>2</td><td>Draft CEA (Technical Standards for Connectivity to the Grid) Regulations, 2026- Invitation of Public Comments</td>
    <td>2026-08-04</td><td><a href="/wp-content/uploads/notification/2026/08/Draft Grid.pdf">file</a></td></tr>
<tr><td>3</td><td>Notice for Filling up One (01) Vacancy of Despatch Rider on a Deputation Basis</td><td>2026-06-25</td>
    <td><a href="/x.pdf">file</a></td></tr>
<tr><td>4</td><td>Notice &amp; Agenda for 18th NPC Meeting to be held on 18.09.2026 at Rajgir</td><td>2026-09-10</td>
    <td><a href="javascript:void(0)">x</a></td></tr>
<tr><td>5</td><td>All India Electricity Statistics General Review 2025</td><td>2026-01-06</td><td></td></tr>
<tr><td>6</td><td>Report on Roadmap to 100 GW of Hydro Pumped Storage Projects</td><td>2019-01-28</td>
    <td><a href="/old.pdf">file</a></td></tr>
</table></body></html>"""

MNRE_HTML = b"""<table><tr><td>Updated (05.06.2025) List-I under ALMM order for Solar PV Modules (1.3 mb PDF)</td>
<td>Updated List-I under ALMM order</td><td>18/08/2026</td><td>18/09/2026</td><td><a href="/files/almm.pdf">View (1 MB)</a></td></tr>
<tr><td>Public Notice : Tender for allocation of seabed for Offshore Wind Energy Projects</td><td>desc</td>
<td>12/07/2026</td><td>12/09/2026</td><td><a href="/files/seabed.pdf">View</a></td></tr></table>"""

GRID_INDIA_HTML = b"""<main><article><h2><a href="/press/gi-peak.pdf">Grid-India meets all-time peak demand of 250 GW successfully</a></h2>
<span class="date">September 18, 2026</span></article>
<article><h2><a href="/press/lfo.pdf">Grid-India releases Load Generation Balance Report 2026-27</a></h2><time>2 April 2026</time></article></main>"""


def price_frame(tickers, days: int = 500, seed: int = 7, intraday: bool = False) -> pd.DataFrame:
    """A yfinance-shaped (ticker, field) multi-index frame of plausible prices."""
    rng = np.random.default_rng(seed)
    if intraday:
        start = pd.Timestamp.now(tz="Asia/Kolkata").normalize() + pd.Timedelta(hours=9, minutes=15)
        index = pd.date_range(start, periods=60, freq="5min")
    else:
        index = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=days)
    cols = {}
    for i, t in enumerate(tickers):
        base = 80 + 40 * i
        walk = np.cumprod(1 + rng.normal(0.0004, 0.016 if not intraday else 0.002, len(index)))
        cols[(t, "Close")] = base * walk
        cols[(t, "Open")] = base * walk
    return pd.DataFrame(cols, index=index)


def fake_download(tickers, period="1y", interval="1d", **kwargs):
    tickers = list(tickers) if not isinstance(tickers, str) else [tickers]
    if interval == "5m":
        return price_frame(tickers, intraday=True)
    days = {"5d": 5, "1y": 250, "2y": 500}.get(period, 500)
    return price_frame(tickers, days=500).tail(days)


ALL_TICKERS = [c.yahoo for c in COMPANIES]
NOW = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)
