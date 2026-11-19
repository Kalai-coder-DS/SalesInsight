"""Plotly chart builders. Each chart can be drawn in several forms; the page
passes the user's choice in `kind`, so the selector really changes the chart.

All builders return (figure, note). `note` is a short message when a chart
type cannot show the data (e.g. a pie cannot show negative profit) and a
safer type was used instead; otherwise it is None.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from components.theme import GAIN, LOSS, PROFIT, REVENUE, SERIES, palette, plotly_layout
from salesinsight.kpis import short_money

CATEGORY_KINDS = ["Bar", "Horizontal bar", "Pie", "Donut", "Treemap"]
TIME_KINDS = ["Line", "Area", "Bar"]
PART_OF_WHOLE = {"Pie", "Donut", "Treemap"}


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _fmt(value: float, value_kind: str) -> str:
    if value_kind == "money":
        return short_money(value)
    if value_kind == "pct":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


def _hover_value(value_kind: str, axis: str = "y") -> str:
    if value_kind == "money":
        return f"$%{{{axis}:,.0f}}"
    if value_kind == "pct":
        return f"%{{{axis}:.1f}}%"
    return f"%{{{axis}:,.0f}}"


def _finish(fig: go.Figure, height: int, showlegend: bool, value_kind: str | None = None,
            value_axis: str = "y") -> go.Figure:
    fig.update_layout(**plotly_layout(), height=height, showlegend=showlegend)
    if value_kind:
        fmt = {"money": "$~s", "pct": ".0f", "int": "~s"}[value_kind]
        suffix = "%" if value_kind == "pct" else ""
        if value_axis == "y":
            fig.update_yaxes(tickformat=fmt, ticksuffix=suffix)
        else:
            fig.update_xaxes(tickformat=fmt, ticksuffix=suffix)
    return fig


# ---------------------------------------------------------------------------
# Categorical breakdowns: bar, horizontal bar, pie, donut, treemap
# ---------------------------------------------------------------------------
def category_chart(data: pd.DataFrame, label: str, value: str, kind: str = "Bar",
                   value_kind: str = "money", value_name: str = "Revenue",
                   height: int = 360) -> tuple[go.Figure, str | None]:
    note = None
    if kind in PART_OF_WHOLE and (data[value] < 0).any():
        note = f"{kind} charts cannot show negative values, so bars are shown instead."
        kind = "Bar"

    labels = data[label].astype(str).tolist()
    values = data[value].astype(float).tolist()
    bar_colors = [LOSS if v < 0 else (PROFIT if value_name == "Profit" else REVENUE) for v in values]
    t = palette()

    if kind == "Bar":
        fig = go.Figure(go.Bar(
            x=labels, y=values, marker_color=bar_colors, marker_line_width=0,
            text=[_fmt(v, value_kind) for v in values], textposition="outside", cliponaxis=False,
            hovertemplate=f"%{{x}}<br>{value_name}: {_hover_value(value_kind)}<extra></extra>"))
        fig.update_layout(bargap=0.35)
        return _finish(fig, height, False, value_kind), note

    if kind == "Horizontal bar":
        order = sorted(zip(values, labels, bar_colors))
        fig = go.Figure(go.Bar(
            y=[o[1] for o in order], x=[o[0] for o in order], orientation="h",
            marker_color=[o[2] for o in order], marker_line_width=0,
            text=[_fmt(o[0], value_kind) for o in order], textposition="outside", cliponaxis=False,
            hovertemplate=f"%{{y}}<br>{value_name}: {_hover_value(value_kind, 'x')}<extra></extra>"))
        fig.update_layout(bargap=0.3)
        return _finish(fig, height, False, value_kind, value_axis="x"), note

    if kind in ("Pie", "Donut"):
        money = "$%{value:,.0f}" if value_kind == "money" else "%{value:,.0f}"
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.58 if kind == "Donut" else 0, sort=False,
            marker=dict(colors=SERIES[:len(labels)], line=dict(color=t["panel"], width=2)),
            textinfo="percent", textfont=dict(size=13),
            hovertemplate=f"%{{label}}<br>{value_name}: {money} (%{{percent}})<extra></extra>"))
        if kind == "Donut":
            fig.add_annotation(text=f"<b>{_fmt(sum(values), value_kind)}</b><br>{value_name}",
                               showarrow=False, font=dict(size=14, color=t["text"]))
        return _finish(fig, height, True), note

    if kind == "Treemap":
        money = "$%{value:,.0f}" if value_kind == "money" else "%{value:,.0f}"
        fig = go.Figure(go.Treemap(
            labels=labels, parents=[""] * len(labels), values=values,
            marker=dict(colors=SERIES[:len(labels)], line=dict(color=t["panel"], width=2)),
            texttemplate=f"<b>%{{label}}</b><br>{money}<br>%{{percentRoot:.1%}}",
            hovertemplate=f"%{{label}}<br>{value_name}: {money}<extra></extra>"))
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        return _finish(fig, height, False), note

    raise ValueError(f"Unknown chart type: {kind}")


# ---------------------------------------------------------------------------
# Time series: line, area, bar
# ---------------------------------------------------------------------------
def time_chart(ts: pd.DataFrame, series: list[tuple[str, str, str]], kind: str = "Line",
               value_kind: str = "money", height: int = 380) -> tuple[go.Figure, str | None]:
    """series: list of (column, display name, colour). Same unit for all series (one axis)."""
    fig = go.Figure()
    markers = len(ts) <= 24
    hover_val = _hover_value(value_kind)
    for column, name, color in series:
        hover = f"%{{customdata}}<br>{name}: {hover_val}<extra></extra>"
        if kind == "Bar":
            fig.add_trace(go.Bar(x=ts["label"], y=ts[column], name=name, marker_color=color,
                                 marker_line_width=0, customdata=ts["label"], hovertemplate=hover))
        else:
            fig.add_trace(go.Scatter(
                x=ts["period"], y=ts[column], name=name, customdata=ts["label"], hovertemplate=hover,
                mode="lines+markers" if markers else "lines",
                line=dict(color=color, width=2.5, shape="spline", smoothing=0.6),
                marker=dict(size=7, color=color),
                fill="tozeroy" if kind == "Area" else None,
                fillcolor=_rgba(color, 0.18) if kind == "Area" else None))
    if kind == "Bar":
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
    fig.update_layout(hovermode="x unified" if kind != "Bar" else "closest")
    return _finish(fig, height, len(series) > 1, value_kind), None


# ---------------------------------------------------------------------------
# Waterfall: how each group adds to (or takes from) the total
# ---------------------------------------------------------------------------
def waterfall_chart(bridge: pd.DataFrame, height: int = 380) -> tuple[go.Figure, str | None]:
    t = palette()
    fig = go.Figure(go.Waterfall(
        x=bridge["label"], y=bridge["value"], measure=bridge["measure"],
        text=[short_money(v) for v in bridge["value"]], textposition="outside", cliponaxis=False,
        increasing=dict(marker=dict(color=GAIN)),
        decreasing=dict(marker=dict(color=LOSS)),
        totals=dict(marker=dict(color="#8b5cf6")),
        connector=dict(line=dict(color=t["grid"], width=1, dash="dot")),
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
    return _finish(fig, height, False, "money"), None
