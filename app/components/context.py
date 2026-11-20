"""Everything a page needs, computed once per run by streamlit_app.py."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from salesinsight.filtering import FilterState


@dataclass
class PageContext:
    data: pd.DataFrame            # all clean data
    filtered: pd.DataFrame        # rows matching the sidebar filters
    previous: pd.DataFrame        # same filters, previous period (may be empty)
    state: FilterState
    window: tuple                 # (start, end) of the selected period
    previous_window: tuple | None
    compare_label: str | None     # e.g. "vs 2016" or "vs previous period"
    # Phase 14: which data is shown
    source: str = "demo"                      # "demo" or "custom"
    source_name: str = "Superstore demo data"
    capabilities: frozenset | None = None     # None = demo (everything available)
    currency: str = "$"


def set_context(ctx: PageContext) -> None:
    st.session_state["_si_ctx"] = ctx


def get_context() -> PageContext:
    return st.session_state["_si_ctx"]
