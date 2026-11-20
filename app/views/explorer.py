"""Data Explorer: search, choose columns, summarise and export the filtered data."""

from __future__ import annotations

import streamlit as st

from components import caps
from components.context import get_context
from components.layout import card, card_title, chart_switch, csv_download, data_table, empty_state, page_header
from salesinsight import dashboard_data as dd
from salesinsight.filtering import describe_filters

GROUP_NEEDS = {"category": "category", "sub_category": "sub_category", "region": "region", "state": "state",
               "segment": "segment", "discount_band": "discount", "ship_mode": "shipping"}
GROUPS = {"Category": "category", "Sub-category": "sub_category", "Region": "region", "State": "state",
          "Segment": "segment", "Year": "order_year", "Ship mode": "ship_mode", "Discount band": "discount_band"}


def render() -> None:
    ctx = get_context()
    df = ctx.filtered
    page_header("Data Explorer", f"{len(df):,} order lines match the sidebar filters",
                eyebrow="Tools", chips=describe_filters(ctx.state))
    if df.empty:
        empty_state()
        return

    with card("exp-main"):
        top = st.columns([2.2, 1.3])
        with top[0]:
            query = st.text_input("Search", key="ex_query", placeholder="Search customers, products, cities, "
                                  "order IDs... (all words must match)", label_visibility="collapsed")
        with top[1]:
            view = chart_switch("ex_view", ["Order lines", "Summary"], label="View")
        rows = dd.search_rows(df, query)
        if query:
            st.caption(f"{len(rows):,} of {len(df):,} order lines contain: {query}")

        if rows.empty:
            st.info("No order lines match the search.")
            return

        if view == "Order lines":
            available = list(df.columns)
            defaults = [c for c in dd.DEFAULT_COLUMNS if c in available]
            st.session_state.setdefault("ex_cols", defaults)
            cols = st.multiselect("Columns", available, key="ex_cols") or defaults
            table = rows[cols].copy()
            if "order_date" in table:
                table["order_date"] = table["order_date"].dt.date
            if "ship_date" in table:
                table["ship_date"] = table["ship_date"].dt.date
            data_table(table, money=["sales", "profit", "unit_price", "gross_sales", "discount_amount"],
                       ints=["quantity"], height=520, key="ex_table")
            csv_download(table, "salesinsight_order_lines.csv", f"Download {len(table):,} rows (.csv)",
                         key="ex_csv")
        else:
            groups = [g for g, col in GROUPS.items() if col not in GROUP_NEEDS or caps.has(GROUP_NEEDS[col])]
            group_label = chart_switch("ex_group", groups, label="Group by")
            summary = dd.explorer_summary(rows, GROUPS[group_label])
            cols = [GROUPS[group_label], "revenue", "profit", "profit_margin_pct", "total_orders", "units_sold",
                    "effective_discount_pct", "loss_lines_pct", "share_of_revenue_pct"]
            data_table(summary[cols], money=["revenue", "profit"],
                       pct=["profit_margin_pct", "effective_discount_pct", "loss_lines_pct", "share_of_revenue_pct"],
                       ints=["total_orders", "units_sold"], height=520, key="ex_summary")
            csv_download(summary[cols], f"summary_by_{GROUPS[group_label]}.csv", "Download summary (.csv)",
                         key="ex_summary_csv")
        card_title("", "Tip: click a column header to sort; use the table's toolbar to search within it or "
                       "view it full screen.")
