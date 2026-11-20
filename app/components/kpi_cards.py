"""KPI cards: value plus change versus the previous period."""

from __future__ import annotations

from html import escape

import streamlit as st

from components import caps
from components.theme import fx
from salesinsight.kpis import format_value, short_money


def _value_text(card: dict) -> str:
    v = card["value"]
    if v is None:
        return "-"
    if card["kind"] == "money":
        return format_value(v, "money") if card["key"] == "avg_order_value" else short_money(v)
    if card["kind"] == "pct":
        return f"{v:.1f}%"
    return f"{int(v):,}"


def _delta_html(card: dict, compare_label: str | None) -> str:
    if compare_label is None or card["previous"] is None:
        return "<div class='si-kpi-delta si-flat'><span>Select a year to compare</span></div>"
    change = card["change"]
    if change is None:
        return (f"<div class='si-kpi-delta si-flat'>&#9679; <span>no % change "
                f"(earlier value {escape(_value_text({**card, 'value': card['previous']}))})</span></div>")
    unit = " pp" if card["unit"] == "pp" else "%"
    if abs(change) < 0.05:
        cls, arrow = "si-flat", "&#9679;"
    elif change > 0:
        cls, arrow = "si-up", "&#9650;"
    else:
        cls, arrow = "si-down", "&#9660;"
    return (f"<div class='si-kpi-delta {cls}'>{arrow} {abs(change):.1f}{unit} "
            f"<span>{escape(compare_label)}</span></div>")


def _grid_class(n: int, default: str) -> str:
    return default if n >= (6 if default == "" else 4) else f" si-cols-{max(n, 1)}"


def render_kpi_cards(cards: list[dict], compare_label: str | None) -> None:
    cards = [c for c in cards if caps.has(*caps.KPI_NEEDS.get(c["key"], set()))]
    html = "".join(
        f"<div class='si-kpi'><div class='si-kpi-label'>{escape(c['label'])}</div>"
        f"<div class='si-kpi-value'>{escape(fx(_value_text(c)))}</div>{fx(_delta_html(c, compare_label))}</div>"
        for c in cards)
    st.markdown(f"<div class='si-kpi-grid{_grid_class(len(cards), '')}'>{html}</div>", unsafe_allow_html=True)


def render_stat_cards(items: list[dict]) -> None:
    """Simple cards: label, big value and a grey line underneath (no comparison).
    Cards the active data cannot support are left out."""
    items = caps.keep(items)
    if not items:
        return
    html = "".join(
        f"<div class='si-kpi'><div class='si-kpi-label'>{escape(i['label'])}</div>"
        f"<div class='si-kpi-value'>{escape(fx(str(i['value'])))}</div>"
        f"<div class='si-kpi-delta si-flat'><span>{escape(fx(i.get('sub', '')))}</span></div></div>"
        for i in items)
    cls = " si-cols-4" if len(items) >= 4 else f" si-cols-{len(items)}"
    st.markdown(f"<div class='si-kpi-grid{cls}'>{html}</div>", unsafe_allow_html=True)
