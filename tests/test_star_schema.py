"""Phase 4 tests: star schema + every SQL query, checked against pandas.

These use Python's built-in sqlite3, so they run without MySQL.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

import pandas as pd
import pytest

from salesinsight.star_schema import FACT_COLUMNS, TABLE_ORDER, build_star_schema, load_queries

REQUIRED_QUERIES = {
    "kpi_overview", "yearly_sales", "monthly_sales", "top10_products_by_revenue",
    "category_performance", "region_performance", "segment_performance", "repeat_customer_rate",
}


def sqlite_with(data: pd.DataFrame) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    for name, table in build_star_schema(data).items():
        table.to_sql(name, con, index=False)
    return con


def q(con, name: str) -> pd.DataFrame:
    return pd.read_sql(load_queries()[name], con)


# --------------------------------------------------------------------------
# Star schema
# --------------------------------------------------------------------------
def test_tables_in_load_order(sales_data):
    assert list(build_star_schema(sales_data)) == TABLE_ORDER


def test_dimension_keys_are_unique(sales_data):
    t = build_star_schema(sales_data)
    assert t["dim_customer"]["customer_id"].is_unique
    assert t["dim_product"]["product_key"].is_unique
    assert t["dim_location"]["location_id"].is_unique
    assert (len(t["dim_customer"]), len(t["dim_product"]), len(t["dim_location"])) == (6, 8, 6)


def test_fact_table(sales_data):
    fact = build_star_schema(sales_data)["fact_sales"]
    assert len(fact) == len(sales_data)
    assert list(fact.columns) == FACT_COLUMNS
    assert "year_month" not in fact.columns          # reserved word in MySQL
    assert fact.loc[0, "order_period"] == "2016-11"
    assert isinstance(fact.loc[0, "order_date"], dt.date)


def test_every_fact_row_has_a_location(sales_data):
    t = build_star_schema(sales_data)
    assert set(t["fact_sales"]["location_id"]) <= set(t["dim_location"]["location_id"])


def test_join_back_gives_original_values(sales_data):
    t = build_star_schema(sales_data)
    joined = t["fact_sales"].merge(t["dim_location"], on="location_id").sort_values("row_id")
    assert joined["state"].tolist() == sales_data.sort_values("row_id")["state"].tolist()


def test_shared_product_id_kept_as_two_products(sales_data):
    df = sales_data.copy()
    df.loc[1, "product_id"] = df.loc[0, "product_id"]
    dim = build_star_schema(df)["dim_product"]
    assert dim["product_id"].duplicated().sum() == 1     # same ID twice
    assert dim["product_key"].is_unique                  # but two different keys


# --------------------------------------------------------------------------
# Query file
# --------------------------------------------------------------------------
def test_query_file_has_all_queries():
    queries = load_queries()
    assert len(queries) >= 20
    assert REQUIRED_QUERIES <= set(queries)
    for name, sql in queries.items():
        assert sql.upper().startswith(("SELECT", "WITH")), name
        assert "USE " not in sql.upper(), name


def test_duplicate_query_name_is_rejected(tmp_path):
    f = tmp_path / "q.sql"
    f.write_text("-- name: a\nSELECT 1;\n-- name: a\nSELECT 2;\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(f)


def test_every_query_runs(sales_data):
    con = sqlite_with(sales_data)
    for name, sql in load_queries().items():
        result = pd.read_sql(sql, con)
        assert len(result) > 0, name


# --------------------------------------------------------------------------
# SQL results must equal pandas results
# --------------------------------------------------------------------------
def test_kpi_overview_matches_pandas(sales_data):
    kpi = q(sqlite_with(sales_data), "kpi_overview").iloc[0]
    assert kpi["total_revenue"] == pytest.approx(round(sales_data["sales"].sum(), 2))
    assert kpi["total_profit"] == pytest.approx(round(sales_data["profit"].sum(), 2))
    assert kpi["total_orders"] == sales_data["order_id"].nunique()
    assert kpi["units_sold"] == sales_data["quantity"].sum()
    aov = sales_data["sales"].sum() / sales_data["order_id"].nunique()
    assert kpi["avg_order_value"] == pytest.approx(round(aov, 2))


def test_yearly_sales_add_up_and_growth(sales_data):
    yearly = q(sqlite_with(sales_data), "yearly_sales")
    assert yearly["revenue"].sum() == pytest.approx(sales_data["sales"].sum(), abs=0.05)
    assert pd.isna(yearly.loc[0, "revenue_growth_pct"])          # no year before the first
    r = yearly["revenue"]
    assert yearly.loc[1, "revenue_growth_pct"] == pytest.approx(round(100 * (r[1] - r[0]) / r[0], 2), abs=0.01)


def test_category_performance_matches_pandas(sales_data):
    sql = q(sqlite_with(sales_data), "category_performance").set_index("category")
    pd_rev = sales_data.groupby("category")["sales"].sum().round(2)
    for cat, rev in pd_rev.items():
        assert sql.loc[cat, "revenue"] == pytest.approx(rev)


def test_region_totals_equal_grand_total(sales_data):
    regions = q(sqlite_with(sales_data), "region_performance")
    assert regions["revenue"].sum() == pytest.approx(sales_data["sales"].sum(), abs=0.05)


def test_top_product_by_revenue(sales_data):
    top = q(sqlite_with(sales_data), "top10_products_by_revenue")
    expected = sales_data.groupby("product_name")["sales"].sum().idxmax()
    assert top.loc[0, "product_name"] == expected
    assert top["revenue"].is_monotonic_decreasing


def test_bottom_product_is_the_biggest_loss(sales_data):
    bottom = q(sqlite_with(sales_data), "bottom10_products_by_profit")
    assert bottom.loc[0, "product_name"] == "Bretford CR4500 Series Slim Rectangular Table"
    assert bottom.loc[0, "profit"] < 0


def test_repeat_customer_rate(sales_data_with_repeat):
    r = q(sqlite_with(sales_data_with_repeat), "repeat_customer_rate").iloc[0]
    assert r["total_customers"] == 6
    assert r["repeat_customers"] == 1
    assert r["repeat_rate_pct"] == pytest.approx(round(100 / 6, 2))


def test_order_frequency_bands(sales_data_with_repeat):
    bands = q(sqlite_with(sales_data_with_repeat), "customer_order_frequency").set_index("order_band")
    assert bands.loc["1 order", "total_customers"] == 5
    assert bands.loc["2-3 orders", "total_customers"] == 1


def test_discount_impact_ordered_by_discount(sales_data):
    d = q(sqlite_with(sales_data), "discount_impact")
    assert d["discount_band"].tolist() == ["No discount", "1-20%", "Over 40%"]
    assert d.loc[2, "loss_lines_pct"] == 100.0
