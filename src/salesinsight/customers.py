"""Phase 9 (Q6): customer purchasing behaviour.

What this module answers:
- How do the Consumer, Corporate and Home Office segments differ?
- How often do customers come back (repeat rate, order frequency, days between orders)?
- How much revenue depends on the top customers?
- Who are the best, at-risk and lost customers (RFM segmentation)?
- Each year, how much revenue comes from new versus returning customers?

RFM = Recency (days since last order), Frequency (number of orders),
Monetary (total revenue). Each is scored 1-5 from the customer's percentile
rank (top 20% = 5); 5 is best. Recency is reversed: fewer days = 5.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from salesinsight.products import performance_table

FREQUENCY_BANDS = [(1, 1, "1 order"), (2, 3, "2-3 orders"), (4, 6, "4-6 orders"),
                   (7, 9, "7-9 orders"), (10, 10_000, "10+ orders")]

RFM_SEGMENT_ORDER = ["Champions", "Loyal", "Potential loyalists", "New customers",
                     "Needs attention", "At risk", "Lost"]


def customer_table(df: pd.DataFrame, snapshot: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per customer with orders, revenue, profit, dates and recency.

    snapshot: the "today" used for recency. Default = day after the last order.
    """
    snapshot = snapshot or df["order_date"].max() + pd.Timedelta(days=1)
    g = df.groupby("customer_id")
    c = pd.DataFrame({
        "customer_name": g["customer_name"].first(),
        "segment": g["segment"].first(),
        "total_orders": g["order_id"].nunique(),
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "units_sold": g["quantity"].sum(),
        "first_order_date": g["order_date"].min(),
        "last_order_date": g["order_date"].max(),
        "active_years": g["order_year"].nunique(),
    }).reset_index()
    c["recency_days"] = (snapshot - c["last_order_date"]).dt.days
    c["tenure_days"] = (c["last_order_date"] - c["first_order_date"]).dt.days
    c["avg_order_value"] = c["revenue"] / c["total_orders"]
    c["profit_margin_pct"] = np.where(c["revenue"] != 0, 100 * c["profit"] / c["revenue"], np.nan)
    return c.sort_values("revenue", ascending=False).reset_index(drop=True)


def segment_performance(df: pd.DataFrame) -> pd.DataFrame:
    out = performance_table(df, ["segment"])
    out["total_customers"] = df.groupby("segment")["customer_id"].nunique().reindex(out["segment"]).to_numpy()
    out["avg_order_value"] = out["revenue"] / out["total_orders"]
    out["orders_per_customer"] = out["total_orders"] / out["total_customers"]
    out["revenue_per_customer"] = out["revenue"] / out["total_customers"]
    out["share_of_profit_pct"] = 100 * out["profit"] / out["profit"].sum()
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def order_frequency(customers: pd.DataFrame) -> pd.DataFrame:
    """How many customers placed 1, 2-3, 4-6, 7-9 or 10+ orders, and their revenue share."""
    rows = []
    for low, high, label in FREQUENCY_BANDS:
        sel = customers[customers["total_orders"].between(low, high)]
        rows.append({"order_band": label, "total_customers": len(sel), "revenue": sel["revenue"].sum()})
    out = pd.DataFrame(rows)
    out["share_of_customers_pct"] = 100 * out["total_customers"] / out["total_customers"].sum()
    out["share_of_revenue_pct"] = 100 * out["revenue"] / out["revenue"].sum()
    return out


def days_between_orders(df: pd.DataFrame) -> pd.Series:
    """Gaps (in days) between one order date and the next, for every customer."""
    dates = df[["customer_id", "order_date"]].drop_duplicates().sort_values(["customer_id", "order_date"])
    gaps = dates.groupby("customer_id")["order_date"].diff().dt.days
    return gaps.dropna()


def concentration(customers: pd.DataFrame, top_pct: float = 20) -> float:
    """Share of revenue (%) from the top `top_pct` % of customers."""
    n = max(1, int(np.ceil(len(customers) * top_pct / 100)))
    top = customers.nlargest(n, "revenue")["revenue"].sum()
    return 100 * top / customers["revenue"].sum()


def customer_pareto(customers: pd.DataFrame) -> pd.DataFrame:
    """Customers sorted by revenue with cumulative share (same columns as products.pareto)."""
    p = customers.sort_values(["revenue", "customer_id"], ascending=[False, True]).reset_index(drop=True)
    p["cum_share_pct"] = 100 * p["revenue"].cumsum() / p["revenue"].sum()
    p["rank_pct"] = 100 * (np.arange(len(p)) + 1) / len(p)
    return p


def _quintile_score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Score 1-5 from the customer's percentile rank.

    score = ceil(percentile x 5), so the top 20% get 5, the next 20% get 4, ...
    Tied values (e.g. two customers with 5 orders each) always get the SAME
    score, because their percentile rank is the same.
    """
    pct = values.rank(method="average", pct=True, ascending=higher_is_better)
    return np.ceil(pct * 5).clip(1, 5).astype(int)


def rfm_segment(r: int, f: int, m: int) -> str:
    """Turn the three scores into a business-friendly segment name (rules applied in order)."""
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r <= 2 and f >= 3:
        return "At risk"            # used to buy often, has not bought for a long time
    if f >= 4:
        return "Loyal"
    if r >= 4 and f == 1:
        return "New customers"
    if r >= 3 and f >= 2:
        return "Potential loyalists"
    if r <= 2 and f <= 2:
        return "Lost"
    return "Needs attention"


def rfm_table(customers: pd.DataFrame) -> pd.DataFrame:
    """Add R, F, M scores, the combined RFM code (e.g. "545") and the segment name."""
    if len(customers) < 5:
        raise ValueError("RFM needs at least 5 customers")
    c = customers.copy()
    c["r_score"] = _quintile_score(c["recency_days"], higher_is_better=False)   # fewer days = better
    c["f_score"] = _quintile_score(c["total_orders"])
    c["m_score"] = _quintile_score(c["revenue"])
    c["rfm_code"] = c["r_score"].astype(str) + c["f_score"].astype(str) + c["m_score"].astype(str)
    c["rfm_segment"] = [rfm_segment(r, f, m) for r, f, m in zip(c["r_score"], c["f_score"], c["m_score"])]
    return c


def rfm_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    g = rfm.groupby("rfm_segment")
    s = pd.DataFrame({
        "total_customers": g.size(),
        "revenue": g["revenue"].sum(),
        "profit": g["profit"].sum(),
        "avg_recency_days": g["recency_days"].mean(),
        "avg_orders": g["total_orders"].mean(),
        "avg_revenue": g["revenue"].mean(),
    })
    s["share_of_customers_pct"] = 100 * s["total_customers"] / s["total_customers"].sum()
    s["share_of_revenue_pct"] = 100 * s["revenue"] / s["revenue"].sum()
    s = s.reindex([seg for seg in RFM_SEGMENT_ORDER if seg in s.index])
    s.index.name = "rfm_segment"
    return s.reset_index()


def new_vs_returning(df: pd.DataFrame) -> pd.DataFrame:
    """Per year: active, new and returning customers, their revenue, and retention.

    new       = first-ever order was in this year
    returning = bought in an earlier year too
    retention = % of last year's active customers who bought again this year
    """
    first_year = df.groupby("customer_id")["order_year"].min().rename("first_year")
    d = df.join(first_year, on="customer_id")
    d["customer_type"] = np.where(d["order_year"] == d["first_year"], "new", "returning")
    rows = []
    years = sorted(d["order_year"].unique())
    active_by_year = {y: set(d.loc[d["order_year"] == y, "customer_id"]) for y in years}
    for y in years:
        dy = d[d["order_year"] == y]
        new = dy[dy["customer_type"] == "new"]
        ret = dy[dy["customer_type"] == "returning"]
        prev = active_by_year.get(y - 1)
        retention = 100 * len(prev & active_by_year[y]) / len(prev) if prev else np.nan
        rows.append({
            "order_year": y,
            "active_customers": dy["customer_id"].nunique(),
            "new_customers": new["customer_id"].nunique(),
            "returning_customers": ret["customer_id"].nunique(),
            "revenue_new": new["sales"].sum(),
            "revenue_returning": ret["sales"].sum(),
            "retention_pct": retention,
        })
    out = pd.DataFrame(rows)
    out["returning_revenue_share_pct"] = 100 * out["revenue_returning"] / (out["revenue_new"] + out["revenue_returning"])
    return out


def customer_summary(df: pd.DataFrame) -> dict[str, object]:
    customers = customer_table(df)
    seg = segment_performance(df)
    rfm = rfm_summary(rfm_table(customers)).set_index("rfm_segment")
    gaps = days_between_orders(df)
    nvr = new_vs_returning(df)

    def seg_value(name: str, col: str) -> float:
        return float(rfm.loc[name, col]) if name in rfm.index else 0.0

    return {
        "total_customers": len(customers),
        "repeat_customers": int((customers["total_orders"] >= 2).sum()),
        "repeat_rate_pct": 100 * float((customers["total_orders"] >= 2).mean()),
        "avg_orders_per_customer": float(customers["total_orders"].mean()),
        "median_days_between_orders": float(gaps.median()) if len(gaps) else float("nan"),
        "avg_revenue_per_customer": float(customers["revenue"].mean()),
        "median_revenue_per_customer": float(customers["revenue"].median()),
        "top10pct_customers_revenue_share": concentration(customers, 10),
        "top20pct_customers_revenue_share": concentration(customers, 20),
        "top_customer": customers.loc[0, "customer_name"],
        "top_customer_revenue": float(customers.loc[0, "revenue"]),
        "loss_making_customers": int((customers["profit"] < 0).sum()),
        "top_segment_by_revenue": seg.loc[0, "segment"],
        "top_segment_revenue_share_pct": float(seg.loc[0, "share_of_revenue_pct"]),
        "best_margin_segment": seg.loc[seg["profit_margin_pct"].idxmax(), "segment"],
        "champions_customers": int(seg_value("Champions", "total_customers")),
        "champions_revenue_share_pct": seg_value("Champions", "share_of_revenue_pct"),
        "at_risk_customers": int(seg_value("At risk", "total_customers")),
        "at_risk_revenue_share_pct": seg_value("At risk", "share_of_revenue_pct"),
        "last_year_retention_pct": float(nvr["retention_pct"].iloc[-1]),
        "last_year_returning_revenue_share_pct": float(nvr["returning_revenue_share_pct"].iloc[-1]),
    }
