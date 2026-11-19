"""Phase 9 tests: customer behaviour and RFM, on a hand-made 6-customer dataset.

Customer  segment      orders (date: sales)                                      revenue
A         Consumer     2016-01-01:100, 2016-03-01:200, 2017-12-01:300               600
B         Corporate    2017-12-20:50                                                  50
C         Consumer     2014-05-01:400, 2014-06-01:100                                500
D         Home Office  2015-01-01:1000                                              1000
E         Corporate    2017-06-01, 07-01, 08-01, 09-01: 10 each                       40
F         Consumer     2016-12-30: one order with two lines (50 + 30)                 80
Snapshot ("today") = 2017-12-21, the day after the last order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from salesinsight import customers as cu

ROWS = [
    ("A", "Consumer", "O1", "2016-01-01", 100), ("A", "Consumer", "O2", "2016-03-01", 200),
    ("A", "Consumer", "O3", "2017-12-01", 300), ("B", "Corporate", "O4", "2017-12-20", 50),
    ("C", "Consumer", "O5", "2014-05-01", 400), ("C", "Consumer", "O6", "2014-06-01", 100),
    ("D", "Home Office", "O7", "2015-01-01", 1000),
    ("E", "Corporate", "O8", "2017-06-01", 10), ("E", "Corporate", "O9", "2017-07-01", 10),
    ("E", "Corporate", "O10", "2017-08-01", 10), ("E", "Corporate", "O11", "2017-09-01", 10),
    ("F", "Consumer", "O12", "2016-12-30", 50), ("F", "Consumer", "O12", "2016-12-30", 30),
]


@pytest.fixture
def df():
    d = pd.DataFrame(ROWS, columns=["customer_id", "segment", "order_id", "order_date", "sales"])
    d["order_date"] = pd.to_datetime(d["order_date"])
    d["order_year"] = d["order_date"].dt.year
    d["customer_name"] = "Customer " + d["customer_id"]
    d["profit"] = 0.1 * d["sales"]
    d["quantity"] = 1
    d["discount"] = 0.0
    d["gross_sales"] = d["sales"]
    d["discount_amount"] = 0.0
    d["is_loss"] = False
    return d


@pytest.fixture
def customers(df):
    return cu.customer_table(df).set_index("customer_id")


def test_customer_table(customers):
    assert customers.loc["A", "total_orders"] == 3
    assert customers.loc["A", "revenue"] == 600
    assert customers.loc["F", "total_orders"] == 1          # two lines, one order
    assert customers.loc["F", "avg_order_value"] == 80
    assert customers.loc["B", "recency_days"] == 1          # 2017-12-20 -> 2017-12-21
    assert customers.loc["A", "recency_days"] == 20
    assert customers.loc["A", "active_years"] == 2
    assert customers.index[0] == "D"                        # sorted by revenue


def test_segment_performance(df):
    seg = cu.segment_performance(df).set_index("segment")
    assert seg.loc["Consumer", "total_customers"] == 3
    assert seg.loc["Consumer", "revenue"] == 1180
    assert seg.loc["Consumer", "total_orders"] == 6
    assert seg.loc["Consumer", "avg_order_value"] == pytest.approx(1180 / 6)
    assert seg.loc["Consumer", "orders_per_customer"] == 2


def test_order_frequency(customers):
    f = cu.order_frequency(customers.reset_index()).set_index("order_band")
    assert f.loc["1 order", "total_customers"] == 3          # B, D, F
    assert f.loc["2-3 orders", "total_customers"] == 2       # A, C
    assert f.loc["4-6 orders", "total_customers"] == 1       # E
    assert f["share_of_customers_pct"].sum() == pytest.approx(100)


def test_days_between_orders(df):
    gaps = sorted(cu.days_between_orders(df))
    # A: 60 (2016 is a leap year), 640; C: 31; E: 30, 31, 31
    assert gaps == [30, 31, 31, 31, 60, 640]


def test_concentration(customers):
    # Top 20% of 6 customers = 2 (rounded up): D 1000 + A 600 of 2270
    assert cu.concentration(customers.reset_index(), 20) == pytest.approx(100 * 1600 / 2270)


def test_customer_pareto(customers):
    p = cu.customer_pareto(customers.reset_index())
    assert p["cum_share_pct"].iloc[-1] == pytest.approx(100)
    assert p["rank_pct"].iloc[0] == pytest.approx(100 / 6)


def test_rfm_scores(customers):
    rfm = cu.rfm_table(customers.reset_index()).set_index("customer_id")
    assert rfm["r_score"].to_dict() == {"D": 2, "A": 5, "C": 1, "F": 3, "B": 5, "E": 4}
    assert rfm["f_score"].to_dict() == {"D": 2, "A": 5, "C": 4, "F": 2, "B": 2, "E": 5}
    assert rfm["m_score"].to_dict() == {"D": 5, "A": 5, "C": 4, "F": 3, "B": 2, "E": 1}
    assert rfm.loc["A", "rfm_code"] == "555"


def test_tied_customers_get_the_same_score(customers):
    rfm = cu.rfm_table(customers.reset_index()).set_index("customer_id")
    # B, D and F each placed 1 order -> same frequency score
    assert rfm.loc[["B", "D", "F"], "f_score"].nunique() == 1


def test_rfm_segments(customers):
    rfm = cu.rfm_table(customers.reset_index()).set_index("customer_id")
    assert rfm["rfm_segment"].to_dict() == {
        "A": "Champions", "B": "Potential loyalists", "C": "At risk",
        "D": "Lost", "E": "Loyal", "F": "Potential loyalists",
    }


@pytest.mark.parametrize("r, f, m, segment", [
    (5, 5, 5, "Champions"), (1, 4, 5, "At risk"), (3, 5, 2, "Loyal"),
    (5, 1, 1, "New customers"), (3, 2, 3, "Potential loyalists"),
    (1, 1, 1, "Lost"), (3, 1, 3, "Needs attention"),
])
def test_rfm_segment_rules(r, f, m, segment):
    assert cu.rfm_segment(r, f, m) == segment


def test_rfm_needs_five_customers(customers):
    with pytest.raises(ValueError):
        cu.rfm_table(customers.reset_index().head(4))


def test_rfm_summary(customers):
    s = cu.rfm_summary(cu.rfm_table(customers.reset_index())).set_index("rfm_segment")
    assert s.loc["Potential loyalists", "total_customers"] == 2
    assert s["share_of_customers_pct"].sum() == pytest.approx(100)
    assert list(s.index) == ["Champions", "Loyal", "Potential loyalists", "At risk", "Lost"]


def test_new_vs_returning(df):
    n = cu.new_vs_returning(df).set_index("order_year")
    assert n.loc[2017, "new_customers"] == 2                 # B, E
    assert n.loc[2017, "returning_customers"] == 1           # A
    assert n.loc[2017, "revenue_returning"] == 300
    assert n.loc[2017, "retention_pct"] == pytest.approx(50)  # 2016: A, F -> only A came back
    assert n.loc[2015, "retention_pct"] == 0
    assert np.isnan(n.loc[2014, "retention_pct"])            # no earlier year


def test_customer_summary(df):
    s = cu.customer_summary(df)
    assert s["total_customers"] == 6
    assert s["repeat_customers"] == 3
    assert s["repeat_rate_pct"] == pytest.approx(50)
    assert s["median_days_between_orders"] == 31
    assert s["top_customer"] == "Customer D"
    assert s["champions_customers"] == 1
    assert s["at_risk_customers"] == 1


def test_customers_on_sample(sales_data):
    c = cu.customer_table(sales_data)
    assert len(c) == 6
    assert c["revenue"].sum() == pytest.approx(sales_data["sales"].sum())
