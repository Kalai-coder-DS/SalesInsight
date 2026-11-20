"""Load the cleaned sales data once and keep it in Streamlit's cache."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from salesinsight import config
from salesinsight.data_loader import load_clean_data


@st.cache_data(show_spinner="Loading sales data...")
def load_sales() -> pd.DataFrame:
    """Read data/processed/sales_clean.csv.

    If only the raw Kaggle file is present, build the clean data first with the
    same Phase 2-3 code (so the app never uses unvalidated numbers).
    Online (no data in the repo) the raw file is first downloaded from Kaggle
    with the API key stored in Streamlit Secrets.
    """
    if config.CLEAN_DATA_FILE.is_file():
        return load_clean_data()
    if not config.RAW_DATA_FILE.is_file():
        username, key = _kaggle_credentials()
        if username and key:
            from salesinsight.kaggle_source import download_raw
            download_raw(username, key)
    if config.RAW_DATA_FILE.is_file():
        from salesinsight.cleaning import clean_data
        from salesinsight.data_loader import load_raw_data
        from salesinsight.features import add_all_features

        clean, _ = clean_data(load_raw_data())
        return add_all_features(clean)
    raise FileNotFoundError(
        "No data found. Put the Kaggle file at data/raw/Superstore.csv, or run "
        "scripts/run_cleaning.py to create data/processed/sales_clean.csv. "
        "Online: add KAGGLE_USERNAME and KAGGLE_KEY in the app's Secrets.")


def _kaggle_credentials() -> tuple[str, str]:
    """Kaggle username and key from Streamlit Secrets, else environment variables."""
    username = key = ""
    try:
        username = st.secrets.get("KAGGLE_USERNAME", "")
        key = st.secrets.get("KAGGLE_KEY", "")
    except Exception:  # noqa: BLE001 - no secrets file locally is normal
        pass
    return (str(username or os.getenv("KAGGLE_USERNAME", "")).strip(),
            str(key or os.getenv("KAGGLE_KEY", "")).strip())
