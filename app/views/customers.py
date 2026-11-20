"""Page 5 - Customer Intelligence: segments, loyalty, RFM and best customers."""

from __future__ import annotations

import streamlit as st

from components import charts
from components.context import get_context
from components.kpi_cards import render_stat_cards
from components.layout import (card, card_title, chart_switch, csv_download, data_table, empty_state,
                               page_header, show_chart)
from components.theme import CUSTOMERS, PROFIT, REVENUE
from salesinsight import customers as cu
from salesinsight import dashboard_data as dd
from salesinsight.filtering import describe_filters


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    start, end = ctx.window
    page_header("Customer Intelligence", f"{start:%d %b %Y} - {end:%d %b %Y}  |  "
                f"{df['customer_id'].nunique():,} customers",
                chips=describe_filters(ctx.state))
    if df.empty:
        empty_state()
        return

    render_stat_cards(dd.customer_stats(df))
    customers = cu.customer_table(df)

    # --- Segments ----------------------------------------------------------------------
    left, right = st.columns(2, gap="medium")
    with left, card("cust-segments"):
        card_title("Customer segments", "Consumer, Corporate and Home Office")
        s_metric = chart_switch("cu_s_metric", list(dd.SEGMENT_METRICS), label="Metric")
        s_kind = chart_switch("cu_s_kind", charts.CATEGORY_KINDS)
        col, kind = dd.SEGMENT_METRICS[s_metric]
        seg = cu.segment_performance(df)
        fig, note = charts.category_chart(seg, "segment", col, s_kind, value_kind=kind, value_name=s_metric,
                                          height=340)
        show_chart(fig, note, key="cu_segments_chart")
    with right, card("cust-frequency"):
        card_title("How often customers order", "Share of customers vs share of revenue")
        freq = cu.order_frequency(customers)
        fig, note = charts.paired_bars(freq, "order_band",
                                       ("share_of_customers_pct", "Share of customers", CUSTOMERS),
                                       ("share_of_revenue_pct", "Share of revenue", REVENUE), height=380)
        show_chart(fig, note, key="cu_freq_chart")

    # --- RFM ---------------------------------------------------------------------------
    with card("cust-rfm"):
        top = st.columns([2.2, 2])
        with top[0]:
            card_title("RFM segments", "Recency, frequency and monetary value, each scored 1-5")
        with top[1]:
            r_view = chart_switch("cu_rfm_view", ["Share bars", "Treemap", "Table"], label="View")
        if len(customers) < 5:
            st.info("RFM needs at least 5 customers. Widen the filters.")
        else:
            rfm = cu.rfm_summary(cu.rfm_table(customers))
            if r_view == "Share bars":
                fig, note = charts.paired_bars(rfm, "rfm_segment",
                                               ("share_of_customers_pct", "Share of customers", CUSTOMERS),
                                               ("share_of_revenue_pct", "Share of revenue", REVENUE),
                                               horizontal=True)
                show_chart(fig, note, key="cu_rfm_chart")
            elif r_view == "Treemap":
                fig, note = charts.category_chart(rfm, "rfm_segment", "revenue", "Treemap",
                                                  value_name="Revenue", height=420)
                show_chart(fig, "Box size = revenue from each segment.", key="cu_rfm_treemap")
            else:
                cols = ["rfm_segment", "total_customers", "revenue", "avg_recency_days", "avg_orders",
                        "avg_revenue", "share_of_customers_pct", "share_of_revenue_pct"]
                data_table(rfm[cols], money=["revenue", "avg_revenue"],
                           pct=["share_of_customers_pct", "share_of_revenue_pct"],
                           ints=["total_customers"], key="cu_rfm_tbl")
            st.caption("Champions: bought recently, often, a lot. At risk: used to buy often, not recently. "
                       "Lost: not recently and rarely.")

    # --- New vs returning + Pareto -------------------------------------------------------
    left, right = st.columns(2, gap="medium")
    with left, card("cust-newret"):
        card_title("New vs returning customers", "Revenue each year")
        nr_kind = chart_switch("cu_nr_kind", ["Stacked bars", "Stacked area"])
        nvr = dd.new_vs_returning_long(df)
        fig, note = charts.stacked_chart(nvr, "label", [("revenue_returning", "Returning customers", REVENUE),
                                                        ("revenue_new", "New customers", CUSTOMERS)], nr_kind)
        retention = nvr["retention_pct"].dropna()
        note = (f"Retention in {nvr['label'].iloc[-1]}: {retention.iloc[-1]:.1f}% of the previous year's "
                "customers bought again." if len(retention) else
                "The first year of the selection has no earlier year, so every customer counts as new.")
        show_chart(fig, note, key="cu_newret_chart")
    with right, card("cust-pareto"):
        card_title("Revenue concentration", "How much revenue depends on the top customers")
        fig, note = charts.pareto_chart(cu.customer_pareto(customers), "customers")
        show_chart(fig, note, key="cu_pareto_chart")

    # --- Top customers -----------------------------------------------------------------------
    with card("cust-top"):
        top = st.columns([1.6, 1.1, 1.8, 1.2, 1.2])
        with top[0]:
            card_title("Top customers")
        with top[1]:
            direction = chart_switch("cu_t_dir", ["Top", "Bottom"], label="Show")
        with top[2]:
            t_metric = chart_switch("cu_t_metric", ["Revenue", "Profit", "Orders"], label="Metric")
        with top[3]:
            t_view = chart_switch("cu_t_view", ["Bars", "Table"], label="View")
        with top[4]:
            n = st.slider("How many", 5, 25, 10, step=5, key="cu_t_n")
        column = {"Revenue": "revenue", "Profit": "profit", "Orders": "total_orders"}[t_metric]
        ranked = customers.sort_values([column, "customer_id"], ascending=[direction == "Bottom", True]).head(n)
        if t_view == "Bars":
            fig, note = charts.ranked_bar(ranked, "customer_name", column,
                                          "int" if t_metric == "Orders" else "money", t_metric,
                                          PROFIT if t_metric == "Profit" else REVENUE,
                                          extra={"segment": ("Segment", "text"), "total_orders": ("Orders", "int")})
            show_chart(fig, note, key="cu_top_chart")
        else:
            cols = ["customer_name", "segment", "total_orders", "revenue", "profit", "profit_margin_pct",
                    "recency_days"]
            data_table(ranked[cols], money=["revenue", "profit"], pct=["profit_margin_pct"],
                       ints=["total_orders", "recency_days"], key="cu_top_tbl")
            csv_download(ranked[cols], f"{direction.lower()}_{n}_customers_by_{t_metric.lower()}.csv",
                         key="cu_top_csv")
