"""Small Streamlit script used by the tests to render ONE page with chosen filters.

Not a test itself (pytest only collects test_*.py). The tests set
session_state["harness_page"] and optionally session_state["harness_filters"] and
session_state["harness_upload"] (a file in data/samples, analysed as the visitor's own data).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]

import streamlit as st  # noqa: E402

from components import theme  # noqa: E402
from components.context import PageContext, set_context  # noqa: E402
from components.data import load_sales  # noqa: E402
from salesinsight.filtering import FilterState, apply_filters, date_window, previous_period  # noqa: E402
from views import customers, data_source, explorer, insights, overview, products, regions, trends  # noqa: E402

PAGES = {"overview": overview, "trends": trends, "products": products, "regions": regions,
         "customers": customers, "insights": insights, "explorer": explorer,
         "data_source": data_source}

upload = st.session_state.get("harness_upload")
extra = {}
if upload:
    from salesinsight.upload import prepare_sales, read_upload, suggest_mapping
    raw = read_upload(upload, (ROOT / "data" / "samples" / upload).read_bytes())
    result = prepare_sales(raw, suggest_mapping(raw)[0])
    data = result.data
    extra = {"source": "custom", "source_name": upload, "capabilities": frozenset(result.capabilities),
             "currency": result.currency or "$"}
else:
    data = load_sales()
state = FilterState(**st.session_state.get("harness_filters", {}))
previous, prev_window = previous_period(data, state)
set_context(PageContext(data=data, filtered=apply_filters(data, state), previous=previous, state=state,
                        window=date_window(data, state), previous_window=prev_window,
                        compare_label="vs previous period" if prev_window else None, **extra))
theme.inject_css()
PAGES[st.session_state.get("harness_page", "overview")].render()
