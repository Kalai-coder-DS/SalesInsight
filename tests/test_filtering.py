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

from pathlib import Path

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


# --------------------------------------------------------------------------
# 13B: trends and products data
# --------------------------------------------------------------------------
def test_metric_series_moving_average(sales_data):
    s = dd.metric_series(sales_data, "Year", "Revenue")
    assert s["value"].tolist() == pytest.approx([907.152, 979.9455, 1008.52, 106.122])
    assert pd.isna(s.loc[0, "moving_avg"])
    assert s.loc[1, "moving_avg"] == pytest.approx((907.152 + 979.9455) / 2)


def test_growth_year(sales_data):
    g = dd.growth(sales_data, "Year").set_index("label")
    assert g.loc["2015", "revenue_growth_pct"] == pytest.approx(100 * (979.9455 - 907.152) / 907.152)
    assert pd.isna(g.loc["2016", "profit_growth_pct"])      # 2015 profit was negative
    assert "2014" not in g.index                            # nothing to compare with


def test_month_by_year(sales_data):
    m = dd.month_by_year(sales_data)
    assert list(m.columns) == dd.MONTHS
    assert m.loc[2016, "Nov"] == pytest.approx(261.96 + 731.94)
    assert pd.isna(m.loc[2014, "Jan"])


def test_seasonality_index_averages_100():
    dates = pd.date_range("2015-01-01", "2016-12-31", freq="MS")
    df = pd.DataFrame({"order_date": dates, "sales": [100.0 * d.month for d in dates],
                       "profit": 1.0, "order_id": range(len(dates))})
    s = dd.seasonality_index(df)
    assert s["index"].mean() == pytest.approx(100)
    assert s.loc[s["month"] == "Dec", "index"].iloc[0] == pytest.approx(100 * 12 / 6.5)


def test_margin_series_blank_for_empty_periods(sales_data):
    m = dd.margin_series(sales_data, "Month")
    assert m["margin_pct"].isna().sum() == (m["revenue"] == 0).sum()


def test_trend_stats(sales_data):
    stats = {s["label"]: s for s in dd.trend_stats(sales_data)}
    assert stats["Best month"]["value"] == "Nov 2016"
    expected_cagr = 100 * ((106.122 / 907.152) ** (1 / 3) - 1)
    assert stats["Revenue growth (CAGR)"]["value"] == f"{expected_cagr:+.1f}%"


def test_trend_stats_single_year(sales_data):
    stats = {s["label"]: s for s in dd.trend_stats(sales_data[sales_data["order_year"] == 2016])}
    assert stats["Revenue growth (CAGR)"]["value"] == "-"


def test_ranked_products(sales_data):
    top = dd.ranked_products(sales_data, "Revenue", 2, top=True)
    assert top.loc[0, "sub_category"] == "Tables"
    bottom = dd.ranked_products(sales_data, "Profit", 1, top=False)
    assert bottom.loc[0, "profit"] == pytest.approx(-383.031)
    units = dd.ranked_products(sales_data, "Units", 1)
    assert units.loc[0, "units_sold"] == 6


def test_category_hierarchy(sales_data):
    h = dd.category_hierarchy(sales_data)
    assert len(h) == 8
    assert h.groupby("category")["revenue"].sum()["Furniture"] == pytest.approx(261.96 + 731.94 + 957.5775)


def test_product_stats(sales_data):
    stats = {s["label"]: s for s in dd.product_stats(sales_data)}
    assert stats["Products sold"]["value"] == "8"
    assert stats["Loss-making products"]["value"] == "1"
    assert stats["Most profitable sub-category"]["value"] == "Chairs"
    assert dd.product_stats(sales_data.iloc[0:0]) == []


# --------------------------------------------------------------------------
# 13C: regions and customers data
# --------------------------------------------------------------------------
def test_state_table_has_codes(sales_data):
    t = dd.state_table(sales_data).set_index("state")
    assert t.loc["Kentucky", "code"] == "KY"
    assert t.loc["Florida", "profit"] == pytest.approx(-383.031 + 2.5164)
    assert dd.state_table(sales_data.iloc[0:0]).empty


def test_region_stats(sales_data):
    stats = {s["label"]: s for s in dd.region_stats(sales_data)}
    assert stats["Largest region"]["value"] == "South"
    assert stats["Loss-making states"]["value"] == "1 of 6"
    assert stats["Discount vs margin (states)"]["value"] == "-"     # too few orders per state


def test_region_by_year(sales_data):
    r = dd.region_by_year(sales_data)
    south_2016 = r[(r["group"] == "South") & (r["x"] == "2016")]["value"].iloc[0]
    assert south_2016 == pytest.approx(261.96 + 731.94)
    assert r["value"].sum() == pytest.approx(sales_data["sales"].sum())


def test_customer_stats(sales_data_with_repeat):
    stats = {s["label"]: s for s in dd.customer_stats(sales_data_with_repeat)}
    assert stats["Customers"]["value"] == "6"
    assert stats["Repeat customers"]["value"] == f"{100 / 6:.1f}%"
    assert dd.customer_stats(sales_data_with_repeat.iloc[0:0]) == []


def test_customer_stats_without_repeats(sales_data):
    stats = {s["label"]: s for s in dd.customer_stats(sales_data)}
    assert stats["Orders per customer"]["sub"] == "no repeat orders yet"


def test_new_vs_returning_long(sales_data_with_repeat):
    n = dd.new_vs_returning_long(sales_data_with_repeat).set_index("label")
    assert n.loc["2017", "revenue_returning"] == pytest.approx(261.96)   # Claire's second order


# --------------------------------------------------------------------------
# 13D: insights and explorer data
# --------------------------------------------------------------------------
def test_safe_findings_full_sample(sales_data_with_repeat):
    f, skipped = dd.safe_findings(sales_data_with_repeat)
    for key in ("kpis", "trends", "products", "regions", "customers", "rfm", "aov_ci"):
        assert key in f, (key, skipped.get(key))
    assert f["high_discount_loss"] == pytest.approx(-383.031)
    assert len(f["tests"]) >= 4


def test_safe_findings_one_region_does_not_crash(sales_data):
    one_region = sales_data[sales_data["region"] == "South"]
    f, skipped = dd.safe_findings(one_region)
    assert "kpis" in f
    # comparing regions is impossible with one region -> that test is skipped, not crashed
    assert "region_margin" not in [t.test for t in f["tests"]]


def test_safe_findings_tiny_selection(sales_data):
    f, skipped = dd.safe_findings(sales_data.iloc[[0]])
    assert "kpis" in f
    assert "rfm" in skipped                    # fewer than 5 customers


def test_safe_recommendations_and_report(sales_data_with_repeat):
    f, _ = dd.safe_findings(sales_data_with_repeat)
    recs = dd.safe_recommendations(f)
    assert len(recs) >= 4
    assert [r.priority for r in recs] == sorted(r.priority for r in recs)
    report = dd.safe_report(f, recs)
    assert report.startswith("# SalesInsight")


def test_safe_recommendations_with_missing_parts():
    assert dd.safe_recommendations({}) == []
    assert dd.safe_report({}, []) is None


def test_key_findings(sales_data_with_repeat):
    f, _ = dd.safe_findings(sales_data_with_repeat)
    titles = [k["title"] for k in dd.key_findings(sales_data_with_repeat, f)]
    assert titles[:2] == ["Revenue and profit", "Discounts"]
    assert "Weakest category" in titles


def test_opportunities(sales_data_with_repeat):
    f, _ = dd.safe_findings(sales_data_with_repeat)
    titles = [o["title"] for o in dd.opportunities(sales_data_with_repeat, f)]
    assert any(t.startswith("Fastest-growing sub-categories") for t in titles) or len(titles) >= 1
    assert "Protect full-price sales" in titles


def test_loss_tables(sales_data):
    t = dd.loss_tables(sales_data)
    assert list(t) == ["Products", "Sub-categories", "States", "Customers"]
    assert t["Products"]["sub_category"].tolist() == ["Tables"]
    assert t["States"]["state"].tolist() == ["Florida"]
    assert dd.loss_tables(sales_data.iloc[0:0]) == {}


@pytest.mark.parametrize("query, expected", [
    ("", 8), ("claire", 2), ("CLAIRE chairs", 1), ("florida tables", 1), ("no-such-thing", 0),
    ("CA-2016-152156", 2),
])
def test_search_rows(sales_data, query, expected):
    assert len(dd.search_rows(sales_data, query)) == expected


def test_explorer_summary(sales_data):
    s = dd.explorer_summary(sales_data, "segment")
    assert s.loc[0, "segment"] == "Consumer"
    assert s["revenue"].sum() == pytest.approx(sales_data["sales"].sum())


def test_safe_findings_skips_trend_for_short_ranges(sales_data):
    one_month = sales_data[sales_data["order_date"].dt.to_period("M") == sales_data["order_date"].dt.to_period("M").iloc[0]]
    findings, skipped = dd.safe_findings(one_month)
    assert "trends" not in findings and "trends" in skipped
    assert "kpis" in findings


def test_highlights_adapt_to_capabilities(sales_data):
    demo = dd.highlights(sales_data)
    assert [h["title"] for h in demo] == ["Largest category", "Weakest region margin", "Loss-making order lines"]
    no_profit = dd.highlights(sales_data, frozenset({"category", "products", "orders"}))
    titles = [h["title"] for h in no_profit]
    assert "Loss-making order lines" not in titles and "Weakest region margin" not in titles
    assert "margin" not in no_profit[0]["text"] and len(no_profit) == 3
    minimal = dd.highlights(sales_data, frozenset())
    assert [h["title"] for h in minimal] == ["Best month", "Average sale"]


def test_q4_stat_without_q4_data(sales_data):
    no_q4 = sales_data[sales_data["order_date"].dt.quarter != 4]
    q4 = next(s for s in dd.trend_stats(no_q4) if s["label"] == "Q4 share of revenue")
    assert q4["value"] == "-" and "no October-December" in q4["sub"]


# --- 14D: Business Insights for uploaded files ----------------------------------------
UPLOAD_SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def _prepared(name):
    from salesinsight.upload import prepare_sales, read_upload, suggest_mapping
    raw = read_upload(name, (UPLOAD_SAMPLES / name).read_bytes())
    r = prepare_sales(raw, suggest_mapping(raw)[0])
    return r.data, frozenset(r.capabilities), r.currency or "$"


def test_rules_and_tests_follow_capabilities():
    df, caps, _ = _prepared("indian_retail_sales.csv")          # no profit data
    findings, skipped = dd.safe_findings(df, caps)
    recs = dd.safe_recommendations(findings, caps)
    assert recs and all(r.area in ("Customers", "Planning") for r in recs)
    assert all(t.test not in ("discount_vs_margin", "region_margin", "category_margin") for t in findings["tests"])
    assert "high_discount_loss" not in findings and "no profit or cost column" in skipped["high_discount_loss"]
    assert dd.loss_tables(df, caps) == {}


def test_demo_safe_layer_unchanged(sales_data):
    a, _ = dd.safe_findings(sales_data)
    b, _ = dd.safe_findings(sales_data, None)
    assert set(a) == set(b) and len(a["tests"]) == len(b["tests"])
    assert [r.title for r in dd.safe_recommendations(a)] == [r.title for r in dd.safe_recommendations(b, None)]


def test_findings_wording_never_misleads():
    df, caps, _ = _prepared("indian_retail_sales.csv")
    findings, _ = dd.safe_findings(df, caps)
    texts = " ".join(x["title"] + " " + x["text"] for x in dd.key_findings(df, findings, caps)
                     + dd.opportunities(df, findings, caps))
    assert "profit" not in texts.lower() and "grows -" not in texts and "-0.0%" not in texts
    assert "Fastest-growing" not in texts or "(-" not in texts.split("Fastest-growing")[1].split(".")[0]


def test_small_upload_still_gets_opportunities_and_report():
    df, caps, cur = _prepared("cafe_daily_sales.csv")
    findings, skipped = dd.safe_findings(df, caps)
    opps = dd.opportunities(df, findings, caps)
    assert [o["title"] for o in opps] == ["Best sellers to keep in stock", "Strongest and weakest day"]
    report = dd.custom_report(df, findings, skipped, [], caps, "cafe_daily_sales.csv", cur)
    assert report.startswith("# SalesInsight report: cafe_daily_sales.csv") and "nan" not in report.lower()
    assert "## Not calculated for this file" in report


def test_custom_report_uses_currency_and_kpi_rows_filter():
    df, caps, cur = _prepared("indian_retail_sales.csv")
    findings, skipped = dd.safe_findings(df, caps)
    report = dd.custom_report(df, findings, skipped, dd.safe_recommendations(findings, caps), caps, "x.csv", cur)
    assert "₹" in report and "$" not in report
    keys = set(dd.kpi_rows(findings["kpis"], caps)["key"])
    assert "total_revenue" in keys and not {"total_profit", "profit_margin_pct", "loss_amount"} & keys
    from salesinsight.kpis import kpi_table
    assert dd.kpi_rows(findings["kpis"]).equals(kpi_table(findings["kpis"]))    # demo: full table
