"""Global filters for the web app, and current-vs-previous period comparison.

Pure pandas (no Streamlit), so every rule is unit-tested.

Filter rules:
- An empty selection means "all" (no filter on that column).
- Year and date range are both applied (rows must match both).
- State choices depend on the chosen regions; sub-category choices depend
  on the chosen categories (cascading filters).
- The previous period has the same length as the selected window and ends
  the day before it starts (e.g. 2017 is compared with 2016).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from salesinsight.kpis import compute_kpis

FILTER_COLUMNS = {
    "regions": "region",
    "states": "state",
    "categories": "category",
    "subcategories": "sub_category",
    "segments": "segment",
}


@dataclass(frozen=True)
class FilterState:
    years: tuple[int, ...] = ()
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    regions: tuple[str, ...] = ()
    states: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    subcategories: tuple[str, ...] = ()
    segments: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict, compare=False)

    def is_default(self) -> bool:
        return not (self.years or self.start or self.end or any(
            getattr(self, name) for name in FILTER_COLUMNS))


# ---------------------------------------------------------------------------
# Options for the filter widgets
# ---------------------------------------------------------------------------
def _sorted_unique(series: pd.Series) -> list:
    return sorted(series.dropna().unique().tolist())


def filter_options(df: pd.DataFrame, state: FilterState | None = None) -> dict[str, list]:
    """Choices for every filter. States follow regions; sub-categories follow categories."""
    state = state or FilterState()
    state_pool = df[df["region"].isin(state.regions)] if state.regions else df
    sub_pool = df[df["category"].isin(state.categories)] if state.categories else df
    return {
        "years": _sorted_unique(df["order_year"]),
        "regions": _sorted_unique(df["region"]),
        "states": _sorted_unique(state_pool["state"]),
        "categories": _sorted_unique(df["category"]),
        "subcategories": _sorted_unique(sub_pool["sub_category"]),
        "segments": _sorted_unique(df["segment"]),
        "min_date": df["order_date"].min(),
        "max_date": df["order_date"].max(),
    }


def prune_selection(selected, options) -> tuple:
    """Drop chosen values that are no longer available (e.g. a state after its region was removed)."""
    allowed = set(options)
    return tuple(v for v in selected if v in allowed)


# ---------------------------------------------------------------------------
# Applying filters
# ---------------------------------------------------------------------------
def _apply_dimensions(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for attr, column in FILTER_COLUMNS.items():
        chosen = getattr(state, attr)
        if chosen:
            mask &= df[column].isin(chosen)
    return df[mask]


def date_window(df: pd.DataFrame, state: FilterState) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The first and last day covered by the year + date-range filters.

    A year filter means whole calendar years (2017 = 1 Jan - 31 Dec 2017), so
    "2017 vs previous period" compares with all of 2016, even if the data
    ends a few days before 31 Dec. Without filters, the window is the data's
    own first and last date.
    """
    if state.years:
        start = pd.Timestamp(year=min(state.years), month=1, day=1)
        end = pd.Timestamp(year=max(state.years), month=12, day=31)
    else:
        start = df["order_date"].min().normalize()
        end = df["order_date"].max().normalize()
    if state.start is not None:
        start = max(start, pd.Timestamp(state.start).normalize())
    if state.end is not None:
        end = min(end, pd.Timestamp(state.end).normalize())
    return start, end


def apply_filters(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    """Rows matching every active filter."""
    out = _apply_dimensions(df, state)
    if state.years:
        out = out[out["order_year"].isin(state.years)]
    start, end = date_window(df, state)
    dates = out["order_date"].dt.normalize()
    return out[(dates >= start) & (dates <= end)]


def years_are_continuous(years: tuple[int, ...]) -> bool:
    return not years or sorted(years) == list(range(min(years), max(years) + 1))


def previous_period(df: pd.DataFrame, state: FilterState) -> tuple[pd.DataFrame, tuple | None]:
    """Rows of the period just before the selected window (same length, same other filters).

    Returns (rows, (start, end)) or (empty frame, None) when there is no
    earlier data or the chosen years have gaps (e.g. 2014 and 2017).
    """
    if not years_are_continuous(state.years):
        return df.iloc[0:0], None
    start, end = date_window(df, state)
    prev_end = start - pd.Timedelta(days=1)
    if state.years and state.start is None and state.end is None:
        # Whole years: compare with the same number of whole calendar years before
        # (handles leap years: 2017 -> 1 Jan-31 Dec 2016).
        prev_start = start - pd.DateOffset(years=len(state.years))
    else:
        prev_start = prev_end - (end - start)
    if prev_end < df["order_date"].min().normalize():
        return df.iloc[0:0], None
    dims = _apply_dimensions(df, state)
    dates = dims["order_date"].dt.normalize()
    prev = dims[(dates >= prev_start) & (dates <= prev_end)]
    return prev, (prev_start, prev_end)


# ---------------------------------------------------------------------------
# KPI comparison for the cards
# ---------------------------------------------------------------------------
KPI_CARDS = [
    # key, label, kind ("money", "int", "pct"); pct KPIs change in percentage points
    ("total_revenue", "Total revenue", "money"),
    ("total_profit", "Total profit", "money"),
    ("profit_margin_pct", "Profit margin", "pct"),
    ("total_orders", "Orders", "int"),
    ("avg_order_value", "Average order value", "money"),
    ("total_customers", "Customers", "int"),
]


def pct_change(current: float, previous: float) -> float | None:
    """% change; None when the previous value is zero or negative (no meaningful %)."""
    if previous is None or not np.isfinite(previous) or previous <= 0:
        return None
    return 100 * (current - previous) / previous


def kpi_comparison(current: pd.DataFrame, previous: pd.DataFrame) -> list[dict]:
    """One dict per KPI card: label, value, kind, change and change unit."""
    cur = compute_kpis(current) if len(current) else None
    prev = compute_kpis(previous) if len(previous) else None
    cards = []
    for key, label, kind in KPI_CARDS:
        value = cur[key] if cur else None
        change, unit = None, None
        if cur and prev:
            if kind == "pct":
                change, unit = cur[key] - prev[key], "pp"
            else:
                change, unit = pct_change(cur[key], prev[key]), "%"
        cards.append({"key": key, "label": label, "kind": kind, "value": value,
                      "previous": prev[key] if prev else None, "change": change, "unit": unit})
    return cards


def describe_filters(state: FilterState) -> list[str]:
    """Short labels for the active filters, e.g. ['Years: 2016-2017', 'Region: West']."""
    chips = []
    if state.years:
        ys = sorted(state.years)
        chips.append(f"Years: {ys[0]}-{ys[-1]}" if years_are_continuous(state.years) and len(ys) > 1
                     else "Years: " + ", ".join(map(str, ys)))
    if state.start is not None or state.end is not None:
        s = pd.Timestamp(state.start).strftime("%d %b %Y") if state.start is not None else "start"
        e = pd.Timestamp(state.end).strftime("%d %b %Y") if state.end is not None else "end"
        chips.append(f"Dates: {s} - {e}")
    names = {"regions": "Region", "states": "State", "categories": "Category",
             "subcategories": "Sub-category", "segments": "Segment"}
    for attr, name in names.items():
        chosen = getattr(state, attr)
        if chosen:
            chips.append(f"{name}: " + (", ".join(chosen) if len(chosen) <= 3 else f"{len(chosen)} selected"))
    return chips


def with_dates(state: FilterState, start, end) -> FilterState:
    return replace(state, start=pd.Timestamp(start) if start is not None else None,
                   end=pd.Timestamp(end) if end is not None else None)
