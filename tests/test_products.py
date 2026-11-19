"""Phase 7 tests: products, Pareto, categories and discount effect.

Sample rows (sub-category / sales / profit / discount):
  Bookcases 261.96 41.91 0.00   Chairs   731.94 219.58 0.00   Labels 14.62 6.87 0.00
  Tables    957.58 -383.03 0.45  Storage   22.37   2.52 0.20   Phones 907.15 90.72 0.20
  Paper      15.55   5.44 0.20  Accessories 90.57 11.77 0.00
"""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight import products as pr


@pytest.fixture
def perf(sales_data):
    return pr.product_performance(sales_data)


def test_one_row_per_product(perf, sales_data):
    assert len(perf) == sales_data["product_key"].nunique() == 8
    assert perf["revenue"].sum() == pytest.approx(sales_data["sales"].sum())
    assert perf["share_of_revenue_pct"].sum() == pytest.approx(100)


def test_top_product_by_revenue(perf):
    top = pr.top_products(perf, "revenue", 3)
    assert top["product_name"].tolist() == [
        "Bretford CR4500 Series Slim Rectangular Table",
        "Mitel 5320 IP Phone VoIP phone",
        "Hon Deluxe Fabric Upholstered Stacking Chairs",
    ]


def test_top_by_units(perf):
    assert pr.top_products(perf, "units_sold", 1).loc[0, "units_sold"] == 6      # the phone


def test_bottom_product_is_the_table(perf):
    worst = pr.bottom_products(perf, "profit", 1).iloc[0]
    assert worst["sub_category"] == "Tables"
    assert worst["profit"] == pytest.approx(-383.031)
    assert worst["profit_margin_pct"] == pytest.approx(-40.0)          # -383.031 / 957.5775


def test_loss_making_products(perf):
    losers = pr.loss_making_products(perf)
    assert len(losers) == 1
    assert losers.loc[0, "loss_lines_pct"] == 100


def test_pareto_cumulative(perf):
    p = pr.pareto(perf)
    assert p["revenue"].is_monotonic_decreasing
    assert p["cum_share_pct"].iloc[-1] == pytest.approx(100)
    assert p["product_rank_pct"].iloc[-1] == pytest.approx(100)
    assert p.loc[0, "cum_share_pct"] == pytest.approx(100 * 957.5775 / 3001.7395)


def test_pareto_summary(perf):
    # Cumulative: 31.9%, 62.1%, 86.5% -> 3 products needed to reach 80%
    s = pr.pareto_summary(perf)
    assert s["products_for_target"] == 3
    assert s["products_for_target_pct"] == pytest.approx(37.5)
    # Top 20% of 8 products = 2 products (rounded up) -> 62.1%
    assert s["top20pct_products_share"] == pytest.approx(100 * (957.5775 + 907.152) / 3001.7395)


def test_pareto_on_equal_products():
    perf = pd.DataFrame({"product_key": list("ABCDE"), "revenue": [10.0] * 5})
    s = pr.pareto_summary(perf)
    assert s["products_for_target"] == 4            # 4 x 20% = 80%


def test_category_performance(sales_data):
    cats = pr.category_performance(sales_data).set_index("category")
    assert cats.loc["Furniture", "revenue"] == pytest.approx(261.96 + 731.94 + 957.5775)
    assert cats.loc["Furniture", "profit"] == pytest.approx(41.9136 + 219.582 - 383.031)
    assert cats["share_of_revenue_pct"].sum() == pytest.approx(100)
    assert list(cats.index) == ["Furniture", "Technology", "Office Supplies"]   # by revenue


def test_subcategory_sorted_by_profit(sales_data):
    subs = pr.subcategory_performance(sales_data)
    assert subs.loc[0, "sub_category"] == "Chairs"
    assert subs.iloc[-1]["sub_category"] == "Tables"
    assert len(subs) == 8


def test_discount_margin_matrix(sales_data):
    m = pr.discount_margin_matrix(sales_data)
    assert list(m.columns) == ["No discount", "1-20%", "Over 40%"]
    assert m.loc["Tables", "Over 40%"] == pytest.approx(-40.0)
    assert pd.isna(m.loc["Tables", "No discount"])        # never sold without discount
    assert m.index[-1] == "Tables"                        # worst overall margin at the bottom


def test_discount_band_performance_order(sales_data):
    bands = pr.discount_band_performance(sales_data)
    assert bands["discount_band"].astype(str).tolist() == ["No discount", "1-20%", "Over 40%"]


def test_product_summary(sales_data):
    s = pr.product_summary(sales_data)
    assert s["products_total"] == 8
    assert s["worst_subcategory_by_profit"] == "Tables"
    assert s["best_subcategory_by_profit"] == "Chairs"
    assert s["loss_subcategories"] == "Tables"
    assert s["margin_over_40pct_discount_pct"] == pytest.approx(-40.0)
    assert s["margin_no_discount_pct"] == pytest.approx(
        100 * (41.9136 + 219.582 + 6.8714 + 11.7741) / (261.96 + 731.94 + 14.62 + 90.57))
