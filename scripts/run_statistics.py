"""Phase 10: statistical tests - are the patterns real or chance?

Run from the project root:
    python scripts/run_statistics.py

Outputs (reports/tables/):
    statistical_tests.csv        one row per test: p-value, effect size, plain-English conclusion
    descriptive_statistics.csv   mean, median, spread, skewness, outliers
    aov_confidence_by_year.csv   average order value with 95% bootstrap confidence interval
Charts (reports/figures/):
    10_margin_by_discount_box.png, 10_loss_rate_by_discount.png,
    10_margin_by_region_box.png, 10_aov_confidence.png
"""

from __future__ import annotations

import sys

from salesinsight import config
from salesinsight import stats_tests as st
from salesinsight import visualization as viz
from salesinsight.data_loader import load_clean_data
from salesinsight.logger import get_logger

logger = get_logger("run_statistics")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    results = st.run_all_tests(df)
    table = st.results_to_frame(results)
    table.to_csv(config.TABLES_DIR / "statistical_tests.csv", index=False)
    descriptive = st.descriptive_statistics(df)
    descriptive.round(3).to_csv(config.TABLES_DIR / "descriptive_statistics.csv", index=False)
    aov_ci = st.aov_confidence_by_year(df)
    aov_ci.round(2).to_csv(config.TABLES_DIR / "aov_confidence_by_year.csv", index=False)

    logger.info("-" * 60)
    logger.info("Descriptive statistics (order lines)")
    for _, r in descriptive.iterrows():
        logger.info("  %-18s mean %10.2f  median %9.2f  skew %5.2f  outliers %5.1f%%",
                    r["variable"], r["mean"], r["median"], r["skewness"], r["outliers_pct"])
    logger.info("-" * 60)
    logger.info("Statistical tests (significance level %.2f)", st.ALPHA)
    for r in results:
        logger.info("[%s] %s", "SIGNIFICANT" if r.significant else "not significant", r.question)
        logger.info("    %s", r.conclusion)
    logger.info("-" * 60)
    logger.info("Average order value, 95 percent confidence interval")
    for _, r in aov_ci.iterrows():
        logger.info("  %d  $%.2f  ($%.2f to $%.2f)", r["order_year"], r["avg_order_value"],
                    r["ci_lower"], r["ci_upper"])

    by_test = {r.test: r for r in results}
    paths = [
        viz.plot_margin_by_discount_box(df, by_test["discount_vs_margin"].conclusion),
        viz.plot_loss_rate_by_discount(df, by_test["discount_vs_loss"].conclusion),
        viz.plot_margin_by_region_box(df, by_test["region_margin"].conclusion),
        viz.plot_aov_confidence(aov_ci),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved 3 tables to reports/tables/")
    logger.info("Phase 10 complete. Ready for Phase 11 (insights report).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
