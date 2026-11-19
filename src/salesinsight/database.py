"""Phase 4: create the MySQL database, load the star schema and run SQL queries.

The same code also works with SQLite, which the tests use, so the tests
run without a MySQL server.

Main functions:
    get_engine()             connect to MySQL using the settings in .env
    create_database()        CREATE DATABASE IF NOT EXISTS salesinsight
    create_tables(engine)    create the 4 star-schema tables
    load_star_schema(...)    empty the tables and insert fresh data
    run_query(engine, sql)   run a SELECT and get a pandas DataFrame
"""

from __future__ import annotations

import re

import pandas as pd
from sqlalchemy import (
    Column, Date, Engine, ForeignKey, Index, Integer, MetaData, Numeric, String,
    Table, create_engine, text,
)

from salesinsight import config
from salesinsight.logger import get_logger
from salesinsight.star_schema import TABLE_ORDER

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Table definitions (must match sql/02_create_tables.sql - a test checks this)
# ---------------------------------------------------------------------------
metadata = MetaData()

dim_customer = Table(
    "dim_customer", metadata,
    Column("customer_id", String(20), primary_key=True),
    Column("customer_name", String(100), nullable=False),
    Column("segment", String(20), nullable=False),
)

dim_product = Table(
    "dim_product", metadata,
    Column("product_key", String(10), primary_key=True),
    Column("product_id", String(20), nullable=False),
    Column("product_name", String(255), nullable=False),
    Column("category", String(30), nullable=False),
    Column("sub_category", String(30), nullable=False),
    Index("ix_product_category", "category", "sub_category"),
)

dim_location = Table(
    "dim_location", metadata,
    Column("location_id", Integer, primary_key=True, autoincrement=False),
    Column("country", String(50), nullable=False),
    Column("region", String(10), nullable=False),
    Column("state", String(50), nullable=False),
    Column("city", String(60), nullable=False),
    Column("postal_code", String(10)),
    Index("ix_location_region_state", "region", "state"),
)

fact_sales = Table(
    "fact_sales", metadata,
    Column("row_id", Integer, primary_key=True, autoincrement=False),
    Column("order_id", String(20), nullable=False),
    Column("order_date", Date, nullable=False),
    Column("ship_date", Date, nullable=False),
    Column("ship_mode", String(20), nullable=False),
    Column("ship_days", Integer, nullable=False),
    Column("customer_id", String(20), ForeignKey("dim_customer.customer_id"), nullable=False),
    Column("product_key", String(10), ForeignKey("dim_product.product_key"), nullable=False),
    Column("location_id", Integer, ForeignKey("dim_location.location_id"), nullable=False),
    Column("order_year", Integer, nullable=False),
    Column("order_quarter", Integer, nullable=False),
    Column("order_month", Integer, nullable=False),
    Column("order_month_name", String(3), nullable=False),
    Column("order_period", String(7), nullable=False),
    Column("sales", Numeric(12, 4), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("discount", Numeric(5, 4), nullable=False),
    Column("discount_band", String(20), nullable=False),
    Column("profit", Numeric(12, 4), nullable=False),
    Index("ix_fact_order_id", "order_id"),
    Index("ix_fact_order_date", "order_date"),
    Index("ix_fact_year_month", "order_year", "order_month"),
)

_VALID_NAME = re.compile(r"^[A-Za-z0-9_]+$")


# ---------------------------------------------------------------------------
# Connecting
# ---------------------------------------------------------------------------
def check_database_name(name: str) -> str:
    """Allow only letters, digits and _ (the name is placed directly in SQL)."""
    if not _VALID_NAME.match(name):
        raise ValueError(f"Invalid database name: {name!r}")
    return name


def get_engine(include_database: bool = True) -> Engine:
    """Create a SQLAlchemy engine for MySQL from the .env settings."""
    return create_engine(config.get_mysql_url(include_database), pool_pre_ping=True)


def create_database(name: str = config.MYSQL_DATABASE) -> None:
    """CREATE DATABASE IF NOT EXISTS (needs a server-only connection)."""
    name = check_database_name(name)
    engine = get_engine(include_database=False)
    try:
        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            ))
        logger.info("Database '%s' is ready", name)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Tables and loading
# ---------------------------------------------------------------------------
def create_tables(engine: Engine) -> None:
    """Create the 4 tables if they do not exist yet."""
    metadata.create_all(engine)
    logger.info("Tables ready: %s", ", ".join(TABLE_ORDER))


def load_star_schema(engine: Engine, tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace the contents of all 4 tables in one transaction.

    Steps: delete old rows (fact first, because it points to the
    dimensions), then insert dimensions first, then facts. If anything
    fails, the transaction is rolled back and the old data stays.
    Returns the number of rows in each table after loading.
    """
    with engine.begin() as conn:
        for name in reversed(TABLE_ORDER):
            conn.execute(text(f"DELETE FROM {name}"))
        for name in TABLE_ORDER:
            tables[name].to_sql(name, conn, if_exists="append", index=False, chunksize=1000)
            logger.info("Inserted %d rows into %s", len(tables[name]), name)

    return table_row_counts(engine)


def table_row_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {name: int(conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar())
                for name in TABLE_ORDER}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _to_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """MySQL returns DECIMAL values as Python Decimal objects; turn them into floats."""
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass  # real text column, keep as is
    return df


def run_query(engine: Engine, sql: str) -> pd.DataFrame:
    """Run one SELECT statement and return the result as a DataFrame."""
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, coerce_float=True)
    return _to_numbers(df)


def run_all_queries(engine: Engine, queries: dict[str, str]) -> dict[str, pd.DataFrame]:
    results = {}
    for name, sql in queries.items():
        results[name] = run_query(engine, sql)
        logger.info("Query %-28s -> %d rows", name, len(results[name]))
    return results
