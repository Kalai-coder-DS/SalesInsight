"""Phase 2 tests: loading the raw CSV."""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight.data_loader import EXPECTED_COLUMNS, load_raw_data, parse_date_column, summarise


def test_loads_all_rows_and_columns(clean_sample):
    assert clean_sample.shape == (8, 21)
    assert list(clean_sample.columns) == EXPECTED_COLUMNS


def test_reads_latin1_characters(clean_sample):
    assert clean_sample.loc[0, "Customer Name"] == "Claire Guté"


def test_dates_are_real_dates(clean_sample):
    assert pd.api.types.is_datetime64_any_dtype(clean_sample["Order Date"])
    assert clean_sample.loc[0, "Order Date"] == pd.Timestamp("2016-11-08")


def test_postal_code_keeps_leading_zero(clean_sample):
    # Burlington, Vermont is 05401 - must not become 5401.
    assert clean_sample.loc[5, "Postal Code"] == "05401"


def test_numbers_are_numeric(clean_sample):
    for col in ("Sales", "Quantity", "Discount", "Profit"):
        assert pd.api.types.is_numeric_dtype(clean_sample[col]), col


def test_country_region_alias_is_renamed(tmp_path, raw_frame):
    path = tmp_path / "alias.csv"
    raw_frame.rename(columns={"Country": "Country/Region"}).to_csv(path, index=False)
    df = load_raw_data(path)
    assert "Country" in df.columns
    assert "Country/Region" not in df.columns


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_raw_data(tmp_path / "does_not_exist.csv")


def test_folder_instead_of_file_gives_clear_error(tmp_path):
    folder = tmp_path / "Superstore.csv"
    folder.mkdir()
    with pytest.raises(IsADirectoryError):
        load_raw_data(folder)


def test_parse_dates_day_first_format():
    s = pd.Series(["25/12/2016", "13/01/2017"])
    parsed = parse_date_column(s)
    assert parsed.tolist() == [pd.Timestamp("2016-12-25"), pd.Timestamp("2017-01-13")]


def test_parse_dates_bad_value_becomes_missing():
    parsed = parse_date_column(pd.Series(["1/5/2016", "not a date"]))
    assert parsed.iloc[0] == pd.Timestamp("2016-01-05")
    assert pd.isna(parsed.iloc[1])


def test_summarise(clean_sample):
    s = summarise(clean_sample)
    assert s["rows"] == 8
    assert s["unique_order_ids"] == 6
    assert s["first_order_date"] == pd.Timestamp("2014-06-09")
    assert s["total_sales"] == round(clean_sample["Sales"].sum(), 2)
