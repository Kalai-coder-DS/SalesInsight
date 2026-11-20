"""Show only what the active data supports (Phase 14C).

Demo data: everything is available (capabilities is None), so every page looks
exactly as before. Uploaded data: prepare_sales() lists its capabilities
(profit, orders, customers, region, ...). Pages ask this module before showing
a metric, a chart option or a card, and show a short "not available" note
instead of misleading charts (for example $0 profit when there is no profit data).
"""

from __future__ import annotations

from html import escape

import streamlit as st

from components.context import get_context

# Metric option label -> capabilities it needs
METRIC_NEEDS: dict[str, set[str]] = {
    "Profit": {"profit"}, "Margin": {"profit"}, "Orders": {"orders"}, "Units": {"quantity"},
    "Customers": {"customers"}, "Avg order value": {"orders"}, "Discount": {"discount"},
}

# Stat-card labels and highlight titles -> capabilities they need
CARD_NEEDS: dict[str, set[str]] = {
    "Products sold": {"products"}, "Products making 80% of revenue": {"products"},
    "Loss-making products": {"products", "profit"}, "Most profitable sub-category": {"sub_category", "profit"},
    "Largest region": {"region"}, "Best margin region": {"region", "profit"},
    "Loss-making states": {"state", "profit"}, "Discount vs margin (states)": {"state", "profit", "discount"},
    "Customers": {"customers"}, "Repeat customers": {"customers", "orders"},
    "Orders per customer": {"customers", "orders"}, "Top 20% of customers": {"customers"},
    "Lost on discounts above 20%": {"discount", "profit"}, "Lines losing money": {"profit"},
}

# KPI card keys (filtering.KPI_CARDS) -> capabilities
KPI_NEEDS: dict[str, set[str]] = {
    "total_profit": {"profit"}, "profit_margin_pct": {"profit"}, "total_orders": {"orders"},
    "avg_order_value": {"orders"}, "total_customers": {"customers"},
}

# What to add to a file to unlock a capability (shown to the visitor)
UNLOCK_HINT: dict[str, str] = {
    "orders": "an order or invoice ID", "customers": "a customer name or ID", "products": "a product name",
    "quantity": "a quantity column", "profit": "a profit or cost column", "discount": "a discount column",
    "category": "a category column", "sub_category": "a sub-category column", "region": "a region column",
    "state": "a state column", "us_map": "US state names", "city": "a city column",
    "segment": "a customer segment column", "shipping": "a ship date",
}

# Breakdown dimensions in order of preference: column -> label
DIMENSIONS: dict[str, str] = {"category": "Category", "region": "Region", "segment": "Segment",
                              "sub_category": "Sub-category", "state": "State"}


def current():
    try:
        return get_context().capabilities
    except Exception:  # noqa: BLE001 - outside a page run
        return None


def has(*needed: str, caps=None) -> bool:
    caps = current() if caps is None else caps
    return caps is None or all(n in caps for n in needed)


def missing(*needed: str, caps=None) -> list[str]:
    caps = current() if caps is None else caps
    return [] if caps is None else [n for n in needed if n not in caps]


def options(labels: list[str], caps=None) -> list[str]:
    """Metric options the data supports (Revenue is always available)."""
    return [x for x in labels if has(*METRIC_NEEDS.get(x, set()), caps=caps)]


def keep(items: list[dict], caps=None) -> list[dict]:
    """Drop stat cards / highlights whose numbers the data cannot support."""
    return [i for i in items if has(*CARD_NEEDS.get(i.get("label") or i.get("title", ""), set()), caps=caps)]


def dimensions(caps=None) -> list[str]:
    return [d for d in DIMENSIONS if has(d, caps=caps)]


def hint(needed) -> str:
    parts = [UNLOCK_HINT.get(n, n) for n in needed]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def unavailable_note(needed, what: str = "This view") -> None:
    st.markdown(f"<div class='si-unavailable'><b>{escape(what)} is not available for your data.</b>"
                f"<p>Add {escape(hint(needed))} to your file and upload it again on the Data Source page.</p></div>",
                unsafe_allow_html=True)


def unavailable_card(key: str, title: str, needed, subtitle: str | None = None) -> None:
    from components.layout import card, card_title
    with card(key):
        card_title(title, subtitle)
        unavailable_note(needed, "This chart")


def page_unavailable(title: str, needed) -> None:
    """Whole page not possible (e.g. Customer Intelligence without customers)."""
    from components.layout import page_header
    page_header(title, "Not available for the uploaded data", eyebrow="Analytics")
    unavailable_note(needed, title)


# Table / hover columns -> capability (columns not listed are always shown)
COLUMN_NEEDS: dict[str, str] = {
    "category": "category", "sub_category": "sub_category", "region": "region", "state": "state",
    "segment": "segment", "units_sold": "quantity", "profit": "profit", "profit_margin_pct": "profit",
    "effective_discount_pct": "discount", "total_orders": "orders",
}


def columns(cols: list[str], caps=None) -> list[str]:
    """Table columns the data supports."""
    return [c for c in cols if c not in COLUMN_NEEDS or has(COLUMN_NEEDS[c], caps=caps)]


def extras(extra: dict, caps=None) -> dict:
    """Hover details (column -> (label, kind)) the data supports."""
    return {c: v for c, v in extra.items() if c not in COLUMN_NEEDS or has(COLUMN_NEEDS[c], caps=caps)}
