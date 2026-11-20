"""Plotly chart builders. Each chart can be drawn in several forms; the page
passes the user's choice in `kind`, so the selector really changes the chart.

All builders return (figure, note). `note` is a short message when a chart
type cannot show the data (e.g. a pie cannot show negative profit) and a
safer type was used instead; otherwise it is None.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from components.theme import GAIN, LOSS, PROFIT, REVENUE, SERIES, currency_symbol, fx, palette, plotly_layout
from salesinsight.kpis import short_money

CATEGORY_KINDS = ["Bar", "Horizontal bar", "Pie", "Donut", "Treemap"]
TIME_KINDS = ["Line", "Area", "Bar"]
PART_OF_WHOLE = {"Pie", "Donut", "Treemap"}


def _cur() -> str:
    """Currency of the active data ("$" for the demo data)."""
    return currency_symbol()


def _money_axis() -> tuple[str, str]:
    """(tickformat, tickprefix) for money axes. "$" keeps Plotly's own dollar format
    (exactly as before Phase 14); other currencies use a prefix."""
    return ("$~s", "") if _cur() == "$" else ("~s", _cur())


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _fmt(value: float, value_kind: str) -> str:
    if value_kind == "money":
        return fx(short_money(value))
    if value_kind == "pct":
        return f"{value:.1f}%"
    return f"{value:,.0f}"


def _hover_value(value_kind: str, axis: str = "y") -> str:
    if value_kind == "money":
        return f"{_cur()}%{{{axis}:,.0f}}"
    if value_kind == "pct":
        return f"%{{{axis}:.1f}}%"
    return f"%{{{axis}:,.0f}}"


def _finish(fig: go.Figure, height: int, showlegend: bool, value_kind: str | None = None,
            value_axis: str = "y") -> go.Figure:
    fig.update_layout(**plotly_layout(), height=height, showlegend=showlegend)
    if value_kind:
        money_fmt, prefix = _money_axis()
        fmt = {"money": money_fmt, "pct": ".0f", "int": "~s"}[value_kind]
        suffix = "%" if value_kind == "pct" else ""
        prefix = prefix if value_kind == "money" else ""
        if value_axis == "y":
            fig.update_yaxes(tickformat=fmt, ticksuffix=suffix, tickprefix=prefix)
        else:
            fig.update_xaxes(tickformat=fmt, ticksuffix=suffix, tickprefix=prefix)
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
        money = f"{_cur()}%{{value:,.0f}}" if value_kind == "money" else "%{value:,.0f}"
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
        money = f"{_cur()}%{{value:,.0f}}" if value_kind == "money" else "%{value:,.0f}"
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
def time_chart(ts: pd.DataFrame, series: list[tuple], kind: str = "Line",
               value_kind: str = "money", height: int = 380) -> tuple[go.Figure, str | None]:
    """series: list of (column, display name, colour[, "line"]). Same unit for all series (one axis).

    A 4th element "line" draws that series as a dashed line on every chart type
    (used for moving averages on top of bars).
    """
    fig = go.Figure()
    markers = len(ts) <= 24
    hover_val = _hover_value(value_kind)
    for spec in series:
        column, name, color = spec[:3]
        force_line = len(spec) > 3 and spec[3] == "line"
        hover = f"%{{customdata}}<br>{name}: {hover_val}<extra></extra>"
        if force_line:
            x = ts["label"] if kind == "Bar" else ts["period"]
            fig.add_trace(go.Scatter(x=x, y=ts[column], name=name, customdata=ts["label"],
                                     hovertemplate=hover, mode="lines",
                                     line=dict(color=color, width=2.5, dash="dash")))
            continue
        if kind == "Bar":
            fig.add_trace(go.Bar(x=ts["label"], y=ts[column], name=name, marker_color=color,
                                 marker_line_width=0, customdata=ts["label"], hovertemplate=hover))
        else:
            fig.add_trace(go.Scatter(
                x=ts["period"], y=ts[column], name=name, customdata=ts["label"], hovertemplate=hover,
                mode="lines+markers" if markers else "lines",
                # Straight segments: a smoothed curve can overshoot and show values that
                # are not in the data (e.g. dips below zero between two months).
                line=dict(color=color, width=2.5, shape="linear"),
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
        text=[fx(short_money(v)) for v in bridge["value"]], textposition="outside", cliponaxis=False,
        increasing=dict(marker=dict(color=GAIN)),
        decreasing=dict(marker=dict(color=LOSS)),
        totals=dict(marker=dict(color="#8b5cf6")),
        connector=dict(line=dict(color=t["grid"], width=1, dash="dot")),
        hovertemplate=f"%{{x}}: {_cur()}%{{y:,.0f}}<extra></extra>"))
    return _finish(fig, height, False, "money"), None


# ---------------------------------------------------------------------------
# 13B charts
# ---------------------------------------------------------------------------
def _short(text: str, limit: int = 42) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def diverging_scale() -> list:
    mid = palette()["panel_2"]
    return [[0.0, "#b91c1c"], [0.35, "#f87171"], [0.5, mid], [0.65, "#93c5fd"], [1.0, "#1d4ed8"]]


def sequential_scale() -> list:
    from components.theme import current_theme
    if current_theme() == "dark":
        return [[0, "#172036"], [0.35, "#1d4ed8"], [0.7, "#60a5fa"], [1, "#dbeafe"]]
    return [[0, "#eff6ff"], [0.35, "#93c5fd"], [0.7, "#3b82f6"], [1, "#1e3a8a"]]


def ranked_bar(data: pd.DataFrame, label: str, value: str, value_kind: str = "money",
               value_name: str = "Revenue", color: str = REVENUE,
               extra: dict | None = None) -> tuple[go.Figure, str | None]:
    """Horizontal ranking (biggest at the top). Long names are shortened on the axis;
    the full name and extra columns show on hover."""
    d = data.reset_index(drop=True).iloc[::-1]
    ids = [f"r{i}" for i in d.index]
    values = d[value].astype(float)
    colors = [LOSS if v < 0 else color for v in values]
    custom = [d[label].astype(str)]
    hover = "<b>%{customdata[0]}</b><br>" + f"{value_name}: {_hover_value(value_kind, 'x')}"
    for i, (col, (name, kind)) in enumerate((extra or {}).items(), start=1):
        custom.append(d[col])
        fmt = {"money": f"{_cur()}%{{customdata[{i}]:,.0f}}", "pct": f"%{{customdata[{i}]:.1f}}%",
               "int": f"%{{customdata[{i}]:,.0f}}", "text": f"%{{customdata[{i}]}}"}[kind]
        hover += f"<br>{name}: {fmt}"
    fig = go.Figure(go.Bar(
        y=ids, x=values, orientation="h", marker_color=colors, marker_line_width=0,
        customdata=list(zip(*custom)), hovertemplate=hover + "<extra></extra>",
        text=[_fmt(v, value_kind) for v in values], textposition="outside", cliponaxis=False))
    fig.update_yaxes(tickvals=ids, ticktext=[_short(t) for t in d[label].astype(str)])
    height = max(320, 34 * len(d) + 60)
    fig.update_layout(bargap=0.28)
    return _finish(fig, height, False, value_kind, value_axis="x"), None


def hierarchy_chart(h: pd.DataFrame, kind: str = "Treemap", size: str = "revenue",
                    size_name: str = "Revenue", height: int = 460) -> tuple[go.Figure, str | None]:
    """Category > sub-category. Size = revenue or units; colour = profit margin
    (red = loss, blue = profit), so profitability is visible at a glance."""
    if kind == "Bar":
        fig = go.Figure()
        for i, (cat, g) in enumerate(h.groupby("category")):
            fig.add_trace(go.Bar(x=g["sub_category"], y=g[size], name=cat, marker_color=SERIES[i],
                                 marker_line_width=0, customdata=g["profit_margin_pct"],
                                 hovertemplate=f"%{{x}}<br>{size_name}: " +
                                 (f"{_cur()}%{{y:,.0f}}" if size == "revenue" else "%{y:,.0f}") +
                                 "<br>Margin: %{customdata:.1f}%<extra>" + cat + "</extra>"))
        fig.update_layout(bargap=0.25)
        fig.update_xaxes(tickangle=-35)
        return _finish(fig, height, True, "money" if size == "revenue" else "int"), None

    cats = h.groupby("category").agg(revenue=("revenue", "sum"), profit=("profit", "sum"),
                                     units_sold=("units_sold", "sum")).reset_index()
    cats["profit_margin_pct"] = 100 * cats["profit"] / cats["revenue"]
    ids = list(cats["category"]) + [f"{c}/{s}" for c, s in zip(h["category"], h["sub_category"])]
    labels = list(cats["category"]) + list(h["sub_category"])
    parents = [""] * len(cats) + list(h["category"])
    values = list(cats[size]) + list(h[size])
    margins = list(cats["profit_margin_pct"]) + list(h["profit_margin_pct"])
    limit = max(5.0, float(pd.Series(margins).abs().quantile(0.9)))
    value_fmt = f"{_cur()}%{{value:,.0f}}" if size == "revenue" else "%{value:,.0f}"
    common = dict(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=margins, colorscale=diverging_scale(), cmid=0, cmin=-limit, cmax=limit,
                    line=dict(color=palette()["panel"], width=2),
                    colorbar=dict(title=dict(text="Margin %", side="right"), thickness=12,
                                  ticksuffix="%", outlinewidth=0)),
        customdata=margins,
        hovertemplate=f"<b>%{{label}}</b><br>{size_name}: {value_fmt}<br>Margin: %{{customdata:.1f}}%"
                      "<extra></extra>",
    )
    trace = (go.Treemap(**common, texttemplate="<b>%{label}</b><br>%{customdata:.1f}% margin")
             if kind == "Treemap" else
             go.Sunburst(**common, insidetextorientation="radial"))
    fig = go.Figure(trace)
    fig.update_layout(margin=dict(l=0, r=0, t=8, b=0))
    return _finish(fig, height, False), None


def heatmap(matrix: pd.DataFrame, value_kind: str = "money", diverging: bool = False,
            value_name: str = "Revenue", height: int | None = None) -> tuple[go.Figure, str | None]:
    z = matrix.astype(float)
    text_fmt = {"money": "%{z:$.3s}" if _cur() == "$" else f"{_cur()}%{{z:.3s}}", "pct": "%{z:.0f}%", "int": "%{z:,.0f}"}[value_kind]
    hover_fmt = {"money": f"{_cur()}%{{z:,.0f}}", "pct": "%{z:.1f}%", "int": "%{z:,.0f}"}[value_kind]
    kwargs = dict(colorscale=sequential_scale())
    if diverging:
        limit = max(5.0, float(pd.Series(z.to_numpy().ravel()).abs().quantile(0.95)))
        kwargs = dict(colorscale=diverging_scale(), zmid=0, zmin=-limit, zmax=limit)
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=[str(c) for c in z.columns], y=[str(i) for i in z.index],
        texttemplate=text_fmt, textfont=dict(size=11), xgap=3, ygap=3, hoverongaps=False,
        hovertemplate=f"%{{y}} / %{{x}}<br>{value_name}: {hover_fmt}<extra></extra>",
        colorbar=dict(thickness=12, outlinewidth=0,
                      ticksuffix="%" if value_kind == "pct" else "",
                      tickprefix=_cur() if value_kind == "money" else ""),
        **kwargs))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, side="top")
    return _finish(fig, height or max(300, 38 * len(z) + 90), False), None


def diverging_bars(data: pd.DataFrame, label: str, value: str, value_name: str = "Profit",
                   value_kind: str = "money") -> tuple[go.Figure, str | None]:
    """Horizontal bars sorted by value; profits blue, losses red (with a legend)."""
    d = data.sort_values(value)
    fig = go.Figure()
    for name, mask, color in (("Loss", d[value] < 0, LOSS), ("Profit", d[value] >= 0, GAIN)):
        part = d[mask]
        if part.empty:
            continue
        fig.add_trace(go.Bar(
            y=part[label], x=part[value], orientation="h", name=name, marker_color=color,
            marker_line_width=0, text=[_fmt(v, value_kind) for v in part[value]],
            textposition="outside", cliponaxis=False,
            hovertemplate=f"%{{y}}<br>{value_name}: {_hover_value(value_kind, 'x')}<extra></extra>"))
    fig.update_yaxes(categoryorder="array", categoryarray=list(d[label]))
    fig.update_layout(barmode="overlay", bargap=0.3)
    return _finish(fig, max(320, 30 * len(d) + 80), True, value_kind, value_axis="x"), None


def bubble_scatter(data: pd.DataFrame, x: str, y: str, size: str, label: str,
                   x_name: str, y_name: str, x_kind: str = "pct", y_kind: str = "pct",
                   size_name: str = "Revenue") -> tuple[go.Figure, str | None]:
    """Each bubble is one item (e.g. a sub-category); bubble size = revenue.
    Red = loss-making, blue = profitable. A dashed least-squares line shows the trend."""
    import numpy as np

    d = data.dropna(subset=[x, y])
    sizes = d[size].clip(lower=0)
    ref = sizes.max() or 1
    colors = [LOSS if v < 0 else GAIN for v in d[y]]
    fig = go.Figure(go.Scatter(
        x=d[x], y=d[y], mode="markers+text", text=d[label], textposition="top center",
        textfont=dict(size=11, color=palette()["muted"]),
        marker=dict(size=12 + 38 * (sizes / ref) ** 0.5, color=colors, opacity=0.85,
                    line=dict(color=palette()["panel"], width=2)),
        customdata=d[size],
        hovertemplate=(f"<b>%{{text}}</b><br>{x_name}: {_hover_value(x_kind, 'x')}"
                       f"<br>{y_name}: {_hover_value(y_kind)}"
                       f"<br>{size_name}: {_cur()}%{{customdata:,.0f}}<extra></extra>")))
    note = None
    if len(d) >= 3 and d[x].nunique() > 1:
        slope, intercept = np.polyfit(d[x], d[y], 1)
        xs = np.linspace(d[x].min(), d[x].max(), 20)
        fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines", name="Trend",
                                 line=dict(color=palette()["muted"], dash="dash", width=1.5),
                                 hoverinfo="skip"))
        corr = float(np.corrcoef(d[x], d[y])[0, 1])
        note = f"Correlation between {x_name.lower()} and {y_name.lower()}: {corr:.2f}"
    fig.add_hline(y=0, line=dict(color=palette()["muted"], width=1))
    fig = _finish(fig, 440, False, y_kind)
    fig.update_xaxes(ticksuffix="%" if x_kind == "pct" else "",
                     tickformat=_money_axis()[0] if x_kind == "money" else None,
                     tickprefix=_money_axis()[1] if x_kind == "money" else "", title_text=x_name)
    fig.update_yaxes(title_text=y_name)
    return fig, note


def pareto_chart(par: pd.DataFrame, entity: str = "products") -> tuple[go.Figure, str | None]:
    rank_col = "rank_pct" if "rank_pct" in par.columns else "product_rank_pct"
    x = [0, *par[rank_col]]
    y = [0, *par["cum_share_pct"]]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=REVENUE, width=3),
                               fill="tozeroy", fillcolor=_rgba(REVENUE, 0.12), name="Cumulative revenue",
                               hovertemplate=f"Top %{{x:.1f}}% of {entity}<br>%{{y:.1f}}% of revenue"
                                             "<extra></extra>"))
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Equal share",
                             line=dict(color=palette()["muted"], dash="dot", width=1), hoverinfo="skip"))
    n80 = int((par["cum_share_pct"] < 80).sum())
    x80 = float(par[rank_col].iloc[min(n80, len(par) - 1)])
    fig.add_hline(y=80, line=dict(color=palette()["muted"], dash="dash", width=1))
    fig.add_vline(x=x80, line=dict(color=palette()["muted"], dash="dash", width=1))
    fig.add_annotation(x=x80, y=80, text=f"<b>{x80:.0f}%</b> of {entity} make <b>80%</b> of revenue",
                       showarrow=True, arrowhead=0, arrowcolor=palette()["muted"], ax=110, ay=70,
                       bgcolor=palette()["panel_2"], bordercolor=palette()["border"], borderpad=6,
                       font=dict(color=palette()["text"], size=12))
    fig = _finish(fig, 400, True)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title_text=f"Share of {entity} (biggest first)")
    fig.update_yaxes(range=[0, 102], ticksuffix="%", title_text="Share of revenue")
    return fig, None


def growth_bars(g: pd.DataFrame, column: str, name: str = "Revenue growth") -> tuple[go.Figure, str | None]:
    d = g.dropna(subset=[column])
    colors = [LOSS if v < 0 else GAIN for v in d[column]]
    fig = go.Figure(go.Bar(
        x=d["label"], y=d[column], marker_color=colors, marker_line_width=0,
        text=[f"{v:+.1f}%" for v in d[column]], textposition="outside", cliponaxis=False,
        hovertemplate=f"%{{x}}<br>{name}: %{{y:+.1f}}%<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=palette()["muted"], width=1))
    fig.update_layout(bargap=0.35)
    return _finish(fig, 360, False, "pct"), None


def month_lines(m: pd.DataFrame, value_kind: str = "money", name: str = "Revenue") -> tuple[go.Figure, str | None]:
    """One line per year across Jan-Dec, to compare seasons year by year."""
    fig = go.Figure()
    for i, (year, row) in enumerate(m.iterrows()):
        fig.add_trace(go.Scatter(x=list(m.columns), y=row.to_numpy(), name=str(year), mode="lines+markers",
                                 line=dict(color=SERIES[i % len(SERIES)], width=2.5),
                                 marker=dict(size=7),
                                 hovertemplate=f"%{{x}} {year}<br>{name}: {_hover_value(value_kind)}"
                                               "<extra></extra>"))
    fig.update_layout(hovermode="x unified")
    return _finish(fig, 380, True, value_kind), None


def index_bars(season: pd.DataFrame) -> tuple[go.Figure, str | None]:
    colors = [REVENUE if v >= 100 else "#64748b" for v in season["index"]]
    fig = go.Figure(go.Bar(x=season["month"], y=season["index"], marker_color=colors, marker_line_width=0,
                           text=[f"{v:.0f}" for v in season["index"]], textposition="outside",
                           cliponaxis=False,
                           hovertemplate="%{x}<br>Index: %{y:.0f} (100 = average month)<extra></extra>"))
    fig.add_hline(y=100, line=dict(color=palette()["muted"], dash="dash", width=1),
                  annotation_text="Average month = 100", annotation_position="top left",
                  annotation_font=dict(color=palette()["muted"], size=11))
    fig.update_layout(bargap=0.3)
    return _finish(fig, 360, False), None


# ---------------------------------------------------------------------------
# 13C charts
# ---------------------------------------------------------------------------
def us_map(states: pd.DataFrame, value: str, value_kind: str = "money", value_name: str = "Revenue",
           diverging: bool = False, height: int = 520) -> tuple[go.Figure, str | None]:
    """Choropleth of US states. Diverging (red/blue around 0) for profit and margin."""
    d = states.dropna(subset=["code"])
    t = palette()
    scale = dict(colorscale=sequential_scale())
    if diverging:
        limit = max(1.0, float(d[value].abs().quantile(0.95)))
        scale = dict(colorscale=diverging_scale(), zmid=0, zmin=-limit, zmax=limit)
    hover_val = {"money": f"{_cur()}%{{z:,.0f}}", "pct": "%{z:.1f}%", "int": "%{z:,.0f}"}[value_kind]
    fig = go.Figure(go.Choropleth(
        locations=d["code"], z=d[value], locationmode="USA-states",
        marker_line_color=t["panel"], marker_line_width=1,
        customdata=list(zip(d["state"], d["region"], d["revenue"], d["profit_margin_pct"])),
        hovertemplate=(f"<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>{value_name}: {hover_val}"
                       f"<br>Revenue: {_cur()}%{{customdata[2]:,.0f}}<br>Margin: %{{customdata[3]:.1f}}%<extra></extra>"),
        colorbar=dict(thickness=12, outlinewidth=0, len=0.75,
                      tickprefix=_cur() if value_kind == "money" else "",
                      ticksuffix="%" if value_kind == "pct" else ""),
        **scale))
    fig.update_geos(scope="usa", bgcolor="rgba(0,0,0,0)", showlakes=False, showland=True,
                    landcolor=t["panel_2"], subunitcolor=t["panel"], showframe=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    note = None
    missing = states["code"].isna().sum()
    if missing:
        note = f"{missing} location(s) without a US state code are not shown on the map."
    return _finish(fig, height, False), note


def group_chart(data: pd.DataFrame, kind: str = "Line", value_kind: str = "money",
                value_name: str = "Revenue", height: int = 380) -> tuple[go.Figure, str | None]:
    """One series per group (columns: group, x, value). Colour follows the group, never its rank."""
    fig = go.Figure()
    groups = sorted(data["group"].unique())
    hover_val = _hover_value(value_kind)
    for i, grp in enumerate(groups):
        part = data[data["group"] == grp]
        color = SERIES[i % len(SERIES)]
        hover = f"{grp} %{{x}}<br>{value_name}: {hover_val}<extra></extra>"
        if kind == "Bar":
            fig.add_trace(go.Bar(x=part["x"], y=part["value"], name=grp, marker_color=color,
                                 marker_line_width=0, hovertemplate=hover))
        else:
            fig.add_trace(go.Scatter(x=part["x"], y=part["value"], name=grp, mode="lines+markers",
                                     line=dict(color=color, width=2.5, shape="linear"),
                                     marker=dict(size=8), hovertemplate=hover,
                                     stackgroup="one" if kind == "Stacked area" else None))
    if kind == "Bar":
        fig.update_layout(barmode="group", bargap=0.22, bargroupgap=0.06)
    return _finish(fig, height, True, value_kind), None


def paired_bars(data: pd.DataFrame, label: str, first: tuple[str, str, str], second: tuple[str, str, str],
                horizontal: bool = False, height: int | None = None) -> tuple[go.Figure, str | None]:
    """Two % series side by side per label, e.g. share of customers vs share of revenue."""
    fig = go.Figure()
    d = data.iloc[::-1] if horizontal else data
    for column, name, color in (first, second):
        values = d[column]
        common = dict(name=name, marker_color=color, marker_line_width=0,
                      text=[f"{v:.0f}%" for v in values], textposition="outside", cliponaxis=False)
        if horizontal:
            fig.add_trace(go.Bar(y=d[label], x=values, orientation="h",
                                 hovertemplate=f"%{{y}}<br>{name}: %{{x:.1f}}%<extra></extra>", **common))
        else:
            fig.add_trace(go.Bar(x=d[label], y=values,
                                 hovertemplate=f"%{{x}}<br>{name}: %{{y:.1f}}%<extra></extra>", **common))
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
    h = height or (max(320, 46 * len(d) + 90) if horizontal else 360)
    return _finish(fig, h, True, "pct", value_axis="x" if horizontal else "y"), None


def stacked_chart(data: pd.DataFrame, x: str, series: list[tuple[str, str, str]], kind: str = "Stacked bars",
                  value_kind: str = "money", height: int = 380) -> tuple[go.Figure, str | None]:
    """Stacked bars or stacked area, e.g. revenue from returning (bottom) and new (top) customers."""
    fig = go.Figure()
    hover_val = _hover_value(value_kind)
    for column, name, color in series:
        hover = f"%{{x}}<br>{name}: {hover_val}<extra></extra>"
        if kind == "Stacked bars":
            fig.add_trace(go.Bar(x=data[x], y=data[column], name=name, marker_color=color,
                                 marker_line_color=palette()["panel"], marker_line_width=2, hovertemplate=hover))
        else:
            fig.add_trace(go.Scatter(x=data[x], y=data[column], name=name, mode="lines", stackgroup="one",
                                     line=dict(color=color, width=2), fillcolor=_rgba(color, 0.45),
                                     hovertemplate=hover))
    if kind == "Stacked bars":
        fig.update_layout(barmode="stack", bargap=0.35)
    return _finish(fig, height, True, value_kind), None
