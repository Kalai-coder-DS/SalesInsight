"""Phase 7 (Q3, Q4): best-selling products and category performance.

Run from the project root:
    python scripts/run_products.py

Outputs (reports/tables/):
    product_performance.csv, top10_products_by_revenue.csv, top10_products_by_units.csv,
    top10_products_by_profit.csv, bottom10_products_by_profit.csv, loss_making_products.csv,
    category_performance.csv, subcategory_performance.csv, discount_margin_matrix.csv,
    discount_band_performance.csv, product_summary.csv
Charts (reports/figures/):
    07_top10_products_by_revenue.png, 07_top10_products_by_profit.png,
    07_category_performance.png, 07_subcategory_profit.png,
    07_pareto_revenue.png, 07_discount_margin_heatmap.png
"""

from __future__ import annotations

import sys

import pandas as pd

from salesinsight import config
from salesinsight import products as pr
from salesinsight import visualization as viz
from salesinsight.data_loader import load_clean_data
from salesinsight.kpis import short_money
from salesinsight.logger import get_logger

logger = get_logger("run_products")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    perf = pr.product_performance(df)
    cats = pr.category_performance(df)
    subs = pr.subcategory_performance(df)
    matrix = pr.discount_margin_matrix(df)
    summary = pr.product_summary(df)

    tables = {
        "product_performance": perf.sort_values("revenue", ascending=False),
        "top10_products_by_revenue": pr.top_products(perf, "revenue"),
        "top10_products_by_units": pr.top_products(perf, "units_sold"),
        "top10_products_by_profit": pr.top_products(perf, "profit"),
        "bottom10_products_by_profit": pr.bottom_products(perf, "profit"),
        "loss_making_products": pr.loss_making_products(perf),
        "category_performance": cats,
        "subcategory_performance": subs,
        "discount_margin_matrix": matrix.reset_index(),
        "discount_band_performance": pr.discount_band_performance(df),
        "product_summary": pd.DataFrame(
            [(k, round(v, 2) if isinstance(v, float) else v) for k, v in summary.items()],
            columns=["metric", "value"]),
    }
    for name, table in tables.items():
        table.round(2).to_csv(config.TABLES_DIR / f"{name}.csv", index=False)

    s = summary
    logger.info("-" * 60)
    logger.info("Products (Q3)")
    logger.info("  Products sold               : %d", s["products_total"])
    logger.info("  Top product by revenue      : %s (%s)", s["top_product_by_revenue"], short_money(s["top_product_revenue"]))
    logger.info("  Biggest loss-making product : %s (%s)", s["worst_product_by_profit"], short_money(s["worst_product_profit"]))
    logger.info("  80%% of revenue comes from   : %d products (%.1f%% of all)",
                s["products_for_80pct_revenue"], s["products_for_80pct_revenue_pct"])
    logger.info("  Top 20%% of products earn    : %.1f%% of revenue", s["top20pct_products_revenue_share"])
    logger.info("  Products losing money       : %d (total %s)", s["loss_making_products"],
                short_money(s["loss_making_products_total"]))
    logger.info("Categories (Q4)")
    for _, c in cats.iterrows():
        logger.info("  %-16s revenue %10s  profit %9s  margin %5.1f%%", c["category"],
                    short_money(c["revenue"]), short_money(c["profit"]), c["profit_margin_pct"])
    logger.info("  Best sub-category (profit)  : %s (%s)", s["best_subcategory_by_profit"], short_money(s["best_subcategory_profit"]))
    logger.info("  Worst sub-category (profit) : %s (%s)", s["worst_subcategory_by_profit"], short_money(s["worst_subcategory_profit"]))
    logger.info("  Sub-categories at a loss    : %s", s["loss_subcategories"] or "none")
    logger.info("Discount effect")
    logger.info("  Margin with no discount     : %.1f%%", s["margin_no_discount_pct"])
    logger.info("  Margin with over 40%% off    : %.1f%%", s["margin_over_40pct_discount_pct"])

    paths = [
        viz.plot_top_products(pr.top_products(perf, "revenue"), "revenue"),
        viz.plot_top_products(pr.top_products(perf, "profit"), "profit"),
        viz.plot_category_performance(cats),
        viz.plot_subcategory_profit(subs),
        viz.plot_pareto(pr.pareto(perf)),
        viz.plot_discount_margin_heatmap(matrix),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved %d tables to reports/tables/", len(tables))
    logger.info("Phase 7 complete. Ready for Phase 8 (regions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
