"""Phase 4: load the clean data into MySQL and run all analysis queries.

Run from the project root (MySQL must be running):
    python scripts/run_database.py

Steps:
  1. CREATE DATABASE salesinsight (if missing)
  2. Create the 4 star-schema tables (if missing)
  3. Split data/processed/sales_clean.csv into the star schema and load it
  4. Reconcile: totals in MySQL must equal totals in pandas
  5. Run every query in sql/03_analysis_queries.sql
     and save each result to reports/tables/sql/<query_name>.csv
"""

from __future__ import annotations

import sys

from salesinsight import config
from salesinsight.data_loader import load_clean_data
from salesinsight.database import (
    create_database, create_tables, get_engine, load_star_schema, run_all_queries, run_query,
)
from salesinsight.logger import get_logger
from salesinsight.star_schema import build_star_schema, load_queries

logger = get_logger("run_database")

SQL_RESULTS_DIR = config.TABLES_DIR / "sql"


def reconcile(engine, data) -> bool:
    """Compare SQL totals with pandas totals. Returns True if they all match."""
    sql = run_query(engine, """
        SELECT COUNT(*) AS row_count,
               SUM(sales) AS sales, SUM(profit) AS profit, SUM(quantity) AS quantity,
               COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT customer_id) AS customers
        FROM fact_sales
    """).iloc[0]
    expected = {
        "row_count": len(data), "sales": data["sales"].sum(), "profit": data["profit"].sum(),
        "quantity": data["quantity"].sum(), "orders": data["order_id"].nunique(),
        "customers": data["customer_id"].nunique(),
    }
    ok = True
    for key, pandas_value in expected.items():
        match = abs(float(sql[key]) - float(pandas_value)) < 0.01
        ok &= match
        logger.info("  %-10s SQL=%-16s pandas=%-16s %s", key, f"{float(sql[key]):,.2f}",
                    f"{float(pandas_value):,.2f}", "OK" if match else "MISMATCH")
    return ok


def main() -> int:
    data = load_clean_data()
    tables = build_star_schema(data)

    create_database()
    engine = get_engine()
    try:
        create_tables(engine)
        counts = load_star_schema(engine, tables)
        logger.info("-" * 60)
        for name, n in counts.items():
            logger.info("  %-14s %6d rows", name, n)

        logger.info("-" * 60)
        logger.info("Reconciliation (MySQL vs pandas)")
        if not reconcile(engine, data):
            logger.error("Totals do not match. Stop and check the load.")
            return 1

        logger.info("-" * 60)
        SQL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        results = run_all_queries(engine, load_queries())
        for name, df in results.items():
            df.to_csv(SQL_RESULTS_DIR / f"{name}.csv", index=False)

        kpi = results["kpi_overview"].iloc[0]
        logger.info("-" * 60)
        logger.info("Headline KPIs from MySQL")
        logger.info("  Revenue          : %s", f"{kpi['total_revenue']:,.2f}")
        logger.info("  Profit           : %s", f"{kpi['total_profit']:,.2f}")
        logger.info("  Profit margin    : %s%%", kpi["profit_margin_pct"])
        logger.info("  Orders           : %s", kpi["total_orders"])
        logger.info("  Customers        : %s", kpi["total_customers"])
        logger.info("  Avg order value  : %s", f"{kpi['avg_order_value']:,.2f}")
        logger.info("Saved %d query results to reports/tables/sql/", len(results))
        logger.info("Phase 4 complete. Ready for Phase 5 (KPI analysis in pandas).")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
