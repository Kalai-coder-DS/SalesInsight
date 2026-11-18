"""Phase 3: clean the raw data, add features and save the processed file.

Run from the project root:
    python scripts/run_cleaning.py

Outputs:
    data/processed/sales_clean.csv     <- used by every later phase
    reports/tables/cleaning_log.csv    <- what was changed and why
"""

from __future__ import annotations

import sys

from salesinsight import config
from salesinsight.cleaning import clean_data
from salesinsight.data_loader import load_clean_data, load_raw_data
from salesinsight.features import add_all_features
from salesinsight.logger import get_logger

logger = get_logger("run_cleaning")


def check_clean(df) -> list[str]:
    """Final checks on the cleaned data. Returns a list of problems (empty = OK)."""
    problems = []
    key_cols = ["row_id", "order_id", "order_date", "ship_date", "customer_id",
                "product_key", "sales", "quantity", "discount", "profit"]
    if df[key_cols].isna().any().any():
        problems.append("Missing values in key columns")
    if df["row_id"].duplicated().any():
        problems.append("Duplicate row_id")
    if df.drop(columns="row_id").duplicated().any():
        problems.append("Duplicate records remain")
    if (df["ship_days"] < 0).any():
        problems.append("Negative ship_days")
    if df["discount_band"].isna().any():
        problems.append("Rows without a discount_band")
    return problems


def main() -> int:
    config.ensure_directories()

    raw = load_raw_data()
    clean, log = clean_data(raw)
    data = add_all_features(clean)

    problems = check_clean(data)
    if problems:
        for p in problems:
            logger.error("Clean data check failed: %s", p)
        return 1

    data.to_csv(config.CLEAN_DATA_FILE, index=False, date_format="%Y-%m-%d")
    log.to_csv(config.TABLES_DIR / "cleaning_log.csv", index=False)

    # Read the file back to prove it can be loaded correctly.
    reloaded = load_clean_data()
    assert len(reloaded) == len(data), "Row count changed after saving"

    logger.info("-" * 60)
    logger.info("Rows: %d raw -> %d clean (%d removed)", len(raw), len(data), len(raw) - len(data))
    logger.info("Columns: %d raw -> %d clean", raw.shape[1], data.shape[1])
    logger.info("Total sales  : %s", f"{data['sales'].sum():,.2f}")
    logger.info("Total profit : %s", f"{data['profit'].sum():,.2f}")
    logger.info("Loss-making rows: %d (%.1f%%)", data["is_loss"].sum(), 100 * data["is_loss"].mean())
    logger.info("Saved %s", config.CLEAN_DATA_FILE.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved reports/tables/cleaning_log.csv")
    logger.info("Phase 3 complete. Ready for Phase 4 (MySQL database).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
