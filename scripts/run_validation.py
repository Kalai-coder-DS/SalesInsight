"""Phase 2: load the raw data, check its quality and write two reports.

Run from the project root:
    python scripts/run_validation.py

Outputs:
    reports/tables/data_quality_report.csv
    reports/tables/data_dictionary.csv
Exit code 0 = no FAIL checks, 1 = at least one FAIL.
"""

from __future__ import annotations

import sys

from salesinsight import config
from salesinsight.data_loader import load_raw_data, summarise
from salesinsight.logger import get_logger
from salesinsight.validation import (
    FAIL, PASS, WARN, build_data_dictionary, has_failures, results_to_frame, run_all_checks,
)

logger = get_logger("run_validation")


def main() -> int:
    config.ensure_directories()

    df = load_raw_data()

    logger.info("-" * 60)
    logger.info("Dataset summary")
    for key, value in summarise(df).items():
        logger.info("  %-22s %s", key, value)
    logger.info("-" * 60)

    results = run_all_checks(df)
    report = results_to_frame(results)
    quality_path = config.TABLES_DIR / "data_quality_report.csv"
    report.to_csv(quality_path, index=False)

    dictionary = build_data_dictionary(df)
    dictionary_path = config.TABLES_DIR / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)

    counts = report["status"].value_counts()
    logger.info("-" * 60)
    logger.info("Checks: %d PASS, %d WARN, %d FAIL",
                counts.get(PASS, 0), counts.get(WARN, 0), counts.get(FAIL, 0))
    logger.info("Saved %s", quality_path.relative_to(config.PROJECT_ROOT).as_posix())
    logger.info("Saved %s", dictionary_path.relative_to(config.PROJECT_ROOT).as_posix())

    if has_failures(results):
        logger.error("Validation found FAIL items. Send the report before moving on.")
        return 1
    logger.info("Validation complete. No blocking problems. Ready for Phase 3 (cleaning).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
