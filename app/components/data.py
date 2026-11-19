"""Load the cleaned sales data once and keep it in Streamlit's cache."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from salesinsight import config
from salesinsight.data_loader import load_clean_data


@st.cache_data(show_spinner="Loading sales data...")
def load_sales() -> pd.DataFrame:
    """Read data/processed/sales_clean.csv.

    If only the raw Kaggle file is present, build the clean data first with the
    same Phase 2-3 code (so the app never uses unvalidated numbers).
    """
    if config.CLEAN_DATA_FILE.is_file():
        return load_clean_data()
    if config.RAW_DATA_FILE.is_file():
        from salesinsight.cleaning import clean_data
        from salesinsight.data_loader import load_raw_data
        from salesinsight.features import add_all_features

        clean, _ = clean_data(load_raw_data())
        return add_all_features(clean)
    raise FileNotFoundError(
        "No data found. Put the Kaggle file at data/raw/Superstore.csv, or run "
        "scripts/run_cleaning.py to create data/processed/sales_clean.csv.")
