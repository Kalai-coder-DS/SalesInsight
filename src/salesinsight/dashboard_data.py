"""Data preparation for the web app's charts (pure pandas, unit-tested).

The analysis itself lives in the Phase 5-11 modules; these helpers only
reshape their results into the simple tables that charts need.
"""

from __future__ import annotations

import pandas as pd

from salesinsight.kpis import short_money
from salesinsight.products import performance_table

GRANULARITY = {"Month": "M", "Quarter": "Q", "Year": "Y"}

METRICS = {
    # label -> (column in the grouped table, kind)
    "Revenue": ("revenue", "money"),
    "Profit": ("profit", "money"),
    "Orders": ("total_orders", "int"),
}


def time_series(df: pd.DataFrame, granularity: str = "Month") -> pd.DataFrame:
    """Revenue, profit and orders per month / quarter / year.

    Missing periods (no sales) are filled with 0 so lines do not jump over gaps.
    Columns: period (timestamp of the period start), label, revenue, profit, total_orders.
    """
    freq = GRANULARITY[granularity]
    if df.empty:
        return pd.DataFrame(columns=["period", "label", "revenue", "profit", "total_orders"])
    periods = df["order_date"].dt.to_period(freq)
    g = df.groupby(periods)
    out = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
    })
    full = pd.period_range(out.index.min(), out.index.max(), freq=freq)
    out = out.reindex(full, fill_value=0)
    out.index.name = "period"
    out = out.reset_index()
    if freq == "M":
        out["label"] = out["period"].dt.strftime("%b %Y")
    elif freq == "Q":
        out["label"] = out["period"].astype(str).str.replace("Q", " Q")
    else:
        out["label"] = out["period"].astype(str)
    out["period"] = out["period"].dt.to_timestamp()
    return out[["period", "label", "revenue", "profit", "total_orders"]]


def breakdown(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Revenue, profit, margin, orders and shares for any column (category, region, segment...)."""
    if df.empty:
        return pd.DataFrame(columns=[by, "revenue", "profit", "total_orders", "profit_margin_pct",
                                     "share_of_revenue_pct"])
    out = performance_table(df, [by])
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def profit_bridge(df: pd.DataFrame, by: str = "category") -> pd.DataFrame:
    """Each group's profit as a step, ending with the total (for a waterfall chart)."""
    if df.empty:
        return pd.DataFrame(columns=["label", "value", "measure"])
    steps = df.groupby(by)["profit"].sum().sort_values(ascending=False)
    rows = [{"label": name, "value": float(v), "measure": "relative"} for name, v in steps.items()]
    rows.append({"label": "Total profit", "value": float(steps.sum()), "measure": "total"})
    return pd.DataFrame(rows)


def highlights(df: pd.DataFrame) -> list[dict]:
    """Three short, data-driven highlights for the overview page."""
    if df.empty:
        return []
    out = []
    cats = breakdown(df, "category")
    top = cats.iloc[0]
    out.append({"title": "Largest category",
                "text": f"{top['category']} brings {top['share_of_revenue_pct']:.1f}% of revenue "
                        f"at a {top['profit_margin_pct']:.1f}% margin."})
    regions = breakdown(df, "region")
    if len(regions) > 1:
        weak = regions.loc[regions["profit_margin_pct"].idxmin()]
        out.append({"title": "Weakest region margin",
                    "text": f"{weak['region']} earns a {weak['profit_margin_pct']:.1f}% margin with a "
                            f"{weak['effective_discount_pct']:.1f}% effective discount."})
    losses = df["profit"] < 0
    out.append({"title": "Loss-making order lines",
                "text": f"{100 * losses.mean():.1f}% of order lines lose money, "
                        f"{short_money(df.loc[losses, 'profit'].sum())} in total."})
    return out
