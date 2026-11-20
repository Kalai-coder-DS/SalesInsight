"""Phase 13 tests: the web app starts and every page renders without errors.

Uses Streamlit's built-in AppTest (runs the app headless, no browser).
Needs streamlit installed and data/processed/sales_clean.csv (run run_cleaning.py).
"""

from __future__ import annotations

import datetime as dt

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest  # noqa: E402

from salesinsight import config  # noqa: E402

APP = str(config.PROJECT_ROOT / "app" / "streamlit_app.py")

pytestmark = pytest.mark.skipif(not config.CLEAN_DATA_FILE.is_file(),
                                reason="run scripts/run_cleaning.py first")


def page_text(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def test_app_starts_on_overview(app):
    assert not app.exception
    text = page_text(app)
    assert "Executive Overview" in text
    assert "Total revenue" in text


def test_region_filter_updates_page(app):
    app.sidebar.multiselect(key="f_regions").set_value(["West"]).run()
    assert not app.exception
    assert "Region: West" in page_text(app)


def test_state_options_follow_region(app):
    app.sidebar.multiselect(key="f_regions").set_value(["West"]).run()
    states = app.sidebar.multiselect(key="f_states").options
    assert "California" in states and "Texas" not in states


def test_year_filter_shows_comparison(app):
    app.sidebar.multiselect(key="f_years").set_value([2017]).run()
    assert not app.exception
    assert "vs 2016" in page_text(app)


def test_filters_with_no_data_show_empty_state(app):
    app.sidebar.multiselect(key="f_years").set_value([2014]).run()
    app.sidebar.date_input(key="f_dates").set_value((dt.date(2017, 1, 1), dt.date(2017, 1, 31))).run()
    assert not app.exception
    assert "No data matches" in page_text(app)


def test_reset_filters(app):
    app.sidebar.multiselect(key="f_regions").set_value(["East"]).run()
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.session_state["f_regions"] == []


def test_light_mode(app):
    app.sidebar.toggle(key="light_mode").set_value(True).run()
    assert not app.exception


# --------------------------------------------------------------------------
# 13B: Sales Trends and Product Intelligence pages, with chart options
# --------------------------------------------------------------------------
HARNESS = str(config.PROJECT_ROOT / "tests" / "app_page_harness.py")


def render_page(page: str, options: dict | None = None, filters: dict | None = None) -> AppTest:
    at = AppTest.from_file(HARNESS, default_timeout=60)
    at.session_state["harness_page"] = page
    if filters:
        at.session_state["harness_filters"] = filters
    for key, value in (options or {}).items():
        at.session_state[key] = value
    at.run()
    return at


@pytest.mark.parametrize("options", [
    {},
    {"tr_metric": "Profit", "tr_grain": "Quarter", "tr_kind": "Bar"},
    {"tr_metric": "Orders", "tr_grain": "Year", "tr_kind": "Area", "tr_ma": False},
    {"tr_g_grain": "Quarter", "tr_g_metric": "Profit"},
    {"tr_sp_view": "Revenue vs profit"},
    {"tr_s_view": "Lines by year", "tr_s_metric": "Orders"},
    {"tr_s_view": "Index"},
    {"tr_w_metric": "Revenue", "tr_w_kind": "Donut"},
])
def test_trends_page(options):
    at = render_page("trends", options)
    assert not at.exception
    assert "Sales Trends" in page_text(at)


@pytest.mark.parametrize("options", [
    {},
    {"pr_dir": "Bottom", "pr_metric": "Profit", "pr_view": "Bars", "pr_n": 25},
    {"pr_metric": "Units", "pr_view": "Treemap"},
    {"pr_view": "Table"},
    {"pr_h_kind": "Sunburst", "pr_h_size": "Units"},
    {"pr_h_kind": "Bar"},
    {"pr_p_view": "Discount vs margin"},
    {"pr_p_view": "Margin heatmap"},
])
def test_products_page(options):
    at = render_page("products", options)
    assert not at.exception
    assert "Product Intelligence" in page_text(at)


@pytest.mark.parametrize("page", ["overview", "trends", "products"])
def test_pages_with_filters(page):
    at = render_page(page, filters={"years": (2016,), "regions": ("West",), "categories": ("Technology",)})
    assert not at.exception


@pytest.mark.parametrize("page", ["trends", "products"])
def test_pages_with_no_data(page):
    at = render_page(page, filters={"years": (2014,), "start": "2017-01-01", "end": "2017-01-31"})
    assert not at.exception
    assert "No data matches" in page_text(at)


def test_navigation_lists_all_pages():
    from pathlib import Path
    text = Path(APP).read_text(encoding="utf-8")
    for title in ("Executive Overview", "Sales Trends", "Product Intelligence",
                  "Regional Intelligence", "Customer Intelligence", "Business Insights", "Data Explorer"):
        assert title in text


# --------------------------------------------------------------------------
# 13C: Regional and Customer Intelligence pages
# --------------------------------------------------------------------------
@pytest.mark.parametrize("options", [
    {},
    {"rg_map_metric": "Profit"},
    {"rg_map_metric": "Margin", "rg_map_view": "Bars"},
    {"rg_r_metric": "Orders", "rg_r_kind": "Donut"},
    {"rg_m_metric": "Revenue"},
    {"rg_s_dir": "Bottom", "rg_s_metric": "Profit", "rg_s_view": "Table"},
    {"rg_y_kind": "Stacked area", "rg_y_metric": "Profit"},
])
def test_regions_page(options):
    at = render_page("regions", options)
    assert not at.exception
    assert "Regional Intelligence" in page_text(at)


@pytest.mark.parametrize("options", [
    {},
    {"cu_s_metric": "Avg order value", "cu_s_kind": "Horizontal bar"},
    {"cu_s_metric": "Customers", "cu_s_kind": "Treemap"},
    {"cu_rfm_view": "Treemap"},
    {"cu_rfm_view": "Table"},
    {"cu_nr_kind": "Stacked area"},
    {"cu_t_dir": "Bottom", "cu_t_metric": "Profit", "cu_t_view": "Table"},
])
def test_customers_page(options):
    at = render_page("customers", options)
    assert not at.exception
    assert "Customer Intelligence" in page_text(at)


@pytest.mark.parametrize("page", ["regions", "customers"])
def test_new_pages_with_filters_and_no_data(page):
    at = render_page(page, filters={"years": (2016,), "regions": ("West",)})
    assert not at.exception
    at = render_page(page, filters={"years": (2014,), "start": "2017-01-01", "end": "2017-01-31"})
    assert not at.exception
    assert "No data matches" in page_text(at)


# --------------------------------------------------------------------------
# 13D: Business Insights and Data Explorer
# --------------------------------------------------------------------------
@pytest.mark.parametrize("options", [{}, {"in_area": "Pricing"}])
def test_insights_page(options):
    at = render_page("insights", options)
    assert not at.exception and not at.error
    text = page_text(at)
    assert "Business Insights" in text and "Priority 1" in text
    assert len(at.tabs) == 4


@pytest.mark.parametrize("options", [
    {},
    {"ex_query": "chair west"},
    {"ex_query": "zzzz-no-match"},
    {"ex_cols": ["order_id", "sales", "ship_date"]},
    {"ex_view": "Summary", "ex_group": "State"},
    {"ex_view": "Summary", "ex_group": "Discount band"},
])
def test_explorer_page(options):
    at = render_page("explorer", options)
    assert not at.exception and not at.error
    assert "Data Explorer" in page_text(at)


@pytest.mark.parametrize("page", ["insights", "explorer"])
def test_13d_pages_with_filters_and_no_data(page):
    for filters in ({"regions": ("West",)}, {"states": ("Vermont",)}, {"years": (2017,), "segments": ("Home Office",)},
                    {"start": "2017-03-01", "end": "2017-03-03"}):
        at = render_page(page, filters=filters)
        assert not at.exception and not at.error, filters
    at = render_page(page, filters={"years": (2014,), "start": "2017-01-01", "end": "2017-01-31"})
    assert not at.exception
    assert "No data matches" in page_text(at)
