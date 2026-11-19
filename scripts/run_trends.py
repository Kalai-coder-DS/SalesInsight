"""Phase 6 (Q2): monthly and yearly sales trends and seasonality.

Run from the project root:
    python scripts/run_trends.py

Outputs:
    reports/tables/monthly_sales.csv       one row per month, with moving average and growth
    reports/tables/quarterly_sales.csv
    reports/tables/revenue_by_month_year.csv
    reports/tables/seasonality.csv
    reports/tables/weekday_sales.csv
    reports/tables/trend_summary.csv
    reports/figures/06_monthly_revenue_trend.png
    reports/figures/06_revenue_heatmap.png
    reports/figures/06_seasonality_index.png
    reports/figures/06_weekday_orders.png
"""

from __future__ import annotations

import sys

import pandas as pd

from salesinsight import config
from salesinsight import trends as t
from salesinsight import visualization as viz
from salesinsight.data_loader import load_clean_data
from salesinsight.kpis import short_money
from salesinsight.logger import get_logger

logger = get_logger("run_trends")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    monthly = t.monthly_sales(df)
    quarterly = t.quarterly_sales(df)
    matrix = t.revenue_matrix(monthly)
    season = t.seasonality(monthly)
    weekday = t.weekday_sales(df)
    summary = t.trend_summary(df)

    tables = {
        "monthly_sales": monthly.assign(period=monthly["period"].dt.strftime("%Y-%m")),
        "quarterly_sales": quarterly,
        "revenue_by_month_year": matrix.reset_index(),
        "seasonality": season,
        "weekday_sales": weekday,
        "trend_summary": pd.DataFrame(
            [(k, round(v, 2) if isinstance(v, float) else v) for k, v in summary.items()],
            columns=["metric", "value"]),
    }
    for name, table in tables.items():
        table.round(2).to_csv(config.TABLES_DIR / f"{name}.csv", index=False)

    s = summary
    logger.info("-" * 60)
    logger.info("Trend summary %d-%d", s["first_year"], s["last_year"])
    logger.info("  Revenue CAGR             : %.1f%% per year", s["revenue_cagr_pct"])
    logger.info("  Best month               : %s (%s)", s["best_month"], short_money(s["best_month_revenue"]))
    logger.info("  Weakest month            : %s (%s)", s["worst_month"], short_money(s["worst_month_revenue"]))
    logger.info("  Peak season              : %s (index %.0f, 100 = average)", s["peak_season_month"], s["peak_season_index"])
    logger.info("  Low season               : %s (index %.0f)", s["low_season_month"], s["low_season_index"])
    logger.info("  Q4 share of revenue      : %.1f%%", s["q4_share_of_revenue_pct"])
    logger.info("  Linear trend             : %s per month (R-squared %.2f)",
                f"{s['monthly_trend_slope']:+,.0f}", s["monthly_trend_r_squared"])
    logger.info("  Busiest weekday (orders) : %s", s["busiest_weekday"])

    paths = [
        viz.plot_monthly_trend(monthly),
        viz.plot_revenue_heatmap(matrix),
        viz.plot_seasonality_index(season),
        viz.plot_weekday_orders(weekday),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved %d tables to reports/tables/", len(tables))
    logger.info("Phase 6 complete. Ready for Phase 7 (products and categories).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
