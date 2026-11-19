"""Phase 4: split the clean table into a star schema, and read the SQL query file.

Star schema = one central FACT table (the sales, with numbers) linked to
DIMENSION tables (descriptions: who, what, where).

    dim_customer (customer_id)  ─┐
    dim_product  (product_key)  ─┼──  fact_sales (row_id)
    dim_location (location_id)  ─┘

Why? Each customer / product / location is stored once instead of being
repeated on thousands of rows, and SQL queries become clear joins.
This module only uses pandas, so it can be tested without a database.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from salesinsight import config

QUERY_FILE: Path = config.SQL_DIR / "03_analysis_queries.sql"

CUSTOMER_COLUMNS = ["customer_id", "customer_name", "segment"]
PRODUCT_COLUMNS = ["product_key", "product_id", "product_name", "category", "sub_category"]
LOCATION_COLUMNS = ["country", "region", "state", "city", "postal_code"]

FACT_COLUMNS = [
    "row_id", "order_id", "order_date", "ship_date", "ship_mode", "ship_days",
    "customer_id", "product_key", "location_id",
    "order_year", "order_quarter", "order_month", "order_month_name", "order_period",
    "sales", "quantity", "discount", "discount_band", "profit",
]

# Load order matters: dimensions first, then the fact table that points to them.
TABLE_ORDER = ["dim_customer", "dim_product", "dim_location", "fact_sales"]


def build_dim_customer(df: pd.DataFrame) -> pd.DataFrame:
    return (df[CUSTOMER_COLUMNS].drop_duplicates("customer_id")
            .sort_values("customer_id").reset_index(drop=True))


def build_dim_product(df: pd.DataFrame) -> pd.DataFrame:
    return (df[PRODUCT_COLUMNS].drop_duplicates("product_key")
            .sort_values("product_key").reset_index(drop=True))


def build_dim_location(df: pd.DataFrame) -> pd.DataFrame:
    """One row per unique (country, region, state, city, postal_code)."""
    dim = (df[LOCATION_COLUMNS].drop_duplicates()
           .sort_values(LOCATION_COLUMNS).reset_index(drop=True))
    dim.insert(0, "location_id", range(1, len(dim) + 1))
    return dim


def build_fact_sales(df: pd.DataFrame, dim_location: pd.DataFrame) -> pd.DataFrame:
    """Replace the location text columns with location_id, keep the numbers."""
    fact = df.merge(dim_location, on=LOCATION_COLUMNS, how="left", validate="many_to_one")
    if fact["location_id"].isna().any():
        raise ValueError("Some rows did not match a location")
    # "year_month" is a reserved word in MySQL, so the column is renamed.
    fact = fact.rename(columns={"year_month": "order_period"})[FACT_COLUMNS].copy()
    fact["location_id"] = fact["location_id"].astype("int64")
    # Plain Python dates are stored as DATE in MySQL (no time part).
    for col in ("order_date", "ship_date"):
        fact[col] = pd.to_datetime(fact[col]).dt.date
    return fact.sort_values("row_id").reset_index(drop=True)


def build_star_schema(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return the four tables, keyed by table name, in load order."""
    dim_location = build_dim_location(df)
    tables = {
        "dim_customer": build_dim_customer(df),
        "dim_product": build_dim_product(df),
        "dim_location": dim_location,
        "fact_sales": build_fact_sales(df, dim_location),
    }
    return {name: tables[name] for name in TABLE_ORDER}


def load_queries(path: Path | str = QUERY_FILE) -> dict[str, str]:
    """Read the SQL file and split it into named queries.

    Each query in the file starts with a line like:
        -- name: yearly_sales
    """
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    queries: dict[str, str] = {}
    # parts = [header, name1, body1, name2, body2, ...]
    for name, body in zip(parts[1::2], parts[2::2]):
        sql_lines = [ln for ln in body.strip().splitlines() if not ln.strip().startswith("--")]
        sql = "\n".join(sql_lines).strip().rstrip(";").strip()
        if name in queries:
            raise ValueError(f"Duplicate query name: {name}")
        queries[name] = sql
    return queries
