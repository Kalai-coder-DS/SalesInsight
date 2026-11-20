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


# ---------------------------------------------------------------------------
# Sales Trends page (13B)
# ---------------------------------------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WINDOW = {"Month": 3, "Quarter": 2, "Year": 2}


def metric_series(df: pd.DataFrame, granularity: str, metric: str) -> pd.DataFrame:
    """One metric over time with its moving average (3 months / 2 quarters / 2 years)."""
    ts = time_series(df, granularity)
    column = METRICS[metric][0]
    out = ts[["period", "label"]].copy()
    out["value"] = ts[column].astype(float)
    window = WINDOW[granularity]
    out["moving_avg"] = out["value"].rolling(window, min_periods=window).mean()
    return out


def growth(df: pd.DataFrame, granularity: str = "Year") -> pd.DataFrame:
    """Growth % versus the previous period for revenue, profit and orders.

    Year: vs previous year. Quarter / Month: vs the same quarter / month one
    year earlier (removes seasonality). Growth is blank when the earlier value
    is zero or negative.
    """
    ts = time_series(df, granularity)
    lag = {"Year": 1, "Quarter": 4, "Month": 12}[granularity]
    out = ts[["period", "label"]].copy()
    for col in ("revenue", "profit", "total_orders"):
        prev = ts[col].shift(lag)
        out[f"{col}_growth_pct"] = (100 * (ts[col] - prev) / prev).where(prev > 0)
    return out.dropna(subset=["revenue_growth_pct", "profit_growth_pct", "total_orders_growth_pct"], how="all")


def month_by_year(df: pd.DataFrame, metric: str = "Revenue") -> pd.DataFrame:
    """Rows = years, columns = Jan..Dec (for the seasonality heatmap and lines)."""
    column = METRICS[metric][0]
    if df.empty:
        return pd.DataFrame(columns=MONTHS)
    g = df.groupby([df["order_date"].dt.year, df["order_date"].dt.month])
    values = {"revenue": g["sales"].sum(), "profit": g["profit"].sum(),
              "total_orders": g["order_id"].nunique()}[column]
    m = values.unstack().reindex(columns=range(1, 13))
    m.columns = MONTHS
    m.index.name = "year"
    return m


def seasonality_index(df: pd.DataFrame, metric: str = "Revenue") -> pd.DataFrame:
    """Average value per calendar month as an index (100 = average month).

    Uses complete years only when there are any, so a half year cannot bias it.
    Months never seen are left out.
    """
    m = month_by_year(df, metric)
    if m.empty:
        return pd.DataFrame(columns=["month", "avg_value", "index"])
    full = m.dropna(how="any")
    use = full if len(full) else m
    avg = use.fillna(0).mean() if len(full) else use.mean()
    avg = avg.dropna()
    out = pd.DataFrame({"month": avg.index, "avg_value": avg.to_numpy()})
    out["index"] = 100 * out["avg_value"] / out["avg_value"].mean() if out["avg_value"].mean() else 0
    return out


def margin_series(df: pd.DataFrame, granularity: str = "Month") -> pd.DataFrame:
    """Profit margin % per period (blank for periods with no sales)."""
    ts = time_series(df, granularity)
    out = ts[["period", "label", "revenue", "profit"]].copy()
    out["margin_pct"] = (100 * out["profit"] / out["revenue"]).where(out["revenue"] > 0)
    return out


def weekday_table(df: pd.DataFrame) -> pd.DataFrame:
    from salesinsight.trends import weekday_sales
    return weekday_sales(df)


def trend_stats(df: pd.DataFrame) -> list[dict]:
    """Headline trend facts for the stat cards (each safe for small selections)."""
    if df.empty:
        return []
    yearly = df.groupby("order_year")["sales"].sum().sort_index()
    if len(yearly) >= 2 and yearly.iloc[0] > 0:
        years = int(yearly.index[-1] - yearly.index[0])
        cagr = 100 * ((yearly.iloc[-1] / yearly.iloc[0]) ** (1 / years) - 1)
        cagr_text, cagr_sub = f"{cagr:+.1f}%", f"per year, {yearly.index[0]}-{yearly.index[-1]}"
    else:
        cagr_text, cagr_sub = "-", "needs 2+ years selected"
    months = time_series(df, "Month")
    best = months.loc[months["revenue"].idxmax()]
    season = seasonality_index(df)
    peak = season.loc[season["index"].idxmax()] if len(season) else None
    q4 = df.loc[df["order_date"].dt.quarter == 4, "sales"].sum() / df["sales"].sum() * 100
    return [
        {"label": "Revenue growth (CAGR)", "value": cagr_text, "sub": cagr_sub},
        {"label": "Best month", "value": best["label"], "sub": f"{short_money(best['revenue'])} revenue"},
        {"label": "Peak season", "value": peak["month"] if peak is not None else "-",
         "sub": f"index {peak['index']:.0f} (100 = average month)" if peak is not None else ""},
        {"label": "Q4 share of revenue", "value": f"{q4:.1f}%", "sub": "October to December"},
    ]


# ---------------------------------------------------------------------------
# Product Intelligence page (13B)
# ---------------------------------------------------------------------------
PRODUCT_METRICS = {"Revenue": ("revenue", "money"), "Profit": ("profit", "money"),
                   "Units": ("units_sold", "int")}


def ranked_products(df: pd.DataFrame, metric: str = "Revenue", n: int = 10, top: bool = True) -> pd.DataFrame:
    """Top or bottom n products by revenue, profit or units (uses products.py)."""
    from salesinsight.products import bottom_products, product_performance, top_products
    perf = product_performance(df)
    column = PRODUCT_METRICS[metric][0]
    return top_products(perf, column, n) if top else bottom_products(perf, column, n)


def category_hierarchy(df: pd.DataFrame) -> pd.DataFrame:
    """Category > sub-category table with revenue, profit, units and margin."""
    if df.empty:
        return pd.DataFrame(columns=["category", "sub_category", "revenue", "profit", "units_sold",
                                     "profit_margin_pct"])
    t = performance_table(df, ["category", "sub_category"])
    return t.sort_values(["category", "revenue"], ascending=[True, False]).reset_index(drop=True)


def product_stats(df: pd.DataFrame) -> list[dict]:
    from salesinsight.products import (loss_making_products, pareto_summary, product_performance,
                                       subcategory_performance)
    if df.empty:
        return []
    perf = product_performance(df)
    par = pareto_summary(perf)
    losers = loss_making_products(perf)
    subs = subcategory_performance(df)
    best = subs.iloc[0]
    return [
        {"label": "Products sold", "value": f"{len(perf):,}", "sub": f"{df['quantity'].sum():,} units"},
        {"label": "Products making 80% of revenue", "value": f"{par['products_for_target']:,}",
         "sub": f"{par['products_for_target_pct']:.1f}% of all products"},
        {"label": "Loss-making products", "value": f"{len(losers):,}",
         "sub": f"{short_money(losers['profit'].sum())} total loss"},
        {"label": "Most profitable sub-category", "value": best["sub_category"],
         "sub": f"{short_money(best['profit'])} profit"},
    ]
