"""Phase 10 tests: every statistical test on data where the right answer is known.

The module is imported as `st` (not `from ... import test_x`) so that pytest
does not mistake its functions for test functions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from salesinsight import stats_tests as st
from salesinsight.features import add_discount_band


# --------------------------------------------------------------------------
# Wording and effect sizes
# --------------------------------------------------------------------------
@pytest.mark.parametrize("p, text", [
    (0.0001, "very unlikely to be chance (p < 0.001)"),
    (0.012, "statistically significant (p = 0.012)"),
    (0.31, "possibly due to chance (p = 0.31)"),
])
def test_describe_p(p, text):
    assert st.describe_p(p) == text


@pytest.mark.parametrize("value, kind, label", [
    (0.05, "r", "negligible"), (-0.2, "r", "small"), (0.4, "r", "medium"), (-0.84, "r", "large"),
    (0.005, "eta", "negligible"), (0.03, "eta", "small"), (0.1, "eta", "medium"), (0.2, "eta", "large"),
])
def test_effect_label(value, kind, label):
    assert st.effect_label(value, kind) == label


def test_cramers_v_perfect_and_none():
    perfect = pd.DataFrame([[50, 0], [0, 50]])
    none = pd.DataFrame([[25, 25], [25, 25]])
    assert st.cramers_v(perfect) == pytest.approx(1.0)
    assert st.cramers_v(none) == pytest.approx(0.0)


def test_epsilon_squared_never_negative():
    assert st.epsilon_squared(h=0.5, n=100, k=4) == 0.0
    assert st.epsilon_squared(h=21.0, n=103, k=4) == pytest.approx(18 / 99)


def test_rank_biserial_limits():
    assert st.rank_biserial(u=100, n1=10, n2=10) == 1.0       # group 1 always larger
    assert st.rank_biserial(u=0, n1=10, n2=10) == -1.0        # group 1 always smaller
    assert st.rank_biserial(u=50, n1=10, n2=10) == 0.0        # no difference


# --------------------------------------------------------------------------
# Tests on synthetic data with a known answer
# --------------------------------------------------------------------------
@pytest.fixture
def lines():
    """400 lines: margin falls exactly as discount rises; Central has lower margins."""
    rng = np.random.default_rng(0)
    n = 400
    discount = np.tile([0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.0], n // 8)
    sales = rng.uniform(50, 500, n)
    df = pd.DataFrame({"discount": discount, "sales": sales})
    df["profit"] = df["sales"] * (0.3 - 0.8 * df["discount"])
    df["region"] = np.tile(["West", "East", "Central", "South"], n // 4)
    df.loc[df["region"] == "Central", "profit"] -= 0.2 * df["sales"]
    df["category"] = np.tile(["Furniture", "Technology"], n // 2)
    df.loc[df["category"] == "Furniture", "profit"] -= 0.15 * df["sales"]
    df["segment"] = "Consumer"
    df["quantity"] = 2
    df["order_id"] = [f"O{i}" for i in range(n)]
    df["order_date"] = pd.Timestamp("2016-01-01") + pd.to_timedelta(np.arange(n) % 365, unit="D")
    df["order_year"] = 2016
    df = add_discount_band(df)
    df["is_loss"] = df["profit"] < 0
    return df


def test_discount_vs_margin_detects_strong_negative(lines):
    r = st.test_discount_vs_margin(lines)
    assert r.effect_size < -0.5
    assert r.significant
    assert r.effect_label == "large"
    assert "lower margins" in r.conclusion


def test_discount_vs_margin_no_relationship():
    # Every profit value appears once with 0% and once with 80% discount,
    # so discount and margin are unrelated by construction (rho = 0 exactly).
    # (Random data would be "significant" by pure chance about 5% of the time.)
    df = pd.DataFrame({"discount": np.tile([0.0, 0.8], 100), "sales": 100.0,
                       "profit": np.repeat(np.linspace(-10, 30, 100), 2)})
    r = st.test_discount_vs_margin(df)
    assert r.effect_size == pytest.approx(0.0, abs=1e-12)
    assert not r.significant
    assert r.effect_label == "negligible"


def test_discount_vs_loss(lines):
    r = st.test_discount_vs_loss(lines)
    assert r.significant
    assert r.effect_size > 0.5
    assert "No discount" in r.conclusion


def test_region_margin_detects_central(lines):
    r = st.test_region_margin(lines)
    assert r.significant
    assert r.conclusion.index("Central") > r.conclusion.index("West")   # Central listed last (lowest)


def test_region_margin_identical_groups():
    df = pd.DataFrame({
        "region": np.repeat(["A", "B", "C"], 50),
        "sales": 100.0,
        "profit": np.tile(np.linspace(-10, 30, 50), 3),
    })
    r = st.test_region_margin(df)
    assert not r.significant
    assert r.effect_size == 0.0


def test_segment_order_value_uses_orders():
    df = pd.DataFrame({
        "order_id": ["A", "A", "B", "C", "D", "E", "F"],
        "segment": ["X", "X", "X", "Y", "Y", "Z", "Z"],
        "sales": [50.0, 50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
    })
    r = st.test_segment_order_value(df)
    assert r.n == 6                          # 6 orders, not 7 lines
    assert not r.significant                 # every order is worth 100


def test_furniture_margin_lower(lines):
    r = st.test_category_margin(lines, "Furniture")
    assert r.significant
    assert r.effect_size < 0
    assert "(lower)" in r.conclusion


def test_q4_vs_rest():
    dates = pd.date_range("2015-01-01", "2016-12-31", freq="D")
    df = pd.DataFrame({"order_date": dates, "sales": np.where(dates.quarter == 4, 300.0, 100.0)})
    df["sales"] += np.random.default_rng(2).normal(0, 5, len(df))
    r = st.test_q4_vs_rest(df)
    assert r.significant
    assert r.n == 24                         # 24 months
    assert r.effect_label == "large"


def test_bootstrap_ci_is_reproducible():
    values = np.random.default_rng(3).gamma(2, 100, 500)
    first = st.bootstrap_ci(values)
    second = st.bootstrap_ci(values)
    assert first == second                   # same seed -> same answer
    est, lo, hi = first
    assert lo < est < hi
    assert est == pytest.approx(values.mean())


def test_bootstrap_ci_constant_values():
    assert st.bootstrap_ci(np.full(50, 7.0)) == (7.0, 7.0, 7.0)


def test_aov_confidence_by_year(sales_data):
    ci = st.aov_confidence_by_year(sales_data)
    assert list(ci["order_year"]) == [2014, 2015, 2016, 2017]
    assert (ci["ci_lower"] <= ci["avg_order_value"]).all()
    assert (ci["avg_order_value"] <= ci["ci_upper"]).all()


def test_descriptive_statistics_outliers():
    df = pd.DataFrame({"sales": [1.0, 2, 3, 4, 100], "profit": 1.0, "quantity": 1, "discount": 0.0})
    d = st.descriptive_statistics(df).set_index("variable")
    # q1 = 2, q3 = 4, IQR = 2 -> anything above 7 is an outlier -> only 100
    assert d.loc["sales", "outliers_iqr"] == 1
    assert d.loc["sales", "median"] == 3
    assert d.loc["sales", "skewness"] > 1


def test_run_all_tests_on_sample(sales_data):
    table = st.results_to_frame(st.run_all_tests(sales_data))
    assert len(table) == 6
    assert table["p_value"].between(0, 1).all()
    assert table["conclusion"].str.len().gt(20).all()
