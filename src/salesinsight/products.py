"""Phase 7 (Q3, Q4): best-selling products and category performance.

What this module answers:
- Which products bring the most revenue, units and profit?
- Which products lose the most money, and why (discount)?
- Do a few products make most of the revenue (80/20 Pareto rule)?
- How do categories and sub-categories compare on revenue, profit and margin?
- At which discount level does each sub-category start losing money?

Products are grouped by product_key (one key per product_id + product_name),
so the 32 shared Product IDs are never mixed up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DISCOUNT_BAND_ORDER = ["No discount", "1-20%", "21-40%", "Over 40%"]


def _performance(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Shared revenue / profit / margin table for any grouping."""
    g = df.groupby(by, observed=True)
    out = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "units_sold": g["quantity"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
        "order_lines": g.size(),
        "loss_lines": g["is_loss"].sum(),
        "discount_given": g["discount_amount"].sum(),
        "gross_sales": g["gross_sales"].sum(),
    }).reset_index()
    out["profit_margin_pct"] = np.where(out["revenue"] != 0, 100 * out["profit"] / out["revenue"], np.nan)
    out["effective_discount_pct"] = 100 * out["discount_given"] / out["gross_sales"]
    out["loss_lines_pct"] = 100 * out["loss_lines"] / out["order_lines"]
    out["share_of_revenue_pct"] = 100 * out["revenue"] / out["revenue"].sum()
    return out.drop(columns=["gross_sales"])


# ---------------------------------------------------------------------------
# Q3: products
# ---------------------------------------------------------------------------
def product_performance(df: pd.DataFrame) -> pd.DataFrame:
    """One row per product with revenue, units, profit, margin and discount."""
    return _performance(df, ["product_key", "product_name", "category", "sub_category"])


def top_products(perf: pd.DataFrame, by: str = "revenue", n: int = 10) -> pd.DataFrame:
    """Top n products by a column (ties broken by product_key, so results are stable)."""
    return perf.sort_values([by, "product_key"], ascending=[False, True]).head(n).reset_index(drop=True)


def bottom_products(perf: pd.DataFrame, by: str = "profit", n: int = 10) -> pd.DataFrame:
    return perf.sort_values([by, "product_key"], ascending=[True, True]).head(n).reset_index(drop=True)


def pareto(perf: pd.DataFrame, value: str = "revenue") -> pd.DataFrame:
    """Products sorted from biggest to smallest, with cumulative shares.

    cum_share_pct        : % of total value from this product and all bigger ones
    product_rank_pct     : this product's position as % of all products
    """
    p = perf.sort_values([value, "product_key"], ascending=[False, True]).reset_index(drop=True)
    p["cum_share_pct"] = 100 * p[value].cumsum() / p[value].sum()
    p["product_rank_pct"] = 100 * (np.arange(len(p)) + 1) / len(p)
    return p


def pareto_summary(perf: pd.DataFrame, value: str = "revenue", target_pct: float = 80) -> dict[str, float]:
    """How many products make up `target_pct` % of the value, and what the top 20% earn."""
    p = pareto(perf, value)
    n_needed = int((p["cum_share_pct"] < target_pct).sum()) + 1
    top20_n = max(1, int(np.ceil(0.2 * len(p))))
    return {
        "products_total": len(p),
        "products_for_target": n_needed,
        "products_for_target_pct": 100 * n_needed / len(p),
        "top20pct_products_share": float(p.loc[top20_n - 1, "cum_share_pct"]),
    }


def loss_making_products(perf: pd.DataFrame) -> pd.DataFrame:
    """Products whose total profit over all years is negative, worst first."""
    return perf[perf["profit"] < 0].sort_values("profit").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Q4: categories and sub-categories
# ---------------------------------------------------------------------------
def category_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = _performance(df, ["category"])
    out["share_of_profit_pct"] = 100 * out["profit"] / out["profit"].sum()
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def subcategory_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = _performance(df, ["category", "sub_category"])
    out["share_of_profit_pct"] = 100 * out["profit"] / out["profit"].sum()
    return out.sort_values("profit", ascending=False).reset_index(drop=True)


def discount_margin_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Profit margin % for each sub-category (rows) at each discount band (columns).

    Empty cells mean the sub-category never sold at that discount level.
    """
    g = df.groupby(["sub_category", "discount_band"], observed=True)[["profit", "sales"]].sum()
    margin = (100 * g["profit"] / g["sales"]).unstack("discount_band")
    margin = margin.reindex(columns=[c for c in DISCOUNT_BAND_ORDER if c in margin.columns])
    # Sort rows by overall margin, best at the top.
    overall = df.groupby("sub_category")["profit"].sum() / df.groupby("sub_category")["sales"].sum()
    return margin.loc[overall.sort_values(ascending=False).index]


def discount_band_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = _performance(df, ["discount_band"])
    out["discount_band"] = pd.Categorical(out["discount_band"], DISCOUNT_BAND_ORDER, ordered=True)
    return out.sort_values("discount_band").reset_index(drop=True)


def product_summary(df: pd.DataFrame) -> dict[str, object]:
    """Key facts for the console output and the final report."""
    perf = product_performance(df)
    cats = category_performance(df)
    subs = subcategory_performance(df)
    losers = loss_making_products(perf)
    par = pareto_summary(perf)
    bands = discount_band_performance(df).set_index("discount_band")

    best_margin_cat = cats.loc[cats["profit_margin_pct"].idxmax()]
    worst_sub = subs.loc[subs["profit"].idxmin()]
    best_sub = subs.loc[subs["profit"].idxmax()]
    return {
        "products_total": par["products_total"],
        "top_product_by_revenue": top_products(perf, "revenue", 1).loc[0, "product_name"],
        "top_product_revenue": float(top_products(perf, "revenue", 1).loc[0, "revenue"]),
        "worst_product_by_profit": bottom_products(perf, "profit", 1).loc[0, "product_name"],
        "worst_product_profit": float(bottom_products(perf, "profit", 1).loc[0, "profit"]),
        "products_for_80pct_revenue": par["products_for_target"],
        "products_for_80pct_revenue_pct": par["products_for_target_pct"],
        "top20pct_products_revenue_share": par["top20pct_products_share"],
        "loss_making_products": len(losers),
        "loss_making_products_total": float(losers["profit"].sum()),
        "top_category_by_revenue": cats.loc[0, "category"],
        "best_margin_category": best_margin_cat["category"],
        "best_margin_category_pct": float(best_margin_cat["profit_margin_pct"]),
        "best_subcategory_by_profit": best_sub["sub_category"],
        "best_subcategory_profit": float(best_sub["profit"]),
        "worst_subcategory_by_profit": worst_sub["sub_category"],
        "worst_subcategory_profit": float(worst_sub["profit"]),
        "loss_subcategories": ", ".join(subs.loc[subs["profit"] < 0, "sub_category"]),
        "margin_no_discount_pct": float(bands.loc["No discount", "profit_margin_pct"])
        if "No discount" in bands.index else float("nan"),
        "margin_over_40pct_discount_pct": float(bands.loc["Over 40%", "profit_margin_pct"])
        if "Over 40%" in bands.index else float("nan"),
    }
