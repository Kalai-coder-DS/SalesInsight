"""Phase 8 tests: regions and states. Values worked out by hand from the 8 sample rows.

Sample by region (sales / profit):
  South   : Kentucky 261.96 + 731.94, Florida 957.5775 + 22.368   -> 1973.8455 / -119.0210
  West    : California 14.62, Washington 90.57                    ->  105.19   /   18.6455
  East    : Vermont 907.152                                        ->  907.152  /   90.7152
  Central : North Carolina 15.552                                  ->   15.552  /    5.4432
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from salesinsight import regions as rg

SOUTH_REV = 261.96 + 731.94 + 957.5775 + 22.368
SOUTH_PROFIT = 41.9136 + 219.582 - 383.031 + 2.5164


def test_region_performance(sales_data):
    r = rg.region_performance(sales_data).set_index("region")
    assert r.loc["South", "revenue"] == pytest.approx(SOUTH_REV)
    assert r.loc["South", "profit"] == pytest.approx(SOUTH_PROFIT)
    assert r.loc["South", "total_orders"] == 2
    assert r.loc["South", "total_customers"] == 2
    assert r.loc["South", "revenue_per_customer"] == pytest.approx(SOUTH_REV / 2)
    assert r["share_of_revenue_pct"].sum() == pytest.approx(100)
    assert list(r.index) == ["South", "East", "West", "Central"]       # sorted by revenue


def test_region_totals_equal_grand_total(sales_data):
    r = rg.region_performance(sales_data)
    assert r["revenue"].sum() == pytest.approx(sales_data["sales"].sum())
    assert r["profit"].sum() == pytest.approx(sales_data["profit"].sum())


def test_state_performance(sales_data):
    s = rg.state_performance(sales_data).set_index("state")
    assert len(s) == 6
    assert s.loc["Florida", "profit"] == pytest.approx(-383.031 + 2.5164)
    assert s.loc["Florida", "region"] == "South"


def test_top_and_bottom_states(sales_data):
    states = rg.state_performance(sales_data)
    assert rg.top_states(states, "revenue", 1).loc[0, "state"] == "Kentucky"   # 993.90
    assert rg.top_states(states, "profit", 1).loc[0, "state"] == "Kentucky"    # 261.50
    assert rg.bottom_states(states, "profit", 1).loc[0, "state"] == "Florida"


def test_city_minimum_orders(sales_data):
    assert len(rg.city_performance(sales_data, min_orders=1)) == 6
    assert len(rg.city_performance(sales_data, min_orders=2)) == 0


def test_region_category_matrix(sales_data):
    m = rg.region_category_matrix(sales_data, "revenue")
    assert m.loc["South", "Furniture"] == pytest.approx(261.96 + 731.94 + 957.5775)
    assert pd.isna(m.loc["Central", "Furniture"])                  # never sold there
    assert list(m.index) == ["South", "East", "West", "Central"]


def test_region_yearly_and_cagr():
    df = pd.DataFrame({
        "region": ["A", "A", "A", "B", "B", "B"],
        "order_year": [2014, 2015, 2016, 2014, 2015, 2016],
        "sales": [100.0, 110.0, 121.0, 200.0, 200.0, 200.0],
        "profit": [10.0] * 6,
    })
    y = rg.region_yearly(df)
    assert y.loc[1, "revenue_growth_pct"] == pytest.approx(10.0)
    c = rg.region_cagr(y).set_index("region")
    assert c.loc["A", "revenue_cagr_pct"] == pytest.approx(10.0)    # 100 -> 121 in 2 years
    assert c.loc["B", "revenue_cagr_pct"] == pytest.approx(0.0)
    assert rg.region_cagr(y).loc[0, "region"] == "A"                # fastest first


def test_discount_margin_correlation():
    states = pd.DataFrame({
        "effective_discount_pct": [0, 10, 20, 30],
        "profit_margin_pct": [20, 10, 0, -10],
        "total_orders": [50, 50, 50, 50],
    })
    assert rg.discount_margin_correlation(states) == pytest.approx(-1.0)
    assert np.isnan(rg.discount_margin_correlation(states.assign(total_orders=1)))   # too few orders


def test_region_summary(sales_data):
    s = rg.region_summary(sales_data)
    assert s["regions"] == 4
    assert s["top_region_by_revenue"] == "South"
    assert s["worst_margin_region"] == "South"
    assert s["loss_making_states"] == 1
    assert s["loss_making_states_list"] == "Florida"
