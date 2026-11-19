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
