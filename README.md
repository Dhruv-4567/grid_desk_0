# The Grid Desk

A newspaper-style site for the Indian power sector, built for an investor relations desk.

| Section | What it shows |
|---|---|
| **Front Page** | Lead story, Tata Power price box and its own news desk, then columns for Tenders & Orders, Government & PSU, Private Sector, Policy & Regulation, Markets & Deals and the latest official notices. Below that, **The Wire**: every story, filterable by section, by one or more companies, and by keyword. |
| **Markets** | Tata Power live price, change, 1M/3M/1Y returns and 52-week range, with a 5-minute chart for today. A peer table of 21 listed generation, transmission and distribution companies (plus an optional "sector ecosystem" group: PFC, REC, IREDA, IEX, BHEL, equipment makers), sortable by day move, returns or news flow. Relative-performance chart, rebased to 100, for up to 8 names. CSV download. |
| **Companies** | Pick any company: price box, one-year chart, a dedicated news search for that company (last 30 days) merged with the wire, filterable by section, and any official notices that name it. |
| **Official Gazette** | Notices read directly from CEA "What's New", MNRE current notices and Grid-India press releases, plus Ministry of Power and MNRE releases (PIB), CERC, SECI, Grid-India and CEA via Google News' index of those sites. Sorted into Tenders, Regulations & Orders, Reports, Schemes & Guidelines, Meetings. Admin clutter (vacancies, recruitment results) is hidden. |
| **Archive** | Search any period back to 2010 by company, topic and keywords. Long periods are split into 12 slices so older years still return stories. Results grouped by month, downloadable as CSV. |

Refresh rates: prices every minute, news every 10 minutes, official notices every 3 hours. The masthead shows whether NSE is open.

## Put it online (Streamlit Community Cloud, free)

**If you already have the old Grid Desk repo**, the cleanest route is to replace everything:

1. On GitHub, open your repo. Delete the old `app.py`, `requirements.txt` and the `powerdesk` and `tests` folders (open each file → `⋯` → Delete file → Commit).
2. Unzip `grid-desk.zip` on a laptop. Open the `grid-desk` folder.
3. On the repo page: **Add file → Upload files**. Select everything *inside* `grid-desk` and **drag** it into the box (drag, don't click "choose files", or folders get dropped). Commit.
4. Check the repo's front page shows `app.py`, `requirements.txt`, `runtime.txt`, and the folders `powerdesk`, `tests` and `.streamlit`. Open `powerdesk`: it must contain 10 files (`__init__.py`, `charts.py`, `config.py`, `net.py`, `news.py`, `official.py`, `prices.py`, `render.py`, `textutil.py`, `theme.py`).
   If `.streamlit` didn't upload (some browsers hide dot-folders): **Add file → Create new file**, name it `.streamlit/config.toml`, paste the contents of that file from the zip, commit. Without it the site still works, just with Streamlit's default colours behind the paper.
5. In Streamlit Cloud, open your app → **⋮ → Reboot app**. For a fresh deploy: **Create app → Deploy a public app from GitHub**, repository `your-username/your-repo` (no `.git` at the end), branch `main`, main file `app.py`, and under **Advanced settings** choose **Python 3.12**.

## Run it on your own computer

```bash
cd grid-desk
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest              # should end with "67 passed"
streamlit run app.py          # opens http://localhost:8501
```

## Changing what it tracks

Everything is in **`powerdesk/config.py`**:

- `COMPANIES`: add a line such as `Company("KPIL", "Kalpataru Projects", "Transmission", keywords=("kalpataru",))`. Use the NSE symbol; set `psu=True` for government-owned companies (this decides whether their news files under "Government & PSU" or "Private Sector").
- `NEWS_FEEDS`: any RSS feed, or a Google News search with `google_news("your search")`.
- `OFFICIAL_PAGES`: any government page that lists notices in a table, list or cards. `OFFICIAL_FEEDS`: follow any official site with `google_news("site:example.gov.in", days=45)`.
- `TOPIC_RULES`, `GOVT_WORDS`, `PROJECT_WORDS`: the words that decide each story's section.
- Timings and limits are at the bottom.

Run `python -m pytest` after any change.

## How it's built to stay up

- **Layers.** `config` (what to track) → `net`, `prices`, `news`, `official` (fetching and parsing; no display code) → `render`, `charts`, `theme` (pure display; no network) → `app.py` (layout only).
- **Nothing in the data layer raises.** Every fetch returns its data plus a list of what failed. One dead feed, a Yahoo rate limit or a government site with an expired certificate just appears under "Source status"; the rest of the page is unaffected.
- **Failures aren't cached.** If a source fails completely it is retried on the next refresh, not 30 minutes later.
- **Every section is fenced.** If a section ever hits an unexpected bug it shows a one-line note and the other sections keep working (this is tested).
- **Safe display.** Every headline is HTML-escaped and stripped of Markdown/LaTeX characters; only plain `http(s)` links are ever shown; downloads are capped at 5 MB with timeouts and two retries.
- **Pinned versions** in `requirements.txt`, so a library update can't change behaviour silently.
- **67 tests** cover parsing real-shaped CEA/MNRE/Grid-India pages, garbage and oversized responses, partial and total outages, bad prices (NaN, zero, negative), market-hours logic including holidays, the archive's date slicing, HTML-injection attempts, and the whole app loading with the network switched off.

## Known limits

- Prices come from Yahoo Finance's free feed and can trail the exchange by a few minutes. Tick-by-tick prices need a paid broker data API.
- Archive depth depends on Google News' index; years before ~2015 are thinner.
- MNRE and Grid-India pages were read using a generic reader built from how those pages are laid out; if either redesigns and yields nothing, the Gazette says so and the same notices still arrive through the Google News route.
