"""Phase 2 tests: every validation check catches the problem it is built for."""

from __future__ import annotations

import pandas as pd

from salesinsight import validation as v


def statuses(results):
    return {r.check: r.status for r in results}


def test_clean_sample_has_no_fail_or_warn(clean_sample):
    results = v.run_all_checks(clean_sample)
    assert not v.has_failures(results)
    assert all(r.status == v.PASS for r in results), statuses(results)


def test_missing_column_fails(clean_sample):
    df = clean_sample.drop(columns=["Profit"])
    result = v.check_required_columns(df)
    assert result.status == v.FAIL
    assert "Profit" in result.details


def test_run_stops_early_when_columns_missing(clean_sample):
    results = v.run_all_checks(clean_sample.drop(columns=["Sales"]))
    assert v.has_failures(results)
    assert len(results) == 2


def test_missing_key_value_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Sales"] = None
    assert v.check_missing_key_values(df).status == v.FAIL


def test_missing_postal_code_is_only_warning(clean_sample):
    df = clean_sample.copy()
    df.loc[5, "Postal Code"] = pd.NA
    result = v.check_missing_other_values(df)
    assert result.status == v.WARN
    assert result.affected_rows == 1


def test_duplicate_row_id_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[1, "Row ID"] = 1
    assert v.check_duplicate_row_ids(df).status == v.FAIL


def test_duplicate_record_warns(clean_sample):
    copy = clean_sample.iloc[[2]].copy()
    copy["Row ID"] = 99
    df = pd.concat([clean_sample, copy], ignore_index=True)
    result = v.check_duplicate_records(df)
    assert result.status == v.WARN
    assert result.affected_rows == 1


def test_ship_before_order_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Ship Date"] = pd.Timestamp("2016-01-01")
    assert v.check_ship_after_order(df).affected_rows == 1


def test_unreadable_date_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Order Date"] = pd.NaT
    assert v.check_dates_parsed(df).status == v.FAIL


def test_text_date_column_fails(raw_frame):
    # Dates still as text (not loaded through the loader) must be caught.
    assert v.check_dates_parsed(raw_frame).status == v.FAIL


def test_negative_sales_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Sales"] = -5
    assert v.check_sales_positive(df).status == v.FAIL


def test_fractional_quantity_fails(clean_sample):
    df = clean_sample.copy()
    df["Quantity"] = df["Quantity"].astype(float)
    df.loc[0, "Quantity"] = 1.5
    assert v.check_quantity_valid(df).status == v.FAIL


def test_discount_out_of_range_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Discount"] = 1.2
    assert v.check_discount_range(df).status == v.FAIL


def test_negative_profit_is_allowed(clean_sample):
    # Row 4 already has a loss (-383.03); losses are real business data, not errors.
    assert (clean_sample["Profit"] < 0).any()
    assert v.check_profit_not_above_sales(clean_sample).status == v.PASS


def test_unknown_region_fails(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "Region"] = "North"
    results = {r.check: r for r in v.check_allowed_values(df)}
    assert results["'Region' has only known values"].status == v.FAIL


def test_order_with_two_customers_warns(clean_sample):
    df = clean_sample.copy()
    df.loc[1, "Customer ID"] = "XX-00000"
    assert v.check_order_consistency(df).status == v.WARN


def test_product_id_with_two_names_warns(clean_sample):
    df = clean_sample.copy()
    df.loc[1, "Product ID"] = df.loc[0, "Product ID"]
    result = v.check_product_id_names(df)
    assert result.status == v.WARN
    assert result.affected_rows == 1


def test_report_and_dictionary_shapes(clean_sample):
    report = v.results_to_frame(v.run_all_checks(clean_sample))
    assert list(report.columns) == ["check", "status", "affected_rows", "details"]
    dictionary = v.build_data_dictionary(clean_sample)
    assert len(dictionary) == 21
    assert dictionary["description"].ne("").all()
