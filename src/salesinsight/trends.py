"""Phase 6 (Q2): monthly and yearly sales trends.

What this module answers:
- How do revenue, profit and orders move month by month?
- What is the smoothed trend (3-month moving average)?
- How much did each month grow versus the previous month and the same
  month last year?
- Which months are always strong or weak (seasonality)?
- Which weekdays get the most orders?
- What is the compound annual growth rate (CAGR) and the linear trend?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def monthly_sales(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """One row per calendar month, including months with no sales (filled with 0).

    Columns: period (first day of month), year, month, revenue, profit,
    total_orders, profit_margin_pct, revenue_ma (moving average over `window`
    months), revenue_mom_pct (vs previous month), revenue_yoy_pct (vs same
    month one year earlier).
    """
    period = df["order_date"].dt.to_period("M")
    g = df.groupby(period)
    monthly = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
    })
    # Make sure every month between the first and last appears exactly once.
    full_range = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
    monthly = monthly.reindex(full_range, fill_value=0)
    monthly.index.name = "period"
    monthly = monthly.reset_index()

    monthly["year"] = monthly["period"].dt.year
    monthly["month"] = monthly["period"].dt.month
    monthly["period"] = monthly["period"].dt.to_timestamp()
    monthly["profit_margin_pct"] = np.where(
        monthly["revenue"] > 0, 100 * monthly["profit"] / monthly["revenue"], np.nan)
    monthly["revenue_ma"] = monthly["revenue"].rolling(window, min_periods=window).mean()
    prev_month = monthly["revenue"].shift(1)
    prev_year = monthly["revenue"].shift(12)
    monthly["revenue_mom_pct"] = np.where(prev_month > 0, 100 * (monthly["revenue"] / prev_month - 1), np.nan)
    monthly["revenue_yoy_pct"] = np.where(prev_year > 0, 100 * (monthly["revenue"] / prev_year - 1), np.nan)
    cols = ["period", "year", "month", "revenue", "profit", "total_orders", "profit_margin_pct",
            "revenue_ma", "revenue_mom_pct", "revenue_yoy_pct"]
    return monthly[cols]


def quarterly_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["order_year", "order_quarter"])
    q = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
    }).reset_index()
    q["quarter_label"] = q["order_year"].astype(str) + "-Q" + q["order_quarter"].astype(str)
    q["share_of_year_pct"] = 100 * q["revenue"] / q.groupby("order_year")["revenue"].transform("sum")
    return q


def revenue_matrix(monthly: pd.DataFrame) -> pd.DataFrame:
    """Year x month table of revenue (rows = years, columns = Jan..Dec)."""
    m = monthly.pivot_table(index="year", columns="month", values="revenue", aggfunc="sum")
    m = m.reindex(columns=range(1, 13))
    m.columns = MONTH_NAMES
    return m


def seasonality(monthly: pd.DataFrame) -> pd.DataFrame:
    """Average revenue for each calendar month across years.

    seasonality_index = month average / average of all months x 100.
    100 = a normal month, 150 = 50% above normal, 70 = 30% below normal.
    Only complete years are used, so a partial first/last year cannot bias it.
    """
    counts = monthly.groupby("year")["month"].count()
    full_years = counts[counts == 12].index
    data = monthly[monthly["year"].isin(full_years)] if len(full_years) else monthly
    s = data.groupby("month").agg(avg_revenue=("revenue", "mean"),
                                  avg_profit=("profit", "mean"),
                                  avg_orders=("total_orders", "mean")).reset_index()
    s["month_name"] = s["month"].map(lambda m: MONTH_NAMES[m - 1])
    s["seasonality_index"] = 100 * s["avg_revenue"] / s["avg_revenue"].mean()
    s["share_of_year_pct"] = 100 * s["avg_revenue"] / s["avg_revenue"].sum()
    return s[["month", "month_name", "avg_revenue", "avg_profit", "avg_orders",
              "seasonality_index", "share_of_year_pct"]]


def weekday_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("order_weekday")
    w = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
    }).reindex(WEEKDAYS, fill_value=0)
    w.index.name = "weekday"
    w["share_of_orders_pct"] = 100 * w["total_orders"] / w["total_orders"].sum()
    return w.reset_index()


def cagr(first_value: float, last_value: float, years: int) -> float:
    """Compound annual growth rate in %: the steady yearly growth that turns
    first_value into last_value over `years` years."""
    if first_value <= 0 or years <= 0:
        return float("nan")
    return 100 * ((last_value / first_value) ** (1 / years) - 1)


def linear_trend(values: pd.Series) -> dict[str, float]:
    """Fit a straight line through the values (x = 0, 1, 2, ...).

    Returns slope (change per step), intercept and r_squared (0-1, how well
    a straight line explains the ups and downs).
    """
    y = np.asarray(values, dtype=float)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return {"slope": float(slope), "intercept": float(intercept), "r_squared": r2}


def trend_summary(df: pd.DataFrame) -> dict[str, object]:
    """Key facts about the trends, used in the console output and the final report."""
    monthly = monthly_sales(df)
    yearly = df.groupby("order_year")["sales"].sum().sort_index()
    season = seasonality(monthly)
    quarterly = quarterly_sales(df)
    weekday = weekday_sales(df)
    trend = linear_trend(monthly["revenue"])

    best = monthly.loc[monthly["revenue"].idxmax()]
    worst = monthly.loc[monthly["revenue"].idxmin()]
    peak = season.loc[season["seasonality_index"].idxmax()]
    low = season.loc[season["seasonality_index"].idxmin()]
    q4_share = quarterly.loc[quarterly["order_quarter"] == 4, "revenue"].sum() / quarterly["revenue"].sum()

    return {
        "first_year": int(yearly.index[0]),
        "last_year": int(yearly.index[-1]),
        "revenue_cagr_pct": cagr(yearly.iloc[0], yearly.iloc[-1], len(yearly) - 1),
        "best_month": best["period"].strftime("%b %Y"),
        "best_month_revenue": float(best["revenue"]),
        "worst_month": worst["period"].strftime("%b %Y"),
        "worst_month_revenue": float(worst["revenue"]),
        "peak_season_month": peak["month_name"],
        "peak_season_index": float(peak["seasonality_index"]),
        "low_season_month": low["month_name"],
        "low_season_index": float(low["seasonality_index"]),
        "q4_share_of_revenue_pct": 100 * float(q4_share),
        "monthly_trend_slope": trend["slope"],
        "monthly_trend_r_squared": trend["r_squared"],
        "busiest_weekday": weekday.loc[weekday["total_orders"].idxmax(), "weekday"],
    }
