"""Share prices from Yahoo Finance (NSE).

Three fetches, cached separately by the app:
  * history  - 2 years of daily closes (52-week range, 1-year return, charts); refreshed every 30 min
  * live     - last 5 daily bars, refreshed every minute (today's bar moves during market hours)
  * intraday - 5-minute bars for one stock, for the "today" chart

Design rule: nothing in here raises. A stock with no usable data is simply absent from the
returned mapping, and build_quotes turns that into a Quote carrying an `error` message.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Iterable, Mapping

import pandas as pd

from .config import MARKET_CLOSE, MARKET_OPEN, Company
from .textutil import IST

log = logging.getLogger(__name__)
PRICE_FIELDS = ("Close", "Adj Close")
Downloader = Callable[..., Any]


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float | None = None
    prev_close: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    ret_1m: float | None = None
    ret_3m: float | None = None
    ret_1y: float | None = None
    as_of: date | None = None
    error: str | None = None

    @property
    def change(self) -> float | None:
        if self.last is None or self.prev_close is None:
            return None
        return self.last - self.prev_close

    @property
    def change_pct(self) -> float | None:
        change = self.change
        if change is None or not self.prev_close:
            return None
        return change / self.prev_close * 100

    @property
    def range_position(self) -> float | None:
        """Where today's price sits in the 52-week range: 0 = at the low, 1 = at the high."""
        if None in (self.last, self.high_52w, self.low_52w) or self.high_52w <= self.low_52w:
            return None
        return min(1.0, max(0.0, (self.last - self.low_52w) / (self.high_52w - self.low_52w)))


# ---------------------------------------------------------------- frame handling

def _first_series(col: Any) -> pd.Series | None:
    if isinstance(col, pd.DataFrame):
        return col.iloc[:, 0] if col.shape[1] else None
    return col if isinstance(col, pd.Series) else None


def extract_closes(frame: Any, ticker: str, allow_flat: bool) -> pd.Series | None:
    """One ticker's close series from whatever shape yfinance returned (or None)."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    cols = frame.columns
    if isinstance(cols, pd.MultiIndex):
        for level in range(cols.nlevels):
            if ticker in cols.get_level_values(level):
                sub = frame.xs(ticker, axis=1, level=level, drop_level=True)
                if not isinstance(sub, pd.DataFrame):
                    return None
                for field in PRICE_FIELDS:
                    if field in sub.columns:
                        return _first_series(sub[field])
        return None
    if allow_flat:                     # a flat frame is unambiguous only for a single ticker
        for field in PRICE_FIELDS:
            if field in cols:
                return _first_series(frame[field])
    return None


def _good(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def clean_closes(series: Any) -> pd.Series | None:
    """Numeric, positive, finite, de-duplicated, date-sorted closes; None if nothing usable."""
    if not isinstance(series, pd.Series) or series.empty:
        return None
    s = pd.to_numeric(series, errors="coerce").astype("float64")
    s = s[s.map(_good)]
    if s.empty:
        return None
    if isinstance(s.index, pd.DatetimeIndex):
        s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def fetch_closes(
    companies: Iterable[Company],
    period: str,
    interval: str = "1d",
    download: Downloader | None = None,
) -> tuple[dict[str, pd.Series], str | None]:
    """Close series per NSE symbol. Returns (series_by_symbol, batch_error_or_None). Never raises."""
    companies = list(companies)
    if not companies:
        return {}, None
    frame, batch_error = None, None
    try:
        if download is None:
            import yfinance as yf
            download = yf.download
        frame = download(
            [c.yahoo for c in companies], period=period, interval=interval, group_by="ticker",
            auto_adjust=False, progress=False, threads=True, timeout=15,
        )
    except Exception as exc:           # network, rate limit, package error: all non-fatal
        log.warning("Price download (%s/%s) failed: %r", period, interval, exc)
        batch_error = f"Price service unavailable ({type(exc).__name__})"

    out: dict[str, pd.Series] = {}
    for c in companies:
        try:
            s = clean_closes(extract_closes(frame, c.yahoo, allow_flat=len(companies) == 1))
        except Exception as exc:
            log.warning("Unreadable prices for %s: %r", c.symbol, exc)
            s = None
        if s is not None:
            out[c.symbol] = s
    return out, batch_error


# ---------------------------------------------------------------- quotes

def _period_return(series: pd.Series, last: float, days: int) -> float | None:
    if not isinstance(series.index, pd.DatetimeIndex) or series.empty:
        return None
    cutoff = series.index[-1] - pd.Timedelta(days=days)
    earlier = series[series.index <= cutoff]
    if earlier.empty:
        return None
    base = float(earlier.iloc[-1])
    return (last / base - 1) * 100 if base > 0 else None


def _bar_date(index_value: Any) -> date | None:
    try:
        ts = pd.Timestamp(index_value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        ts = ts.tz_convert(IST)
    return ts.date()


def build_quotes(
    companies: Iterable[Company],
    history: Mapping[str, pd.Series],
    live: Mapping[str, pd.Series],
    error: str | None = None,
) -> dict[str, Quote]:
    """Merge 1-year history with the latest bars into one Quote per company."""
    quotes: dict[str, Quote] = {}
    for c in companies:
        try:
            quotes[c.symbol] = _one_quote(c.symbol, history.get(c.symbol), live.get(c.symbol), error)
        except Exception as exc:
            log.warning("Quote for %s failed: %r", c.symbol, exc)
            quotes[c.symbol] = Quote(c.symbol, error=f"Unreadable data ({type(exc).__name__})")
    return quotes


def _one_quote(symbol: str, hist: pd.Series | None, live: pd.Series | None, error: str | None) -> Quote:
    recent = live if live is not None and not live.empty else hist
    if recent is None or recent.empty:
        return Quote(symbol, error=error or "No price data")

    last = float(recent.iloc[-1])
    prev = float(recent.iloc[-2]) if len(recent) > 1 else None
    as_of = _bar_date(recent.index[-1]) if isinstance(recent.index, pd.DatetimeIndex) else None

    hi = lo = r1m = r3m = r1y = None
    if hist is not None and not hist.empty:
        year = hist
        if isinstance(hist.index, pd.DatetimeIndex):
            year = hist[hist.index >= hist.index[-1] - pd.Timedelta(days=365)]
        hi, lo = max(float(year.max()), last), min(float(year.min()), last)
        r1m, r3m, r1y = (_period_return(hist, last, d) for d in (30, 91, 365))
    return Quote(symbol, last, prev, hi, lo, r1m, r3m, r1y, as_of)


def rebased(history: Mapping[str, pd.Series], symbols: Iterable[str], days: int) -> pd.DataFrame:
    """Long table (date, symbol, value) with each series rebased to 100 at the start of the window."""
    rows = []
    for sym in symbols:
        s = history.get(sym)
        if s is None or s.empty or not isinstance(s.index, pd.DatetimeIndex):
            continue
        window = s[s.index >= s.index[-1] - pd.Timedelta(days=days)]
        if len(window) < 2 or window.iloc[0] <= 0:
            continue
        values = window / window.iloc[0] * 100
        rows.append(pd.DataFrame({"date": window.index, "symbol": sym, "value": values.to_numpy()}))
    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "value"])
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------- market clock

def market_status(now: datetime, last_bar: date | None) -> str:
    """'open' only on a weekday, inside NSE hours, when today's bar actually exists (so holidays read closed)."""
    local = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    minutes = local.hour * 60 + local.minute
    in_hours = MARKET_OPEN[0] * 60 + MARKET_OPEN[1] <= minutes < MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1]
    if local.weekday() < 5 and in_hours and last_bar == local.date():
        return "open"
    if local.weekday() < 5 and minutes < MARKET_OPEN[0] * 60 + MARKET_OPEN[1]:
        return "pre-open"
    return "closed"
