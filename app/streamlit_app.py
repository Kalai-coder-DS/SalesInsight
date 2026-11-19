"""SalesInsight web application - entry point.

Run locally from the project root:
    streamlit run app/streamlit_app.py

This file sets up the page, theme, data and global filters, then hands
over to the page chosen in the sidebar navigation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "app"):      # works without "pip install -e ." (e.g. on Streamlit Cloud)
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components import theme  # noqa: E402
from components.context import PageContext, set_context  # noqa: E402
from components.data import load_sales  # noqa: E402
from components.filters import render_filters  # noqa: E402
from salesinsight.filtering import apply_filters, date_window, previous_period  # noqa: E402
from views import overview  # noqa: E402

st.set_page_config(
    page_title="SalesInsight - Sales Intelligence",
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.inject_css()


def compare_label(state, prev_window) -> str | None:
    if prev_window is None:
        return None
    if state.years and state.start is None and state.end is None:
        first, last = prev_window[0].year, prev_window[1].year
        return f"vs {first}" if first == last else f"vs {first}-{last}"
    return f"vs {prev_window[0]:%d %b %Y} - {prev_window[1]:%d %b %Y}"


# --- Sidebar brand ------------------------------------------------------------------
st.sidebar.markdown(
    "<div class='si-brand'><div class='si-brand-mark'>S</div><div>"
    "<div class='si-brand-name'>SalesInsight</div>"
    "<div class='si-brand-sub'>Sales intelligence platform</div></div></div>",
    unsafe_allow_html=True)

# --- Data -------------------------------------------------------------------------
try:
    data = load_sales()
except Exception as exc:  # show a clear message instead of a traceback
    st.error(f"Could not load the sales data. {exc}")
    st.stop()

# --- Navigation (pages are added step by step: 13A = Overview) ----------------------
pages = {
    "Analytics": [
        st.Page(overview.render, title="Executive Overview", icon=":material/space_dashboard:",
                url_path="overview", default=True),
    ],
}
page = st.navigation(pages, position="sidebar")

# --- Global filters (same for every page) ------------------------------------------
state = render_filters(data)
st.sidebar.markdown("<div class='si-side-title'>Appearance</div>", unsafe_allow_html=True)
st.sidebar.toggle("Light mode", key="light_mode")

filtered = apply_filters(data, state)
previous, prev_window = previous_period(data, state)
set_context(PageContext(
    data=data,
    filtered=filtered,
    previous=previous,
    state=state,
    window=date_window(data, state),
    previous_window=prev_window,
    compare_label=compare_label(state, prev_window),
))

page.run()

st.sidebar.caption(f"Data: {len(data):,} order lines, "
                   f"{data['order_date'].min():%b %Y} - {data['order_date'].max():%b %Y}")
