"""Phase 5 (Q1): revenue and profit KPIs, calculated with pandas.

Definitions (fixed in Phase 0, identical to the SQL in kpi_overview):
    revenue              = sum of sales (sales is already after discount)
    profit margin        = profit / revenue
    orders               = number of distinct order_id
    average order value  = revenue / orders
    effective discount   = money given away as discount / price before discount
"""

from __future__ import annotations

import pandas as pd


def compute_kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs for the whole dataset (or any slice of it)."""
    revenue = float(df["sales"].sum())
    profit = float(df["profit"].sum())
    orders = int(df["order_id"].nunique())
    units = int(df["quantity"].sum())
    gross = float(df["gross_sales"].sum())
    discount_given = float(df["discount_amount"].sum())
    loss_rows = df["profit"] < 0

    return {
        "total_revenue": revenue,
        "total_profit": profit,
        "profit_margin_pct": 100 * profit / revenue if revenue else float("nan"),
        "total_orders": orders,
        "total_customers": int(df["customer_id"].nunique()),
        "total_products": int(df["product_key"].nunique()),
        "units_sold": units,
        "avg_order_value": revenue / orders if orders else float("nan"),
        "avg_units_per_order": units / orders if orders else float("nan"),
        "revenue_before_discount": gross,
        "discount_given": discount_given,
        "effective_discount_pct": 100 * discount_given / gross if gross else float("nan"),
        "avg_line_discount_pct": 100 * float(df["discount"].mean()),
        "loss_lines": int(loss_rows.sum()),
        "loss_lines_pct": 100 * float(loss_rows.mean()),
        "loss_amount": float(df.loc[loss_rows, "profit"].sum()),
        "first_order_date": df["order_date"].min(),
        "last_order_date": df["order_date"].max(),
    }


def kpis_by(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Main KPIs for each group, e.g. kpis_by(df, "order_year")."""
    g = df.groupby(by)
    out = pd.DataFrame({
        "revenue": g["sales"].sum(),
        "profit": g["profit"].sum(),
        "total_orders": g["order_id"].nunique(),
        "total_customers": g["customer_id"].nunique(),
        "units_sold": g["quantity"].sum(),
        "discount_given": g["discount_amount"].sum(),
    })
    out["profit_margin_pct"] = 100 * out["profit"] / out["revenue"]
    out["avg_order_value"] = out["revenue"] / out["total_orders"]
    return out.reset_index()


def yearly_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """KPIs per year plus year-on-year growth (%) of revenue, profit and orders."""
    yearly = kpis_by(df, "order_year").sort_values("order_year").reset_index(drop=True)
    for col in ("revenue", "profit", "total_orders"):
        yearly[f"{col}_growth_pct"] = 100 * yearly[col].pct_change()
    return yearly


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------
KPI_LABELS: dict[str, tuple[str, str]] = {
    # key: (label, format) - format is "money", "pct", "int" or "num"
    "total_revenue": ("Total revenue", "money"),
    "total_profit": ("Total profit", "money"),
    "profit_margin_pct": ("Profit margin", "pct"),
    "total_orders": ("Orders", "int"),
    "total_customers": ("Customers", "int"),
    "total_products": ("Products", "int"),
    "units_sold": ("Units sold", "int"),
    "avg_order_value": ("Average order value", "money"),
    "avg_units_per_order": ("Units per order", "num"),
    "revenue_before_discount": ("Revenue before discount", "money"),
    "discount_given": ("Discount given away", "money"),
    "effective_discount_pct": ("Effective discount rate", "pct"),
    "avg_line_discount_pct": ("Average line discount", "pct"),
    "loss_lines": ("Loss-making order lines", "int"),
    "loss_lines_pct": ("Share of lines at a loss", "pct"),
    "loss_amount": ("Total loss on those lines", "money"),
}


def format_value(value: float, kind: str) -> str:
    if kind == "money":
        sign = "-" if value < 0 else ""
        return f"{sign}${abs(value):,.2f}"
    if kind == "pct":
        return f"{value:.2f}%"
    if kind == "int":
        return f"{int(value):,}"
    return f"{value:,.2f}"


def short_money(value: float) -> str:
    """$2.30M, $286.4K - for chart labels and tiles."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:.1f}K"
    return f"{sign}${v:,.0f}"


def kpi_table(kpis: dict[str, float]) -> pd.DataFrame:
    """KPIs as a 3-column table: metric, value, display (formatted text)."""
    rows = []
    for key, (label, kind) in KPI_LABELS.items():
        rows.append({"metric": label, "key": key, "value": round(kpis[key], 4),
                     "display": format_value(kpis[key], kind)})
    return pd.DataFrame(rows)


def compare_with_sql(kpis: dict[str, float], sql_kpi: pd.Series) -> pd.DataFrame:
    """Put pandas and MySQL KPIs side by side (MySQL values are rounded to 2 dp)."""
    pairs = {
        "total_revenue": "total_revenue",
        "total_profit": "total_profit",
        "profit_margin_pct": "profit_margin_pct",
        "total_orders": "total_orders",
        "total_customers": "total_customers",
        "units_sold": "units_sold",
        "avg_order_value": "avg_order_value",
    }
    rows = []
    for py_key, sql_key in pairs.items():
        py_val = round(float(kpis[py_key]), 2)
        sql_val = float(sql_kpi[sql_key])
        rows.append({"kpi": py_key, "pandas": py_val, "mysql": sql_val,
                     "match": abs(py_val - sql_val) <= 0.01})
    return pd.DataFrame(rows)
