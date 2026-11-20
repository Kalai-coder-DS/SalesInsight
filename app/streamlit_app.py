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

from components import data_source as ds  # noqa: E402
from components import theme  # noqa: E402
from components.context import PageContext, set_context  # noqa: E402
from components.data import load_sales  # noqa: E402
from components.filters import render_filters  # noqa: E402
from salesinsight.filtering import apply_filters, date_window, previous_period  # noqa: E402
from views import customers, data_source, explorer, insights, overview, products, regions, trends  # noqa: E402

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


# --- Brand: logo at the very top of the sidebar (icon only when collapsed) ------------
ASSETS = ROOT / "app" / "assets"
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))

# --- Data: the demo data, or the visitor's own file (kept only in this session) -------
data, data_error = None, None
if ds.mode() == "custom":
    data = ds.custom_result().data
else:
    try:
        data = load_sales()
    except Exception as exc:  # show a clear message instead of a traceback
        data_error = str(exc)

# --- Navigation ---------------------------------------------------------------------
source_page = st.Page(data_source.render, title="Data Source", icon=":material/upload_file:",
                      url_path="data-source", default=data is None)
overview_page = st.Page(overview.render, title="Executive Overview", icon=":material/space_dashboard:",
                        url_path="overview", default=data is not None)
st.session_state["_si_pages"] = {"overview": overview_page, "data_source": source_page}
pages = {
    "Data": [source_page],
    "Analytics": [
        overview_page,
        st.Page(trends.render, title="Sales Trends", icon=":material/trending_up:", url_path="trends"),
        st.Page(products.render, title="Product Intelligence", icon=":material/inventory_2:",
                url_path="products"),
        st.Page(regions.render, title="Regional Intelligence", icon=":material/public:", url_path="regions"),
        st.Page(customers.render, title="Customer Intelligence", icon=":material/groups:",
                url_path="customers"),
    ],
    "Intelligence": [
        st.Page(insights.render, title="Business Insights", icon=":material/lightbulb:", url_path="insights"),
    ],
    "Tools": [
        st.Page(explorer.render, title="Data Explorer", icon=":material/table_view:", url_path="explorer"),
    ],
}
if data is None:      # demo data could not be loaded: uploading a file still works
    page = st.navigation({"Data": [source_page]}, position="sidebar")
    st.error(f"Could not load the demo sales data. {data_error} You can still upload your own file below.",
             icon=":material/error:")
    page.run()
    st.stop()
page = st.navigation(pages, position="sidebar")

# --- Which data is active (sidebar badge) ------------------------------------------
st.sidebar.markdown("<div class='si-side-title'>Data</div>", unsafe_allow_html=True)
if ds.mode() == "custom":
    st.sidebar.markdown(f"<div class='si-source si-source-custom'>Your file<b>{ds.source_name()}</b></div>",
                        unsafe_allow_html=True)
    st.sidebar.button("Use demo data", icon=":material/restart_alt:", key="ds_side_demo", on_click=ds.use_demo,
                      width="stretch")
else:
    st.sidebar.markdown(f"<div class='si-source'>Demo<b>{ds.DEMO_NAME}</b></div>", unsafe_allow_html=True)

# --- Global filters (same for every page) ------------------------------------------
state = render_filters(data, ds.capabilities())
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
    source=ds.mode(),
    source_name=ds.source_name(),
    capabilities=ds.capabilities(),
    currency=ds.currency(),
))

# --- Run the chosen page; any unexpected error is shown politely, not as a crash ----
try:
    page.run()
except Exception as exc:  # noqa: BLE001 - the user sees a clear message and can report the details
    st.error("Something went wrong while drawing this page. Try changing or resetting the filters.",
             icon=":material/error:")
    with st.expander("Technical details"):
        st.exception(exc)

st.sidebar.caption(f"Data: {len(data):,} order lines, "
                   f"{data['order_date'].min():%b %Y} - {data['order_date'].max():%b %Y}")
