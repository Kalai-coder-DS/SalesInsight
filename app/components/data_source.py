"""Which data the app analyses: the demo Superstore data or the visitor's own file.

Privacy: an uploaded file is kept only in this visitor's session
(st.session_state). It is never written to disk, never put in st.cache_data
(which is shared by all visitors) and disappears when the session ends or the
visitor clicks "Remove my file".

Session keys
    ds_mode          "demo" or "custom" (custom only after a successful analysis)
    ds_raw           the uploaded table as read (for re-mapping)
    ds_file_name     original file name
    ds_file_key      name + size (+ sheet), to notice a new upload
    ds_result        PrepResult of the active custom data
    ds_active_name   file name of the active custom data (a newer upload may fail its check)
    ds_last_result   PrepResult of the last "Check & analyse" (may have errors)
    ds_currency      currency symbol chosen for the custom data
"""

from __future__ import annotations

import streamlit as st

DEMO_NAME = "Superstore demo data"
SESSION_KEYS = ("ds_mode", "ds_raw", "ds_file_name", "ds_file_key", "ds_result", "ds_last_result",
                "ds_currency", "ds_sheets", "ds_active_name", "ds_currency_choice")
NOT_IN_FILE = "- not in my file -"


def mode() -> str:
    result = st.session_state.get("ds_result")
    if st.session_state.get("ds_mode") == "custom" and result is not None and result.ok:
        return "custom"
    return "demo"


def custom_result():
    return st.session_state.get("ds_result") if mode() == "custom" else None


def source_name() -> str:
    return st.session_state.get("ds_active_name", "your file") if mode() == "custom" else DEMO_NAME


def currency() -> str:
    """Currency symbol for money values ("" = no symbol)."""
    if mode() != "custom":
        return "$"
    symbol = st.session_state.get("ds_currency")
    return "$" if symbol is None else symbol


def capabilities() -> frozenset | None:
    """None in demo mode (everything available); otherwise what the uploaded data supports."""
    result = custom_result()
    return frozenset(result.capabilities) if result is not None else None


def clear_filters() -> None:
    """Filters belong to one dataset (years, states...), so start fresh after a switch."""
    for key in [k for k in st.session_state.keys() if str(k).startswith("f_")]:
        del st.session_state[key]


def use_demo() -> None:
    if st.session_state.get("ds_mode") != "demo":
        st.session_state["ds_mode"] = "demo"
        clear_filters()
    st.session_state["ds_choice"] = "Demo data"


def use_custom() -> None:
    result = st.session_state.get("ds_result")
    if result is not None and result.ok and st.session_state.get("ds_mode") != "custom":
        st.session_state["ds_mode"] = "custom"
        clear_filters()


def remove_file() -> None:
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    for key in [k for k in st.session_state.keys() if str(k).startswith("map_")]:
        del st.session_state[key]
    st.session_state["ds_mode"] = "demo"
    st.session_state["ds_choice"] = "Demo data"
    clear_filters()
