"""Phase 12 tests: the pipeline lists every script, in a valid order."""

from __future__ import annotations

import importlib.util

from salesinsight import config

spec = importlib.util.spec_from_file_location("run_pipeline", config.PROJECT_ROOT / "scripts" / "run_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def test_every_step_script_exists():
    for script, _, _ in pipeline.STEPS:
        assert (config.PROJECT_ROOT / "scripts" / script).is_file(), script


def test_cleaning_runs_before_every_analysis():
    order = [s for s, _ in pipeline.build_steps()]
    clean = order.index("run_cleaning.py")
    for script in ("run_database.py", "run_kpis.py", "run_trends.py", "run_products.py",
                   "run_regions.py", "run_customers.py", "run_statistics.py", "run_insights.py"):
        assert order.index(script) > clean, script


def test_insights_report_is_last():
    assert pipeline.build_steps()[-1][0] == "run_insights.py"


def test_database_runs_before_kpis():
    # run_kpis.py cross-checks its numbers against the MySQL results
    order = [s for s, _ in pipeline.build_steps()]
    assert order.index("run_database.py") < order.index("run_kpis.py")


def test_skip_database_removes_mysql_steps():
    scripts = [s for s, _ in pipeline.build_steps(skip_database=True)]
    assert "run_database.py" not in scripts
    assert "check_setup.py" not in scripts
    assert "run_cleaning.py" in scripts
