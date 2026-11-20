"""KPI cards: value plus change versus the previous period."""

from __future__ import annotations

from html import escape

import streamlit as st

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


def render_kpi_cards(cards: list[dict], compare_label: str | None) -> None:
    html = "".join(
        f"<div class='si-kpi'><div class='si-kpi-label'>{escape(c['label'])}</div>"
        f"<div class='si-kpi-value'>{escape(_value_text(c))}</div>{_delta_html(c, compare_label)}</div>"
        for c in cards)
    st.markdown(f"<div class='si-kpi-grid'>{html}</div>", unsafe_allow_html=True)


def render_stat_cards(items: list[dict]) -> None:
    """Simple cards: label, big value and a grey line underneath (no comparison)."""
    html = "".join(
        f"<div class='si-kpi'><div class='si-kpi-label'>{escape(i['label'])}</div>"
        f"<div class='si-kpi-value'>{escape(str(i['value']))}</div>"
        f"<div class='si-kpi-delta si-flat'><span>{escape(i.get('sub', ''))}</span></div></div>"
        for i in items)
    st.markdown(f"<div class='si-kpi-grid si-cols-4'>{html}</div>", unsafe_allow_html=True)
