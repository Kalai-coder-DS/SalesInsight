"""Shared chart style and the charts for each phase.

Style rules used in every chart:
- One colour per series, always in the same fixed order (revenue = blue,
  profit = orange), from a colour-blind-checked palette.
- Thin bars with a small white gap between them, light grid, no box around the plot.
- Text is dark grey, never the series colour.
- One y-axis per chart (two different measures -> two charts).
- Every chart is saved as a PNG in reports/figures/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files only; no window needed

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import pandas as pd  # noqa: E402

from salesinsight import config  # noqa: E402
from salesinsight.kpis import KPI_LABELS, format_value, short_money  # noqa: E402

# Validated categorical palette (light mode), fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
REVENUE_COLOR = SERIES[0]
PROFIT_COLOR = SERIES[1]

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BASELINE = "#b8b7b2"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.edgecolor": BASELINE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "ytick.left": False,
        "text.color": TEXT_PRIMARY,
        "legend.frameon": False,
        "lines.linewidth": 2,
    })


def save_figure(fig: plt.Figure, name: str, folder: Path | None = None) -> Path:
    folder = Path(folder) if folder else config.FIGURES_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def axis_money(value: float) -> str:
    """Axis labels without decimals: $0, $200K, $1.5M."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:g}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:g}K"
    return f"{sign}${v:g}"


def money_axis(ax: plt.Axes) -> None:
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: axis_money(v)))


# ---------------------------------------------------------------------------
# Phase 5 charts
# ---------------------------------------------------------------------------
TILE_KEYS = [
    "total_revenue", "total_profit", "profit_margin_pct", "total_orders",
    "avg_order_value", "total_customers", "effective_discount_pct", "loss_lines_pct",
]


def plot_kpi_tiles(kpis: dict[str, float], folder: Path | None = None) -> Path:
    """A 2 x 4 grid of headline numbers (a picture of the KPI cards)."""
    apply_style()
    fig = plt.figure(figsize=(12, 3.6))
    fig.text(0.02, 0.95, "SalesInsight - headline KPIs", fontsize=15, fontweight="bold",
             color=TEXT_PRIMARY, va="top")
    first, last = kpis.get("first_order_date"), kpis.get("last_order_date")
    if first is not None and last is not None:
        fig.text(0.02, 0.87, f"Superstore orders, {first:%d %b %Y} to {last:%d %b %Y}",
                 fontsize=10, color=TEXT_SECONDARY, va="top")

    for i, key in enumerate(TILE_KEYS):
        row, col = divmod(i, 4)
        x, y = 0.02 + col * 0.245, 0.60 - row * 0.40
        label, kind = KPI_LABELS[key]
        value = short_money(kpis[key]) if kind == "money" else format_value(kpis[key], kind)
        box = plt.Rectangle((x, y - 0.17), 0.225, 0.33, transform=fig.transFigure,
                            facecolor="white", edgecolor=GRID, linewidth=1)
        fig.patches.append(box)
        fig.text(x + 0.015, y + 0.10, label, fontsize=10, color=TEXT_SECONDARY, va="top")
        fig.text(x + 0.015, y - 0.05, value, fontsize=22, fontweight="bold",
                 color=TEXT_PRIMARY, va="center")
    return save_figure(fig, "05_kpi_tiles", folder)


def plot_revenue_profit_by_year(yearly: pd.DataFrame, folder: Path | None = None) -> Path:
    """Grouped bars: revenue and profit per year (same unit, so one axis is honest)."""
    apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    years = yearly["order_year"].astype(str).tolist()
    x = range(len(years))
    width = 0.36
    bars_r = ax.bar([i - width / 2 for i in x], yearly["revenue"], width,
                    color=REVENUE_COLOR, label="Revenue", edgecolor=SURFACE, linewidth=2)
    bars_p = ax.bar([i + width / 2 for i in x], yearly["profit"], width,
                    color=PROFIT_COLOR, label="Profit", edgecolor=SURFACE, linewidth=2)
    for bars in (bars_r, bars_p):
        for bar in bars:
            ax.annotate(short_money(bar.get_height()), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 4), textcoords="offset points", ha="center",
                        fontsize=9, color=TEXT_SECONDARY)
    ax.set_xticks(list(x), years)
    ax.tick_params(axis="x", length=0)
    money_axis(ax)
    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_title("Revenue and profit by year")
    ax.legend(loc="upper left", ncols=2)
    ax.margins(y=0.12)
    return save_figure(fig, "05_revenue_profit_by_year", folder)


def plot_margin_by_year(yearly: pd.DataFrame, overall_margin: float, folder: Path | None = None) -> Path:
    """Profit margin % per year, with the overall margin as a reference line."""
    apply_style()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    years = yearly["order_year"].astype(str).tolist()
    ax.plot(years, yearly["profit_margin_pct"], color=PROFIT_COLOR, marker="o", markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2)
    for xv, yv in zip(years, yearly["profit_margin_pct"]):
        ax.annotate(f"{yv:.1f}%", (xv, yv), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=9, color=TEXT_SECONDARY)
    ax.axhline(overall_margin, color=BASELINE, linewidth=1, linestyle="--")
    ax.annotate(f"All years: {overall_margin:.1f}%", (len(years) - 1, overall_margin),
                xytext=(8, -14), textcoords="offset points", fontsize=9, color=TEXT_SECONDARY,
                ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.tick_params(axis="x", length=0)
    ax.set_title("Profit margin by year")
    ax.margins(y=0.25)
    return save_figure(fig, "05_profit_margin_by_year", folder)


# ---------------------------------------------------------------------------
# Phase 6 charts: trends and seasonality
# ---------------------------------------------------------------------------
# Single-hue blue ramp (light -> dark) for magnitude, e.g. heatmaps.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
REVENUE_LIGHT = "#86b6ef"   # raw monthly values (recede)
REVENUE_DARK = "#1c5cab"    # smoothed trend (stands out)


def plot_monthly_trend(monthly: pd.DataFrame, folder: Path | None = None) -> Path:
    """Monthly revenue with its 3-month moving average."""
    apply_style()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(monthly["period"], monthly["revenue"], color=REVENUE_LIGHT, linewidth=1.5,
            marker="o", markersize=4, label="Monthly revenue")
    ax.plot(monthly["period"], monthly["revenue_ma"], color=REVENUE_DARK, linewidth=2.5,
            label="3-month moving average")
    best = monthly.loc[monthly["revenue"].idxmax()]
    ax.annotate(f"Best month: {best['period']:%b %Y}\n{short_money(best['revenue'])}",
                (best["period"], best["revenue"]), xytext=(-12, 0), textcoords="offset points",
                ha="right", va="center", fontsize=9, color=TEXT_SECONDARY)
    money_axis(ax)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(bottom=0)
    ax.set_title("Monthly revenue and 3-month moving average")
    ax.legend(loc="upper left", ncols=2)
    return save_figure(fig, "06_monthly_revenue_trend", folder)


def plot_revenue_heatmap(matrix: pd.DataFrame, folder: Path | None = None) -> Path:
    """Year x month heatmap: darker blue = more revenue."""
    from matplotlib.colors import LinearSegmentedColormap

    apply_style()
    cmap = LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(12, 1.2 + 0.8 * len(matrix)))
    values = matrix.to_numpy(dtype=float)
    image = ax.imshow(values, cmap=cmap, aspect="auto")
    vmin, vmax = image.get_clim()
    for (r, c), v in pd.DataFrame(values).stack().items():
        dark = (v - vmin) / (vmax - vmin or 1) > 0.55
        ax.text(c, r, short_money(v), ha="center", va="center", fontsize=8.5,
                color="white" if dark else TEXT_PRIMARY)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix.index)), matrix.index.astype(str))
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    # White gaps between cells.
    ax.set_xticks([x - 0.5 for x in range(1, len(matrix.columns))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(matrix.index))], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_title("Revenue by month and year")
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.01)
    cbar.outline.set_visible(False)
    cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: axis_money(v)))
    cbar.ax.tick_params(colors=TEXT_SECONDARY, length=0)
    return save_figure(fig, "06_revenue_heatmap", folder)


def plot_seasonality_index(season: pd.DataFrame, folder: Path | None = None) -> Path:
    """Bars per calendar month; 100 = an average month."""
    apply_style()
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(season["month_name"], season["seasonality_index"], width=0.6, color=REVENUE_COLOR,
           edgecolor=SURFACE, linewidth=2)
    ax.axhline(100, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.annotate("Average month = 100", (-0.45, 100), xytext=(0, 5),
                textcoords="offset points", ha="left", fontsize=9, color=TEXT_SECONDARY)
    for idx in (season["seasonality_index"].idxmax(), season["seasonality_index"].idxmin()):
        row = season.loc[idx]
        ax.annotate(f"{row['seasonality_index']:.0f}", (row["month_name"], row["seasonality_index"]),
                    xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9,
                    color=TEXT_PRIMARY, fontweight="bold")
    ax.tick_params(axis="x", length=0)
    ax.set_title("Seasonality: average revenue per calendar month (index)")
    ax.margins(y=0.1)
    return save_figure(fig, "06_seasonality_index", folder)


def plot_weekday_orders(weekday: pd.DataFrame, folder: Path | None = None) -> Path:
    """Share of orders placed on each weekday."""
    apply_style()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    labels = [d[:3] for d in weekday["weekday"]]
    bars = ax.bar(labels, weekday["share_of_orders_pct"], width=0.6, color=REVENUE_COLOR,
                  edgecolor=SURFACE, linewidth=2)
    for bar, v in zip(bars, weekday["share_of_orders_pct"]):
        ax.annotate(f"{v:.1f}%", (bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=9, color=TEXT_SECONDARY)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.tick_params(axis="x", length=0)
    ax.set_title("Share of orders by weekday")
    ax.margins(y=0.12)
    return save_figure(fig, "06_weekday_orders", folder)


# ---------------------------------------------------------------------------
# Phase 7 charts: products and categories
# ---------------------------------------------------------------------------
# Diverging ramp for values that can be negative or positive (e.g. margin %):
# red = loss, grey = break-even, blue = profit. Equal steps on each side.
DIVERGING = ["#a32c2c", "#e34948", "#f2a5a4", "#f0efec", "#9ec5f4", "#3987e5", "#184f95"]
LOSS_COLOR = "#e34948"
GAIN_COLOR = "#3987e5"


def _shorten(text: str, limit: int = 45) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def plot_top_products(top: pd.DataFrame, value: str = "revenue", folder: Path | None = None) -> Path:
    """Horizontal bars of the top products (biggest at the top)."""
    apply_style()
    data = top.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 0.5 * len(data) + 1.4))
    bars = ax.barh([_shorten(n) for n in data["product_name"]], data[value], height=0.6,
                   color=REVENUE_COLOR if value == "revenue" else PROFIT_COLOR,
                   edgecolor=SURFACE, linewidth=2)
    for bar, v in zip(bars, data[value]):
        ax.annotate(short_money(v), (v, bar.get_y() + bar.get_height() / 2), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=9, color=TEXT_SECONDARY)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: axis_money(v)))
    ax.tick_params(axis="y", length=0)
    ax.margins(x=0.12)
    ax.set_title(f"Top {len(data)} products by {value}")
    return save_figure(fig, f"07_top10_products_by_{value}", folder)


def plot_category_performance(cats: pd.DataFrame, folder: Path | None = None) -> Path:
    """Revenue and profit per category, with the margin written under each name."""
    apply_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(cats))
    width = 0.36
    bars_r = ax.bar([i - width / 2 for i in x], cats["revenue"], width, color=REVENUE_COLOR,
                    label="Revenue", edgecolor=SURFACE, linewidth=2)
    bars_p = ax.bar([i + width / 2 for i in x], cats["profit"], width, color=PROFIT_COLOR,
                    label="Profit", edgecolor=SURFACE, linewidth=2)
    for bars in (bars_r, bars_p):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(short_money(h), (bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 4 if h >= 0 else -12), textcoords="offset points",
                        ha="center", fontsize=9, color=TEXT_SECONDARY)
    labels = [f"{c}\nmargin {m:.1f}%" for c, m in zip(cats["category"], cats["profit_margin_pct"])]
    ax.set_xticks(list(x), labels)
    ax.tick_params(axis="x", length=0)
    ax.axhline(0, color=BASELINE, linewidth=1)
    money_axis(ax)
    ax.legend(loc="upper right", ncols=2)
    ax.margins(y=0.12)
    ax.set_title("Revenue and profit by category")
    return save_figure(fig, "07_category_performance", folder)


def plot_subcategory_profit(subs: pd.DataFrame, folder: Path | None = None) -> Path:
    """Profit per sub-category, sorted; losses in red, profits in blue."""
    apply_style()
    data = subs.sort_values("profit")
    colors = [LOSS_COLOR if v < 0 else GAIN_COLOR for v in data["profit"]]
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(data) + 1.6))
    bars = ax.barh(data["sub_category"], data["profit"], height=0.65, color=colors,
                   edgecolor=SURFACE, linewidth=2)
    for bar, v in zip(bars, data["profit"]):
        ax.annotate(short_money(v), (v, bar.get_y() + bar.get_height() / 2),
                    xytext=(4 if v >= 0 else -4, 0), textcoords="offset points", va="center",
                    ha="left" if v >= 0 else "right", fontsize=9, color=TEXT_SECONDARY)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: axis_money(v)))
    ax.tick_params(axis="y", length=0)
    ax.margins(x=0.15)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=GAIN_COLOR, label="Profit"), Patch(color=LOSS_COLOR, label="Loss")],
              loc="lower right")
    ax.set_title("Total profit by sub-category")
    return save_figure(fig, "07_subcategory_profit", folder)


def plot_pareto(par: pd.DataFrame, folder: Path | None = None) -> Path:
    """Cumulative share of revenue vs share of products (80/20 check)."""
    apply_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    x = [0, *par["product_rank_pct"]]
    y = [0, *par["cum_share_pct"]]
    ax.plot(x, y, color=REVENUE_COLOR, linewidth=2.5)
    ax.plot([0, 100], [0, 100], color=BASELINE, linewidth=1, linestyle=":")
    n80 = int((par["cum_share_pct"] < 80).sum())
    x80 = float(par.loc[n80, "product_rank_pct"])
    ax.axhline(80, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.axvline(x80, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.annotate(f"{x80:.0f}% of products make\n80% of revenue", (x80, 80), xytext=(10, -40),
                textcoords="offset points", fontsize=10, color=TEXT_PRIMARY)
    ax.annotate("Equal share line", (70, 70), xytext=(4, -14), textcoords="offset points",
                fontsize=9, color=TEXT_SECONDARY)
    pct = mticker.FuncFormatter(lambda v, _: f"{v:.0f}%")
    ax.xaxis.set_major_formatter(pct)
    ax.yaxis.set_major_formatter(pct)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_xlabel("Share of products (biggest sellers first)")
    ax.set_ylabel("Cumulative share of revenue")
    ax.grid(axis="x", visible=True)
    ax.set_title("Pareto check: how concentrated is revenue?")
    return save_figure(fig, "07_pareto_revenue", folder)


def plot_discount_margin_heatmap(matrix: pd.DataFrame, folder: Path | None = None) -> Path:
    """Margin % by sub-category and discount band; red = loss, blue = profit."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    apply_style()
    cmap = LinearSegmentedColormap.from_list("diverging", DIVERGING).with_extremes(bad=SURFACE)
    values = matrix.to_numpy(dtype=float)
    limit = float(pd.Series(values.ravel()).abs().quantile(0.95)) or 1.0
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(matrix) + 1.8))
    image = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")
    for r in range(values.shape[0]):
        for c in range(values.shape[1]):
            v = values[r, c]
            if pd.isna(v):
                ax.text(c, r, "–", ha="center", va="center", fontsize=9, color=TEXT_SECONDARY)
                continue
            strong = abs(v) > 0.6 * limit
            ax.text(c, r, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                    color="white" if strong else TEXT_PRIMARY)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns)
    ax.set_yticks(range(len(matrix.index)), matrix.index)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, values.shape[1])], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, values.shape[0])], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_title("Profit margin by sub-category and discount level", pad=28)
    cbar = fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    cbar.outline.set_visible(False)
    cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    cbar.ax.tick_params(colors=TEXT_SECONDARY, length=0)
    return save_figure(fig, "07_discount_margin_heatmap", folder)
