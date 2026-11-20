"""Page 2 - Sales Trends: how sales move over time, growth and seasonality."""

from __future__ import annotations

import streamlit as st

from components import charts
from components.context import get_context
from components.kpi_cards import render_stat_cards
from components.layout import card, card_title, chart_switch, empty_state, page_header, show_chart
from components.theme import PROFIT, REVENUE
from salesinsight import dashboard_data as dd
from salesinsight.filtering import describe_filters

METRIC_COLORS = {"Revenue": REVENUE, "Profit": PROFIT, "Orders": "#8b5cf6"}
MA_COLOR = {"Revenue": "#1d4ed8", "Profit": "#c2410c", "Orders": "#6d28d9"}


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    start, end = ctx.window
    page_header("Sales Trends", f"{start:%d %b %Y} - {end:%d %b %Y}  |  growth, seasonality and patterns",
                chips=describe_filters(ctx.state))
    if df.empty:
        empty_state()
        return

    render_stat_cards(dd.trend_stats(df))

    # --- Main time series --------------------------------------------------------
    with card("trend-main"):
        top = st.columns([1.6, 1.3, 1.3, 1.3, 0.9])
        with top[0]:
            card_title("Sales over time")
        with top[1]:
            metric = chart_switch("tr_metric", list(dd.METRICS), label="Metric")
        with top[2]:
            grain = chart_switch("tr_grain", ["Month", "Quarter", "Year"], label="Period")
        with top[3]:
            kind = chart_switch("tr_kind", charts.TIME_KINDS)
        with top[4]:
            show_ma = st.toggle("Moving avg", value=True, key="tr_ma")
        series = dd.metric_series(df, grain, metric)
        spec = [("value", metric, METRIC_COLORS[metric])]
        if show_ma:
            spec.append(("moving_avg", f"{dd.WINDOW[grain]}-{grain.lower()} moving average",
                         MA_COLOR[metric], "line"))
        fig, note = charts.time_chart(series, spec, kind, value_kind=dd.METRICS[metric][1])
        show_chart(fig, note, key="tr_main_chart")

    # --- Growth and margin ---------------------------------------------------------
    left, right = st.columns(2, gap="medium")
    with left, card("trend-growth"):
        card_title("Growth", "Versus the same period one year earlier")
        c1, c2 = st.columns(2)
        with c1:
            g_grain = chart_switch("tr_g_grain", ["Year", "Quarter"], label="Compare")
        with c2:
            g_metric = chart_switch("tr_g_metric", list(dd.METRICS), label="Metric")
        g = dd.growth(df, g_grain)
        column = f"{dd.METRICS[g_metric][0]}_growth_pct"
        if g[column].notna().any():
            fig, note = charts.growth_bars(g, column, f"{g_metric} growth")
            show_chart(fig, note, key="tr_growth_chart")
        else:
            st.info("Growth needs at least two comparable periods. Select more years.")
    with right, card("trend-margin"):
        card_title("Sales vs profit", "How much of each sales dollar is kept as profit")
        view = chart_switch("tr_sp_view", ["Margin trend", "Revenue vs profit"], label="View")
        if view == "Margin trend":
            m_grain = "Quarter" if grain == "Month" else grain
            m = dd.margin_series(df, m_grain).dropna(subset=["margin_pct"])
            fig, note = charts.time_chart(m, [("margin_pct", "Profit margin", PROFIT)], "Line",
                                          value_kind="pct", height=330)
            fig.add_hline(y=100 * df["profit"].sum() / df["sales"].sum(),
                          line=dict(color="#94a3b8", dash="dash", width=1),
                          annotation_text="Average for the selection", annotation_position="bottom right")
            show_chart(fig, note, key="tr_margin_chart")
        else:
            m = dd.margin_series(df, "Month")
            m = m[m["revenue"] > 0].assign(year=lambda d: d["period"].dt.year.astype(str))
            fig, note = charts.bubble_scatter(
                m.assign(size=m["revenue"]), "revenue", "profit", "size", "label",
                "Monthly revenue", "Monthly profit", x_kind="money", y_kind="money")
            fig.update_traces(mode="markers", selector=dict(mode="markers+text"))
            show_chart(fig, note, key="tr_scatter_chart")

    # --- Seasonality -----------------------------------------------------------------
    with card("trend-season"):
        top = st.columns([2, 1.4, 1.6])
        with top[0]:
            card_title("Seasonality", "Which months are strong or weak")
        with top[1]:
            s_metric = chart_switch("tr_s_metric", list(dd.METRICS), label="Metric")
        with top[2]:
            s_view = chart_switch("tr_s_view", ["Heatmap", "Lines by year", "Index"], label="View")
        value_kind = dd.METRICS[s_metric][1]
        if s_view == "Heatmap":
            fig, note = charts.heatmap(dd.month_by_year(df, s_metric), value_kind, value_name=s_metric)
        elif s_view == "Lines by year":
            fig, note = charts.month_lines(dd.month_by_year(df, s_metric), value_kind, s_metric)
        else:
            fig, note = charts.index_bars(dd.seasonality_index(df, s_metric))
        show_chart(fig, note, key="tr_season_chart")

    # --- Weekday ---------------------------------------------------------------------
    with card("trend-weekday"):
        top = st.columns([2, 1.6, 1.4])
        with top[0]:
            card_title("Day of the week", "When orders are placed")
        with top[1]:
            w_metric = chart_switch("tr_w_metric", ["Orders", "Revenue", "Profit"], label="Metric")
        with top[2]:
            w_kind = chart_switch("tr_w_kind", ["Bar", "Donut"])
        w = dd.weekday_table(df)
        column = {"Orders": "total_orders", "Revenue": "revenue", "Profit": "profit"}[w_metric]
        fig, note = charts.category_chart(w, "weekday", column, w_kind,
                                          value_kind="int" if w_metric == "Orders" else "money",
                                          value_name=w_metric, height=320)
        show_chart(fig, note, key="tr_weekday_chart")
