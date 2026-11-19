"""Phase 5 (Q1): calculate revenue and profit KPIs and draw the first charts.

Run from the project root:
    python scripts/run_kpis.py

Outputs:
    reports/tables/kpi_summary.csv
    reports/tables/kpi_by_year.csv
    reports/tables/kpi_pandas_vs_mysql.csv   (if Phase 4 results exist)
    reports/figures/05_kpi_tiles.png
    reports/figures/05_revenue_profit_by_year.png
    reports/figures/05_profit_margin_by_year.png
"""

from __future__ import annotations

import sys

import pandas as pd

from salesinsight import config
from salesinsight.data_loader import load_clean_data
from salesinsight.kpis import compare_with_sql, compute_kpis, format_value, kpi_table, yearly_kpis
from salesinsight.logger import get_logger
from salesinsight.visualization import (
    plot_kpi_tiles, plot_margin_by_year, plot_revenue_profit_by_year,
)

logger = get_logger("run_kpis")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    kpis = compute_kpis(df)
    table = kpi_table(kpis)
    table.to_csv(config.TABLES_DIR / "kpi_summary.csv", index=False)

    yearly = yearly_kpis(df)
    yearly.round(2).to_csv(config.TABLES_DIR / "kpi_by_year.csv", index=False)

    logger.info("-" * 60)
    logger.info("Headline KPIs (pandas)")
    for _, row in table.iterrows():
        logger.info("  %-28s %s", row["metric"], row["display"])

    logger.info("-" * 60)
    logger.info("By year")
    for _, r in yearly.iterrows():
        growth = "" if pd.isna(r["revenue_growth_pct"]) else f"  revenue growth {r['revenue_growth_pct']:+.1f}%"
        logger.info("  %d  revenue %14s  profit %12s  margin %5.1f%%%s",
                    r["order_year"], format_value(r["revenue"], "money"), format_value(r["profit"], "money"),
                    r["profit_margin_pct"], growth)

    # Cross-check against MySQL results from Phase 4.
    sql_file = config.TABLES_DIR / "sql" / "kpi_overview.csv"
    if sql_file.exists():
        check = compare_with_sql(kpis, pd.read_csv(sql_file).iloc[0])
        check.to_csv(config.TABLES_DIR / "kpi_pandas_vs_mysql.csv", index=False)
        logger.info("-" * 60)
        logger.info("pandas vs MySQL: %d of %d KPIs match", check["match"].sum(), len(check))
        if not check["match"].all():
            logger.error("Mismatch:\n%s", check[~check["match"]].to_string(index=False))
            return 1
    else:
        logger.warning("No MySQL results found; run scripts/run_database.py to cross-check.")

    paths = [
        plot_kpi_tiles(kpis),
        plot_revenue_profit_by_year(yearly),
        plot_margin_by_year(yearly, kpis["profit_margin_pct"]),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Phase 5 complete. Ready for Phase 6 (sales trends).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
