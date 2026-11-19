"""Phase 4 tests: the SQLAlchemy database layer.

A temporary SQLite file stands in for MySQL, so no server is needed.
The same functions are used against MySQL by scripts/run_database.py.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine  # noqa: E402

from salesinsight import config  # noqa: E402
from salesinsight import database as db  # noqa: E402
from salesinsight.star_schema import TABLE_ORDER, build_star_schema, load_queries  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_tables(eng)
    yield eng
    eng.dispose()


def test_database_name_check():
    assert db.check_database_name("salesinsight") == "salesinsight"
    for bad in ("sales insight", "x; DROP DATABASE y", "name`", ""):
        with pytest.raises(ValueError):
            db.check_database_name(bad)


def test_create_tables(engine):
    from sqlalchemy import inspect
    assert set(TABLE_ORDER) <= set(inspect(engine).get_table_names())


def test_load_row_counts(engine, sales_data):
    tables = build_star_schema(sales_data)
    counts = db.load_star_schema(engine, tables)
    assert counts == {name: len(df) for name, df in tables.items()}


def test_loading_twice_does_not_duplicate(engine, sales_data):
    tables = build_star_schema(sales_data)
    db.load_star_schema(engine, tables)
    counts = db.load_star_schema(engine, tables)
    assert counts["fact_sales"] == len(sales_data)


def test_failed_load_keeps_old_data(engine, sales_data):
    tables = build_star_schema(sales_data)
    db.load_star_schema(engine, tables)
    broken = dict(tables)
    broken["fact_sales"] = tables["fact_sales"].assign(not_a_column=1)
    with pytest.raises(Exception):
        db.load_star_schema(engine, broken)
    assert db.table_row_counts(engine)["fact_sales"] == len(sales_data)


def test_sql_totals_equal_pandas(engine, sales_data):
    db.load_star_schema(engine, build_star_schema(sales_data))
    r = db.run_query(engine, "SELECT SUM(sales) AS s, SUM(profit) AS p, SUM(quantity) AS q FROM fact_sales").iloc[0]
    assert r["s"] == pytest.approx(sales_data["sales"].sum())
    assert r["p"] == pytest.approx(sales_data["profit"].sum())
    assert r["q"] == sales_data["quantity"].sum()


def test_run_all_queries(engine, sales_data):
    db.load_star_schema(engine, build_star_schema(sales_data))
    results = db.run_all_queries(engine, load_queries())
    assert len(results) >= 20
    assert all(len(df) > 0 for df in results.values())
    assert pd.api.types.is_numeric_dtype(results["kpi_overview"]["total_revenue"])


def test_sql_file_matches_python_tables():
    """sql/02_create_tables.sql and database.py must define the same columns."""
    ddl = (config.SQL_DIR / "02_create_tables.sql").read_text(encoding="utf-8")
    skip = {"PRIMARY", "INDEX", "CONSTRAINT", "UNIQUE", "KEY", "FOREIGN"}
    for table in db.metadata.sorted_tables:
        block = re.search(rf"CREATE TABLE {table.name} \((.*?)\) ENGINE", ddl, re.S)
        assert block, f"{table.name} missing from SQL file"
        sql_cols = [ln.split()[0] for ln in block.group(1).splitlines()
                    if ln.strip() and ln.split()[0] not in skip and not ln.strip().startswith("--")]
        assert sql_cols == [c.name for c in table.columns], table.name
