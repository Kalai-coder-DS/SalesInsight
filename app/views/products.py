"""Page 3 - Product Intelligence: best and worst products, categories and profitability."""

from __future__ import annotations

import streamlit as st

from components import charts
from components.context import get_context
from components.kpi_cards import render_stat_cards
from components.layout import (card, card_title, chart_switch, csv_download, data_table, empty_state,
                               page_header, show_chart)
from components.theme import PROFIT, REVENUE
from salesinsight import dashboard_data as dd
from salesinsight import products as pr
from salesinsight.filtering import describe_filters

METRIC_COLOR = {"Revenue": REVENUE, "Profit": PROFIT, "Units": "#8b5cf6"}


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    start, end = ctx.window
    page_header("Product Intelligence", f"{start:%d %b %Y} - {end:%d %b %Y}  |  "
                f"{df['product_key'].nunique():,} products in the selection",
                chips=describe_filters(ctx.state))
    if df.empty:
        empty_state()
        return

    render_stat_cards(dd.product_stats(df))

    # --- Top / bottom products ---------------------------------------------------------
    with card("prod-rank"):
        top = st.columns([1.5, 1.1, 1.4, 1.3, 1.3])
        with top[0]:
            card_title("Product ranking")
        with top[1]:
            direction = chart_switch("pr_dir", ["Top", "Bottom"], label="Show")
        with top[2]:
            metric = chart_switch("pr_metric", list(dd.PRODUCT_METRICS), label="Metric")
        with top[3]:
            view = chart_switch("pr_view", ["Bars", "Treemap", "Table"], label="View")
        with top[4]:
            n = st.slider("How many", 5, 25, 10, step=5, key="pr_n")
        ranked = dd.ranked_products(df, metric, n, top=(direction == "Top"))
        column, value_kind = dd.PRODUCT_METRICS[metric]
        if view == "Bars":
            fig, note = charts.ranked_bar(
                ranked, "product_name", column, value_kind, metric, METRIC_COLOR[metric],
                extra={"sub_category": ("Sub-category", "text"), "profit_margin_pct": ("Margin", "pct"),
                       "effective_discount_pct": ("Discount", "pct")})
            show_chart(fig, note, key="pr_rank_chart")
        elif view == "Treemap":
            fig, note = charts.category_chart(ranked, "product_name", column, "Treemap",
                                              value_kind=value_kind, value_name=metric, height=440)
            show_chart(fig, note, key="pr_rank_treemap")
        else:
            cols = ["product_name", "category", "sub_category", "revenue", "units_sold", "profit",
                    "profit_margin_pct", "effective_discount_pct"]
            data_table(ranked[cols], money=["revenue", "profit"], pct=["profit_margin_pct",
                       "effective_discount_pct"], ints=["units_sold"], key="pr_rank_table")
            csv_download(ranked[cols], f"{direction.lower()}_{n}_products_by_{metric.lower()}.csv",
                         key="pr_rank_csv")

    # --- Category > sub-category ------------------------------------------------------------
    with card("prod-hierarchy"):
        top = st.columns([2, 1.3, 1.7])
        with top[0]:
            card_title("Categories and sub-categories", "Size = sales, colour = profit margin")
        with top[1]:
            size_label = chart_switch("pr_h_size", ["Revenue", "Units"], label="Size")
        with top[2]:
            h_kind = chart_switch("pr_h_kind", ["Treemap", "Sunburst", "Bar"])
        size = "revenue" if size_label == "Revenue" else "units_sold"
        fig, note = charts.hierarchy_chart(dd.category_hierarchy(df), h_kind, size, size_label)
        show_chart(fig, note, key="pr_hier_chart")

    # --- Sub-category profitability -------------------------------------------------------
    with card("prod-profit"):
        top = st.columns([2, 2.6])
        with top[0]:
            card_title("Sub-category profitability", "Where profit is made and lost")
        with top[1]:
            p_view = chart_switch("pr_p_view", ["Profit bars", "Discount vs margin", "Margin heatmap"],
                                  label="View")
        subs = pr.subcategory_performance(df)
        if p_view == "Profit bars":
            fig, note = charts.diverging_bars(subs, "sub_category", "profit")
        elif p_view == "Discount vs margin":
            fig, note = charts.bubble_scatter(subs, "effective_discount_pct", "profit_margin_pct", "revenue",
                                              "sub_category", "Effective discount", "Profit margin")
        else:
            fig, note = charts.heatmap(pr.discount_margin_matrix(df), "pct", diverging=True,
                                       value_name="Margin")
            note = "Rows: sub-categories (best margin at the top). Columns: discount level. Blank = never sold at that discount."
        show_chart(fig, note, key="pr_profit_chart")

    # --- Pareto and loss-makers --------------------------------------------------------------
    left, right = st.columns([1, 1.25], gap="medium")
    with left, card("prod-pareto"):
        card_title("Revenue concentration", "Do a few products make most of the revenue?")
        perf = pr.product_performance(df)
        fig, note = charts.pareto_chart(pr.pareto(perf), "products")
        show_chart(fig, note, key="pr_pareto_chart")
    with right, card("prod-losers"):
        losers = pr.loss_making_products(perf)
        card_title("Loss-making products", f"{len(losers):,} products lost money in the selection")
        if losers.empty:
            st.success("No product lost money in this selection.")
        else:
            cols = ["product_name", "sub_category", "revenue", "profit", "profit_margin_pct",
                    "effective_discount_pct"]
            data_table(losers[cols], money=["revenue", "profit"],
                       pct=["profit_margin_pct", "effective_discount_pct"], height=320, key="pr_losers")
            csv_download(losers[cols], "loss_making_products.csv", key="pr_losers_csv")
