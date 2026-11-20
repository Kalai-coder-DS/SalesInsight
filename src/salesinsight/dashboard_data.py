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


# ---------------------------------------------------------------------------
# Regional Intelligence page (13C)
# ---------------------------------------------------------------------------
STATE_METRICS = {
    # label -> (column, kind, diverging colour scale?)
    "Revenue": ("revenue", "money", False),
    "Profit": ("profit", "money", True),
    "Margin": ("profit_margin_pct", "pct", True),
    "Discount": ("effective_discount_pct", "pct", False),
    "Orders": ("total_orders", "int", False),
}


def state_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per state with revenue, profit, margin, discount, orders and its map code."""
    from salesinsight.geo import state_code
    from salesinsight.regions import state_performance
    if df.empty:
        return pd.DataFrame(columns=["region", "state", "code", "revenue", "profit", "profit_margin_pct",
                                     "effective_discount_pct", "total_orders"])
    t = state_performance(df)
    t.insert(2, "code", t["state"].map(state_code))
    return t


def region_stats(df: pd.DataFrame) -> list[dict]:
    from salesinsight.regions import discount_margin_correlation, region_performance
    if df.empty:
        return []
    regions = region_performance(df)
    states = state_table(df)
    top = regions.iloc[0]
    best = regions.loc[regions["profit_margin_pct"].idxmax()]
    losing = states[states["profit"] < 0]
    corr = discount_margin_correlation(states)
    return [
        {"label": "Largest region", "value": top["region"],
         "sub": f"{top['share_of_revenue_pct']:.1f}% of revenue"},
        {"label": "Best margin region", "value": best["region"],
         "sub": f"{best['profit_margin_pct']:.1f}% profit margin"},
        {"label": "Loss-making states", "value": f"{len(losing)} of {len(states)}",
         "sub": f"{short_money(losing['profit'].sum())} total" if len(losing) else "no state loses money"},
        {"label": "Discount vs margin (states)", "value": f"{corr:.2f}" if pd.notna(corr) else "-",
         "sub": "correlation, states with 10+ orders" if pd.notna(corr) else "needs 3+ states with 10+ orders"},
    ]


def region_by_year(df: pd.DataFrame, metric: str = "Revenue") -> pd.DataFrame:
    """Long table: region, year, value - for one line per region."""
    column = METRICS[metric][0]
    if df.empty:
        return pd.DataFrame(columns=["group", "x", "value"])
    g = df.groupby(["region", "order_year"])
    values = {"revenue": g["sales"].sum(), "profit": g["profit"].sum(),
              "total_orders": g["order_id"].nunique()}[column]
    out = values.reset_index()
    out.columns = ["group", "x", "value"]
    out["x"] = out["x"].astype(str)
    return out


# ---------------------------------------------------------------------------
# Customer Intelligence page (13C)
# ---------------------------------------------------------------------------
SEGMENT_METRICS = {
    "Revenue": ("revenue", "money"), "Profit": ("profit", "money"),
    "Customers": ("total_customers", "int"), "Avg order value": ("avg_order_value", "money"),
}


def customer_stats(df: pd.DataFrame) -> list[dict]:
    from salesinsight.customers import concentration, customer_table, days_between_orders
    if df.empty:
        return []
    c = customer_table(df)
    repeat = 100 * (c["total_orders"] >= 2).mean()
    gaps = days_between_orders(df)
    return [
        {"label": "Customers", "value": f"{len(c):,}", "sub": f"{short_money(c['revenue'].mean())} revenue each"},
        {"label": "Repeat customers", "value": f"{repeat:.1f}%", "sub": "ordered more than once"},
        {"label": "Orders per customer", "value": f"{c['total_orders'].mean():.1f}",
         "sub": f"median {gaps.median():.0f} days between orders" if len(gaps) else "no repeat orders yet"},
        {"label": "Top 20% of customers", "value": f"{concentration(c, 20):.1f}%", "sub": "of revenue"},
    ]


def new_vs_returning_long(df: pd.DataFrame) -> pd.DataFrame:
    """new_vs_returning() reshaped for a stacked chart, plus retention per year."""
    from salesinsight.customers import new_vs_returning
    if df.empty:
        return pd.DataFrame(columns=["label", "revenue_returning", "revenue_new", "retention_pct"])
    n = new_vs_returning(df)
    n["label"] = n["order_year"].astype(str)
    return n


# ---------------------------------------------------------------------------
# Business Insights page (13D)
#
# insights.py and stats_tests.py were written for the whole dataset. In the
# app the data is filtered (one region, one segment...), and some parts cannot
# be calculated then (e.g. comparing regions when only one is selected). Each
# part therefore runs on its own; a part that cannot be calculated is skipped
# and reported, instead of breaking the whole page.
# ---------------------------------------------------------------------------
def _attempt(func):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return func(), None
        except Exception as exc:  # the reason is shown to the user as "skipped"
            return None, f"{type(exc).__name__}: {exc}"


def safe_findings(df: pd.DataFrame) -> tuple[dict, dict]:
    """Same keys as insights.collect_findings(); returns (findings, skipped {key: reason})."""
    from salesinsight import customers as cu
    from salesinsight import kpis as kp
    from salesinsight import products as pr
    from salesinsight import regions as rg
    from salesinsight import stats_tests as st_
    from salesinsight import trends as tr

    high = df[df["discount"] > 0.2]
    parts = {
        "kpis": lambda: kp.compute_kpis(df),
        "yearly": lambda: kp.yearly_kpis(df),
        "trends": lambda: tr.trend_summary(df),
        "products": lambda: pr.product_summary(df),
        "categories": lambda: pr.category_performance(df),
        "subcategories": lambda: pr.subcategory_performance(df),
        "discount_bands": lambda: pr.discount_band_performance(df),
        "regions": lambda: rg.region_performance(df),
        "region_summary": lambda: rg.region_summary(df),
        "segments": lambda: cu.segment_performance(df),
        "customers": lambda: cu.customer_summary(df),
        "rfm": lambda: cu.rfm_summary(cu.rfm_table(cu.customer_table(df))),
        "aov_ci": lambda: st_.aov_confidence_by_year(df),
        "high_discount_loss": lambda: float(high.loc[high["profit"] < 0, "profit"].sum()),
        "high_discount_lines_pct": lambda: 100 * len(high) / len(df),
    }
    findings, skipped = {}, {}
    # A trend line needs at least 3 months; fewer would make NumPy fit a line through 1-2 points.
    if df["order_date"].dt.to_period("M").nunique() < 3:
        parts.pop("trends")
        skipped["trends"] = "a trend needs at least 3 months of data"
    for key, func in parts.items():
        value, error = _attempt(func)
        if error is None:
            findings[key] = value
        else:
            skipped[key] = error
    tests = []
    for test in (st_.test_discount_vs_margin, st_.test_discount_vs_loss, st_.test_region_margin,
                 st_.test_segment_order_value, lambda d: st_.test_category_margin(d, "Furniture"),
                 st_.test_q4_vs_rest):
        result, error = _attempt(lambda t=test: t(df))
        if error is None and result is not None and pd.notna(result.p_value):
            tests.append(result)
    findings["tests"] = tests
    return findings, skipped


def safe_recommendations(findings: dict) -> list:
    """Run every recommendation rule; a rule whose inputs are missing is skipped."""
    from salesinsight.insights import RULES
    recs = []
    for rule in RULES:
        rec, error = _attempt(lambda r=rule: r(findings))
        if error is None and rec is not None:
            recs.append(rec)
    return sorted(recs, key=lambda r: r.priority)


def safe_report(findings: dict, recs: list) -> str | None:
    from salesinsight.insights import build_report
    report, error = _attempt(lambda: build_report(findings, recs))
    return report if error is None else None


def key_findings(df: pd.DataFrame, findings: dict) -> list[dict]:
    """Short headline findings for the selection (each only if it can be calculated)."""
    out = []
    k = findings.get("kpis")
    if k:
        out.append({"title": "Revenue and profit",
                    "text": f"{short_money(k['total_revenue'])} revenue and {short_money(k['total_profit'])} "
                            f"profit, a {k['profit_margin_pct']:.1f}% margin."})
        out.append({"title": "Discounts",
                    "text": f"{short_money(k['discount_given'])} given away ({k['effective_discount_pct']:.1f}% of "
                            f"list price); {k['loss_lines_pct']:.1f}% of order lines lose money "
                            f"({short_money(k['loss_amount'])})."})
    s = findings.get("region_summary")
    if s and s["loss_making_states"]:
        out.append({"title": "Loss-making states",
                    "text": f"{s['loss_making_states']} state(s) lose money in total "
                            f"({short_money(s['loss_making_states_total'])}); worst: {s['worst_state_by_profit']}."})
    cats = findings.get("categories")
    if cats is not None and len(cats) > 1:
        weak = cats.loc[cats["profit_margin_pct"].idxmin()]
        out.append({"title": "Weakest category",
                    "text": f"{weak['category']} keeps only {weak['profit_margin_pct']:.1f}% of revenue as profit, "
                            f"with {weak['loss_lines_pct']:.0f}% of its lines at a loss."})
    t = findings.get("trends")
    if t and pd.notna(t.get("revenue_cagr_pct")):
        out.append({"title": "Growth and seasonality",
                    "text": f"Revenue grows {t['revenue_cagr_pct']:.1f}% a year; {t['peak_season_month']} is the peak "
                            f"month and Q4 brings {t['q4_share_of_revenue_pct']:.1f}% of revenue."})
    return out


def opportunities(df: pd.DataFrame, findings: dict) -> list[dict]:
    """Where to grow: fastest-growing sub-categories and regions, and customers to win back."""
    out = []
    years = sorted(df["order_year"].unique())
    if len(years) >= 2:
        last, prev = years[-1], years[-2]
        g = df[df["order_year"].isin([prev, last])].pivot_table(
            index="sub_category", columns="order_year", values="sales", aggfunc="sum", fill_value=0)
        g = g[(g[prev] > 0) & (g[last] >= 0.01 * g[last].sum())]
        if len(g):
            g["growth"] = 100 * (g[last] - g[prev]) / g[prev]
            top = g.sort_values("growth", ascending=False).head(3)
            text = ", ".join(f"{name} ({row['growth']:+.0f}%)" for name, row in top.iterrows())
            out.append({"title": f"Fastest-growing sub-categories ({last} vs {prev})", "text": text + "."})
    s = findings.get("region_summary")
    if s and pd.notna(s.get("fastest_growing_region_cagr_pct")):
        out.append({"title": "Fastest-growing region",
                    "text": f"{s['fastest_growing_region']} grows {s['fastest_growing_region_cagr_pct']:.1f}% a year."})
    rfm = findings.get("rfm")
    if rfm is not None and "At risk" in set(rfm["rfm_segment"]):
        r = rfm.set_index("rfm_segment").loc["At risk"]
        out.append({"title": "Customers to win back",
                    "text": f"{int(r['total_customers'])} 'At risk' customers brought {short_money(r['revenue'])} "
                            f"({r['share_of_revenue_pct']:.1f}% of revenue) but have stopped ordering."})
    bands = findings.get("discount_bands")
    if bands is not None and len(bands):
        nd = bands[bands["discount_band"].astype(str) == "No discount"]
        if len(nd):
            out.append({"title": "Protect full-price sales",
                        "text": f"Lines sold without discount earn a {nd['profit_margin_pct'].iloc[0]:.1f}% margin."})
    return out


def loss_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Everything that lost money in the selection: products, sub-categories, states, customers."""
    from salesinsight.customers import customer_table
    from salesinsight.products import loss_making_products, product_performance, subcategory_performance
    if df.empty:
        return {}
    subs = subcategory_performance(df)
    states = state_table(df)
    cust = customer_table(df)
    return {
        "Products": loss_making_products(product_performance(df))[
            ["product_name", "sub_category", "revenue", "profit", "profit_margin_pct", "effective_discount_pct"]],
        "Sub-categories": subs[subs["profit"] < 0].sort_values("profit")[
            ["category", "sub_category", "revenue", "profit", "profit_margin_pct", "effective_discount_pct"]],
        "States": states[states["profit"] < 0].sort_values("profit")[
            ["state", "region", "revenue", "profit", "profit_margin_pct", "effective_discount_pct"]],
        "Customers": cust[cust["profit"] < 0].sort_values("profit")[
            ["customer_name", "segment", "total_orders", "revenue", "profit", "profit_margin_pct"]],
    }


# ---------------------------------------------------------------------------
# Data Explorer page (13D)
# ---------------------------------------------------------------------------
SEARCH_COLUMNS = ["order_id", "customer_id", "customer_name", "product_id", "product_name", "category",
                  "sub_category", "segment", "region", "state", "city"]
DEFAULT_COLUMNS = ["order_date", "order_id", "customer_name", "segment", "region", "state", "category",
                   "sub_category", "product_name", "sales", "quantity", "discount", "profit"]


def search_rows(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Rows where EVERY word of the query appears in at least one text column (case-insensitive)."""
    words = [w for w in str(query).lower().split() if w]
    if not words:
        return df
    cols = [c for c in SEARCH_COLUMNS if c in df.columns]
    haystack = df[cols].astype(str).agg(" ".join, axis=1).str.lower()
    mask = pd.Series(True, index=df.index)
    for word in words:
        mask &= haystack.str.contains(word, regex=False)
    return df[mask]


def explorer_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Totals per group (revenue, profit, orders, margin, discount) for the explorer's summary view."""
    if df.empty:
        return pd.DataFrame(columns=[by, "revenue", "profit", "total_orders", "profit_margin_pct"])
    return performance_table(df, [by]).sort_values("revenue", ascending=False).reset_index(drop=True)
