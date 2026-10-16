"""Everything you might want to change lives in this one file.

Companies, news feeds, official sources, categories and timings. No other file needs editing.
After any change, run `python -m pytest` before deploying.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


# ---------------------------------------------------------------- companies

@dataclass(frozen=True)
class Company:
    symbol: str                       # NSE symbol, e.g. "TATAPOWER"
    name: str
    segment: str                      # one of SEGMENTS below
    psu: bool = False                 # government-owned (decides "Government" vs "Private" for its news)
    keywords: tuple[str, ...] = ()    # extra phrases that identify the company in headlines

    @property
    def yahoo(self) -> str:
        return f"{self.symbol}.NS"

    @property
    def match_terms(self) -> tuple[str, ...]:
        terms = (self.name, *self.keywords)
        if len(self.symbol) >= 4:     # short symbols like "IEX" are matched only via keywords
            terms = (self.symbol, *terms)
        return tuple(dict.fromkeys(t.lower() for t in terms if t))

    @property
    def search_query(self) -> str:
        return f'"{self.name}"'


HOME_SYMBOL = "TATAPOWER"

# Order here is the order shown on the Markets page.
SEGMENTS: tuple[str, ...] = (
    "Integrated utilities",
    "Thermal & conventional generation",
    "Hydro & renewable generation",
    "Transmission",
    "Sector ecosystem",
)
CORE_SEGMENTS = SEGMENTS[:4]          # generation, transmission, distribution peers
ECOSYSTEM_SEGMENT = SEGMENTS[4]       # financiers, exchange, equipment: shown only when switched on

COMPANIES: tuple[Company, ...] = (
    # Integrated: generation + transmission + distribution
    Company("TATAPOWER", "Tata Power", "Integrated utilities", keywords=("tata power", "tata power renewable", "mundra", "tprel")),
    Company("TORNTPOWER", "Torrent Power", "Integrated utilities"),
    Company("CESC", "CESC", "Integrated utilities", keywords=("rp-sanjiv goenka",)),
    Company("ADANIENSOL", "Adani Energy Solutions", "Transmission", keywords=("adani transmission", "aesl")),
    # Thermal and conventional generation
    Company("NTPC", "NTPC", "Thermal & conventional generation", psu=True),
    Company("ADANIPOWER", "Adani Power", "Thermal & conventional generation"),
    Company("JSWENERGY", "JSW Energy", "Thermal & conventional generation", keywords=("jsw neo",)),
    Company("NLCINDIA", "NLC India", "Thermal & conventional generation", psu=True, keywords=("neyveli",)),
    Company("RPOWER", "Reliance Power", "Thermal & conventional generation"),
    Company("JPPOWER", "Jaiprakash Power Ventures", "Thermal & conventional generation", keywords=("jp power",)),
    Company("RTNPOWER", "RattanIndia Power", "Thermal & conventional generation"),
    Company("GIPCL", "Gujarat Industries Power", "Thermal & conventional generation", psu=True),
    # Hydro and renewable generation
    Company("NHPC", "NHPC", "Hydro & renewable generation", psu=True),
    Company("SJVN", "SJVN", "Hydro & renewable generation", psu=True, keywords=("sjvn green",)),
    Company("NTPCGREEN", "NTPC Green Energy", "Hydro & renewable generation", psu=True, keywords=("ntpc green", "ntpc rel", "ngel")),
    Company("ADANIGREEN", "Adani Green Energy", "Hydro & renewable generation", keywords=("adani green", "agel")),
    Company("ACMESOLAR", "ACME Solar", "Hydro & renewable generation", keywords=("acme solar",)),
    Company("KPIGREEN", "KPI Green Energy", "Hydro & renewable generation", keywords=("kpi green",)),
    # Transmission
    Company("POWERGRID", "Power Grid Corporation", "Transmission", psu=True, keywords=("power grid", "powergrid", "pgcil")),
    Company("INDIGRID", "IndiGrid", "Transmission", keywords=("india grid trust",)),
    Company("PGINVIT", "PowerGrid InvIT", "Transmission", psu=True, keywords=("pginvit",)),
    # Ecosystem (off by default on the Markets page)
    Company("PFC", "Power Finance Corporation", ECOSYSTEM_SEGMENT, psu=True, keywords=("pfc",)),
    Company("RECLTD", "REC", ECOSYSTEM_SEGMENT, psu=True, keywords=("rec limited", "rec ltd", "recpdcl")),
    Company("IREDA", "IREDA", ECOSYSTEM_SEGMENT, psu=True),
    Company("IEX", "Indian Energy Exchange", ECOSYSTEM_SEGMENT, keywords=("iex",)),
    Company("BHEL", "BHEL", ECOSYSTEM_SEGMENT, psu=True),
    Company("POWERINDIA", "Hitachi Energy India", ECOSYSTEM_SEGMENT, keywords=("hitachi energy",)),
    Company("SUZLON", "Suzlon Energy", ECOSYSTEM_SEGMENT, keywords=("suzlon",)),
    Company("WAAREEENER", "Waaree Energies", ECOSYSTEM_SEGMENT, keywords=("waaree",)),
    Company("PREMIERENE", "Premier Energies", ECOSYSTEM_SEGMENT),
)


# ---------------------------------------------------------------- news

@dataclass(frozen=True)
class Feed:
    name: str
    url: str


def google_news(query: str, days: int | None = 7) -> str:
    """Google News RSS search URL. `days=None` means no recency limit (use after:/before: in the query)."""
    q = f"{query} when:{days}d" if days else query
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=en-IN&gl=IN&ceid=IN:en"


NEWS_FEEDS: tuple[Feed, ...] = (
    Feed("Sector", google_news("India power sector")),
    Feed("Tenders", google_news("power tender OR auction OR SECI OR NHPC OR NTPC MW India")),
    Feed("Transmission", google_news("transmission project India TBCB OR POWERGRID OR substation")),
    Feed("Storage", google_news("battery energy storage India MWh")),
    Feed("Renewables", google_news("solar OR wind OR hybrid project India MW")),
    Feed("Thermal & hydro", google_news("thermal power plant OR hydro project OR pumped storage India MW")),
    Feed("Distribution", google_news("discom India electricity distribution")),
    Feed("Regulators", google_news("CERC OR SERC OR APTEL electricity order tariff")),
    Feed("Power stocks", google_news("power stocks NSE")),
    Feed("Tata Power", google_news('"Tata Power"')),
    Feed("Mercom India", "https://www.mercomindia.com/feed"),
    Feed("Power Peak Digest", "https://powerpeakdigest.com/feed/"),
)

# Checked top to bottom; first hit wins. "govt"/"private" are decided after these,
# using company ownership (Company.psu) and the GOVT_WORDS / PROJECT_WORDS lists.
TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tender", (
        "tender", "tenders", "bid", "bids", "bidder", "bidders", "auction", "auctions", "rfs", "rfp",
        "l1", "order", "orders", "contract", "awarded", "award", "wins", "bags", "secures", "loa", "epc",
    )),
    ("policy", (
        "cerc", "merc", "serc", "aptel", "regulator", "regulatory", "commission order", "ministry",
        "mnre", "cea", "policy", "draft", "rules", "guidelines", "scheme", "yojana", "tariff order",
        "amendment", "notification", "budget", "electricity act",
    )),
    ("markets", (
        "shares", "share price", "stock", "stocks", "ipo", "bond", "bonds", "ncd", "qip", "stake",
        "invests", "investment", "acquires", "acquisition", "results", "q1", "q2", "q3", "q4",
        "profit", "revenue", "ebitda", "dividend", "target price", "brokerage", "rating", "upgrade", "downgrade",
    )),
)
GOVT_WORDS: tuple[str, ...] = (
    "government", "govt", "state-run", "state-owned", "psu", "cabinet", "centre", "union minister",
    "power minister", "chief minister", "discom", "discoms", "state utility", "dvc", "grid-india", "grid india",
)
PROJECT_WORDS: tuple[str, ...] = (
    "commissions", "commissioned", "commissioning", "inaugurates", "plant", "project", "projects",
    "capacity", "mw", "gw", "mwh", "gwh", "manufacturing", "facility", "ppa", "signs", "partners",
)

CATEGORIES: tuple[tuple[str, str], ...] = (
    ("tender", "Tenders & Orders"),
    ("govt", "Government & PSU"),
    ("private", "Private Sector"),
    ("policy", "Policy & Regulation"),
    ("markets", "Markets & Deals"),
    ("other", "Sector Wire"),
)

# Archive tab: optional topic filters turned into search terms
ARCHIVE_TOPICS: tuple[tuple[str, str], ...] = (
    ("Any topic", ""),
    ("Tenders & auctions", "tender OR auction OR bid"),
    ("New projects", "project MW OR commissioned OR commissions"),
    ("Policy & regulation", "CERC OR ministry OR policy OR regulation"),
    ("Deals & results", "acquisition OR stake OR results OR profit"),
    ("Transmission", "transmission OR substation OR HVDC"),
    ("Storage", "battery storage OR BESS OR pumped storage"),
)
ARCHIVE_EARLIEST_YEAR = 2010
ARCHIVE_MAX_WINDOWS = 12              # a long range is split into this many slices (each returns up to ~100 stories)


# ---------------------------------------------------------------- official sources

@dataclass(frozen=True)
class OfficialPage:
    body: str                         # short label shown on the site
    url: str                          # a page that lists notices in a table or dated list


OFFICIAL_PAGES: tuple[OfficialPage, ...] = (
    OfficialPage("CEA", "https://cea.nic.in/whats-new/?lang=en"),
    OfficialPage("MNRE", "https://mnre.gov.in/en/past-notices/current-notices/"),
    OfficialPage("Grid-India", "https://grid-india.in/press-release/"),
)

# Official sites without a readable notice page are followed through Google News' index of that site.
OFFICIAL_FEEDS: tuple[Feed, ...] = (
    Feed("Ministry of Power", google_news('site:pib.gov.in "Ministry of Power"', days=45)),
    Feed("MNRE (PIB)", google_news('site:pib.gov.in "New and Renewable Energy"', days=45)),
    Feed("CERC", google_news("site:cercind.gov.in", days=45)),
    Feed("SECI", google_news("site:seci.co.in", days=45)),
    Feed("Grid-India", google_news("site:grid-india.in", days=45)),
    Feed("CEA", google_news("site:cea.nic.in", days=45)),
)

OFFICIAL_KINDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("tender", "Tenders & Bids", ("tender", "bid", "bids", "rfp", "rfs", "eoi", "expression of interest", "auction", "gem")),
    ("regulation", "Regulations & Orders", (
        "regulation", "regulations", "draft", "amendment", "public comments", "comments", "rules",
        "notification", "gazette", "clarification", "order", "orders", "petition",
    )),
    ("report", "Reports & Data", ("report", "capacity", "statistics", "review", "plan", "roadmap", "study", "data", "status", "outlook")),
    ("scheme", "Schemes & Guidelines", (
        "scheme", "yojana", "guidelines", "guideline", "advisory", "procedure", "framework", "almm",
        "policy", "mission", "specification", "specifications",
    )),
    ("meeting", "Meetings & Minutes", ("minutes", "agenda", "meeting", "workshop", "webinar", "conference")),
)
OFFICIAL_OTHER = ("other", "Announcements")

# Admin notices with these words are hidden.
OFFICIAL_NOISE: tuple[str, ...] = (
    "vacancy", "vacancies", "recruitment", "canteen", "deputation", "apprentice", "apprentices",
    "notice of result", "shortlisted", "flag code", "compassionate", "young professional",
    "rajbhasha", "hindi pakhwada", "blood donation", "yoga", "interview", "despatch rider",
    "stenographer", "post of", "consultant in cea", "multi-tasking staff",
)


# ---------------------------------------------------------------- timings and limits

LIVE_TTL_SECONDS = 60                 # live prices: how often to re-check
HISTORY_TTL_SECONDS = 1800            # 1-year history (52-week range, charts)
NEWS_TTL_SECONDS = 600                # live news
COMPANY_NEWS_TTL_SECONDS = 1800
OFFICIAL_TTL_SECONDS = 3 * 3600
ARCHIVE_TTL_SECONDS = 12 * 3600

NEWS_MAX_AGE_DAYS = 14
NEWS_MAX_ITEMS = 400
OFFICIAL_MAX_AGE_DAYS = 180
OFFICIAL_MAX_ITEMS = 400
ARCHIVE_MAX_ITEMS = 1000

HTTP_TIMEOUT = (5, 15)                # (connect, read) seconds
HTTP_WORKERS = 8
MAX_DOWNLOAD_BYTES = 5_000_000
USER_AGENT = "Mozilla/5.0 (compatible; GridDesk/2.0; personal research dashboard)"

MARKET_OPEN = (9, 15)                 # NSE cash market, IST
MARKET_CLOSE = (15, 30)
