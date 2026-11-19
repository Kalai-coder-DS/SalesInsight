"""Phase 13 tests: every chart type is really built (needs plotly + streamlit installed)."""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("plotly")
pytest.importorskip("streamlit")

from salesinsight import config  # noqa: E402

sys.path.insert(0, str(config.PROJECT_ROOT / "app"))

from components import charts  # noqa: E402
from salesinsight import dashboard_data as dd  # noqa: E402


@pytest.mark.parametrize("kind, trace_type", [
    ("Bar", "bar"), ("Horizontal bar", "bar"), ("Pie", "pie"), ("Donut", "pie"), ("Treemap", "treemap"),
])
def test_category_chart_kinds(sales_data, kind, trace_type):
    fig, note = charts.category_chart(dd.breakdown(sales_data, "category"), "category", "revenue", kind)
    assert fig.data[0].type == trace_type
    assert note is None


def test_horizontal_bar_is_horizontal(sales_data):
    fig, _ = charts.category_chart(dd.breakdown(sales_data, "region"), "region", "revenue", "Horizontal bar")
    assert fig.data[0].orientation == "h"


def test_donut_has_hole_and_pie_does_not(sales_data):
    data = dd.breakdown(sales_data, "region")
    pie, _ = charts.category_chart(data, "region", "revenue", "Pie")
    donut, _ = charts.category_chart(data, "region", "revenue", "Donut")
    assert pie.data[0].hole == 0
    assert donut.data[0].hole > 0


def test_negative_values_fall_back_to_bars(sales_data):
    # Furniture profit is negative in the sample -> a pie cannot show it
    fig, note = charts.category_chart(dd.breakdown(sales_data, "category"), "category", "profit", "Pie",
                                      value_name="Profit")
    assert fig.data[0].type == "bar"
    assert "negative" in note


@pytest.mark.parametrize("kind, trace_type, fill", [
    ("Line", "scatter", None), ("Area", "scatter", "tozeroy"), ("Bar", "bar", None),
])
def test_time_chart_kinds(sales_data, kind, trace_type, fill):
    ts = dd.time_series(sales_data, "Year")
    fig, _ = charts.time_chart(ts, [("revenue", "Revenue", "#3b82f6"), ("profit", "Profit", "#f97316")], kind)
    assert len(fig.data) == 2
    assert fig.data[0].type == trace_type
    if trace_type == "scatter":
        assert fig.data[0].fill == fill


def test_waterfall(sales_data):
    fig, _ = charts.waterfall_chart(dd.profit_bridge(sales_data, "region"))
    assert fig.data[0].type == "waterfall"
    assert list(fig.data[0].measure)[-1] == "total"
