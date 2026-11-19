"""Phase 9 (Q6): customer purchasing behaviour.

Run from the project root:
    python scripts/run_customers.py

Outputs (reports/tables/):
    customer_table.csv, customer_rfm.csv, rfm_summary.csv, segment_performance.csv,
    order_frequency.csv, new_vs_returning.csv, top10_customers.csv, customer_summary.csv
Charts (reports/figures/):
    09_segment_performance.png, 09_order_frequency.png, 09_customer_pareto.png,
    09_rfm_segments.png, 09_new_vs_returning.png
"""

from __future__ import annotations

import sys

import pandas as pd

from salesinsight import config
from salesinsight import customers as cu
from salesinsight import visualization as viz
from salesinsight.data_loader import load_clean_data
from salesinsight.kpis import short_money
from salesinsight.logger import get_logger

logger = get_logger("run_customers")


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    customers = cu.customer_table(df)
    rfm = cu.rfm_table(customers)
    rfm_sum = cu.rfm_summary(rfm)
    seg = cu.segment_performance(df)
    freq = cu.order_frequency(customers)
    nvr = cu.new_vs_returning(df)
    summary = cu.customer_summary(df)

    date_cols = ["first_order_date", "last_order_date"]
    tables = {
        "customer_table": customers.assign(**{c: customers[c].dt.strftime("%Y-%m-%d") for c in date_cols}),
        "customer_rfm": rfm[["customer_id", "customer_name", "segment", "recency_days", "total_orders",
                             "revenue", "r_score", "f_score", "m_score", "rfm_code", "rfm_segment"]],
        "rfm_summary": rfm_sum,
        "segment_performance": seg,
        "order_frequency": freq,
        "new_vs_returning": nvr,
        "top10_customers": customers.head(10).drop(columns=date_cols),
        "customer_summary": pd.DataFrame(
            [(k, round(v, 2) if isinstance(v, float) else v) for k, v in summary.items()],
            columns=["metric", "value"]),
    }
    for name, table in tables.items():
        table.round(2).to_csv(config.TABLES_DIR / f"{name}.csv", index=False)

    s = summary
    logger.info("-" * 60)
    logger.info("Customers (Q6)")
    logger.info("  Customers                   : %d", s["total_customers"])
    logger.info("  Repeat customers            : %d (%.1f%%)", s["repeat_customers"], s["repeat_rate_pct"])
    logger.info("  Orders per customer         : %.1f on average", s["avg_orders_per_customer"])
    logger.info("  Days between orders         : %.0f (median)", s["median_days_between_orders"])
    logger.info("  Revenue per customer        : %s average, %s median",
                short_money(s["avg_revenue_per_customer"]), short_money(s["median_revenue_per_customer"]))
    logger.info("  Top 10%% / 20%% of customers  : %.1f%% / %.1f%% of revenue",
                s["top10pct_customers_revenue_share"], s["top20pct_customers_revenue_share"])
    logger.info("  Customers losing money      : %d", s["loss_making_customers"])
    logger.info("Segments")
    for _, r in seg.iterrows():
        logger.info("  %-12s customers %4d  revenue %9s (%4.1f%%)  margin %5.1f%%  AOV %s",
                    r["segment"], r["total_customers"], short_money(r["revenue"]),
                    r["share_of_revenue_pct"], r["profit_margin_pct"], short_money(r["avg_order_value"]))
    logger.info("RFM segments")
    for _, r in rfm_sum.iterrows():
        logger.info("  %-20s %4d customers (%4.1f%%)  %4.1f%% of revenue",
                    r["rfm_segment"], r["total_customers"], r["share_of_customers_pct"], r["share_of_revenue_pct"])
    logger.info("New vs returning")
    for _, r in nvr.iterrows():
        retention = "" if pd.isna(r["retention_pct"]) else f"  retention {r['retention_pct']:.1f}%"
        logger.info("  %d  new %3d  returning %3d  returning share of revenue %5.1f%%%s",
                    r["order_year"], r["new_customers"], r["returning_customers"],
                    r["returning_revenue_share_pct"], retention)

    paths = [
        viz.plot_segment_performance(seg),
        viz.plot_order_frequency(freq),
        viz.plot_pareto(cu.customer_pareto(customers), entity="customers", name="09_customer_pareto"),
        viz.plot_rfm_segments(rfm_sum),
        viz.plot_new_vs_returning(nvr),
    ]
    logger.info("-" * 60)
    for p in paths:
        logger.info("Saved %s", p.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved %d tables to reports/tables/", len(tables))
    logger.info("Phase 9 complete. Ready for Phase 10 (statistical analysis).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
