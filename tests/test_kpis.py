"""Phase 5 tests: KPI values worked out by hand from the 8 sample rows.

Sample rows (sales / profit / quantity / discount):
  1  261.96    41.9136  2  0.00      5   22.368     2.5164  2  0.20
  2  731.94   219.582   3  0.00      6  907.152    90.7152  6  0.20
  3   14.62     6.8714  2  0.00      7   15.552     5.4432  3  0.20
  4  957.5775 -383.031  5  0.45      8   90.57     11.7741  3  0.00
"""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight import kpis as k

REVENUE = 3001.7395           # sum of the 8 sales values
PROFIT = -4.2151              # sum of the 8 profit values
ORDERS = 6
UNITS = 26
# Price before discount: 957.5775/0.55 + 22.368/0.8 + 907.152/0.8 + 15.552/0.8 + no-discount rows
DISCOUNT_GIVEN = 783.4725 + 5.592 + 226.788 + 3.888     # = 1019.7405
GROSS = REVENUE + DISCOUNT_GIVEN                        # = 4021.48


@pytest.fixture
def kpis(sales_data):
    return k.compute_kpis(sales_data)


def test_revenue_and_profit(kpis):
    assert kpis["total_revenue"] == pytest.approx(REVENUE)
    assert kpis["total_profit"] == pytest.approx(PROFIT)
    assert kpis["profit_margin_pct"] == pytest.approx(100 * PROFIT / REVENUE)


def test_counts(kpis):
    assert kpis["total_orders"] == ORDERS
    assert kpis["total_customers"] == 6
    assert kpis["total_products"] == 8
    assert kpis["units_sold"] == UNITS


def test_average_order_value_uses_orders_not_rows(kpis):
    # 8 rows but 6 orders: AOV = revenue / 6, not revenue / 8
    assert kpis["avg_order_value"] == pytest.approx(REVENUE / 6)
    assert kpis["avg_units_per_order"] == pytest.approx(26 / 6)


def test_discount_kpis(kpis):
    assert kpis["discount_given"] == pytest.approx(DISCOUNT_GIVEN)
    assert kpis["revenue_before_discount"] == pytest.approx(GROSS)
    assert kpis["effective_discount_pct"] == pytest.approx(100 * DISCOUNT_GIVEN / GROSS)
    assert kpis["avg_line_discount_pct"] == pytest.approx(100 * (0.45 + 0.2 * 3) / 8)


def test_loss_kpis(kpis):
    assert kpis["loss_lines"] == 1
    assert kpis["loss_lines_pct"] == pytest.approx(12.5)
    assert kpis["loss_amount"] == pytest.approx(-383.031)


def test_date_range(kpis):
    assert kpis["first_order_date"] == pd.Timestamp("2014-06-09")
    assert kpis["last_order_date"] == pd.Timestamp("2017-12-05")


def test_yearly_kpis(sales_data):
    y = k.yearly_kpis(sales_data).set_index("order_year")
    assert y.loc[2014, "revenue"] == pytest.approx(907.152)
    assert y.loc[2015, "revenue"] == pytest.approx(957.5775 + 22.368)
    assert y.loc[2015, "profit"] == pytest.approx(-383.031 + 2.5164)
    assert y.loc[2016, "total_orders"] == 2
    assert pd.isna(y.loc[2014, "revenue_growth_pct"])
    assert y.loc[2015, "revenue_growth_pct"] == pytest.approx(100 * (979.9455 - 907.152) / 907.152)


def test_yearly_totals_add_up(sales_data):
    y = k.yearly_kpis(sales_data)
    assert y["revenue"].sum() == pytest.approx(REVENUE)
    assert y["units_sold"].sum() == UNITS


def test_kpis_by_any_column(sales_data):
    by_region = k.kpis_by(sales_data, "region").set_index("region")
    assert by_region.loc["South", "total_orders"] == 2
    assert by_region["revenue"].sum() == pytest.approx(REVENUE)


@pytest.mark.parametrize("value, kind, text", [
    (2296919.4931, "money", "$2,296,919.49"),
    (-383.031, "money", "-$383.03"),
    (12.4567, "pct", "12.46%"),
    (5009, "int", "5,009"),
])
def test_format_value(value, kind, text):
    assert k.format_value(value, kind) == text


@pytest.mark.parametrize("value, text", [
    (2296919.49, "$2.30M"), (286409.08, "$286.4K"), (-383.0, "-$383"),
])
def test_short_money(value, text):
    assert k.short_money(value) == text


def test_kpi_table(kpis):
    table = k.kpi_table(kpis)
    assert list(table.columns) == ["metric", "key", "value", "display"]
    assert len(table) == len(k.KPI_LABELS)
    assert table.set_index("key").loc["total_orders", "display"] == "6"


def test_compare_with_sql_detects_match_and_mismatch(kpis):
    sql = pd.Series({
        "total_revenue": 3001.74, "total_profit": -4.22, "profit_margin_pct": -0.14,
        "total_orders": 6, "total_customers": 6, "units_sold": 26, "avg_order_value": 500.29,
    })
    assert k.compare_with_sql(kpis, sql)["match"].all()
    sql["total_orders"] = 7
    result = k.compare_with_sql(kpis, sql).set_index("kpi")
    assert not result.loc["total_orders", "match"]
