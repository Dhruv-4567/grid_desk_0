"""Charts in the paper's house style (Altair). Each builder returns a chart, or None when there is
nothing sensible to draw, so the app can show a note instead of an empty frame."""
from __future__ import annotations

import altair as alt
import pandas as pd

from .theme import ACCENT, HAIRLINE, INK, MUTED

FONT = "Libre Franklin, Helvetica Neue, Arial, sans-serif"
# Tata Power in the paper's red; peers in distinct, muted inks.
PEER_COLORS = ("#2F4B7C", "#7A6A3A", "#3E7C6B", "#6B4C7A", "#8A5A44", "#4F6D8F", "#5C7A3A", "#7D4E57")


def _style(chart: alt.Chart, height: int) -> alt.Chart:
    return (chart.properties(height=height, background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=MUTED, titleColor=MUTED,
                            gridColor=HAIRLINE, gridOpacity=0.6, domainColor=INK, tickColor=INK, labelFontSize=11)
            .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=INK, orient="top", title=None, labelFontSize=11))


def price_line(series: pd.Series | None, title: str, prev_close: float | None = None, intraday: bool = False):
    """Single-stock line: intraday (with yesterday's close as a dotted rule) or daily history."""
    if series is None or len(series) < 2 or not isinstance(series.index, pd.DatetimeIndex):
        return None
    idx = series.index
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    df = pd.DataFrame({"time": idx, "price": series.to_numpy()})
    lo, hi = float(df["price"].min()), float(df["price"].max())
    if prev_close:
        lo, hi = min(lo, prev_close), max(hi, prev_close)
    pad = (hi - lo) * 0.08 or hi * 0.01
    x = alt.X("time:T", title=None, axis=alt.Axis(format="%H:%M" if intraday else "%b %y", labelAngle=0, tickCount=6))
    y = alt.Y("price:Q", title=None, scale=alt.Scale(domain=[lo - pad, hi + pad], nice=False),
              axis=alt.Axis(format=",.0f", orient="right"))
    line = alt.Chart(df).mark_line(color=ACCENT if intraday else INK, strokeWidth=1.8).encode(
        x=x, y=y, tooltip=[alt.Tooltip("time:T", title="Time" if intraday else "Date",
                                       format="%d %b %H:%M" if intraday else "%d %b %Y"),
                           alt.Tooltip("price:Q", title="₹", format=",.2f")])
    layers = [line]
    if prev_close:
        layers.append(alt.Chart(pd.DataFrame({"y": [prev_close]})).mark_rule(
            color=MUTED, strokeDash=[3, 3]).encode(y="y:Q"))
    return _style(alt.layer(*layers).properties(title=alt.TitleParams(
        title, font=FONT, fontSize=11, color=MUTED, anchor="start", fontWeight=600)), 240)


def relative_performance(df: pd.DataFrame, home_symbol: str):
    """Rebased-to-100 lines. The home company is drawn thicker in the accent colour."""
    if df is None or df.empty or df["symbol"].nunique() < 1:
        return None
    symbols = list(dict.fromkeys(df["symbol"]))
    others = [s for s in symbols if s != home_symbol]
    domain = ([home_symbol] if home_symbol in symbols else []) + others
    colors = ([ACCENT] if home_symbol in symbols else []) + [PEER_COLORS[i % len(PEER_COLORS)] for i in range(len(others))]
    base = alt.Chart(df).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%d %b %y", labelAngle=0, tickCount=6)),
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(orient="right")),
        color=alt.Color("symbol:N", scale=alt.Scale(domain=domain, range=colors)),
        strokeWidth=alt.condition(alt.datum.symbol == home_symbol, alt.value(2.6), alt.value(1.3)),
        tooltip=[alt.Tooltip("symbol:N", title="Stock"), alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                 alt.Tooltip("value:Q", title="Index (start = 100)", format=".1f")],
    )
    rule = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color=MUTED, strokeDash=[2, 3]).encode(y="y:Q")
    return _style(alt.layer(rule, base.mark_line()), 320)
