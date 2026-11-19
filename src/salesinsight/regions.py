"""Phase 8 (Q5): region-wise and state-wise sales.

What this module answers:
- Which regions and states bring the most revenue and profit?
- Which states lose money, and is discounting the reason?
- How does each category perform in each region?
- Which regions are growing fastest?

All tables use the same measures as Phase 7 (revenue, profit, margin,
effective discount, % of order lines at a loss), so results can be compared.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from salesinsight.products import performance_table


def region_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = performance_table(df, ["region"])
    out["total_customers"] = df.groupby("region")["customer_id"].nunique().reindex(out["region"]).to_numpy()
    out["revenue_per_customer"] = out["revenue"] / out["total_customers"]
    out["share_of_profit_pct"] = 100 * out["profit"] / out["profit"].sum()
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def state_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = performance_table(df, ["region", "state"])
    out["share_of_profit_pct"] = 100 * out["profit"] / out["profit"].sum()
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def city_performance(df: pd.DataFrame, min_orders: int = 10) -> pd.DataFrame:
    """Cities with at least `min_orders` orders (tiny cities make misleading margins)."""
    out = performance_table(df, ["region", "state", "city"])
    out = out[out["total_orders"] >= min_orders]
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def top_states(states: pd.DataFrame, by: str = "revenue", n: int = 10) -> pd.DataFrame:
    return states.sort_values([by, "state"], ascending=[False, True]).head(n).reset_index(drop=True)


def bottom_states(states: pd.DataFrame, by: str = "profit", n: int = 10) -> pd.DataFrame:
    return states.sort_values([by, "state"], ascending=[True, True]).head(n).reset_index(drop=True)


def region_category_matrix(df: pd.DataFrame, value: str = "profit_margin_pct") -> pd.DataFrame:
    """Regions (rows) x categories (columns) for revenue, profit or profit_margin_pct."""
    t = performance_table(df, ["region", "category"])
    m = t.pivot(index="region", columns="category", values=value)
    order = region_performance(df)["region"]
    return m.reindex(order)


def region_yearly(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue per region per year, with year-on-year growth %."""
    t = df.groupby(["region", "order_year"])[["sales", "profit"]].sum().reset_index()
    t = t.rename(columns={"sales": "revenue"}).sort_values(["region", "order_year"])
    t["revenue_growth_pct"] = 100 * t.groupby("region")["revenue"].pct_change()
    return t.reset_index(drop=True)


def region_cagr(yearly: pd.DataFrame) -> pd.DataFrame:
    """Compound annual revenue growth per region, first year to last year."""
    rows = []
    for region, g in yearly.groupby("region"):
        g = g.sort_values("order_year")
        years = int(g["order_year"].iloc[-1] - g["order_year"].iloc[0])
        first, last = g["revenue"].iloc[0], g["revenue"].iloc[-1]
        cagr = 100 * ((last / first) ** (1 / years) - 1) if years > 0 and first > 0 else np.nan
        rows.append({"region": region, "first_year_revenue": first,
                     "last_year_revenue": last, "revenue_cagr_pct": cagr})
    return pd.DataFrame(rows).sort_values("revenue_cagr_pct", ascending=False).reset_index(drop=True)


def discount_margin_correlation(states: pd.DataFrame, min_orders: int = 10) -> float:
    """Pearson correlation between a state's effective discount and its margin.

    Close to -1: states that discount more earn clearly lower margins.
    Only states with at least `min_orders` orders are used.
    """
    s = states[states["total_orders"] >= min_orders]
    if len(s) < 3:
        return float("nan")
    return float(np.corrcoef(s["effective_discount_pct"], s["profit_margin_pct"])[0, 1])


def region_summary(df: pd.DataFrame) -> dict[str, object]:
    regions = region_performance(df)
    states = state_performance(df)
    cagr = region_cagr(region_yearly(df))
    losing = states[states["profit"] < 0].sort_values("profit")

    best_rev = regions.iloc[0]
    best_margin = regions.loc[regions["profit_margin_pct"].idxmax()]
    worst_margin = regions.loc[regions["profit_margin_pct"].idxmin()]
    return {
        "regions": len(regions),
        "states": len(states),
        "top_region_by_revenue": best_rev["region"],
        "top_region_revenue_share_pct": float(best_rev["share_of_revenue_pct"]),
        "best_margin_region": best_margin["region"],
        "best_margin_region_pct": float(best_margin["profit_margin_pct"]),
        "worst_margin_region": worst_margin["region"],
        "worst_margin_region_pct": float(worst_margin["profit_margin_pct"]),
        "fastest_growing_region": cagr.loc[0, "region"],
        "fastest_growing_region_cagr_pct": float(cagr.loc[0, "revenue_cagr_pct"]),
        "top_state_by_revenue": top_states(states, "revenue", 1).loc[0, "state"],
        "top_state_revenue": float(top_states(states, "revenue", 1).loc[0, "revenue"]),
        "top_state_by_profit": top_states(states, "profit", 1).loc[0, "state"],
        "top_state_profit": float(top_states(states, "profit", 1).loc[0, "profit"]),
        "worst_state_by_profit": bottom_states(states, "profit", 1).loc[0, "state"],
        "worst_state_profit": float(bottom_states(states, "profit", 1).loc[0, "profit"]),
        "loss_making_states": len(losing),
        "loss_making_states_total": float(losing["profit"].sum()),
        "loss_making_states_list": ", ".join(losing["state"]),
        "state_discount_margin_correlation": discount_margin_correlation(states),
    }
