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


# --------------------------------------------------------------------------
# 13B chart builders
# --------------------------------------------------------------------------
def test_time_chart_moving_average_stays_a_line(sales_data):
    s = dd.metric_series(sales_data, "Year", "Revenue")
    fig, _ = charts.time_chart(s, [("value", "Revenue", "#3b82f6"), ("moving_avg", "MA", "#1d4ed8", "line")], "Bar")
    assert [t.type for t in fig.data] == ["bar", "scatter"]


def test_ranked_bar_keeps_every_product(sales_data):
    ranked = dd.ranked_products(sales_data, "Revenue", 8)
    fig, _ = charts.ranked_bar(ranked, "product_name", "revenue")
    assert len(fig.data[0].y) == 8
    assert fig.data[0].orientation == "h"


@pytest.mark.parametrize("kind, trace_type", [("Treemap", "treemap"), ("Sunburst", "sunburst"), ("Bar", "bar")])
def test_hierarchy_chart(sales_data, kind, trace_type):
    fig, _ = charts.hierarchy_chart(dd.category_hierarchy(sales_data), kind)
    assert fig.data[0].type == trace_type


def test_heatmaps(sales_data):
    from salesinsight import products as pr
    seq, _ = charts.heatmap(dd.month_by_year(sales_data), "money")
    div, _ = charts.heatmap(pr.discount_margin_matrix(sales_data), "pct", diverging=True)
    assert seq.data[0].type == div.data[0].type == "heatmap"
    assert div.data[0].zmid == 0


def test_diverging_bars_split_profit_and_loss(sales_data):
    from salesinsight import products as pr
    fig, _ = charts.diverging_bars(pr.subcategory_performance(sales_data), "sub_category", "profit")
    assert {t.name for t in fig.data} == {"Profit", "Loss"}


def test_bubble_scatter_trend_line(sales_data):
    from salesinsight import products as pr
    fig, note = charts.bubble_scatter(pr.subcategory_performance(sales_data), "effective_discount_pct",
                                      "profit_margin_pct", "revenue", "sub_category", "Discount", "Margin")
    assert len(fig.data) == 2 and "Correlation" in note


def test_pareto_growth_lines_index(sales_data):
    from salesinsight import products as pr
    assert charts.pareto_chart(pr.pareto(pr.product_performance(sales_data)))[0].data
    assert charts.growth_bars(dd.growth(sales_data, "Year"), "revenue_growth_pct")[0].data[0].type == "bar"
    assert len(charts.month_lines(dd.month_by_year(sales_data))[0].data) == 4
    assert charts.index_bars(dd.seasonality_index(sales_data))[0].data[0].type == "bar"


def test_lines_are_not_smoothed(sales_data):
    # Smoothed (spline) lines overshoot between points and show values not in the data.
    ts = dd.time_series(sales_data, "Month")
    fig, _ = charts.time_chart(ts, [("revenue", "Revenue", "#3b82f6")], "Line")
    assert fig.data[0].line.shape == "linear"


# --------------------------------------------------------------------------
# 13C chart builders
# --------------------------------------------------------------------------
@pytest.mark.parametrize("metric", ["Revenue", "Profit", "Margin", "Discount", "Orders"])
def test_us_map(sales_data, metric):
    column, kind, diverging = dd.STATE_METRICS[metric]
    fig, _ = charts.us_map(dd.state_table(sales_data), column, kind, metric, diverging)
    trace = fig.data[0]
    assert trace.type == "choropleth"
    assert trace.locationmode == "USA-states"
    assert set(trace.locations) == {"KY", "CA", "FL", "VT", "NC", "WA"}
    assert (trace.zmid == 0) == diverging


@pytest.mark.parametrize("kind, trace_type", [("Line", "scatter"), ("Bar", "bar"), ("Stacked area", "scatter")])
def test_group_chart(sales_data, kind, trace_type):
    fig, _ = charts.group_chart(dd.region_by_year(sales_data), kind)
    assert len(fig.data) == 4                     # one series per region
    assert fig.data[0].type == trace_type
    if trace_type == "scatter":                   # bars have no stackgroup setting in Plotly
        assert (fig.data[0].stackgroup == "one") == (kind == "Stacked area")


def test_paired_bars(sales_data):
    from salesinsight import customers as cu
    freq = cu.order_frequency(cu.customer_table(sales_data))
    fig, _ = charts.paired_bars(freq, "order_band", ("share_of_customers_pct", "Customers", "#10b981"),
                                ("share_of_revenue_pct", "Revenue", "#3b82f6"), horizontal=True)
    assert len(fig.data) == 2 and fig.data[0].orientation == "h"


@pytest.mark.parametrize("kind, trace_type", [("Stacked bars", "bar"), ("Stacked area", "scatter")])
def test_stacked_chart(sales_data_with_repeat, kind, trace_type):
    nvr = dd.new_vs_returning_long(sales_data_with_repeat)
    fig, _ = charts.stacked_chart(nvr, "label", [("revenue_returning", "Returning", "#3b82f6"),
                                                 ("revenue_new", "New", "#10b981")], kind)
    assert [t.type for t in fig.data] == [trace_type, trace_type]
