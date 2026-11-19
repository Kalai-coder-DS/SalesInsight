"""Phase 13A tests: global filters, previous period, KPI comparison and chart data.

Sample rows (row: date, region, state, category, segment, sales):
  1 2016-11-08 South Kentucky   Furniture       Consumer     261.96
  2 2016-11-08 South Kentucky   Furniture       Consumer     731.94
  3 2016-06-12 West  California Office Supplies Corporate     14.62
  4 2015-10-11 South Florida    Furniture       Consumer     957.5775
  5 2015-10-11 South Florida    Office Supplies Consumer      22.368
  6 2014-06-09 East  Vermont    Technology      Consumer     907.152
  7 2017-04-15 Central N. Carolina Office Supplies Home Office 15.552
  8 2017-12-05 West  Washington Technology      Consumer      90.57
"""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight import dashboard_data as dd
from salesinsight import filtering as fl
from salesinsight.filtering import FilterState


def test_default_state_keeps_everything(sales_data):
    assert FilterState().is_default()
    assert len(fl.apply_filters(sales_data, FilterState())) == 8


def test_filter_by_region(sales_data):
    out = fl.apply_filters(sales_data, FilterState(regions=("South",)))
    assert len(out) == 4
    assert set(out["state"]) == {"Kentucky", "Florida"}


def test_filters_combine_with_and(sales_data):
    out = fl.apply_filters(sales_data, FilterState(regions=("South",), categories=("Furniture",)))
    assert sorted(out["row_id"]) == [1, 2, 4]


def test_filter_by_year(sales_data):
    out = fl.apply_filters(sales_data, FilterState(years=(2016,)))
    assert sorted(out["row_id"]) == [1, 2, 3]


def test_year_and_date_range_both_apply(sales_data):
    state = FilterState(years=(2016,), start=pd.Timestamp("2016-07-01"), end=pd.Timestamp("2017-12-31"))
    out = fl.apply_filters(sales_data, state)
    assert sorted(out["row_id"]) == [1, 2]       # 2016 AND after 1 Jul 2016


def test_date_range_is_inclusive(sales_data):
    state = FilterState(start=pd.Timestamp("2016-11-08"), end=pd.Timestamp("2016-11-08"))
    assert len(fl.apply_filters(sales_data, state)) == 2


def test_no_match_returns_empty(sales_data):
    out = fl.apply_filters(sales_data, FilterState(regions=("West",), categories=("Furniture",)))
    assert out.empty


def test_cascading_options(sales_data):
    opts = fl.filter_options(sales_data, FilterState(regions=("West",), categories=("Technology",)))
    assert opts["states"] == ["California", "Washington"]
    assert opts["subcategories"] == ["Accessories", "Phones"]
    assert opts["years"] == [2014, 2015, 2016, 2017]
    assert len(opts["regions"]) == 4                  # region list itself is never narrowed


def test_prune_selection():
    assert fl.prune_selection(("Texas", "Ohio"), ["Ohio", "Utah"]) == ("Ohio",)


def test_date_window(sales_data):
    start, end = fl.date_window(sales_data, FilterState(years=(2015, 2016)))
    assert (start, end) == (pd.Timestamp("2015-01-01"), pd.Timestamp("2016-12-31"))
    start, end = fl.date_window(sales_data, FilterState())
    assert (start, end) == (pd.Timestamp("2014-06-09"), pd.Timestamp("2017-12-05"))


def test_previous_period_of_a_year(sales_data):
    prev, window = fl.previous_period(sales_data, FilterState(years=(2017,)))
    assert window == (pd.Timestamp("2016-01-01"), pd.Timestamp("2016-12-31"))
    assert sorted(prev["row_id"]) == [1, 2, 3]


def test_previous_period_keeps_other_filters(sales_data):
    prev, _ = fl.previous_period(sales_data, FilterState(years=(2016,), regions=("South",)))
    assert sorted(prev["row_id"]) == [4, 5]          # 2015, South only


def test_no_previous_period_before_first_date(sales_data):
    prev, window = fl.previous_period(sales_data, FilterState())
    assert window is None and prev.empty


def test_no_previous_period_for_gapped_years(sales_data):
    prev, window = fl.previous_period(sales_data, FilterState(years=(2014, 2017)))
    assert window is None and prev.empty


@pytest.mark.parametrize("cur, prev, expected", [
    (120, 100, 20.0), (80, 100, -20.0), (50, 0, None), (50, -10, None),
])
def test_pct_change(cur, prev, expected):
    assert fl.pct_change(cur, prev) == (pytest.approx(expected) if expected is not None else None)


def test_kpi_comparison(sales_data):
    state = FilterState(years=(2016,))
    cur = fl.apply_filters(sales_data, state)
    prev, _ = fl.previous_period(sales_data, state)
    cards = {c["key"]: c for c in fl.kpi_comparison(cur, prev)}
    rev_2016 = 261.96 + 731.94 + 14.62
    rev_2015 = 957.5775 + 22.368
    assert cards["total_revenue"]["value"] == pytest.approx(rev_2016)
    assert cards["total_revenue"]["change"] == pytest.approx(100 * (rev_2016 - rev_2015) / rev_2015)
    assert cards["total_revenue"]["unit"] == "%"
    # Profit 2015 was negative -> no meaningful % change
    assert cards["total_profit"]["change"] is None
    # Margin changes in percentage points
    m16 = 100 * (41.9136 + 219.582 + 6.8714) / rev_2016
    m15 = 100 * (-383.031 + 2.5164) / rev_2015
    assert cards["profit_margin_pct"]["change"] == pytest.approx(m16 - m15)
    assert cards["profit_margin_pct"]["unit"] == "pp"


def test_kpi_comparison_without_previous(sales_data):
    cards = fl.kpi_comparison(sales_data, sales_data.iloc[0:0])
    assert all(c["change"] is None for c in cards)
    assert cards[0]["value"] == pytest.approx(sales_data["sales"].sum())


def test_kpi_comparison_empty_selection(sales_data):
    cards = fl.kpi_comparison(sales_data.iloc[0:0], sales_data.iloc[0:0])
    assert all(c["value"] is None for c in cards)


def test_describe_filters():
    chips = fl.describe_filters(FilterState(years=(2016, 2017), regions=("West",),
                                            states=("A", "B", "C", "D")))
    assert chips == ["Years: 2016-2017", "Region: West", "State: 4 selected"]


# --------------------------------------------------------------------------
# Chart data
# --------------------------------------------------------------------------
def test_time_series_month_fills_gaps(sales_data):
    ts = dd.time_series(sales_data, "Month")
    assert len(ts) == 43                                   # Jun 2014 .. Dec 2017
    assert ts["revenue"].sum() == pytest.approx(sales_data["sales"].sum())
    assert ts.loc[0, "label"] == "Jun 2014"


def test_time_series_quarter_and_year(sales_data):
    q = dd.time_series(sales_data, "Quarter")
    assert q.loc[0, "label"] == "2014 Q2"
    y = dd.time_series(sales_data, "Year")
    assert y["label"].tolist() == ["2014", "2015", "2016", "2017"]
    assert y.loc[1, "total_orders"] == 1


def test_time_series_empty(sales_data):
    assert dd.time_series(sales_data.iloc[0:0]).empty


def test_breakdown(sales_data):
    b = dd.breakdown(sales_data, "category")
    assert b.loc[0, "category"] == "Furniture"
    assert b["share_of_revenue_pct"].sum() == pytest.approx(100)


def test_profit_bridge_ends_with_total(sales_data):
    bridge = dd.profit_bridge(sales_data, "category")
    assert bridge.iloc[-1]["measure"] == "total"
    assert bridge.iloc[-1]["value"] == pytest.approx(sales_data["profit"].sum())
    assert bridge.iloc[:-1]["value"].sum() == pytest.approx(sales_data["profit"].sum())


def test_highlights(sales_data):
    h = dd.highlights(sales_data)
    assert [x["title"] for x in h] == ["Largest category", "Weakest region margin", "Loss-making order lines"]
    assert "Furniture" in h[0]["text"]
    assert dd.highlights(sales_data.iloc[0:0]) == []


def test_previous_period_two_years_spans_two_years(sales_data):
    _, window = fl.previous_period(sales_data, FilterState(years=(2016, 2017)))
    assert window == (pd.Timestamp("2014-01-01"), pd.Timestamp("2015-12-31"))


def test_previous_period_for_custom_dates_has_same_length(sales_data):
    state = FilterState(start=pd.Timestamp("2017-01-01"), end=pd.Timestamp("2017-01-10"))
    _, window = fl.previous_period(sales_data, state)
    assert window == (pd.Timestamp("2016-12-22"), pd.Timestamp("2016-12-31"))
