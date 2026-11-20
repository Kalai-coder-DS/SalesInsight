"""Sidebar filters shared by every page.

Widget values live in st.session_state (keys start with "f_"), so a filter
chosen on one page is still applied after switching to another page.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from salesinsight.filtering import FilterState, filter_options, prune_selection

MULTI_KEYS = ["f_years", "f_regions", "f_states", "f_categories", "f_subcategories", "f_segments"]


def _init_state(opts: dict) -> None:
    for key in MULTI_KEYS:
        st.session_state.setdefault(key, [])
    st.session_state.setdefault("f_dates", (opts["min_date"].date(), opts["max_date"].date()))


def reset_filters(opts: dict) -> None:
    for key in MULTI_KEYS:
        st.session_state[key] = []
    st.session_state["f_dates"] = (opts["min_date"].date(), opts["max_date"].date())


def _date_range(value, opts: dict) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Turn the date widget value into (start, end); the full range means 'no date filter'."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:   # user is still picking
        return None, None
    start, end = pd.Timestamp(value[0]), pd.Timestamp(value[1])
    if start <= opts["min_date"].normalize() and end >= opts["max_date"].normalize():
        return None, None
    return start, end


def render_filters(df: pd.DataFrame, capabilities: frozenset | None = None) -> FilterState:
    """capabilities=None (demo data) shows every filter; for an uploaded file only the
    fields it really has are shown (Phase 14C)."""
    def show(cap: str) -> bool:
        return capabilities is None or cap in capabilities

    base_opts = filter_options(df)
    _init_state(base_opts)

    st.sidebar.markdown("<div class='si-side-title'>Filters</div>", unsafe_allow_html=True)
    sb = st.sidebar

    sb.multiselect("Year", base_opts["years"], key="f_years", placeholder="All years")
    sb.date_input("Date range", key="f_dates",
                  min_value=base_opts["min_date"].date(), max_value=base_opts["max_date"].date(),
                  format="DD/MM/YYYY")

    if show("region"):
        sb.multiselect("Region", base_opts["regions"], key="f_regions", placeholder="All regions")
    if show("state"):
        # Cascading: only states inside the chosen regions; drop states that no longer fit.
        opts = filter_options(df, FilterState(regions=tuple(st.session_state["f_regions"]),
                                              categories=tuple(st.session_state["f_categories"])))
        st.session_state["f_states"] = list(prune_selection(st.session_state["f_states"], opts["states"]))
        sb.multiselect("State", opts["states"], key="f_states", placeholder="All states")

    if show("category"):
        sb.multiselect("Category", base_opts["categories"], key="f_categories", placeholder="All categories")
    if show("sub_category"):
        opts = filter_options(df, FilterState(categories=tuple(st.session_state["f_categories"])))
        st.session_state["f_subcategories"] = list(
            prune_selection(st.session_state["f_subcategories"], opts["subcategories"]))
        sb.multiselect("Sub-category", opts["subcategories"], key="f_subcategories",
                       placeholder="All sub-categories")

    if show("segment"):
        sb.multiselect("Customer segment", base_opts["segments"], key="f_segments", placeholder="All segments")
    sb.button("Reset filters", on_click=reset_filters, args=(base_opts,), width="stretch",
              icon=":material/restart_alt:")

    start, end = _date_range(st.session_state["f_dates"], base_opts)
    return FilterState(
        years=tuple(sorted(st.session_state["f_years"])),
        start=start, end=end,
        regions=tuple(st.session_state["f_regions"]),
        states=tuple(st.session_state["f_states"]),
        categories=tuple(st.session_state["f_categories"]),
        subcategories=tuple(st.session_state["f_subcategories"]),
        segments=tuple(st.session_state["f_segments"]),
    )


def today() -> dt.date:
    return dt.date.today()
