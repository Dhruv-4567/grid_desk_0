"""The newspaper look: fonts, paper, rules and column styles. Pure CSS, injected once by app.py."""

PAPER = "#F4EFE4"
PAPER_DEEP = "#ECE5D6"
INK = "#1A1917"
MUTED = "#5F5A50"
HAIRLINE = "#CDC3AF"
ACCENT = "#9E1B1B"
UP = "#1E6B3C"
DOWN = "#A3221F"

FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=UnifrakturMaguntia&"
    "family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&"
    "family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&"
    "family=Libre+Franklin:wght@500;600;700&display=swap"
)

CSS = f"""
<style>
@import url('{FONTS_URL}');
:root {{
  --paper:{PAPER}; --paper-deep:{PAPER_DEEP}; --ink:{INK}; --muted:{MUTED};
  --hair:{HAIRLINE}; --accent:{ACCENT}; --up:{UP}; --down:{DOWN};
  --serif:'Source Serif 4', Georgia, 'Times New Roman', serif;
  --display:'Playfair Display', Georgia, serif;
  --sans:'Libre Franklin', 'Helvetica Neue', Arial, sans-serif;
}}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--paper); color: var(--ink); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width: 1280px; padding-top: 1.2rem; padding-bottom: 4rem; }}
.stApp, .stApp p, .stApp li, .stApp label {{ font-family: var(--serif); }}

/* section navigation = the paper's section bar */
[data-testid="stTabs"] [role="tablist"], [data-baseweb="tab-list"] {{ gap: 0; border-top: 1px solid var(--ink); border-bottom: 3px double var(--ink); justify-content: center; flex-wrap: wrap; margin-top: .4rem; }}
[data-testid="stTab"], [data-baseweb="tab-list"] button {{ padding: .55rem 1.2rem !important; }}
[data-testid="stTab"] p, [data-baseweb="tab-list"] button p {{ font-family: var(--sans) !important; text-transform: uppercase; letter-spacing: .14em; font-size: .76rem !important; font-weight: 600; color: var(--ink); }}
[data-testid="stTab"][aria-selected="true"] p {{ color: var(--accent); }}
.react-aria-SelectionIndicator, [data-baseweb="tab-highlight"] {{ background-color: var(--accent) !important; }}
[data-baseweb="tab-border"] {{ display: none; }}

/* nameplate */
.gd-mast {{ text-align: center; border-bottom: 1px solid var(--ink); padding-bottom: .4rem; }}
.gd-ears {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; font-family: var(--sans); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
.gd-ear {{ border: 1px solid var(--ink); padding: .35rem .55rem; text-align: left; min-width: 150px; line-height: 1.35; color: var(--ink); }}
.gd-ear.right {{ text-align: right; }}
.gd-ear b {{ font-size: .95rem; letter-spacing: 0; text-transform: none; font-variant-numeric: tabular-nums; }}
.gd-name {{ font-family: 'UnifrakturMaguntia', var(--display); font-size: clamp(2.6rem, 7vw, 5.2rem); line-height: 1; margin: .2rem 0 .1rem; color: var(--ink); font-weight: 400; }}
.gd-motto {{ font-family: var(--serif); font-style: italic; color: var(--muted); font-size: .95rem; }}
.gd-dateline {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: .3rem 1rem; border-top: 3px double var(--ink); border-bottom: 1px solid var(--ink); margin-top: .5rem; padding: .3rem .1rem; font-family: var(--sans); font-size: .74rem; text-transform: uppercase; letter-spacing: .1em; }}
.gd-live {{ color: var(--up); font-weight: 700; }}
.gd-closed {{ color: var(--muted); font-weight: 700; }}

/* ticker */
.gd-ticker {{ overflow: hidden; white-space: nowrap; border-bottom: 1px solid var(--ink); padding: .35rem 0; font-family: var(--sans); font-size: .8rem; font-variant-numeric: tabular-nums; }}
.gd-ticker-track {{ display: inline-block; padding-left: 100%; animation: gd-scroll 90s linear infinite; }}
.gd-ticker:hover .gd-ticker-track {{ animation-play-state: paused; }}
.gd-tick {{ margin-right: 2rem; }}
.gd-tick b {{ margin-right: .35rem; letter-spacing: .03em; }}
@keyframes gd-scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100%); }} }}
@media (prefers-reduced-motion: reduce) {{ .gd-ticker {{ overflow-x: auto; }} .gd-ticker-track {{ animation: none; padding-left: 0; }} }}
.up {{ color: var(--up); }} .down {{ color: var(--down); }} .flat {{ color: var(--muted); }}

/* section heads */
.gd-section {{ border-top: 3px solid var(--ink); margin: 1.2rem 0 .5rem; padding-top: .25rem; display: flex; justify-content: space-between; align-items: baseline; }}
.gd-section .gd-h2 {{ font-family: var(--sans); font-size: .82rem; text-transform: uppercase; letter-spacing: .14em; margin: 0; padding: 0; font-weight: 700; color: var(--ink); }}
.gd-section span {{ font-family: var(--sans); font-size: .72rem; color: var(--muted); letter-spacing: .04em; }}

/* stories */
.gd-story {{ padding: .55rem 0 .65rem; border-bottom: 1px solid var(--hair); }}
.gd-story:last-child {{ border-bottom: 0; }}
.gd-kicker {{ font-family: var(--sans); font-size: .66rem; text-transform: uppercase; letter-spacing: .12em; color: var(--accent); font-weight: 700; }}
.gd-story .gd-h3 {{ font-family: var(--display); font-weight: 700; font-size: 1.08rem; line-height: 1.22; margin: .15rem 0 .2rem; padding: 0; color: var(--ink); }}
.gd-story .gd-h3 a, .gd-lead .gd-h1 a, .gd-gazette a {{ color: var(--ink); text-decoration: none; }}
.gd-story .gd-h3 a:hover, .gd-lead .gd-h1 a:hover, .gd-gazette a:hover {{ text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
.gd-dek {{ font-family: var(--serif); font-size: .93rem; line-height: 1.45; color: #2E2B26; margin: .1rem 0 .25rem; }}
.gd-byline {{ font-family: var(--sans); font-size: .7rem; color: var(--muted); letter-spacing: .02em; }}
.gd-tag {{ display: inline-block; border: 1px solid var(--hair); padding: 0 .3rem; margin-left: .3rem; font-size: .64rem; letter-spacing: .05em; color: var(--ink); }}
.gd-lead {{ padding: .3rem 0 .8rem; }}
.gd-lead .gd-h1 {{ font-family: var(--display); font-weight: 800; font-size: clamp(1.7rem, 3.4vw, 2.6rem); line-height: 1.1; margin: .25rem 0 .5rem; padding: 0; color: var(--ink); }}
.gd-lead .gd-dek {{ font-size: 1.08rem; }}
.gd-day {{ font-family: var(--sans); font-size: .7rem; text-transform: uppercase; letter-spacing: .14em; color: var(--muted); border-bottom: 1px solid var(--ink); margin: 1rem 0 .1rem; padding-bottom: .15rem; }}
.gd-empty {{ font-family: var(--serif); font-style: italic; color: var(--muted); padding: .6rem 0; }}
.gd-note {{ font-family: var(--sans); font-size: .72rem; color: var(--muted); margin-top: .4rem; }}

/* quote box */
.gd-quote {{ border: 1px solid var(--ink); padding: .7rem .8rem .8rem; background: var(--paper); }}
.gd-quote .gd-qname {{ font-family: var(--display); font-weight: 700; font-size: 1.25rem; }}
.gd-quote .gd-qsym {{ font-family: var(--sans); font-size: .7rem; letter-spacing: .1em; color: var(--muted); }}
.gd-qprice {{ font-family: var(--display); font-size: 2.3rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; margin-top: .3rem; }}
.gd-qchg {{ font-family: var(--sans); font-weight: 600; font-size: .95rem; font-variant-numeric: tabular-nums; }}
.gd-qgrid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .4rem; margin-top: .7rem; border-top: 1px solid var(--hair); padding-top: .5rem; }}
.gd-qgrid div {{ font-family: var(--sans); font-size: .68rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }}
.gd-qgrid b {{ display: block; font-size: .95rem; color: var(--ink); text-transform: none; letter-spacing: 0; font-variant-numeric: tabular-nums; }}
.gd-range {{ margin-top: .7rem; font-family: var(--sans); font-size: .68rem; color: var(--muted); }}
.gd-range-bar {{ position: relative; height: 4px; background: var(--hair); margin: .35rem 0 .25rem; }}
.gd-range-dot {{ position: absolute; top: -4px; width: 2px; height: 12px; background: var(--ink); }}
.gd-range-ends {{ display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }}

/* market table */
.gd-table {{ width: 100%; border-collapse: collapse; font-family: var(--sans); font-size: .82rem; font-variant-numeric: tabular-nums; }}
.gd-table th {{ text-align: right; font-size: .66rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); border-bottom: 1px solid var(--ink); padding: .35rem .4rem; font-weight: 600; }}
.gd-table th:first-child, .gd-table td:first-child {{ text-align: left; }}
.gd-table td {{ text-align: right; padding: .38rem .4rem; border-bottom: 1px solid var(--hair); white-space: nowrap; }}
.gd-table tr.gd-seg td {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; border-bottom: 1px solid var(--ink); padding-top: .9rem; color: var(--ink); background: transparent; }}
.gd-table tr.gd-home td {{ background: var(--paper-deep); font-weight: 600; }}
.gd-table .gd-co {{ font-family: var(--serif); font-size: .92rem; }}
.gd-table .gd-co small {{ font-family: var(--sans); color: var(--muted); font-size: .66rem; margin-left: .35rem; letter-spacing: .05em; }}
.gd-minirange {{ display: inline-block; position: relative; width: 70px; height: 3px; background: var(--hair); vertical-align: middle; }}
.gd-minirange i {{ position: absolute; top: -3px; width: 2px; height: 9px; background: var(--ink); }}
.gd-table-wrap {{ overflow-x: auto; }}
.stApp .gd-table, .stApp .gd-table tr, .stApp .gd-table th, .stApp .gd-table td {{ border-left: 0 !important; border-right: 0 !important; border-top: 0 !important; background: transparent; }}
.stApp .gd-table {{ border: 0 !important; margin: 0; }}
.stApp .gd-table tr.gd-home td {{ background: var(--paper-deep); }}

/* gazette */
.gd-gazette {{ padding: .5rem 0; border-bottom: 1px solid var(--hair); }}
.gd-gazette .gd-gtitle {{ font-family: var(--serif); font-size: 1rem; line-height: 1.35; font-weight: 600; }}
.gd-new {{ font-family: var(--sans); font-size: .6rem; font-weight: 700; letter-spacing: .12em; color: var(--paper); background: var(--accent); padding: .05rem .3rem; margin-right: .4rem; vertical-align: 2px; }}

/* widgets, quieter */
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] div {{ flex-wrap: wrap; max-width: 100%; }}
.stApp [data-testid="stWidgetLabel"] p {{ font-family: var(--sans); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
.stApp .stButton button, .stApp .stDownloadButton button, .stApp .stFormSubmitButton button {{ border-radius: 0; border: 1px solid var(--ink); font-family: var(--sans); text-transform: uppercase; letter-spacing: .08em; font-size: .74rem; }}
.stApp [data-testid="stExpander"] details {{ border-radius: 0; border-color: var(--hair); }}
.gd-footer {{ border-top: 3px double var(--ink); margin-top: 2rem; padding-top: .5rem; font-family: var(--sans); font-size: .7rem; color: var(--muted); text-align: center; letter-spacing: .04em; }}
@media (max-width: 640px) {{ .gd-ear {{ display: none; }} .gd-qprice {{ font-size: 1.9rem; }} }}
</style>
"""
