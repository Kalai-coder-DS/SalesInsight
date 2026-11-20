"""Page 4 - Regional Intelligence: where sales and profit come from, on a US map."""

from __future__ import annotations

import streamlit as st

from components import caps, charts
from components.context import get_context
from components.kpi_cards import render_stat_cards
from components.layout import (card, card_title, chart_switch, csv_download, data_table, empty_state,
                               page_header, show_chart)
from components.theme import PROFIT, REVENUE
from salesinsight import dashboard_data as dd
from salesinsight import regions as rg
from salesinsight.filtering import describe_filters


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    start, end = ctx.window
    if not (caps.has("region") or caps.has("state")):
        caps.page_unavailable("Regional Intelligence", ["region"])
        return
    counts = ([f"{df['region'].nunique()} regions"] if caps.has("region") else []) + \
             ([f"{df['state'].nunique()} states"] if caps.has("state") else [])
    page_header("Regional Intelligence", f"{start:%d %b %Y} - {end:%d %b %Y}  |  " + ", ".join(counts),
                chips=describe_filters(ctx.state))
    if df.empty:
        empty_state()
        return

    render_stat_cards(dd.region_stats(df))
    states = dd.state_table(df) if caps.has("state") else None

    # --- Map -----------------------------------------------------------------------
    if states is None:
        caps.unavailable_card("reg-map", "Sales by state", ["state"])
    else:
        with card("reg-map"):
            top = st.columns([1.6, 3, 1.3])
            with top[0]:
                card_title("Sales by state", "Hover a state for details")
            with top[1]:
                metric = chart_switch("rg_map_metric", caps.options(list(dd.STATE_METRICS)), label="Metric")
            with top[2]:
                view = chart_switch("rg_map_view", ["Map", "Bars"] if caps.has("us_map") else ["Bars"], label="View")
            column, kind, diverging = dd.STATE_METRICS[metric]
            if view == "Map":
                fig, note = charts.us_map(states, column, kind, metric, diverging)
                if diverging:
                    note = ((note + " ") if note else "") + "Red = loss / low, blue = profit / high, grey = around zero."
            else:
                ranked = states.sort_values(column, ascending=False).head(20)
                fig, note = charts.ranked_bar(ranked, "state", column, kind, metric,
                                              PROFIT if metric == "Profit" else REVENUE,
                                              extra=caps.extras({"region": ("Region", "text")}))
                note = "Top 20 states for the chosen metric." + (
                    "" if caps.has("us_map") else " The map needs US state names.")
            show_chart(fig, note, key="rg_map_chart")

    # --- Regions + region x category -------------------------------------------------
    left, right = st.columns(2, gap="medium")
    with left:
        if not caps.has("region"):
            caps.unavailable_card("reg-regions", "Region comparison", ["region"])
        else:
            with card("reg-regions"):
                card_title("Region comparison")
                r_metric = chart_switch("rg_r_metric", caps.options(list(dd.METRICS)), label="Metric")
                r_kind = chart_switch("rg_r_kind", charts.CATEGORY_KINDS)
                col, kind = dd.METRICS[r_metric]
                fig, note = charts.category_chart(dd.breakdown(df, "region"), "region", col, r_kind,
                                                  value_kind=kind, value_name=r_metric, height=340)
                show_chart(fig, note, key="rg_regions_chart")
    with right:
        if not caps.has("region", "category"):
            caps.unavailable_card("reg-matrix", "Region x category", caps.missing("region", "category"))
        else:
            with card("reg-matrix"):
                card_title("Region x category", "Spot weak combinations")
                m_metric = chart_switch("rg_m_metric", caps.options(["Margin", "Revenue", "Profit"]), label="Metric")
                value = {"Margin": "profit_margin_pct", "Revenue": "revenue", "Profit": "profit"}[m_metric]
                fig, note = charts.heatmap(rg.region_category_matrix(df, value),
                                           "pct" if m_metric == "Margin" else "money",
                                           diverging=m_metric != "Revenue", value_name=m_metric, height=340)
                show_chart(fig, note, key="rg_matrix_chart")

    # --- State ranking -----------------------------------------------------------------
    if states is None:
        caps.unavailable_card("reg-states", "State ranking", ["state"])
    else:
        with card("reg-states"):
            top = st.columns([1.5, 1.1, 1.8, 1.2, 1.2])
            with top[0]:
                card_title("State ranking")
            with top[1]:
                direction = chart_switch("rg_s_dir", ["Top", "Bottom"], label="Show")
            with top[2]:
                s_metric = chart_switch("rg_s_metric", caps.options(["Revenue", "Profit", "Margin"]), label="Metric")
            with top[3]:
                s_view = chart_switch("rg_s_view", ["Bars", "Table"], label="View")
            with top[4]:
                n = st.slider("How many", 5, 25, 10, step=5, key="rg_s_n")
            column = {"Revenue": "revenue", "Profit": "profit", "Margin": "profit_margin_pct"}[s_metric]
            kind = "pct" if s_metric == "Margin" else "money"
            ranked = states.sort_values(column, ascending=(direction == "Bottom")).head(n)
            if s_view == "Bars":
                fig, note = charts.ranked_bar(ranked, "state", column, kind, s_metric,
                                              PROFIT if s_metric == "Profit" else REVENUE,
                                              extra=caps.extras({"region": ("Region", "text"),
                                                                 "effective_discount_pct": ("Discount", "pct")}))
                show_chart(fig, note, key="rg_states_chart")
            else:
                cols = caps.columns(["state", "region", "revenue", "profit", "profit_margin_pct",
                                     "effective_discount_pct", "total_orders"])
                data_table(ranked[cols], money=["revenue", "profit"],
                           pct=["profit_margin_pct", "effective_discount_pct"], ints=["total_orders"], key="rg_states_tbl")
                csv_download(ranked[cols], f"{direction.lower()}_{n}_states_by_{s_metric.lower()}.csv", key="rg_states_csv")

    # --- Discount vs margin + regions over time ----------------------------------------
    left, right = st.columns(2, gap="medium")
    with left:
        if states is None or not caps.has("profit", "discount"):
            caps.unavailable_card("reg-discount", "Discount vs margin by state", caps.missing("state", "profit", "discount"))
        else:
            with card("reg-discount"):
                card_title("Discount vs margin by state", "States with 10+ orders; bubble size = revenue")
                busy = states[states["total_orders"] >= 10]
                if len(busy) >= 3:
                    fig, note = charts.bubble_scatter(busy, "effective_discount_pct", "profit_margin_pct", "revenue",
                                                      "code", "Effective discount", "Profit margin")
                    show_chart(fig, note, key="rg_discount_chart")
                else:
                    st.info("Needs at least 3 states with 10 or more orders. Widen the filters.")
    with right:
        if not caps.has("region"):
            caps.unavailable_card("reg-years", "Regions over time", ["region"])
        else:
            with card("reg-years"):
                card_title("Regions over time")
                c1, c2 = st.columns([1, 1.4])
                with c1:
                    y_metric = chart_switch("rg_y_metric", caps.options(list(dd.METRICS)), label="Metric")
                with c2:
                    y_kind = chart_switch("rg_y_kind", ["Line", "Bar", "Stacked area"])
                fig, note = charts.group_chart(dd.region_by_year(df, y_metric), y_kind, dd.METRICS[y_metric][1],
                                               y_metric, height=360)
                show_chart(fig, note, key="rg_years_chart")
