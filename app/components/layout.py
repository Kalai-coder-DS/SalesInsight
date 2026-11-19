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
    st.markdown(f"<div class='si-card-title'>{escape(title)}</div>{sub}", unsafe_allow_html=True)


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
