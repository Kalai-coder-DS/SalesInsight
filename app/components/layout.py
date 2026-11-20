"""Reusable page building blocks: header, cards, chart selectors, empty states."""

from __future__ import annotations

from html import escape

import streamlit as st

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "salesinsight_chart"},
}


def page_header(title: str, subtitle: str, eyebrow: str = "Analytics", chips: list[str] | None = None) -> None:
    chip_html = ""
    if chips:
        chip_html = "<div class='si-chips'>" + "".join(
            f"<span class='si-chip si-chip-accent'>{escape(c)}</span>" for c in chips) + "</div>"
    else:
        chip_html = "<div class='si-chips'><span class='si-chip'>All data - no filters applied</span></div>"
    st.markdown(
        f"<div class='si-header'><span class='si-eyebrow'>{escape(eyebrow)}</span>"
        f"<h1 class='si-title'>{escape(title)}</h1>"
        f"<div class='si-subtitle'>{escape(subtitle)}</div>{chip_html}</div>",
        unsafe_allow_html=True)


def card(key: str):
    """A styled panel. Use as: `with card("revenue-trend"): ...`"""
    return st.container(key=f"card-{key}")


def card_title(title: str, subtitle: str | None = None) -> None:
    sub = f"<div class='si-card-sub'>{escape(subtitle)}</div>" if subtitle else ""
    head = f"<div class='si-card-title'>{escape(title)}</div>" if title else ""
    st.markdown(head + sub, unsafe_allow_html=True)


def chart_switch(key: str, options: list[str], default: str | None = None, label: str = "Chart type") -> str:
    """Segmented buttons to choose a chart type (or a metric). Always returns a valid option."""
    default = default or options[0]
    choice = st.segmented_control(label, options, default=default, key=key,
                                  label_visibility="collapsed")
    return choice if choice in options else default


def show_chart(fig, note: str | None = None, key: str | None = None) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG, key=key)
    if note:
        st.caption(note)


def empty_state(message: str = "No data matches the current filters.",
                hint: str = "Change or reset the filters in the sidebar.") -> None:
    st.markdown(f"<div class='si-empty'><h3>{escape(message)}</h3><p>{escape(hint)}</p></div>",
                unsafe_allow_html=True)


def highlight_list(items: list[dict]) -> None:
    html = "".join(f"<div class='si-highlight'><b>{escape(i['title'])}</b><p>{escape(i['text'])}</p></div>"
                   for i in items)
    st.markdown(html, unsafe_allow_html=True)


COLUMN_LABELS = {
    "product_name": "Product", "product_key": "Product key", "product_id": "Product ID",
    "category": "Category", "sub_category": "Sub-category", "region": "Region", "state": "State",
    "city": "City", "segment": "Segment", "customer_id": "Customer ID", "customer_name": "Customer",
    "revenue": "Revenue", "sales": "Sales", "profit": "Profit", "units_sold": "Units",
    "quantity": "Quantity", "total_orders": "Orders", "order_lines": "Order lines",
    "profit_margin_pct": "Margin", "effective_discount_pct": "Discount", "discount": "Discount",
    "loss_lines_pct": "Lines at a loss", "share_of_revenue_pct": "Share of revenue",
    "order_id": "Order ID", "order_date": "Order date", "ship_date": "Ship date",
    "rfm_segment": "RFM segment", "total_customers": "Customers", "avg_recency_days": "Days since last order",
    "avg_orders": "Orders per customer", "avg_revenue": "Revenue per customer", "recency_days": "Days since last order",
    "share_of_customers_pct": "Share of customers", "order_year": "Year", "ship_mode": "Ship mode",
    "discount_band": "Discount band", "unit_price": "Unit price", "gross_sales": "Sales before discount",
    "discount_amount": "Discount amount", "postal_code": "Postal code", "ship_days": "Days to ship",
    "is_loss": "Loss?", "order_month_name": "Month", "year_month": "Year-month", "order_weekday": "Weekday",
    "order_quarter": "Quarter", "order_month": "Month no.", "country": "Country", "row_id": "Row ID",
    "priority": "Priority", "area": "Area", "title": "Recommendation", "finding": "Finding",
    "action": "Action", "impact": "Expected impact",
}


def column_label(name: str) -> str:
    return COLUMN_LABELS.get(name, name.replace("_", " ").capitalize())


def data_table(df, money: list[str] = (), pct: list[str] = (), ints: list[str] = (),
               height: int | None = None, key: str | None = None) -> None:
    """A sortable table with friendly column names and readable number formats."""
    config = {c: st.column_config.Column(column_label(c)) for c in df.columns}
    config.update({c: st.column_config.NumberColumn(column_label(c), format="dollar")
                   for c in money if c in df.columns})
    config.update({c: st.column_config.NumberColumn(column_label(c), format="%.1f%%")
                   for c in pct if c in df.columns})
    config.update({c: st.column_config.NumberColumn(column_label(c), format="localized")
                   for c in ints if c in df.columns})
    kwargs = {"height": height} if height else {}
    st.dataframe(df, column_config=config, hide_index=True, width="stretch", key=key, **kwargs)


def csv_download(df, filename: str, label: str = "Download CSV", key: str | None = None) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename,
                       mime="text/csv", icon=":material/download:", key=key)


def recommendation_cards(recs: list) -> None:
    html = []
    for i, r in enumerate(recs, 1):
        badge = "si-badge si-badge-p1" if r.priority == 1 else "si-badge"
        html.append(
            f"<div class='si-rec'><div class='si-rec-head'>"
            f"<span class='{badge}'>Priority {r.priority}</span><span class='si-badge'>{escape(r.area)}</span>"
            f"<span class='si-rec-title'>{i}. {escape(r.title)}</span></div>"
            f"<p><b>Finding:</b> {escape(r.finding)}</p>"
            f"<p><b>Action:</b> {escape(r.action)}</p>"
            f"<p><b>Expected impact:</b> {escape(r.impact)}</p></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def text_download(text: str, filename: str, label: str, mime: str = "text/markdown",
                  key: str | None = None) -> None:
    st.download_button(label, text.encode("utf-8"), file_name=filename, mime=mime,
                       icon=":material/description:", key=key)
