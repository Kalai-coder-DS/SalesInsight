"""Page 1 - Executive Overview: headline KPIs and the big picture."""

from __future__ import annotations

import streamlit as st

from components import charts
from components.context import get_context
from components.kpi_cards import render_kpi_cards
from components.layout import (card, card_title, chart_switch, empty_state, highlight_list, page_header,
                               show_chart)
from components.theme import PROFIT, REVENUE
from salesinsight import dashboard_data as dd
from salesinsight.filtering import describe_filters, kpi_comparison

METRIC_OPTIONS = ["Revenue", "Profit", "Orders"]


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    start, end = ctx.window
    page_header(
        "Executive Overview",
        f"{start:%d %b %Y} - {end:%d %b %Y}  |  {len(df):,} order lines  |  "
        f"{df['order_id'].nunique():,} orders",
        eyebrow="Analytics",
        chips=describe_filters(ctx.state),
    )
    if df.empty:
        empty_state()
        return

    render_kpi_cards(kpi_comparison(df, ctx.previous), ctx.compare_label)

    # --- Revenue and profit over time -------------------------------------------
    with card("overview-trend"):
        top = st.columns([2, 1.2, 1.2])
        with top[0]:
            card_title("Revenue and profit over time", "Both in dollars, on one shared axis")
        with top[1]:
            grain = chart_switch("ov_grain", ["Month", "Quarter", "Year"], label="Period")
        with top[2]:
            kind = chart_switch("ov_trend_kind", charts.TIME_KINDS)
        ts = dd.time_series(df, grain)
        fig, note = charts.time_chart(ts, [("revenue", "Revenue", REVENUE), ("profit", "Profit", PROFIT)], kind)
        show_chart(fig, note, key="ov_trend_chart")

    # --- Breakdowns by category and by region ------------------------------------
    left, right = st.columns(2, gap="medium")
    for column, dim, title, key in ((left, "category", "Sales by category", "ov_cat"),
                                    (right, "region", "Sales by region", "ov_reg")):
        with column, card(key):
            card_title(title)
            # Metric and chart type on separate rows: 5 chart types do not fit beside the metric in a half card.
            metric = chart_switch(f"{key}_metric", METRIC_OPTIONS, label="Metric")
            kind = chart_switch(f"{key}_kind", charts.CATEGORY_KINDS)
            value_col, value_kind = dd.METRICS[metric]
            fig, note = charts.category_chart(dd.breakdown(df, dim), dim, value_col, kind,
                                              value_kind=value_kind, value_name=metric, height=340)
            show_chart(fig, note, key=f"{key}_chart")

    # --- Profit bridge and highlights --------------------------------------------
    left, right = st.columns([1.7, 1], gap="medium")
    with left, card("overview-bridge"):
        top = st.columns([1.4, 1.6])
        with top[0]:
            card_title("Where the profit comes from", "Each bar adds to or takes away from total profit")
        with top[1]:
            dim_label = chart_switch("ov_bridge_dim", ["Category", "Region", "Segment"], label="Split by")
        dim = {"Category": "category", "Region": "region", "Segment": "segment"}[dim_label]
        fig, note = charts.waterfall_chart(dd.profit_bridge(df, dim))
        show_chart(fig, note, key="ov_bridge_chart")
    with right, card("overview-highlights"):
        card_title("Highlights", "Calculated from the filtered data")
        highlight_list(dd.highlights(df))
