"""Phase 3 tests: feature engineering. Expected values are worked out by hand."""

from __future__ import annotations

import pandas as pd
import pytest

from salesinsight.cleaning import clean_data
from salesinsight.features import add_all_features


@pytest.fixture
def featured(clean_sample) -> pd.DataFrame:
    clean, _ = clean_data(clean_sample)
    return add_all_features(clean)


def test_time_features(featured):
    row = featured.iloc[0]                       # ordered 2016-11-08 (a Tuesday)
    assert row["order_year"] == 2016
    assert row["order_quarter"] == 4
    assert row["order_month"] == 11
    assert row["order_month_name"] == "Nov"
    assert row["year_month"] == "2016-11"
    assert row["order_weekday"] == "Tuesday"


def test_ship_days(featured):
    assert featured.iloc[0]["ship_days"] == 3    # 8 Nov -> 11 Nov
    assert featured.iloc[3]["ship_days"] == 7    # 11 Oct -> 18 Oct
    assert (featured["ship_days"] >= 0).all()


def test_profit_margin(featured):
    # Row 1: 41.9136 / 261.96 = 0.16
    assert featured.iloc[0]["profit_margin"] == pytest.approx(0.16)


def test_unit_price(featured):
    assert featured.iloc[0]["unit_price"] == pytest.approx(261.96 / 2)


def test_gross_sales_and_discount_amount(featured):
    # Row 4: sales 957.5775 after 45% discount -> before discount 1741.05
    row = featured.iloc[3]
    assert row["gross_sales"] == pytest.approx(1741.05)
    assert row["discount_amount"] == pytest.approx(1741.05 - 957.5775)
    # No discount -> gross equals sales
    assert featured.iloc[0]["gross_sales"] == pytest.approx(261.96)


def test_is_loss(featured):
    assert featured.iloc[3]["is_loss"]
    assert not featured.iloc[0]["is_loss"]
    assert featured["is_loss"].sum() == 1


@pytest.mark.parametrize("discount, band", [
    (0.0, "No discount"), (0.1, "1-20%"), (0.2, "1-20%"),
    (0.3, "21-40%"), (0.4, "21-40%"), (0.45, "Over 40%"), (0.8, "Over 40%"),
])
def test_discount_bands(featured, discount, band):
    df = featured.copy()
    df["discount"] = discount
    from salesinsight.features import add_discount_band
    assert (add_discount_band(df)["discount_band"] == band).all()


def test_save_and_reload_round_trip(featured, tmp_path):
    from salesinsight.data_loader import load_clean_data
    path = tmp_path / "sales_clean.csv"
    featured.to_csv(path, index=False, date_format="%Y-%m-%d")
    back = load_clean_data(path)
    assert len(back) == len(featured)
    assert back.loc[5, "postal_code"] == "05401"          # leading zero survives
    assert pd.api.types.is_datetime64_any_dtype(back["order_date"])
    assert back["sales"].sum() == pytest.approx(featured["sales"].sum())
