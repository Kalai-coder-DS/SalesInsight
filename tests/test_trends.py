"""Phase 6 tests: trends, growth, seasonality. Expected values worked out by hand."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from salesinsight import trends as t


def make_sales(rows):
    """Tiny dataset: rows of (date, sales, profit, order_id)."""
    df = pd.DataFrame(rows, columns=["order_date", "sales", "profit", "order_id"])
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["order_year"] = df["order_date"].dt.year
    df["order_quarter"] = df["order_date"].dt.quarter
    df["order_weekday"] = df["order_date"].dt.day_name()
    return df


@pytest.fixture
def two_years():
    """24 months, revenue = 100 x month number, every month of 2014 and 2015."""
    rows = []
    for year in (2014, 2015):
        for month in range(1, 13):
            rows.append((f"{year}-{month:02d}-15", 100.0 * month * (2 if year == 2015 else 1), 10.0, f"{year}-{month}"))
    return make_sales(rows)


def test_monthly_fills_missing_months():
    df = make_sales([("2016-01-10", 100, 10, "A"), ("2016-04-02", 50, 5, "B")])
    m = t.monthly_sales(df)
    assert m["period"].dt.strftime("%Y-%m").tolist() == ["2016-01", "2016-02", "2016-03", "2016-04"]
    assert m["revenue"].tolist() == [100, 0, 0, 50]


def test_monthly_counts_orders_not_rows():
    df = make_sales([("2016-01-10", 100, 10, "A"), ("2016-01-10", 50, 5, "A"), ("2016-01-20", 30, 3, "B")])
    m = t.monthly_sales(df)
    assert m.loc[0, "total_orders"] == 2
    assert m.loc[0, "revenue"] == 180


def test_moving_average(two_years):
    m = t.monthly_sales(two_years)
    assert m["revenue_ma"].isna().sum() == 2              # first 2 months have no 3-month window
    assert m.loc[2, "revenue_ma"] == pytest.approx((100 + 200 + 300) / 3)


def test_month_on_month_growth(two_years):
    m = t.monthly_sales(two_years)
    assert np.isnan(m.loc[0, "revenue_mom_pct"])
    assert m.loc[1, "revenue_mom_pct"] == pytest.approx(100.0)   # 100 -> 200


def test_year_on_year_growth(two_years):
    m = t.monthly_sales(two_years)
    assert m["revenue_yoy_pct"].iloc[:12].isna().all()            # no previous year
    assert m["revenue_yoy_pct"].iloc[12:].tolist() == pytest.approx([100.0] * 12)  # 2015 doubled


def test_mom_growth_after_zero_month_is_missing():
    df = make_sales([("2016-01-10", 100, 10, "A"), ("2016-03-02", 50, 5, "B")])
    m = t.monthly_sales(df)
    assert np.isnan(m.loc[2, "revenue_mom_pct"])                  # previous month was 0


def test_revenue_matrix(two_years):
    mat = t.revenue_matrix(t.monthly_sales(two_years))
    assert list(mat.columns) == t.MONTH_NAMES
    assert mat.loc[2015, "Dec"] == 2400


def test_seasonality_index(two_years):
    s = t.seasonality(t.monthly_sales(two_years))
    # Month k averages 150*k; the mean of all months is 150*6.5, so the index is 100*k/6.5.
    assert s.loc[s["month"] == 12, "seasonality_index"].iloc[0] == pytest.approx(100 * 12 / 6.5)
    assert s["seasonality_index"].mean() == pytest.approx(100)
    assert s["share_of_year_pct"].sum() == pytest.approx(100)


def test_seasonality_ignores_partial_years(two_years):
    extra = make_sales([("2016-01-15", 999999, 0, "X")])          # 2016 has only January
    s = t.seasonality(t.monthly_sales(pd.concat([two_years, extra], ignore_index=True)))
    jan = s.loc[s["month"] == 1, "avg_revenue"].iloc[0]
    assert jan == pytest.approx((100 + 200) / 2)


def test_quarterly_share(two_years):
    q = t.quarterly_sales(two_years)
    assert q.groupby("order_year")["share_of_year_pct"].sum().tolist() == pytest.approx([100, 100])
    assert q.loc[0, "quarter_label"] == "2014-Q1"


def test_weekday_order_and_shares():
    df = make_sales([("2024-01-01", 10, 1, "A"), ("2024-01-01", 10, 1, "B"), ("2024-01-06", 10, 1, "C")])
    w = t.weekday_sales(df)       # 1 Jan 2024 = Monday, 6 Jan 2024 = Saturday
    assert w["weekday"].tolist() == t.WEEKDAYS
    assert w.set_index("weekday").loc["Monday", "total_orders"] == 2
    assert w["share_of_orders_pct"].sum() == pytest.approx(100)


@pytest.mark.parametrize("first, last, years, expected", [
    (100, 121, 2, 10.0),          # 100 -> 110 -> 121
    (100, 100, 3, 0.0),
    (200, 100, 1, -50.0),
])
def test_cagr(first, last, years, expected):
    assert t.cagr(first, last, years) == pytest.approx(expected)


def test_cagr_invalid():
    assert np.isnan(t.cagr(0, 100, 3))


def test_linear_trend_perfect_line():
    r = t.linear_trend(pd.Series([10, 12, 14, 16, 18]))
    assert r["slope"] == pytest.approx(2)
    assert r["intercept"] == pytest.approx(10)
    assert r["r_squared"] == pytest.approx(1)


def test_trend_summary(two_years):
    s = t.trend_summary(two_years)
    assert s["best_month"] == "Dec 2015"
    assert s["worst_month"] == "Jan 2014"
    assert s["peak_season_month"] == "Dec"
    assert s["revenue_cagr_pct"] == pytest.approx(100.0)          # revenue doubled in 1 year


def test_trends_on_sample(sales_data):
    m = t.monthly_sales(sales_data)
    assert m["revenue"].sum() == pytest.approx(sales_data["sales"].sum())
    assert len(m) == 43                                           # Jun 2014 .. Dec 2017
