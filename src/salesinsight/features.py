"""Phase 3: add new columns (features) used by the analysis phases.

Time features   : order_year, order_quarter, order_month, order_month_name,
                  year_month, order_weekday
Shipping        : ship_days (days between order and shipping)
Money           : profit_margin, unit_price, gross_sales, discount_amount, is_loss
Discount groups : discount_band (No discount, 1-20%, 21-40%, Over 40%)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DISCOUNT_BINS = [-0.001, 0.0, 0.2, 0.4, 1.0]
DISCOUNT_LABELS = ["No discount", "1-20%", "21-40%", "Over 40%"]


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    d = df["order_date"]
    df["order_year"] = d.dt.year.astype("int64")
    df["order_quarter"] = d.dt.quarter.astype("int64")
    df["order_month"] = d.dt.month.astype("int64")
    df["order_month_name"] = d.dt.strftime("%b")      # Jan, Feb, ...
    df["year_month"] = d.dt.strftime("%Y-%m")         # 2016-11
    df["order_weekday"] = d.dt.day_name()             # Monday, ...
    return df


def add_shipping_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ship_days"] = (df["ship_date"] - df["order_date"]).dt.days.astype("int64")
    return df


def add_money_features(df: pd.DataFrame) -> pd.DataFrame:
    """Profit margin, price per unit, and the revenue before discount.

    Sales in this dataset is already after discount, so:
        gross_sales     = sales / (1 - discount)   (price before discount)
        discount_amount = gross_sales - sales      (money given away)
    """
    df = df.copy()
    df["profit_margin"] = np.where(df["sales"] != 0, df["profit"] / df["sales"], np.nan)
    df["unit_price"] = df["sales"] / df["quantity"]
    df["gross_sales"] = df["sales"] / (1 - df["discount"])
    df["discount_amount"] = df["gross_sales"] - df["sales"]
    df["is_loss"] = df["profit"] < 0
    return df


def add_discount_band(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["discount_band"] = pd.cut(
        df["discount"], bins=DISCOUNT_BINS, labels=DISCOUNT_LABELS
    ).astype("string")
    return df


def add_all_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_time_features(df)
    df = add_shipping_features(df)
    df = add_money_features(df)
    df = add_discount_band(df)
    return df
