"""Run the whole SalesInsight project with one command.

Run from the project root:
    python scripts/run_pipeline.py                  # every step
    python scripts/run_pipeline.py --skip-database  # without MySQL (e.g. MySQL not running)
    python scripts/run_pipeline.py --with-tests     # run the test suite first

Each step runs as its own Python process. The pipeline stops at the first
step that fails, so later steps never use broken or missing data.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (script, description, needs MySQL)
STEPS: list[tuple[str, str, bool]] = [
    ("check_setup.py", "Check environment and MySQL connection", True),
    ("run_validation.py", "Phase 2  - Load and validate raw data", False),
    ("run_cleaning.py", "Phase 3  - Clean data and add features", False),
    ("run_database.py", "Phase 4  - Load MySQL star schema and run SQL queries", True),
    ("run_kpis.py", "Phase 5  - Revenue and profit KPIs (Q1)", False),
    ("run_trends.py", "Phase 6  - Monthly and yearly trends (Q2)", False),
    ("run_products.py", "Phase 7  - Products and categories (Q3, Q4)", False),
    ("run_regions.py", "Phase 8  - Regions and states (Q5)", False),
    ("run_customers.py", "Phase 9  - Customer behaviour and RFM (Q6)", False),
    ("run_statistics.py", "Phase 10 - Statistical tests", False),
    ("run_insights.py", "Phase 11 - Insights report and recommendations (Q7)", False),
]


def build_steps(skip_database: bool = False) -> list[tuple[str, str]]:
    return [(script, desc) for script, desc, needs_db in STEPS if not (skip_database and needs_db)]


def run(command: list[str], label: str) -> tuple[bool, float]:
    print(f"\n=== {label} ===", flush=True)
    start = time.perf_counter()
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    return result.returncode == 0, time.perf_counter() - start


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SalesInsight pipeline.")
    parser.add_argument("--skip-database", action="store_true", help="skip the steps that need MySQL")
    parser.add_argument("--with-tests", action="store_true", help="run pytest before the pipeline")
    args = parser.parse_args(argv)

    timings: list[tuple[str, float]] = []
    if args.with_tests:
        ok, seconds = run([sys.executable, "-m", "pytest", "-q"], "Test suite")
        timings.append(("Test suite", seconds))
        if not ok:
            print("\nTests failed - pipeline stopped.")
            return 1

    for script, description in build_steps(args.skip_database):
        ok, seconds = run([sys.executable, str(PROJECT_ROOT / "scripts" / script)], description)
        timings.append((description, seconds))
        if not ok:
            print(f"\nStep failed: {description} ({script}). Fix it and run the pipeline again.")
            return 1

    print("\n" + "=" * 70)
    print("Pipeline complete")
    for description, seconds in timings:
        print(f"  {seconds:6.1f}s  {description}")
    print(f"  {sum(s for _, s in timings):6.1f}s  TOTAL")
    print("Report: reports/insights_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
