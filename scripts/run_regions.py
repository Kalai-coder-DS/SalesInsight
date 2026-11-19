"""Phase 8 (Q5): region-wise and state-wise sales.

Run from the project root:
    python scripts/run_regions.py

Outputs (reports/tables/):
    region_performance.csv, state_performance.csv, city_performance.csv,
    top10_states_by_revenue.csv, bottom10_states_by_profit.csv,
    region_category_margin.csv, region_category_revenue.csv,
    region_yearly.csv, region_cagr.csv, region_summary.csv
Charts (reports/figures/):
    08_region_performance.png, 08_top10_states_by_revenue.png,
    08_state_profit_extremes.png, 08_region_category_margin.png,
    08_state_discount_vs_margin.png, 08_region_revenue_by_year.png
"""

from __future__ import annotations

import sys

import pandas as pd

from salesinsight import config
from salesinsight import regions as rg
from salesinsight import visualization as viz
from salesinsight.data_loader import load_clean_data
from salesinsight.kpis import short_money
from salesinsight.logger import get_logger

logger = get_logger("run_regions")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    regions = rg.region_performance(df)
    states = rg.state_performance(df)
    yearly = rg.region_yearly(df)
    cagr = rg.region_cagr(yearly)
    margin_matrix = rg.region_category_matrix(df, "profit_margin_pct")
    summary = rg.region_summary(df)

    tables = {
        "region_performance": regions,
        "state_performance": states,
        "city_performance": rg.city_performance(df),
        "top10_states_by_revenue": rg.top_states(states, "revenue"),
        "bottom10_states_by_profit": rg.bottom_states(states, "profit"),
        "region_category_margin": margin_matrix.reset_index(),
        "region_category_revenue": rg.region_category_matrix(df, "revenue").reset_index(),
        "region_yearly": yearly,
        "region_cagr": cagr,
        "region_summary": pd.DataFrame(
            [(k, round(v, 2) if isinstance(v, float) else v) for k, v in summary.items()],
            columns=["metric", "value"]),
    }
    for name, table in tables.items():
        table.round(2).to_csv(config.TABLES_DIR / f"{name}.csv", index=False)

    s = summary
    logger.info("-" * 60)
    logger.info("Regions (Q5)")
    for _, r in regions.iterrows():
        logger.info("  %-8s revenue %9s (%4.1f%%)  profit %9s  margin %5.1f%%  discount %4.1f%%",
                    r["region"], short_money(r["revenue"]), r["share_of_revenue_pct"],
                    short_money(r["profit"]), r["profit_margin_pct"], r["effective_discount_pct"])
    logger.info("  Fastest-growing region      : %s (CAGR %.1f%%)", s["fastest_growing_region"],
                s["fastest_growing_region_cagr_pct"])
    logger.info("States")
    logger.info("  Top state by revenue        : %s (%s)", s["top_state_by_revenue"], short_money(s["top_state_revenue"]))
    logger.info("  Top state by profit         : %s (%s)", s["top_state_by_profit"], short_money(s["top_state_profit"]))
    logger.info("  Biggest loss-making state   : %s (%s)", s["worst_state_by_profit"], short_money(s["worst_state_profit"]))
    logger.info("  States losing money         : %d (total %s)", s["loss_making_states"],
                short_money(s["loss_making_states_total"]))
    logger.info("  They are                    : %s", s["loss_making_states_list"] or "none")
    logger.info("  Discount vs margin (states) : correlation %.2f", s["state_discount_margin_correlation"])

    paths = [
        viz.plot_region_performance(regions),
        viz.plot_top_states_revenue(rg.top_states(states, "revenue")),
        viz.plot_state_profit_extremes(states),
        viz.plot_region_category_heatmap(margin_matrix),
        viz.plot_state_discount_vs_margin(states, s["state_discount_margin_correlation"]),
        viz.plot_region_revenue_by_year(yearly),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved %d tables to reports/tables/", len(tables))
    logger.info("Phase 8 complete. Ready for Phase 9 (customer behaviour).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
