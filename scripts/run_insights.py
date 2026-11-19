"""Phase 11 (Q7): generate the business insights report and recommendations.

Run from the project root (after the earlier phases, so the charts exist):
    python scripts/run_insights.py

Outputs:
    reports/insights_report.md          the full report (opens nicely in VS Code and on GitHub)
    reports/tables/recommendations.csv  one row per recommendation
"""

from __future__ import annotations

import sys

from salesinsight import config
from salesinsight import insights as ins
from salesinsight.data_loader import load_clean_data
from salesinsight.logger import get_logger

logger = get_logger("run_insights")

REPORT_FILE = config.REPORTS_DIR / "insights_report.md"


def main() -> int:
    config.ensure_directories()
    df = load_clean_data()

    findings = ins.collect_findings(df)
    recs = ins.build_recommendations(findings)
    report = ins.build_report(findings, recs)

    REPORT_FILE.write_text(report, encoding="utf-8")
    ins.recommendations_to_frame(recs).to_csv(config.TABLES_DIR / "recommendations.csv", index=False)

    logger.info("-" * 60)
    logger.info("Recommendations (most important first)")
    for i, r in enumerate(recs, 1):
        logger.info("  %d. [%s] %s", i, r.area, r.title)
        logger.info("     Impact: %s", r.impact)
    logger.info("-" * 60)
    logger.info("Saved %s (%d lines)", REPORT_FILE.relative_to(config.PROJECT_ROOT).as_posix(),
                report.count("\n"))
    logger.info("Saved reports/tables/recommendations.csv")
    logger.info("Phase 11 complete. Open the report in VS Code: right-click it -> Open Preview.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
