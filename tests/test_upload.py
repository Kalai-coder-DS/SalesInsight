"""Phase 14A tests: reading, detecting, cleaning and validating uploaded sales files."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from salesinsight.upload import parsing as P
from salesinsight.upload import reader
from salesinsight.upload.detect import name_score, sales_like_problem, suggest_mapping
from salesinsight.upload.prepare import OUTPUT_COLUMNS, check_mapping, prepare_sales
from salesinsight.upload.reader import UploadError, excel_sheets, read_upload

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("1250", 1250.0), ("₹1,25,000.50", 125000.5), ("$ 1,250", 1250.0), ("Rs. 300", 300.0),
    ("INR 99", 99.0), ("(500)", -500.0), ("500-", -500.0), ("-12.5", -12.5), ("1.234,56", 1234.56),
    ("12,50", 12.5), ("€ 7", 7.0), ("+40", 40.0), ("1 000", 1000.0),
])
def test_parse_number(text, expected):
    assert P.parse_number(pd.Series([text])).iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "-", "N/A", "null", "abc", None])
def test_parse_number_missing(text):
    assert np.isnan(P.parse_number(pd.Series([text], dtype=object)).iloc[0])


def test_parse_percent_forms():
    assert P.parse_percent(pd.Series(["20%", "5%"])).tolist() == pytest.approx([0.2, 0.05])
    assert P.parse_percent(pd.Series(["0.2", "0"])).tolist() == pytest.approx([0.2, 0.0])
    assert P.parse_percent(pd.Series(["20", "50"])).tolist() == pytest.approx([0.2, 0.5])


@pytest.mark.parametrize("values, order", [
    (["2024-03-05", "2024-12-31"], "iso"),
    (["25/03/2024", "05/04/2024"], "day-first"),
    (["03/25/2024", "04/05/2024"], "month-first"),
    (["05/03/2024", "04/02/2024"], "ambiguous"),
    (["45356", "45400"], "excel"),
    (["5 Mar 2024", "March 7, 2024"], "other"),
])
def test_date_order(values, order):
    assert P.date_order(pd.Series(values)) == order


def test_parse_dates_day_and_month_first():
    d, order = P.parse_dates(pd.Series(["25/03/2024", "05/04/2024"]))
    assert order == "day-first" and d.tolist() == [pd.Timestamp("2024-03-25"), pd.Timestamp("2024-04-05")]
    d, _ = P.parse_dates(pd.Series(["03/25/2024", "04/05/2024"]))
    assert d.iloc[1] == pd.Timestamp("2024-04-05")


def test_parse_dates_ambiguous_follows_user_choice():
    values = pd.Series(["05/03/2024", "04/02/2024"])
    assert P.parse_dates(values)[0].iloc[0] == pd.Timestamp("2024-03-05")          # default: day first
    assert P.parse_dates(values, dayfirst=False)[0].iloc[0] == pd.Timestamp("2024-05-03")


def test_parse_dates_excel_numbers_and_text_months():
    d, order = P.parse_dates(pd.Series(["45356", ""]))
    assert order == "excel" and d.iloc[0] == pd.Timestamp("2024-03-05") and pd.isna(d.iloc[1])
    d, _ = P.parse_dates(pd.Series(["5 Mar 2024", "March 7, 2024", "garbage"]))
    assert d.iloc[1] == pd.Timestamp("2024-03-07") and pd.isna(d.iloc[2])


def test_dates_with_times_and_impossible_dates():
    d, _ = P.parse_dates(pd.Series(["2024-03-05 14:30:00", "2024-03-06 09:00:00"]))
    assert d.iloc[0] == pd.Timestamp("2024-03-05 14:30")
    d, _ = P.parse_dates(pd.Series(["31/02/2024", "28/02/2024", "15/03/2024"]))
    assert pd.isna(d.iloc[0]) and d.iloc[1] == pd.Timestamp("2024-02-28")


def test_plain_numbers_are_not_dates():
    assert P.date_ratio(pd.Series(["12", "250", "3"])) == 0.0
    assert P.date_ratio(pd.Series(["2024-01-01", "2024-02-01"])) == 1.0


@pytest.mark.parametrize("values, symbol", [(["₹1,200"], "₹"), (["Rs 50"], "₹"), (["$5"], "$"),
                                            (["€5"], "€"), (["5", "6"], None)])
def test_detect_currency(values, symbol):
    assert P.detect_currency(pd.Series(values)) == symbol


# --------------------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------------------
def frame(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols)


def test_suggest_mapping_with_different_names():
    df = frame(**{"Invoice No": ["A1", "A2"], "Bill Date": ["2024-01-05", "2024-01-06"],
                  "Client": ["X", "Y"], "Item Name": ["Pen", "Cup"], "Qty": ["2", "1"],
                  "Revenue (₹)": ["₹200", "₹150"], "Payment Type": ["Cash", "Card"],
                  "Discount": ["0%", "10%"], "Zone": ["North", "South"]})
    m, conf = suggest_mapping(df)
    assert m["order_date"] == "Bill Date" and m["sales"] == "Revenue (₹)" and m["order_id"] == "Invoice No"
    assert m["customer_name"] == "Client" and m["product_name"] == "Item Name" and m["quantity"] == "Qty"
    assert m["discount"] == "Discount" and m["region"] == "Zone"
    assert m["sub_category"] is None and m["segment"] is None        # "Payment Type" is not a product type
    assert conf["order_date"] > 50


def test_each_column_used_once_and_specific_names_win():
    df = frame(**{"Order Date": ["2024-01-01"] * 3, "Ship Date": ["2024-01-03"] * 3, "Sales": ["5", "6", "7"],
                  "Category": ["A", "B", "C"], "Sub-Category": ["a", "b", "c"], "Customer ID": ["1", "2", "3"],
                  "Customer Name": ["P", "Q", "R"]})
    m, _ = suggest_mapping(df)
    assert m["order_date"] == "Order Date" and m["ship_date"] == "Ship Date"
    assert m["category"] == "Category" and m["sub_category"] == "Sub-Category"
    assert m["customer_id"] == "Customer ID" and m["customer_name"] == "Customer Name"
    chosen = [v for v in m.values() if v]
    assert len(chosen) == len(set(chosen))


def test_unit_price_only_when_no_sales_column():
    with_sales = frame(Date=["2024-01-01"], Price=["2"], Qty=["3"], Amount=["6"])
    assert suggest_mapping(with_sales)[0]["unit_price"] is None
    without = frame(Date=["2024-01-01"], Price=["2"], Qty=["3"])
    m = suggest_mapping(without)[0]
    assert m["unit_price"] == "Price" and m["sales"] is None


def test_values_must_fit_the_field():
    df = frame(**{"Date": ["soon", "later"], "Sales": ["lots", "few"]})
    m, _ = suggest_mapping(df)
    assert m["order_date"] is None and m["sales"] is None


def test_name_score_rules():
    assert name_score("Order Date", ("order date",)) == 100
    assert 70 <= name_score("Order Date (dd/mm)", ("order date",), "date") < 100
    assert name_score("Payment Type", ("type",), "text") == 0


def test_sales_like_problem():
    assert sales_like_problem(frame(Date=["2024-01-01"], Amount=["5"])) is None
    msg = sales_like_problem(frame(Name=["A"], Dept=["HR"]))
    assert "doesn't look like sales data" in msg and "date column" in msg


# --------------------------------------------------------------------------------------
# Reading files
# --------------------------------------------------------------------------------------
def test_read_csv_semicolon_and_encoding():
    data = "Datum;Betrag;Kunde\n2024-01-01;12,50;Müller\n".encode("latin-1")
    df = read_upload("sales.csv", data)
    assert list(df.columns) == ["Datum", "Betrag", "Kunde"] and df.iloc[0, 2] == "Müller"


def test_read_excel_and_sheets():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"Notes": ["x"]}).to_excel(xw, sheet_name="Readme", index=False)
        pd.DataFrame({"Date": pd.to_datetime(["2024-01-01"]), "Sales": [5]}).to_excel(xw, sheet_name="Data",
                                                                                     index=False)
    data = buf.getvalue()
    assert excel_sheets(data) == ["Readme", "Data"]
    df = read_upload("book.xlsx", data, sheet="Data")
    assert pd.api.types.is_datetime64_any_dtype(df["Date"]) and df["Sales"].iloc[0] == "5"


@pytest.mark.parametrize("name, data, text", [
    ("sales.pdf", b"x", "CSV file"), ("sales.xls", b"x", ".xlsx"), ("sales.csv", b"", "empty"),
    ("sales.csv", b"a,a\n1,2\n", "same name"), ("sales.csv", b"only\n", "No data found"),
    ("sales.xlsx", b"not an excel file", "could not be read"),
])
def test_bad_files_have_clear_messages(name, data, text):
    with pytest.raises(UploadError, match=text):
        read_upload(name, data)


def test_size_and_row_limits(monkeypatch):
    monkeypatch.setattr(reader, "MAX_FILE_MB", 0.0001)
    with pytest.raises(UploadError, match="limit is"):
        read_upload("s.csv", b"Date,Sales\n" + b"2024-01-01,5\n" * 50)
    monkeypatch.setattr(reader, "MAX_FILE_MB", 20)
    monkeypatch.setattr(reader, "MAX_ROWS", 10)
    with pytest.raises(UploadError, match="more than 10 rows"):
        read_upload("s.csv", b"Date,Sales\n" + b"2024-01-01,5\n" * 11)


def test_blank_rows_removed():
    df = read_upload("s.csv", b"Date,Sales\n2024-01-01,5\n,\n,\n")
    assert len(df) == 1


# --------------------------------------------------------------------------------------
# Preparing (mapping -> clean data in the app's format)
# --------------------------------------------------------------------------------------
RAW = frame(**{
    "Inv": ["A1", "A1", "A2", "A3", "A4", "A5"],
    "Dt": ["05/01/2024", "05/01/2024", "13/02/2024", "not a date", "20/03/2024", "21/03/2024"],
    "Amt": ["₹1,000", "₹500", "₹2,000", "₹300", "", "(₹100)"],
    "Cost": ["600", "450", "2,500", "100", "50", "0"],
    "Disc": ["10%", "", "150%", "0%", "5%", "0%"],
    "Cust": ["Ravi", "Ravi", "Meena", "Arun", "Ravi", ""],
    "Item": ["Pen", "Ink", "Desk", "Pen", "Ink", "Pen"],
})
MAP = {"order_id": "Inv", "order_date": "Dt", "sales": "Amt", "cost": "Cost", "discount": "Disc",
       "customer_name": "Cust", "product_name": "Item"}


def texts(result, level):
    return " ".join(m.text for m in result.messages if m.level == level)


def test_prepare_output_matches_app_format():
    r = prepare_sales(RAW, MAP)
    assert r.ok and list(r.data.columns) == OUTPUT_COLUMNS
    d = r.data
    assert len(d) == 4 and r.rows_in == 6 and r.rows_out == 4                # no date + no sales removed
    assert d["sales"].tolist() == [1000.0, 500.0, 2000.0, -100.0]
    assert d["profit"].tolist() == [400.0, 50.0, -500.0, -100.0]             # sales - cost
    assert d["discount"].tolist() == pytest.approx([0.1, 0.0, 0.0, 0.0])     # empty -> 0, 150% -> 0
    assert d["customer_name"].iloc[3] == "Unknown" and d["customer_id"].iloc[0] == "Ravi"
    assert d["order_date"].iloc[2] == pd.Timestamp("2024-02-13") and d["order_year"].iloc[0] == 2024
    assert d["is_loss"].tolist() == [False, False, True, True]
    assert r.currency == "₹" and r.date_order == "day-first"


def test_prepare_report_explains_every_fix():
    r = prepare_sales(RAW, MAP)
    fixed, warn, info = texts(r, "fixed"), texts(r, "warning"), texts(r, "info")
    assert "1 row without a valid order date removed" in fixed
    assert "1 row without a valid sales amount removed" in fixed
    assert "Profit was calculated as sales minus cost" in fixed
    assert "empty discount set to 0" in fixed and "outside 0-99%" in warn
    assert "negative sales kept" in info and "4 of 6 rows ready" in info


def test_capabilities_reflect_the_data():
    r = prepare_sales(RAW, MAP)
    assert {"orders", "customers", "products", "profit", "discount"} <= r.capabilities
    assert not {"quantity", "region", "us_map", "category"} & r.capabilities
    minimal = prepare_sales(frame(D=["2024-01-01", "2024-01-02"], S=["5", "6"]), {"order_date": "D", "sales": "S"})
    assert minimal.ok and minimal.capabilities == set()
    assert minimal.data["order_id"].tolist() == ["LINE-1", "LINE-2"]
    assert minimal.data["profit"].isna().all() and minimal.data["category"].eq("Unknown").all()


def test_us_states_enable_the_map():
    df = frame(D=["2024-01-01"] * 3, S=["1", "2", "3"], St=["Texas", "Ohio", "Florida"])
    r = prepare_sales(df, {"order_date": "D", "sales": "S", "state": "St"})
    assert {"state", "us_map"} <= r.capabilities
    df["St"] = ["Kerala", "Delhi", "Goa"]
    r = prepare_sales(df, {"order_date": "D", "sales": "S", "state": "St"})
    assert "state" in r.capabilities and "us_map" not in r.capabilities


def test_sales_from_price_and_quantity():
    df = frame(D=["2024-01-01", "2024-01-02"], P=["2.50", "4"], Q=["2", "3"])
    r = prepare_sales(df, {"order_date": "D", "unit_price": "P", "quantity": "Q"})
    assert r.ok and r.data["sales"].tolist() == [5.0, 12.0] and r.data["unit_price"].tolist() == [2.5, 4.0]


@pytest.mark.parametrize("mapping, text", [
    ({"sales": "Amt"}, "order date"),
    ({"order_date": "Dt"}, "sales amount"),
    ({"order_date": "Dt", "sales": "Dt"}, "more than one field"),
    ({"order_date": "Nope", "sales": "Amt"}, "not in the file"),
])
def test_mapping_problems(mapping, text):
    assert any(text in p for p in check_mapping(mapping, RAW.columns))
    r = prepare_sales(RAW, mapping)
    assert not r.ok and r.data is None and text in texts(r, "error")


def test_wrong_columns_are_caught():
    r = prepare_sales(RAW, {"order_date": "Cust", "sales": "Amt"})
    assert not r.ok and "not dates" in texts(r, "error")
    r = prepare_sales(RAW, {"order_date": "Dt", "sales": "Item"})
    assert not r.ok and "not numbers" in texts(r, "error")


def test_duplicates_kept_or_removed():
    df = frame(O=["1", "1", "2"], D=["2024-01-01"] * 3, S=["5", "5", "7"])
    m = {"order_id": "O", "order_date": "D", "sales": "S"}
    kept = prepare_sales(df, m)
    assert kept.duplicates == 1 and len(kept.data) == 3 and "duplicate" in texts(kept, "warning")
    removed = prepare_sales(df, m, remove_duplicates=True)
    assert len(removed.data) == 2 and "duplicate row removed" in texts(removed, "fixed")


def test_ambiguous_dates_warning_and_override():
    df = frame(D=["05/03/2024", "04/02/2024"], S=["1", "2"])
    r = prepare_sales(df, {"order_date": "D", "sales": "S"})
    assert "read two ways" in texts(r, "warning") and r.data["order_date"].iloc[1] == pd.Timestamp("2024-03-05")
    r = prepare_sales(df, {"order_date": "D", "sales": "S"}, dayfirst=False)
    assert r.data["order_date"].tolist() == [pd.Timestamp("2024-04-02"), pd.Timestamp("2024-05-03")]


def test_superstore_file_maps_itself_and_matches_phase3(raw_csv, sales_data):
    """The original Kaggle file, uploaded, gives the same totals as the Phase 2-3 pipeline."""
    raw = read_upload("Superstore.csv", raw_csv.read_bytes())
    m, _ = suggest_mapping(raw)
    for key, col in {"order_date": "Order Date", "sales": "Sales", "profit": "Profit", "order_id": "Order ID",
                     "customer_id": "Customer ID", "customer_name": "Customer Name", "product_id": "Product ID",
                     "product_name": "Product Name", "category": "Category", "sub_category": "Sub-Category",
                     "region": "Region", "state": "State", "segment": "Segment", "ship_date": "Ship Date",
                     "quantity": "Quantity", "discount": "Discount"}.items():
        assert m[key] == col, key
    r = prepare_sales(raw, m)
    assert r.ok and r.date_order == "month-first"
    assert r.data["sales"].sum() == pytest.approx(sales_data["sales"].sum())
    assert r.data["profit"].sum() == pytest.approx(sales_data["profit"].sum())
    assert r.data["order_id"].nunique() == sales_data["order_id"].nunique()


def test_existing_analysis_runs_on_uploaded_data():
    from salesinsight import dashboard_data as dd
    from salesinsight.kpis import compute_kpis
    r = prepare_sales(RAW, MAP)
    k = compute_kpis(r.data)
    assert k["total_revenue"] == pytest.approx(3400.0) and k["total_orders"] == 3
    findings, _ = dd.safe_findings(r.data)
    assert "kpis" in findings


@pytest.mark.parametrize("name", ["indian_retail_sales.csv", "online_store_orders.xlsx", "cafe_daily_sales.csv"])
def test_sample_files_work_end_to_end(name):
    raw = read_upload(name, (SAMPLES / name).read_bytes())
    assert sales_like_problem(raw) is None
    m, _ = suggest_mapping(raw)
    r = prepare_sales(raw, m)
    assert r.ok and r.rows_out > 500 and list(r.data.columns) == OUTPUT_COLUMNS


def test_not_sales_sample_is_rejected():
    raw = read_upload("not_sales_data.csv", (SAMPLES / "not_sales_data.csv").read_bytes())
    assert sales_like_problem(raw) is not None
    assert not prepare_sales(raw, suggest_mapping(raw)[0]).ok


def test_fast_time_features_match_phase3(sales_data):
    """The upload's faster time features give exactly the Phase 3 values."""
    from salesinsight.features import add_time_features
    from salesinsight.upload.prepare import time_features
    cols = ["order_year", "order_quarter", "order_month", "order_month_name", "year_month", "order_weekday"]
    base = sales_data[["order_date"]]
    pd.testing.assert_frame_equal(time_features(base)[cols].astype(str), add_time_features(base)[cols].astype(str))
