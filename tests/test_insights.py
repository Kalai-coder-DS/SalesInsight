"""Phase 11 tests: findings, recommendation rules and the generated report."""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight import insights as ins


@pytest.fixture
def findings(sales_data_with_repeat):
    return ins.collect_findings(sales_data_with_repeat)


def test_collect_findings_has_every_section(findings):
    for key in ("kpis", "yearly", "trends", "products", "categories", "subcategories", "discount_bands",
                "regions", "region_summary", "segments", "customers", "rfm", "tests", "aov_ci"):
        assert key in findings, key


def test_high_discount_loss(findings, sales_data_with_repeat):
    # Only the 45%-discount table line is above 20% and it lost 383.031
    assert findings["high_discount_loss"] == pytest.approx(-383.031)


def test_discount_cap_rule_fires(findings):
    rec = ins.rule_discount_cap(findings)
    assert rec is not None
    assert rec.priority == 1
    assert "-40.0% margin" in rec.finding
    assert "$383" in rec.impact


def test_discount_cap_rule_silent_when_profitable(findings):
    f = dict(findings)
    f["discount_bands"] = findings["discount_bands"].assign(profit_margin_pct=5.0)
    assert ins.rule_discount_cap(f) is None


def test_loss_states_rule(findings):
    rec = ins.rule_loss_states(findings)
    assert rec is not None and "Florida" in rec.finding


def test_loss_states_rule_silent_without_losses(findings):
    f = dict(findings)
    f["region_summary"] = {**findings["region_summary"], "loss_making_states": 0}
    assert ins.rule_loss_states(f) is None


def test_loss_subcategories_rule(findings):
    rec = ins.rule_loss_subcategories(findings)
    assert rec is not None and "Tables" in rec.finding


def test_weak_category_rule(findings):
    # Furniture margin is negative in the sample, far below the company average
    rec = ins.rule_weak_category(findings)
    assert rec is not None and "Furniture" in rec.title


def test_acquisition_rule_threshold(findings):
    f = dict(findings)
    f["customers"] = {**findings["customers"], "last_year_returning_revenue_share_pct": 99.0}
    assert ins.rule_acquisition(f) is not None
    f["customers"] = {**findings["customers"], "last_year_returning_revenue_share_pct": 50.0}
    assert ins.rule_acquisition(f) is None


def test_order_value_rule_reports_uncertainty():
    ci = pd.DataFrame({"order_year": [2014, 2017], "avg_order_value": [499.0, 435.0],
                       "ci_lower": [434.0, 395.0], "ci_upper": [580.0, 481.0]})
    rec = ins.rule_order_value({"aov_ci": ci, "kpis": {"total_orders": 5000}})
    assert "not statistically certain" in rec.finding
    ci_clear = ci.assign(ci_lower=[490.0, 430.0], ci_upper=[510.0, 440.0])
    assert "the fall is real" in ins.rule_order_value({"aov_ci": ci_clear, "kpis": {"total_orders": 5000}}).finding


def test_order_value_rule_silent_when_rising():
    ci = pd.DataFrame({"order_year": [2014, 2017], "avg_order_value": [400.0, 450.0],
                       "ci_lower": [380.0, 430.0], "ci_upper": [420.0, 470.0]})
    assert ins.rule_order_value({"aov_ci": ci, "kpis": {"total_orders": 5000}}) is None


def test_recommendations_sorted_by_priority(findings):
    recs = ins.build_recommendations(findings)
    assert len(recs) >= 4
    assert [r.priority for r in recs] == sorted(r.priority for r in recs)
    frame = ins.recommendations_to_frame(recs)
    assert list(frame.columns) == ["priority", "area", "title", "finding", "action", "impact"]


def test_report_contains_all_sections(findings):
    report = ins.build_report(findings, ins.build_recommendations(findings))
    for heading in ("# SalesInsight - Business Insights Report", "## Executive summary",
                    "## Top recommendations", "## 1. Revenue and profit (Q1)", "## 2. Sales trends (Q2)",
                    "## 3. Best-selling products (Q3)", "## 4. Category performance (Q4)",
                    "## 5. Region-wise sales (Q5)", "## 6. Customer behaviour (Q6)",
                    "## 7. Statistical evidence", "## 8. Recommendations (Q7)", "## 9. Limitations"):
        assert heading in report, heading


def test_report_numbers_come_from_data(findings, sales_data_with_repeat):
    report = ins.build_report(findings, ins.build_recommendations(findings))
    revenue = sales_data_with_repeat["sales"].sum()
    assert f"${revenue:,.2f}" in report
    assert "nan" not in report.lower().replace("financial", "")


def test_markdown_table():
    md = ins._md_table(pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}))
    assert md.splitlines() == ["| A | B |", "| --- | --- |", "| 1 | x |", "| 2 | y |"]


def test_report_handles_small_data_without_nan(sales_data):
    # Too few states for a correlation and no repeat orders: no "nan" may appear.
    f = ins.collect_findings(sales_data)
    report = ins.build_report(f, ins.build_recommendations(f))
    assert "nan" not in report.lower().replace("financial", "")
    assert "1 state loses money" in report
    assert "no repeat orders to time yet" in report
