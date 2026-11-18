"""Phase 3 tests: cleaning steps."""

from __future__ import annotations

import pandas as pd

from salesinsight import cleaning as c


def test_snake_case_names():
    assert c.to_snake_case("Sub-Category") == "sub_category"
    assert c.to_snake_case("Row ID") == "row_id"
    assert c.to_snake_case(" Order Date ") == "order_date"


def test_clean_keeps_all_valid_rows(clean_sample):
    clean, log = c.clean_data(clean_sample)
    assert len(clean) == len(clean_sample)
    assert "sub_category" in clean.columns
    assert list(log.columns) == ["step", "rows_before", "rows_after", "values_changed", "note"]


def test_text_is_trimmed(clean_sample):
    df = clean_sample.copy()
    df.loc[0, "City"] = "  Henderson "
    clean, _ = c.clean_data(df)
    assert clean.loc[0, "city"] == "Henderson"


def test_postal_code_padded_to_five_digits(clean_sample):
    df = clean_sample.copy()
    df.loc[5, "Postal Code"] = "5401"          # leading zero lost, as in the real CSV
    clean, _ = c.clean_data(df)
    assert clean.loc[5, "postal_code"] == "05401"


def test_missing_postal_code_filled_from_same_city(clean_sample):
    df = clean_sample.copy()
    df.loc[1, "Postal Code"] = pd.NA            # Henderson, Kentucky - row 0 has 42420
    clean, _ = c.clean_data(df)
    assert clean.loc[1, "postal_code"] == "42420"


def test_missing_burlington_postal_code_uses_known_value(clean_sample):
    df = clean_sample.copy()
    df.loc[5, "Postal Code"] = pd.NA            # the only Burlington, Vermont row
    clean, _ = c.clean_data(df)
    assert clean.loc[5, "postal_code"] == "05401"


def test_duplicate_record_removed(clean_sample):
    dupe = clean_sample.iloc[[2]].copy()
    dupe["Row ID"] = 99
    df = pd.concat([clean_sample, dupe], ignore_index=True)
    clean, log = c.clean_data(df)
    assert len(clean) == len(clean_sample)
    assert 99 not in clean["row_id"].tolist()   # first copy kept, second removed
    step = log.set_index("step").loc["Remove duplicate records"]
    assert step["values_changed"] == 1


def test_shared_product_id_gets_two_keys(clean_sample):
    df = clean_sample.copy()
    df.loc[1, "Product ID"] = df.loc[0, "Product ID"]   # same ID, different names
    clean, _ = c.clean_data(df)
    assert clean.loc[0, "product_id"] == clean.loc[1, "product_id"]
    assert clean.loc[0, "product_key"] != clean.loc[1, "product_key"]


def test_same_product_gets_same_key(clean_sample):
    df = pd.concat([clean_sample, clean_sample.iloc[[0]].assign(**{"Row ID": 50, "Quantity": 7})],
                   ignore_index=True)
    clean, _ = c.clean_data(df)
    keys = clean.loc[clean["product_id"] == "FUR-BO-10001798", "product_key"].unique()
    assert len(keys) == 1


def test_types(clean_sample):
    clean, _ = c.clean_data(clean_sample)
    assert clean["quantity"].dtype == "int64"
    assert clean["sales"].dtype == "float64"
    assert pd.api.types.is_datetime64_any_dtype(clean["order_date"])


def test_raw_data_not_modified(clean_sample):
    before = clean_sample.copy()
    c.clean_data(clean_sample)
    pd.testing.assert_frame_equal(clean_sample, before)
